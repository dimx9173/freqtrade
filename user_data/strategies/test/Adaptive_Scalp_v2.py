# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

"""
Adaptive_Scalp_v2 - Adaptive Market Regime Scalping Strategy
============================================================
Timeframe: 5m
Mode: Futures (long/short)
Leverage: 5x

Market Regime Detection:
- Regime 0 (Choppy): ADX < 20 AND BB Width < 0.02 -> Mean Reversion
- Regime 1 (Transition): ADX 20-25 -> Breakout / Watch
- Regime 2 (Strong Trend): ADX > 25 AND BB Width > 0.02 -> Trend Following

Entry Logic:
- Long (Choppy): Close < BB_lower AND RSI < 35 AND Volume > MA
- Long (Trend): Close > BB_middle AND EMA alignment AND ADX > 25
- Short: Inverse of long conditions

Exit Logic:
- ROI: Tiered take profit (3% -> 2% -> 1%)
- Stoploss: ATR-based dynamic stop loss
"""

import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy, RealParameter


class Adaptive_Scalp_v2(IStrategy):
    """
    Adaptive Scalp Strategy v2 - Dynamically switches between
    mean reversion and trend following based on market regime.
    """

    # === Timeframe Settings ===
    timeframe = "5m"

    # === Futures / Short Settings ===
    can_short = True
    process_only_new_candles = True

    # === Stop Loss Settings ===
    stoploss = -0.05  # Maximum stop loss: 5%
    use_custom_stoploss = True

    # === ROI Settings (Tiered) ===
    minimal_roi = {
        "0": 0.03,  # 3% at 0 minutes
        "30": 0.02,  # 2% after 30 minutes
        "60": 0.015,  # 1.5% after 60 minutes
        "120": 0.01,  # 1% after 120 minutes
    }

    # === Regime Detection Parameters ===
    adx_period = IntParameter(10, 20, default=14, space="buy")
    adx_strong_threshold = IntParameter(22, 30, default=25, space="buy")
    adx_weak_threshold = IntParameter(15, 25, default=20, space="buy")
    bb_width_threshold = DecimalParameter(0.015, 0.05, default=0.02, space="buy")

    # === Bollinger Bands Parameters ===
    bb_length = IntParameter(10, 30, default=20, space="buy")
    bb_std = RealParameter(1.5, 3.0, default=2.0, space="buy")

    # === RSI Parameters ===
    rsi_length = IntParameter(10, 20, default=14, space="buy")
    rsi_oversold = IntParameter(25, 40, default=35, space="buy")
    rsi_overbought = IntParameter(60, 75, default=65, space="sell")

    # === ATR Parameters (Dynamic Stop Loss) ===
    atr_length = IntParameter(10, 20, default=14, space="sell")
    atr_multiplier = RealParameter(1.5, 3.0, default=2.0, space="sell")

    # === EMA Parameters (Trend Following) ===
    ema_fast_length = IntParameter(5, 15, default=9, space="buy")
    ema_slow_length = IntParameter(15, 30, default=21, space="buy")

    # === Volume MA Parameters ===
    volume_ma_length = IntParameter(15, 30, default=20, space="buy")

    # === Entry Threshold Parameters ===
    bb_touch_threshold = RealParameter(0.95, 1.0, default=0.99, space="buy")
    bb_upper_threshold = RealParameter(1.0, 1.05, default=1.01, space="sell")

    # === Slippage Protection ===
    max_spread_pct = DecimalParameter(0.003, 0.01, default=0.005, space="sell")
    max_atr_pct = DecimalParameter(0.008, 0.02, default=0.012, space="sell")

    def leverage(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """
        Set leverage to 5x for all trades.
        """
        return 5.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate all indicators required for the strategy.
        """
        # === ADX Series (Regime Detection) ===
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.adx_period.value)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.adx_period.value)

        # === ATR (Volatility & Dynamic Stop Loss) ===
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_length.value)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # === Bollinger Bands ===
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe),
            window=self.bb_length.value,
            stds=self.bb_std.value,
        )
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]

        # BB Width (Normalized Volatility)
        dataframe["bb_width"] = (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe[
            "bb_middleband"
        ]

        # BB %B (Price Position)
        dataframe["bb_pct"] = (dataframe["close"] - dataframe["bb_lowerband"]) / (
            dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        )

        # === RSI ===
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_length.value)

        # === EMA Series (Trend Direction) ===
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_length.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_length.value)

        # EMA Alignment (Trend direction confirmation)
        dataframe["ema_aligned"] = dataframe["ema_fast"] > dataframe["ema_slow"]

        # EMA Slope (Trend momentum)
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # === Volume MA ===
        dataframe["volume_ma"] = ta.SMA(
            dataframe,
            timeperiod=self.volume_ma_length.value,
            price="volume",
        )

        # === Regime Classification ===
        # Regime 2 (Strong Trend): ADX > strong_threshold AND BB Width > threshold
        dataframe["regime_strong"] = (dataframe["adx"] > self.adx_strong_threshold.value) & (
            dataframe["bb_width"] > self.bb_width_threshold.value
        )

        # Regime 0 (Choppy): ADX < weak_threshold AND BB Width < threshold
        dataframe["regime_choppy"] = (dataframe["adx"] < self.adx_weak_threshold.value) & (
            dataframe["bb_width"] < self.bb_width_threshold.value
        )

        # Regime 1 (Transition): Between choppy and strong
        dataframe["regime_transition"] = ~dataframe["regime_strong"] & ~dataframe["regime_choppy"]

        # Trend Direction
        dataframe["bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        # ADX Rising (Momentum building)
        dataframe["adx_rising"] = dataframe["adx"] > dataframe["adx"].shift(2)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate entry signals based on market regime.
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # === Regime 0 (Choppy): Mean Reversion Entry ===
        # Long: Price touches BB lower AND RSI oversold AND bullish candle
        cond_mr_long = (
            (dataframe["close"] < dataframe["bb_lowerband"] * self.bb_touch_threshold.value)
            & (dataframe["rsi"] < self.rsi_oversold.value)
            & (dataframe["close"] > dataframe["open"])  # Bullish candle
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        # Short: Price touches BB upper AND RSI overbought AND bearish candle
        cond_mr_short = (
            (dataframe["close"] > dataframe["bb_upperband"] * self.bb_upper_threshold.value)
            & (dataframe["rsi"] > self.rsi_overbought.value)
            & (dataframe["close"] < dataframe["open"])  # Bearish candle
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        # === Regime 2 (Strong Trend): Trend Following Entry ===
        # Long: EMA aligned, price above BB middle, ADX strong, bullish
        cond_tf_long = (
            dataframe["regime_strong"]
            & dataframe["bullish"]
            & dataframe["ema_aligned"]
            & dataframe["ema_rising"]
            & (dataframe["close"] > dataframe["bb_middleband"])
        )

        # Short: EMA aligned (inverted), price below BB middle, ADX strong, bearish
        cond_tf_short = (
            dataframe["regime_strong"]
            & dataframe["bearish"]
            & ~dataframe["ema_aligned"]
            & (dataframe["close"] < dataframe["bb_middleband"])
        )

        # === Regime 1 (Transition): Breakout Entry ===
        # Long breakout: Price above BB upper with volume surge
        cond_bo_long = (
            dataframe["regime_transition"]
            & (dataframe["close"] > dataframe["bb_upperband"])
            & (dataframe["volume"] > dataframe["volume_ma"] * 1.5)
            & dataframe["adx_rising"]
            & dataframe["bullish"]
        )

        # Short breakout: Price below BB lower with volume surge
        cond_bo_short = (
            dataframe["regime_transition"]
            & (dataframe["close"] < dataframe["bb_lowerband"])
            & (dataframe["volume"] > dataframe["volume_ma"] * 1.5)
            & dataframe["adx_rising"]
            & dataframe["bearish"]
        )

        # === Combine entries based on regime priority ===
        # For Long: Prefer TF in strong trend, MR in choppy, BO in transition
        long_conditions = cond_tf_long | cond_mr_long | cond_bo_long
        short_conditions = cond_tf_short | cond_mr_short | cond_bo_short

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate exit signals.
        Exit signals are primarily handled by ROI and custom_stoploss.
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float:
        """
        Custom dynamic stoploss using ATR multiplier.
        Returns the stoploss percentage relative to entry price.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        # Calculate stoploss distance based on ATR
        stoploss_distance = (atr * self.atr_multiplier.value) / current_rate
        return -stoploss_distance

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> bool:
        """
        Confirm trade entry with slippage and volatility checks.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return False

        last_candle = dataframe.iloc[-1]

        # Check spread (high spread = high slippage risk)
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > self.max_spread_pct.value:
            return False

        # Check ATR volatility
        atr_pct = last_candle["atr_pct"]
        if atr_pct > self.max_atr_pct.value:
            return False

        return True

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        """
        Custom exit logic for additional take profit or stop management.
        """
        # Could add partial exit logic here if needed
        return None

    # === Hyperopt Space Configuration ===
    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "lookback_period_candles": 60,
                "stop_duration_candles": 10,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 60,
                "trade_limit": 20,
                "stop_duration_candles": 30,
                "max_allowed_drawdown": 0.15,
            },
        ]
