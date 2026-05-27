"""
Regime Adaptive Strategy B - Calibrated for BTC 15m
=====================================================
Direction B: Regime-Adaptive Strategy → 三市場通用

A regime-adaptive strategy that works across:
- Bull market (20251001-20251231)
- Bear market (20251201-20260430)
- Consolidation (20251101-20251130)

Key calibration findings:
- ADX is almost always > 7 (99.9% of time)
- Better thresholds: TREND (ADX > 30), VOLATILE (ADX 20-30), RANGE (ADX < 20)
- BB width ratio helps distinguish VOLATILE from TREND
- DI direction provides trend bias

Strategy logic:
1. Compute indicators in populate_indicators()
2. Detect regime using calibrated thresholds
3. Apply regime-specific entry/exit/risk parameters
4. Use dynamic stoploss/ROI based on confirmed regime

Author: Brian
Timeframe: 15m
"""

import talib.abstract as ta
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from typing import Optional


class MarketRegime:
    """Market regime constants"""

    UNKNOWN = 0
    TREND = 1  # Strong trend (ADX > 30)
    VOLATILE = 2  # Volatile/transitional (ADX 20-30)
    RANGE = 3  # Sideways/Low volatility (ADX < 20)


class RegimeAdaptive_B(IStrategy):
    """
    Regime-Adaptive Strategy B - Calibrated for BTC 15m

    Uses calibrated thresholds based on actual BTC 15m data analysis:
    - TREND: ADX > 30 (strong directional moves)
    - VOLATILE: ADX 20-30 (moderate trend or breakout setup)
    - RANGE: ADX < 20 (weak trend, potential mean-reversion)

    Entry logic adapts to regime:
    - TREND: EMA cross + ADX confirmation + DI direction
    - VOLATILE: Bollinger Band touch + RSI extreme + ATR expansion
    - RANGE: Mean reversion at BB bounds + RSI exhaustion

    Risk management adapts to regime:
    - TREND: Wider stop, longer hold, trailing profit
    - VOLATILE: Moderate stop, take quick profit on volatility
    - RANGE: Tight stop, fast profit taking
    """

    # ==================== Basic Settings ====================
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 200

    # ==================== Regime Detection (Calibrated) ====================
    # These thresholds are calibrated for BTC 15m on Bybit
    ADX_TREND_THRESHOLD = 30.0  # ADX > 30 = strong trend
    ADX_VOLATILE_MAX = 30.0  # ADX 20-30 = volatile/transitional
    ADX_RANGE_MAX = 20.0  # ADX < 20 = range/sideways

    # State confirmation buffer
    REGIME_CONFIRM_CANDLES = 3

    # BB width for volatility detection
    BB_PERIOD = 20
    BB_WIDTH_RATIO_THRESHOLD = 1.1  # BB width expanding

    # ==================== TREND Mode Parameters ====================
    TREND_STOP_LOSS = -0.035
    TREND_ROI = {
        "0": 0.10,  # 10% immediate target
        "480": 0.06,  # 6% after 8 hours
        "1440": 0.03,  # 3% after 24 hours (let it run)
    }
    TREND_TRAILING_POSITIVE = 0.025
    TREND_TRAILING_OFFSET = 0.05

    # Entry: EMA cross + ADX + DI confirmation
    TREND_ENTRY_ADX_MIN = 30.0

    # ==================== VOLATILE Mode Parameters ====================
    VOLATILE_STOP_LOSS = -0.025
    VOLATILE_ROI = {
        "0": 0.06,  # 6% quick take
        "180": 0.04,  # 4% after 3 hours
        "360": 0.02,  # 2% after 6 hours
    }
    VOLATILE_TRAILING_POSITIVE = 0.015
    VOLATILE_TRAILING_OFFSET = 0.03

    # Entry: BB touch + RSI extreme + some trend confirmation
    VOLATILE_ENTRY_ADX_MIN = 20.0
    VOLATILE_ENTRY_RSI_LOW = 35
    VOLATILE_ENTRY_RSI_HIGH = 65

    # ==================== RANGE Mode Parameters ====================
    RANGE_STOP_LOSS = -0.02
    RANGE_ROI = {
        "0": 0.03,  # 3% quick take
        "120": 0.015,  # 1.5% after 2 hours
        "240": 0.01,  # 1% after 4 hours
    }
    RANGE_TRAILING = False  # No trailing in range mode

    # Entry: BB touch + RSI exhaustion
    RANGE_ENTRY_RSI_LOW = 25
    RANGE_ENTRY_RSI_HIGH = 75

    # ==================== Fixed Parameters (required by Freqtrade) ====================
    stoploss = -0.03
    minimal_roi = {"0": 0.05, "360": 0.03}
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ==================== Internal State ====================
    _confirmed_regime = MarketRegime.UNKNOWN
    _regime_candle_count = 0
    _last_regime = MarketRegime.UNKNOWN

    # ==================== Indicator Calculation ====================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate all indicators needed for regime detection and trading signals.
        """

        # ========== 1. Core Trend Indicators ==========
        # ADX for trend strength
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # EMA for trend direction
        dataframe["ema_9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # EMA alignment for trend direction
        dataframe["ema_bullish"] = (dataframe["ema_9"] > dataframe["ema_21"]) & (
            dataframe["ema_21"] > dataframe["ema_50"]
        )
        dataframe["ema_bearish"] = (dataframe["ema_9"] < dataframe["ema_21"]) & (
            dataframe["ema_21"] < dataframe["ema_50"]
        )

        # ========== 2. RSI ==========
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ========== 3. ATR for volatility ==========
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_ma"] = dataframe["atr"].rolling(window=20).mean()
        dataframe["atr_ratio"] = dataframe["atr"] / dataframe["atr_ma"]

        # ========== 4. Bollinger Bands ==========
        bb_result = ta.BBANDS(dataframe, timeperiod=self.BB_PERIOD, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb_result["upperband"]
        dataframe["bb_middle"] = bb_result["middleband"]
        dataframe["bb_lower"] = bb_result["lowerband"]

        # BB width for volatility detection
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe[
            "bb_middle"
        ]
        dataframe["bb_width_ma"] = dataframe["bb_width"].rolling(window=20).mean()
        dataframe["bb_width_ratio"] = dataframe["bb_width"] / dataframe["bb_width_ma"]

        # BB position (0 = at lower band, 1 = at upper band)
        dataframe["bb_position"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )

        # BB touch conditions
        dataframe["bb_touch_lower"] = dataframe["close"] <= dataframe["bb_lower"] * 1.01
        dataframe["bb_touch_upper"] = dataframe["close"] >= dataframe["bb_upper"] * 0.99

        # ========== 5. Momentum ==========
        dataframe["roc"] = ta.ROCP(dataframe, timeperiod=10) * 100
        dataframe["mom"] = ta.MOM(dataframe, timeperiod=10)

        # ========== 6. Volume ==========
        dataframe["volume_ma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma"]

        # ========== 7. Regime Detection Signals ==========
        dataframe["regime_trend_signal"] = self._detect_trend_regime(dataframe)
        dataframe["regime_volatile_signal"] = self._detect_volatile_regime(dataframe)
        dataframe["regime_range_signal"] = self._detect_range_regime(dataframe)

        # Current regime (instant)
        dataframe["current_regime"] = self._get_current_regime(dataframe)

        # Confirmed regime (with buffer)
        dataframe["confirmed_regime"] = self._get_confirmed_regime(dataframe)

        return dataframe

    def _detect_trend_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        Detect TREND regime: ADX > 30 (strong directional trend)
        """
        return dataframe["adx"] > self.ADX_TREND_THRESHOLD

    def _detect_volatile_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        Detect VOLATILE regime: ADX 20-30 (moderate trend or breakout setup)
        Needs BB expansion to confirm volatility, not just ADX in range
        """
        adx_in_range = (dataframe["adx"] > 15) & (dataframe["adx"] <= self.ADX_VOLATILE_MAX)
        bb_expanding = dataframe["bb_width_ratio"] > self.BB_WIDTH_RATIO_THRESHOLD

        return adx_in_range & bb_expanding

    def _detect_range_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        Detect RANGE regime: ADX < 20 (weak trend, potential mean-reversion)
        """
        return dataframe["adx"] < self.ADX_RANGE_MAX

    def _get_current_regime(self, dataframe: DataFrame) -> int:
        """
        Get current instant regime (priority: TREND > VOLATILE > RANGE)
        """
        trend_signal = dataframe["regime_trend_signal"].iloc[-1]
        volatile_signal = dataframe["regime_volatile_signal"].iloc[-1]

        if trend_signal:
            return MarketRegime.TREND
        elif volatile_signal:
            return MarketRegime.VOLATILE
        else:
            return MarketRegime.RANGE

    def _get_confirmed_regime(self, dataframe: DataFrame) -> int:
        """
        Get confirmed regime with buffer - needs N consecutive candles
        """
        lookback = min(self.REGIME_CONFIRM_CANDLES, len(dataframe))
        recent = dataframe.iloc[-lookback:]

        # Count confirmations
        trend_count = recent["regime_trend_signal"].sum()
        volatile_count = recent["regime_volatile_signal"].sum()
        range_count = recent["regime_range_signal"].sum()

        current_regime = self._get_current_regime(dataframe)

        # Confirm regime if N consecutive candles agree
        if current_regime == MarketRegime.TREND and trend_count >= self.REGIME_CONFIRM_CANDLES:
            self._last_regime = self._confirmed_regime
            self._confirmed_regime = MarketRegime.TREND
            self._regime_candle_count = 0
        elif (
            current_regime == MarketRegime.VOLATILE
            and volatile_count >= self.REGIME_CONFIRM_CANDLES
        ):
            self._last_regime = self._confirmed_regime
            self._confirmed_regime = MarketRegime.VOLATILE
            self._regime_candle_count = 0
        elif current_regime == MarketRegime.RANGE and range_count >= self.REGIME_CONFIRM_CANDLES:
            self._last_regime = self._confirmed_regime
            self._confirmed_regime = MarketRegime.RANGE
            self._regime_candle_count = 0
        else:
            self._regime_candle_count += 1

        return self._confirmed_regime

    # ==================== Entry Logic ====================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Route entry logic based on confirmed regime
        """
        # Ensure confirmed regime is updated
        self._get_confirmed_regime(dataframe)

        # Clear previous signals
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        if self._confirmed_regime == MarketRegime.TREND:
            dataframe = self._entry_trend_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.VOLATILE:
            dataframe = self._entry_volatile_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.RANGE:
            dataframe = self._entry_range_mode(dataframe)

        return dataframe

    def _entry_trend_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        TREND entry: EMA cross + ADX + DI confirmation
        Only trade in direction of established trend
        """
        # Long entries: EMA bullish + ADX strong + DI confirming
        long_conditions = (
            dataframe["ema_bullish"]
            & (dataframe["adx"] > self.TREND_ENTRY_ADX_MIN)
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["rsi"] > 40)
            & (dataframe["rsi"] < 70)
            & (dataframe["volume"] > 0)
        )

        # Short entries: EMA bearish + ADX strong + DI confirming
        short_conditions = (
            dataframe["ema_bearish"]
            & (dataframe["adx"] > self.TREND_ENTRY_ADX_MIN)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["rsi"] < 60)
            & (dataframe["rsi"] > 30)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def _entry_volatile_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        VOLATILE entry: BB touch + RSI extreme + some trend confirmation
        Trade reversals at BB bounds when in volatile regime
        """
        # Long entries: BB lower touch + RSI oversold
        long_conditions = (
            dataframe["bb_touch_lower"]
            & (dataframe["rsi"] < self.VOLATILE_ENTRY_RSI_LOW)
            & (dataframe["adx"] > self.VOLATILE_ENTRY_ADX_MIN)
            & (dataframe["volume_ratio"] > 0.8)
            & (dataframe["volume"] > 0)
        )

        # Short entries: BB upper touch + RSI overbought
        short_conditions = (
            dataframe["bb_touch_upper"]
            & (dataframe["rsi"] > self.VOLATILE_ENTRY_RSI_HIGH)
            & (dataframe["adx"] > self.VOLATILE_ENTRY_ADX_MIN)
            & (dataframe["volume_ratio"] > 0.8)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def _entry_range_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        RANGE entry: Mean reversion at BB bounds + RSI exhaustion
        Quick trades expecting reversal to mean
        """
        # Long: BB lower touch + RSI very oversold
        long_conditions = (
            dataframe["bb_touch_lower"]
            & (dataframe["rsi"] < self.RANGE_ENTRY_RSI_LOW)
            & (dataframe["bb_position"] < 0.15)
            & (dataframe["volume"] > 0)
        )

        # Short: BB upper touch + RSI very overbought
        short_conditions = (
            dataframe["bb_touch_upper"]
            & (dataframe["rsi"] > self.RANGE_ENTRY_RSI_HIGH)
            & (dataframe["bb_position"] > 0.85)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    # ==================== Exit Logic ====================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Route exit logic based on confirmed regime
        """
        if self._confirmed_regime == MarketRegime.TREND:
            dataframe = self._exit_trend_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.VOLATILE:
            dataframe = self._exit_volatile_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.RANGE:
            dataframe = self._exit_range_mode(dataframe)

        return dataframe

    def _exit_trend_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        TREND exit: EMA reversal or ADX weakening
        """
        # Long exit: EMA bearish or ADX dropping
        long_exit = (
            dataframe["ema_bearish"]
            | (dataframe["adx"] < 20)
            | ((dataframe["minus_di"] > dataframe["plus_di"]) & dataframe["di_cross_down"])
        )

        # Short exit: EMA bullish or ADX dropping
        short_exit = (
            dataframe["ema_bullish"]
            | (dataframe["adx"] < 20)
            | ((dataframe["plus_di"] > dataframe["minus_di"]) & dataframe["di_cross_up"])
        )

        dataframe.loc[long_exit, "exit_long"] = 1
        dataframe.loc[short_exit, "exit_short"] = 1

        return dataframe

    def _exit_volatile_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        VOLATILE exit: RSI neutralization or momentum shift
        """
        # Exit when RSI returns to neutral zone
        rsi_neutral = (dataframe["rsi"] >= 45) & (dataframe["rsi"] <= 55)

        dataframe.loc[rsi_neutral, "exit_long"] = 1
        dataframe.loc[rsi_neutral, "exit_short"] = 1

        return dataframe

    def _exit_range_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        RANGE exit: Quick profit taking when price reverts
        """
        # Mean reversion targets hit
        long_exit = (dataframe["bb_position"] > 0.4) & (dataframe["bb_position"] < 0.6)
        short_exit = (dataframe["bb_position"] > 0.4) & (dataframe["bb_position"] < 0.6)

        dataframe.loc[long_exit, "exit_long"] = 1
        dataframe.loc[short_exit, "exit_short"] = 1

        return dataframe

    # ==================== Dynamic Risk Management ====================

    def get_stoploss(
        self, trade, entry, current_time, lookback_1h, current_rate, current_time_1h, **kwargs
    ) -> float:
        """
        Return regime-specific stoploss
        """
        if self._confirmed_regime == MarketRegime.TREND:
            return self.TREND_STOP_LOSS
        elif self._confirmed_regime == MarketRegime.VOLATILE:
            return self.VOLATILE_STOP_LOSS
        elif self._confirmed_regime == MarketRegime.RANGE:
            return self.RANGE_STOP_LOSS
        return -0.03

    def get_roi_table(self, trade) -> Optional[dict]:
        """
        Return regime-specific ROI table
        """
        if self._confirmed_regime == MarketRegime.TREND:
            return self.TREND_ROI
        elif self._confirmed_regime == MarketRegime.VOLATILE:
            return self.VOLATILE_ROI
        elif self._confirmed_regime == MarketRegime.RANGE:
            return self.RANGE_ROI
        return {"0": 0.05, "360": 0.03}

    @property
    def trailing_stop(self) -> bool:
        """
        Range mode doesn't use trailing
        """
        return self._confirmed_regime != MarketRegime.RANGE

    @property
    def trailing_stop_positive(self) -> float:
        if self._confirmed_regime == MarketRegime.TREND:
            return self.TREND_TRAILING_POSITIVE
        elif self._confirmed_regime == MarketRegime.VOLATILE:
            return self.VOLATILE_TRAILING_POSITIVE
        return 0.015

    @property
    def trailing_stop_positive_offset(self) -> float:
        if self._confirmed_regime == MarketRegime.TREND:
            return self.TREND_TRAILING_OFFSET
        elif self._confirmed_regime == MarketRegime.VOLATILE:
            return self.VOLATILE_TRAILING_OFFSET
        return 0.03
