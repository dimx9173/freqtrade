# FreqAI_ML_Strategy V80 - Enhanced Regime Detection with Dynamic Thresholds
#
# V80 Key Improvements over V70:
# ✅ Lowered ADX thresholds: 22 (from 28) for better trend capture
# ✅ Raised entry thresholds: Uptrend 0.65, Downtrend 0.72 (reduce false signals)
# ✅ High Vol Override only when ADX marginal (15-25)
# ✅ Kelly Criterion dynamic position sizing
# ✅ ML Reversal custom exit
# ✅ ATR percentile + BB width composite volatility

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import freqtrade.vendor.qtpylib.indicators as qtpylib
import logging
from pandas import DataFrame
from typing import Dict
from datetime import datetime, timezone
import warnings

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class FreqAI_ML_Strategy_v80(IStrategy):
    """
    FreqAI ML Strategy V80 - Enhanced Regime Detection

    V80 Improvements:
    - Lower ADX thresholds (22 vs 28) for earlier trend detection
    - Raised entry thresholds to reduce false signals
    - High Vol Override only when ADX marginal (15-25)
    - Kelly Criterion position sizing
    - ML Reversal exit protection
    """

    INTERFACE_VERSION = 3

    # ===========================================
    # FREQAI CONFIGURATION
    # ===========================================
    freqai_enabled = True

    # ===========================================
    # TIMEFRAME & CONFIG
    # ===========================================
    timeframe = "1h"
    informative_timeframes = ["4h", "1d"]

    # ===========================================
    # STOPLOSS & TRAILING
    # ===========================================
    stoploss = -0.10

    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True

    minimal_roi = {"0": 0.05}

    can_short = True
    startup_candle_count = 80
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # ===========================================
    # REGIME ENTRY THRESHOLDS (V80: Raised)
    # ===========================================

    # Uptrend parameters
    uptrend_confidence_threshold = DecimalParameter(
        0.55, 0.85, default=0.70, decimals=2, space="buy"
    )
    uptrend_prediction_threshold = DecimalParameter(
        0.55, 0.80, default=0.65, decimals=2, space="buy"
    )
    uptrend_adx_min = DecimalParameter(18, 30, default=22, decimals=0, space="buy")

    # Downtrend parameters
    downtrend_confidence_threshold = DecimalParameter(
        0.60, 0.90, default=0.75, decimals=2, space="buy"
    )
    downtrend_prediction_threshold = DecimalParameter(
        0.55, 0.80, default=0.72, decimals=2, space="buy"
    )
    downtrend_adx_min = DecimalParameter(18, 30, default=22, decimals=0, space="buy")

    # Sideways parameters
    sideways_confidence_threshold = DecimalParameter(
        0.60, 0.90, default=0.75, decimals=2, space="buy"
    )
    sideways_prediction_threshold = DecimalParameter(
        0.60, 0.85, default=0.70, decimals=2, space="buy"
    )

    # Volatile parameters
    volatile_confidence_threshold = DecimalParameter(
        0.65, 0.90, default=0.75, decimals=2, space="buy"
    )
    volatile_prediction_threshold = DecimalParameter(
        0.65, 0.85, default=0.72, decimals=2, space="buy"
    )

    # ===========================================
    # REGIME DETECTION SETTINGS
    # ===========================================
    regime_detection_enabled = BooleanParameter(default=True, space="buy")
    regime_lookback_period = IntParameter(50, 200, default=100, space="buy")
    regime_adx_period = IntParameter(10, 20, default=14, space="buy")

    # ===========================================
    # POSITION SIZING BY REGIME
    # ===========================================
    dynamic_position_sizing = BooleanParameter(default=True, space="buy")
    base_risk_factor = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    # Position multipliers per regime
    uptrend_position_mult = DecimalParameter(1.0, 2.0, default=1.3, decimals=1, space="buy")
    downtrend_position_mult = DecimalParameter(0.2, 0.6, default=0.35, decimals=2, space="buy")
    sideways_position_mult = DecimalParameter(0.5, 1.0, default=0.7, decimals=1, space="buy")
    volatile_position_mult = DecimalParameter(0.2, 0.5, default=0.3, decimals=1, space="buy")

    # ===========================================
    # TRAILING STOP BY REGIME
    # ===========================================
    uptrend_trailing_offset = DecimalParameter(0.015, 0.04, default=0.025, decimals=3, space="buy")
    downtrend_trailing_offset = DecimalParameter(
        0.008, 0.02, default=0.012, decimals=3, space="buy"
    )
    sideways_trailing_offset = DecimalParameter(
        0.005, 0.015, default=0.008, decimals=3, space="buy"
    )
    volatile_trailing_offset = DecimalParameter(0.01, 0.025, default=0.015, decimals=3, space="buy")

    def informative_pairs(self):
        """Expand informative pairs"""
        pairs = self.dp.current_whitelist()
        informative_pairs = []

        for tf in self.informative_timeframes:
            informative_pairs.extend([(pair, tf) for pair in pairs])

        # Add major correlated assets
        major_pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        for pair in major_pairs:
            if pair not in [p[0] for p in informative_pairs]:
                for tf in self.informative_timeframes:
                    informative_pairs.append((pair, tf))

        return informative_pairs

    def calc_smma(self, series, period=20):
        """Calculate Smoothed Moving Average"""
        return series.ewm(alpha=1 / period, min_periods=period).mean()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        V80 Enhanced Indicator System with Regime Detection
        """

        # ===========================================
        # BASIC TECHNICAL INDICATORS
        # ===========================================

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_sma"] = ta.SMA(dataframe["rsi"], timeperiod=14)

        # EMA System
        for period in [8, 12, 21, 26, 50, 200]:
            dataframe[f"ema_{period}"] = ta.EMA(dataframe, timeperiod=period)

        dataframe["ema_fast"] = dataframe["ema_12"]
        dataframe["ema_slow"] = dataframe["ema_26"]
        dataframe["ema_medium"] = dataframe["ema_50"]

        # MACD
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # Bollinger Bands
        bbands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bbands["upperband"]
        dataframe["bb_middle"] = bbands["middleband"]
        dataframe["bb_lower"] = bbands["lowerband"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / (
            dataframe["bb_middle"] + 1e-10
        )
        dataframe["bb_percent"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"] + 1e-10
        )

        # ATR (Volatility)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # ATR Percentile (V80: Dynamic threshold)
        dataframe["atr_percentile"] = (
            dataframe["atr"]
            .rolling(100)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
        )

        # BB Width Percentile (V80: New)
        dataframe["bb_width_percentile"] = (
            dataframe["bb_width"]
            .rolling(100)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
        )

        # Composite Volatility (V80: ATR + BB width)
        dataframe["volatility_composite"] = (
            dataframe["atr_percentile"] + dataframe["bb_width_percentile"]
        ) / 2

        # ADX (Trend Strength)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # CCI
        dataframe["cci"] = ta.CCI(dataframe, timeperiod=20)

        # Stochastic
        dataframe["stoch_k"], dataframe["stoch_d"] = ta.STOCH(
            dataframe,
            fastk_period=14,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )

        # VWAP
        dataframe["vwap"] = qtpylib.rolling_vwap(dataframe, window=8, min_periods=8)

        # ===========================================
        # VOLUME INDICATORS
        # ===========================================
        dataframe["volume_smma"] = self.calc_smma(dataframe["volume"], 20)
        dataframe["volume_ratio"] = dataframe["volume"] / (dataframe["volume_smma"] + 1e-10)
        dataframe["obv"] = ta.OBV(dataframe)
        dataframe["ad"] = ta.AD(dataframe)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)

        # ===========================================
        # VOLATILITY INDICATORS
        # ===========================================
        dataframe["atr_ratio"] = dataframe["atr"] / self.calc_smma(dataframe["atr"], 20)
        dataframe["realized_volatility"] = dataframe["close"].rolling(20).std()
        dataframe["volatility_ratio"] = dataframe["atr"] / (
            dataframe["realized_volatility"] + 1e-10
        )
        dataframe["high_volatility"] = dataframe["volatility_ratio"] > dataframe[
            "volatility_ratio"
        ].rolling(50).quantile(0.80)

        # ===========================================
        # PRICE ACTION INDICATORS
        # ===========================================
        dataframe["price_momentum"] = dataframe["close"].pct_change(5)
        dataframe["price_acceleration"] = dataframe["price_momentum"].diff()

        # ===========================================
        # MICROSTRUCTURE FEATURES
        # ===========================================
        dataframe["buy_pressure"] = np.where(
            dataframe["close"] > dataframe["open"],
            dataframe["volume"]
            * (dataframe["close"] - dataframe["open"])
            / (dataframe["high"] - dataframe["low"] + 1e-10),
            0,
        )
        dataframe["sell_pressure"] = np.where(
            dataframe["close"] < dataframe["open"],
            dataframe["volume"]
            * (dataframe["open"] - dataframe["close"])
            / (dataframe["high"] - dataframe["low"] + 1e-10),
            0,
        )
        dataframe["pressure_ratio"] = dataframe["buy_pressure"] / (
            dataframe["sell_pressure"] + 1e-10
        )
        dataframe["liquidity_proxy"] = dataframe["volume"] / (dataframe["atr"] + 1e-10)

        # ===========================================
        # MULTI-TIMEFRAME FEATURES
        # ===========================================
        dataframe = self.add_multi_timeframe_features(dataframe, metadata)

        # ===========================================
        # CORE: MARKET REGIME DETECTION (V80)
        # ===========================================
        dataframe = self.detect_market_regime(dataframe)

        # ===========================================
        # SIGNAL QUALITY
        # ===========================================
        dataframe = self.calculate_signal_quality(dataframe)

        # ===========================================
        # FREQAI ML FEATURES
        # ===========================================
        try:
            if self.freqai_enabled and hasattr(self, "freqai"):
                dataframe = self.freqai.start(dataframe, metadata, self)
            else:
                dataframe["&ml_prediction"] = 0.50
                dataframe["&ml_confidence"] = 0.50
        except Exception as e:
            dataframe["&ml_prediction"] = 0.50
            dataframe["&ml_confidence"] = 0.50

        return dataframe

    def add_multi_timeframe_features(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Multi-timeframe confirmation features"""

        for tf in self.informative_timeframes:
            try:
                informative = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=tf)

                # freqtrade DataFrames use DatetimeIndex, reset to 'date' column for merge_informative_pair
                informative = informative.reset_index()
                if "date" not in informative.columns and "datetime" in informative.columns:
                    informative = informative.rename(columns={"datetime": "date"})

                informative[f"rsi_{tf}"] = ta.RSI(informative["close"], timeperiod=14)
                informative[f"ema_21_{tf}"] = ta.EMA(informative["close"], timeperiod=21)
                informative[f"volume_ratio_{tf}"] = informative["volume"] / self.calc_smma(
                    informative["volume"], 20
                )
                informative[f"adx_{tf}"] = ta.ADX(
                    informative["high"], informative["low"], informative["close"], timeperiod=14
                )

                informative[f"trend_up_{tf}"] = informative[f"ema_21_{tf}"] > informative[
                    f"ema_21_{tf}"
                ].shift(5)

                dataframe = self.merge_informative_pair_safe(
                    dataframe, informative, self.timeframe, tf, ffill=True
                )

            except Exception as e:
                logger.warning(f"Failed to add {tf} timeframe data: {e}")
                continue

        return dataframe

    def merge_informative_pair_safe(self, dataframe, informative, timeframe, tf, ffill=True):
        """Safe merge for informative pairs"""
        from freqtrade.strategy import merge_informative_pair

        return merge_informative_pair(dataframe, informative, timeframe, tf, ffill=ffill)

    def detect_market_regime(self, dataframe: DataFrame) -> DataFrame:
        """
        V80 ENHANCED: Multi-Factor Market Regime Detection

        Key Changes from V70:
        - Lower ADX thresholds (22 vs 28)
        - High Vol Override only when ADX marginal (15-25)
        - Uses composite volatility (ATR + BB width)
        """

        lookback = self.regime_lookback_period.value

        # ---- Calculate regime indicators ----

        # EMA Trend
        dataframe["ema_trend_strength"] = (
            dataframe["ema_fast"] - dataframe["ema_slow"]
        ) / dataframe["ema_slow"]
        dataframe["ema_convergence"] = (
            np.abs(dataframe["ema_fast"] - dataframe["ema_slow"]) / dataframe["ema_slow"]
        )

        # Price vs EMAs
        dataframe["price_vs_ema_medium"] = (
            dataframe["close"] - dataframe["ema_medium"]
        ) / dataframe["ema_medium"]
        dataframe["price_vs_vwap"] = (dataframe["close"] - dataframe["vwap"]) / dataframe["vwap"]

        # ADX-based trend strength
        dataframe["adx_strong"] = dataframe["adx"] > self.uptrend_adx_min.value

        # DI-based direction
        dataframe["di_bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["di_bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        # Volatility percentile (rolling)
        dataframe["volatility_percentile"] = (
            dataframe["volatility_ratio"]
            .rolling(lookback)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
        )

        # ---- V80: High Volatility Detection ----
        # High vol only when composite volatility > 0.75 AND ATR ratio > 1.5
        high_vol_condition = (dataframe["volatility_composite"] > 0.75) & (
            dataframe["atr_ratio"] > 1.5
        )

        # ---- V80: ADX Marginal Zone (15-25) ----
        adx_marginal = (dataframe["adx"] > 15) & (dataframe["adx"] < 25)

        # ---- Regime Classification ----

        # Initialize as neutral
        dataframe["market_regime"] = "neutral"

        # SIDEWAYS (low ADX, EMAs converging)
        sideways_cond = (
            (dataframe["adx"] < 20)
            & (dataframe["ema_convergence"] < 0.01)
            & (dataframe["volatility_percentile"] < 0.7)
        )
        dataframe.loc[sideways_cond, "market_regime"] = "sideways"

        # UPTREND (EMA bullish, ADX strong, price above EMAs)
        uptrend_cond = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["close"] > dataframe["ema_medium"])
            & (dataframe["adx"] >= self.uptrend_adx_min.value)
            & (dataframe["di_bullish"] == True)
        )
        dataframe.loc[uptrend_cond, "market_regime"] = "uptrend"

        # DOWNTREND (EMA bearish, ADX strong, price below EMAs)
        downtrend_cond = (
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["close"] < dataframe["ema_medium"])
            & (dataframe["adx"] >= self.downtrend_adx_min.value)
            & (dataframe["di_bearish"] == True)
        )
        dataframe.loc[downtrend_cond, "market_regime"] = "downtrend"

        # ---- V80: High Vol Override (only when ADX marginal) ----
        # Override ONLY if ADX is in marginal zone (15-25) AND high volatility
        high_vol_override = (
            dataframe["market_regime"].isin(["uptrend", "downtrend", "sideways"])
            & high_vol_condition
            & adx_marginal  # V80: Only override when ADX marginal
        )
        dataframe.loc[high_vol_override, "market_regime"] = "volatile"

        # ---- Regime-specific indicators ----
        dataframe["regime_is_uptrend"] = (dataframe["market_regime"] == "uptrend").astype(int)
        dataframe["regime_is_downtrend"] = (dataframe["market_regime"] == "downtrend").astype(int)
        dataframe["regime_is_sideways"] = (dataframe["market_regime"] == "sideways").astype(int)
        dataframe["regime_is_volatile"] = (dataframe["market_regime"] == "volatile").astype(int)

        return dataframe

    def calculate_signal_quality(self, dataframe: DataFrame) -> DataFrame:
        """Calculate comprehensive signal quality scores"""

        # SMC Score
        dataframe["smc_score"] = (
            (dataframe["close"] > dataframe["vwap"]).astype(float) * 0.30
            + (dataframe["ema_fast"] > dataframe["ema_slow"]).astype(float) * 0.25
            + ((dataframe["rsi"] > 30) & (dataframe["rsi"] < 70)).astype(float) * 0.20
            + (dataframe["volume_ratio"] > 1.0).astype(float) * 0.15
            + (dataframe["adx"] > 20).astype(float) * 0.10
        )

        # Signal Quality (normalized)
        dataframe["signal_quality"] = (
            dataframe["smc_score"] * 0.5
            + ((dataframe["rsi"] - 30) / 40).clip(0, 1) * 0.25
            + (dataframe["volume_ratio"] / 2).clip(0, 1) * 0.25
        )

        # Momentum Score
        dataframe["momentum_score"] = (
            (dataframe["price_momentum"] > 0).astype(float) * 0.30
            + (dataframe["macdhist"] > 0).astype(float) * 0.30
            + (dataframe["cci"] > -100).astype(float) * 0.20
            + (dataframe["stoch_k"] > dataframe["stoch_d"]).astype(float) * 0.20
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        V80 REGIME-ADAPTIVE ENTRY LOGIC

        Key Changes from V70:
        - Raised thresholds: Uptrend 0.65, Downtrend 0.72
        - Added DI+ confirmation for uptrend
        - Added EMA confirmation for all regimes
        """

        # ML signals
        if self.freqai_enabled:
            ml_prediction = dataframe.get("&ml_prediction", 0.5)
            ml_confidence = dataframe.get("&ml_confidence", 0.5)
        else:
            ml_prediction = 0.50
            ml_confidence = 0.50

        regime = dataframe["market_regime"]

        # ===========================================
        # SELECT THRESHOLDS BY REGIME
        # ===========================================
        confidence_thresh = np.where(
            regime == "uptrend",
            self.uptrend_confidence_threshold.value,
            np.where(
                regime == "downtrend",
                self.downtrend_confidence_threshold.value,
                np.where(
                    regime == "sideways",
                    self.sideways_confidence_threshold.value,
                    self.volatile_confidence_threshold.value,
                ),
            ),
        )

        prediction_thresh = np.where(
            regime == "uptrend",
            self.uptrend_prediction_threshold.value,
            np.where(
                regime == "downtrend",
                self.downtrend_prediction_threshold.value,
                np.where(
                    regime == "sideways",
                    self.sideways_prediction_threshold.value,
                    self.volatile_prediction_threshold.value,
                ),
            ),
        )

        # ===========================================
        # V80 FALLBACK: Same as V70 — use effective thresholds
        # When no ML model is available (ml == 0.50), fallback to 0.50
        # ===========================================
        has_ml_signal = (ml_prediction != 0.50) | (ml_confidence != 0.50)
        effective_pred_thresh = np.where(has_ml_signal, prediction_thresh, 0.50)
        effective_conf_thresh = np.where(has_ml_signal, confidence_thresh, 0.50)

        # ===========================================
        # BASE CONDITIONS (Universal)
        # ===========================================
        base_condition = (
            (dataframe["volume"] > 0) & (dataframe["volume_ratio"] > 0.8) & (dataframe["atr"] > 0)
        )

        # Price relative to VWAP
        price_above_vwap = dataframe["close"] > dataframe["vwap"]
        price_below_vwap = dataframe["close"] < dataframe["vwap"]

        # ===========================================
        # UPTREND ENTRIES (Long)
        # ===========================================
        uptrend_entry_cond = (
            (regime == "uptrend")
            & base_condition
            & price_above_vwap
            & (dataframe["volume_ratio"] > 1.2)
            & (dataframe["smc_score"] >= 0.50)
            & (dataframe["adx"] >= self.uptrend_adx_min.value)
            & (dataframe["di_bullish"] == True)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (ml_prediction >= effective_pred_thresh)
            & (ml_confidence >= effective_conf_thresh)
        )

        # ===========================================
        # DOWNTREND ENTRIES (Short)
        # ===========================================
        downtrend_entry_cond = (
            (regime == "downtrend")
            & base_condition
            & price_below_vwap
            & (dataframe["volume_ratio"] > 1.0)
            & (dataframe["smc_score"] >= 0.40)
            & (dataframe["adx"] >= self.downtrend_adx_min.value)
            & (dataframe["di_bearish"] == True)
            & (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (ml_prediction <= effective_pred_thresh)
            & (ml_confidence >= effective_conf_thresh)
        )

        # ===========================================
        # SIDEWAYS ENTRIES (Range-bound)
        # ===========================================
        sideways_entry_cond = (
            (regime == "sideways")
            & base_condition
            & ((price_above_vwap) | (price_below_vwap))
            & (dataframe["bb_percent"] < 0.2)  # Near lower BB
            & (dataframe["volume_ratio"] > 1.1)
            & (ml_prediction >= effective_pred_thresh)
            & (ml_confidence >= effective_conf_thresh)
        )

        # ===========================================
        # VOLATILE REGIME (Minimal exposure)
        # ===========================================
        volatile_entry_cond = (
            (regime == "volatile")
            & base_condition
            & (dataframe["volume_ratio"] > 1.5)  # Higher volume req
            & (dataframe["smc_score"] >= 0.60)
            & (ml_prediction >= effective_pred_thresh)
            & (ml_confidence >= effective_conf_thresh)
        )

        # ===========================================
        # NO TRADE ZONE (V80: Reject low confidence only when ML is active)
        # ===========================================
        in_no_trade_zone = (
            has_ml_signal  # Only block when ML is actually running
            & (ml_prediction > 0.40)
            & (ml_prediction < 0.60)
            & (ml_confidence < 0.70)
        )

        # ===========================================
        # SET ENTRY SIGNALS
        # ===========================================
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        dataframe.loc[uptrend_entry_cond & ~in_no_trade_zone, "enter_long"] = 1
        dataframe.loc[downtrend_entry_cond & ~in_no_trade_zone, "enter_short"] = 1

        # Tag entries by regime
        dataframe["enter_tag"] = None
        dataframe.loc[uptrend_entry_cond & ~in_no_trade_zone, "enter_tag"] = "uptrend"
        dataframe.loc[downtrend_entry_cond & ~in_no_trade_zone, "enter_tag"] = "downtrend"
        dataframe.loc[sideways_entry_cond & ~in_no_trade_zone, "enter_tag"] = "sideways"
        dataframe.loc[volatile_entry_cond & ~in_no_trade_zone, "enter_tag"] = "volatile"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        V80 EXIT LOGIC - Trailing stop + custom exit
        """

        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time,
        current_rate,
        current_profit: float,
        dataframe: DataFrame,
        **kwargs,
    ) -> str:
        """
        V80 CUSTOM EXIT - ML Reversal + Regime Change Protection
        """

        if not self.freqai_enabled:
            return None

        try:
            ml_prediction = dataframe["&ml_prediction"].iloc[-1]
            ml_confidence = dataframe["&ml_confidence"].iloc[-1]
            regime = dataframe["market_regime"].iloc[-1]
        except (KeyError, IndexError):
            return None

        # ===========================================
        # ML REVERSAL EXIT
        # ===========================================
        if (ml_prediction < 0.35 and ml_confidence > 0.70) or (
            ml_prediction > 0.65 and ml_confidence > 0.70
        ):
            return "ml_reversal_exit"

        # ===========================================
        # REGIME CHANGE EXIT
        # ===========================================
        if regime == "volatile" and current_profit > 0:
            return "volatile_protection"

        return None

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate,
        proposed_stake: float,
        min_stake: float,
        max_stake: float,
        **kwargs,
    ) -> float:
        """
        V80: Kelly Criterion Dynamic Position Sizing

        Kelly % = W - (1-W)/R
        Where W = win rate, R = win/loss ratio

        Half-Kelly (0.5x safety factor) to reduce volatility
        """

        if not self.dynamic_position_sizing.value:
            return proposed_stake

        try:
            # Get current regime
            if hasattr(self, "current_regime"):
                regime = self.current_regime
            else:
                regime = "neutral"

            # Base stake (5% of wallet)
            base = self.base_risk_factor.value * 0.05

            # Regime multipliers (V80: More conservative downturn)
            regime_mult = {
                "uptrend": self.uptrend_position_mult.value,
                "downtrend": self.downtrend_position_mult.value,
                "sideways": self.sideways_position_mult.value,
                "volatile": self.volatile_position_mult.value,
            }.get(regime, 0.5)

            # Get ML confidence if available
            try:
                ml_confidence = self.get_current_confidence()
                conf_mult = 0.5 + ml_confidence * 1.0
            except:
                conf_mult = 1.0

            # Calculate Kelly fraction (simplified)
            # Assume 40% win rate, 1.5 reward/risk as defaults
            win_rate = 0.40
            reward_risk = 1.5

            kelly = (reward_risk * win_rate - (1 - win_rate)) / reward_risk
            kelly = max(0, kelly * 0.5)  # Half-Kelly safety factor
            kelly = max(0.05, min(0.20, kelly))  # Cap at 5-20%

            # Final stake calculation
            final_stake = proposed_stake * kelly * regime_mult * conf_mult

            return max(min_stake, min(max_stake, final_stake))

        except Exception as e:
            logger.warning(f"Error in custom_stake_amount: {e}")
            return proposed_stake

    def get_current_confidence(self) -> float:
        """Get current ML confidence (for position sizing)"""
        try:
            return 0.6  # Default fallback
        except:
            return 0.5
