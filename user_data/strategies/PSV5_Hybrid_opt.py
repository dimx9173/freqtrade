"""
PSV5_Hybrid - 動態市場狀態切換策略
根據 ATR 波動率在 PSV5_Final_Best（突破）和 PSV1_ATR_Filter（趨勢）之間切換

邏輯:
- 高波動率（ATR ratio > 1.5）→ PSV5_Final_Best 邏輯（突破策略）
- 低波動率（ATR ratio <= 1.5）→ PSV1_ATR_Filter 邏輯（趨勢策略）

結合兩個最佳策略的優點:
- PSV5_Final_Best 的高收益特性
- PSV1_ATR_Filter 的低回撤特性
"""

import talib.abstract as ta
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter


class PSV5_Hybrid_opt(IStrategy):
    """
    Hybrid Strategy: Dynamically switches between breakout (PSV5) and trend-following (PSV1)
    based on market volatility (ATR ratio).
    """

    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = False

    # ========== Base Stop Loss and ROI ==========
    stoploss = -0.05  # Dynamic base stoploss
    minimal_roi = {"0": 0.08, "60": 0.05, "120": 0.03}
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ========== Startup Settings ==========
    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    # ========== Volatility Regime Parameters (Hyperoptable) ==========
    buy_volatility_threshold = DecimalParameter(1.0, 3.0, default=1.5, decimals=1, space="buy")
    buy_atr_threshold_high = DecimalParameter(1.5, 4.0, default=2.0, decimals=1, space="buy")
    buy_atr_threshold_low = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    # Volume confirmation threshold
    buy_volume_ratio_min = DecimalParameter(1.0, 2.0, default=1.2, decimals=1, space="buy")

    # ADX threshold for trend confirmation
    buy_adx_min = DecimalParameter(3.0, 25.0, default=5.0, decimals=0, space="buy")
    buy_adx_trend_min = DecimalParameter(10.0, 30.0, default=18.0, decimals=0, space="buy")

    # RSI thresholds
    buy_rsi_short_min = DecimalParameter(50.0, 65.0, default=55.0, decimals=0, space="buy")
    buy_rsi_short_max = DecimalParameter(60.0, 75.0, default=65.0, decimals=0, space="buy")
    buy_rsi_long_max = DecimalParameter(35.0, 50.0, default=45.0, decimals=0, space="buy")

    # EMA proximity threshold
    buy_ema_proximity_pct = DecimalParameter(0.3, 1.5, default=0.5, decimals=1, space="buy")

    # ROC momentum threshold
    buy_roc_threshold = DecimalParameter(0.0, 2.0, default=0.0, decimals=1, space="buy")

    # ========== Buy/Sell Parameters ==========
    buy_params = {
        "buy_volatility_threshold": 1.5,
        "buy_atr_threshold_high": 2.0,
        "buy_atr_threshold_low": 1.0,
        "buy_volume_ratio_min": 1.2,
        "buy_adx_min": 5.0,
        "buy_adx_trend_min": 18.0,
        "buy_rsi_short_min": 55.0,
        "buy_rsi_short_max": 65.0,
        "buy_rsi_long_max": 45.0,
        "buy_ema_proximity_pct": 0.5,
        "buy_roc_threshold": 0.0,
    }

    sell_params = {}

    # ========== Stoploss Parameters (Fixed — not hyperopted) ==========
    # Note: stoploss is defined as a static value above.
    # Stoploss space is intentionally NOT made hyperoptable to avoid KeyError conflicts.

    # ========== Trailing Stop Parameters (Fixed — not hyperopted) ==========
    # Note: trailing_* is defined as static values above.
    # Trailing space is intentionally NOT made hyperoptable to avoid KeyError conflicts.

    # ========== ROI Parameters (Fixed — not hyperopted) ==========
    # Note: minimal_roi is defined as a static dict above.
    # ROI space is intentionally NOT made hyperoptable to avoid KeyError conflicts.

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ========== 1. ATR - 波動率測量 ==========
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_ma"] = dataframe["atr"].rolling(window=20).mean()
        dataframe["atr_ratio"] = dataframe["atr"] / dataframe["atr_ma"]

        # ========== 2. Price Breakout Indicators (PSV5 logic) ==========
        dataframe["recent_high"] = dataframe["high"].rolling(window=10).max()
        dataframe["recent_low"] = dataframe["low"].rolling(window=10).min()

        # Breakout signals
        dataframe["breakout_up"] = dataframe["close"] > dataframe["recent_high"].shift(1)
        dataframe["breakout_down"] = dataframe["close"] < dataframe["recent_low"].shift(1)

        # ========== 3. Volume Indicators ==========
        dataframe["volume_ma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma"]

        # ========== 4. ADX Directional Indicators ==========
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        dataframe["adx_strong"] = dataframe["adx"] > self.buy_adx_min.value
        dataframe["di_bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["di_bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        # ========== 5. Volatility Regime Flag ==========
        dataframe["high_volatility"] = dataframe["atr_ratio"] > self.buy_volatility_threshold.value

        # ========== 6. Bollinger Bands ==========
        bb_result = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb_result["upperband"]
        dataframe["bb_lower"] = bb_result["lowerband"]
        dataframe["bb_width"] = (bb_result["upperband"] - bb_result["lowerband"]) / bb_result[
            "middleband"
        ]

        # ========== 7. Rate of Change - 動量 ==========
        dataframe["roc"] = ta.ROCP(dataframe, timeperiod=10) * 100

        # ========== 8. PSV1 Trend Indicators ==========
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Close at EMA proximity
        ema_prox = self.buy_ema_proximity_pct.value / 100
        dataframe["at_ema"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < ema_prox
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < ema_prox)

        # ATR filter for PSV1 mode
        dataframe["atr_filter"] = dataframe["atr"] > dataframe["atr_ma"] * 0.9

        # ========== 9. Dynamic Stop Loss Percentage (ATR-based) ==========
        # Used by custom_stoploss for dynamic adjustment
        dataframe["atr_stop_pct"] = (dataframe["atr"] * 1.5) / dataframe["close"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Get current volatility regime
        high_vol = dataframe["high_volatility"]

        # ========== HIGH VOLATILITY MODE: PSV5 Breakout Logic ==========
        # Entry conditions from PSV5_Final_Best
        breakout_long = (
            high_vol  # Volatility expansion
            & dataframe["breakout_up"]  # Price breakout above 10-bar high
            & (dataframe["volume_ratio"] > self.buy_volume_ratio_min.value)  # Volume confirmation
            & dataframe["adx_strong"]  # ADX > threshold (trending)
            & dataframe["di_bullish"]  # +DI > -DI (bullish)
            & (dataframe["roc"] > self.buy_roc_threshold.value)  # Positive momentum
        )

        breakout_short = (
            high_vol  # Volatility expansion
            & dataframe["breakout_down"]  # Price breakdown below 10-bar low
            & (dataframe["volume_ratio"] > self.buy_volume_ratio_min.value)  # Volume confirmation
            & dataframe["adx_strong"]  # ADX > threshold (trending)
            & dataframe["di_bearish"]  # -DI > +DI (bearish)
            & (dataframe["roc"] < -self.buy_roc_threshold.value)  # Negative momentum
        )

        # ========== LOW VOLATILITY MODE: PSV1 Trend-Following Logic ==========
        # Entry conditions from PSV1_ATR_Filter (trend-following, mainly short)
        trend_short = (
            (~high_vol)  # Low volatility regime
            & (dataframe["ema9"] < dataframe["ema21"])  # EMA bearish alignment
            & (dataframe["adx"] > self.buy_adx_trend_min.value)  # ADX confirm trend
            & (dataframe["minus_di"] > dataframe["plus_di"])  # Bearish DI
            & (dataframe["rsi"] > self.buy_rsi_short_min.value)  # RSI in upper zone
            & (dataframe["rsi"] < self.buy_rsi_short_max.value)  # RSI not overbought
            & dataframe["at_ema"]  # Price near EMA
            & (dataframe["close"] < dataframe["ema200"])  # Below 200 EMA
            & dataframe["atr_filter"]  # ATR confirms volatility
        )

        # Long during low volatility - pullback entries
        trend_long = (
            (~high_vol)  # Low volatility regime
            & (dataframe["ema9"] > dataframe["ema21"])  # EMA bullish alignment
            & (dataframe["adx"] > self.buy_adx_trend_min.value)  # ADX confirm trend
            & (dataframe["plus_di"] > dataframe["minus_di"])  # Bullish DI
            & (dataframe["rsi"] < self.buy_rsi_long_max.value)  # RSI in lower zone (pullback)
            & dataframe["at_ema"]  # Price near EMA
            & (dataframe["close"] > dataframe["ema200"])  # Above 200 EMA
            & dataframe["atr_filter"]  # ATR confirms volatility
        )

        # Combine all conditions
        dataframe.loc[breakout_long | trend_long, "enter_long"] = 1
        dataframe.loc[breakout_short | trend_short, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit handled by ROI and stoploss
        """
        return dataframe

    def custom_stoploss(
        self, pair, trade, current_time, current_rate, current_profit, after_fill, mode=None
    ) -> float:
        """
        Dynamic ATR-based stoploss:
        - High volatility: Use wider stop from PSV5 logic
        - Low volatility: Use tighter ATR-based stop from PSV1 logic
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe is None or len(dataframe) < 2:
            return self.stoploss

        last_candle = dataframe.iloc[-1]
        atr_ratio = last_candle.get("atr_ratio", 1.0)
        atr = last_candle.get("atr")

        if atr is None or np.isnan(atr):
            return self.stoploss

        # High volatility mode: Use PSV5 wide stop
        if atr_ratio > self.buy_volatility_threshold.value:
            return max(0.02, min(0.05, 0.04))

        # Low volatility mode: Use PSV1 ATR-based stop
        atr_multiplier = 1.5
        stoploss_pct = (atr * atr_multiplier) / current_rate

        # Cap stoploss to reasonable bounds (0.5% to 3%)
        stoploss_pct = max(0.005, min(0.03, stoploss_pct))

        return -stoploss_pct

    def adjust_position_size(self, dataframe: DataFrame, metadata: dict) -> float:
        # Position sizing based on volatility
        atr_ratio = dataframe["atr_ratio"].iloc[-1]

        if atr_ratio > self.buy_atr_threshold_high.value:
            return 0.5  # Reduce to 50% position size
        elif atr_ratio < self.buy_atr_threshold_low.value:
            return 1.0  # Full position size
        else:
            return 0.75  # Medium position size
