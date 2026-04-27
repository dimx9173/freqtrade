# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

"""
Adaptive_Scalp_v2 - Adaptive Market Regime Scalping Strategy
============================================================
Timeframe: 5m
Mode: Futures (long/short)
Leverage: 5x

Market Regime Detection:
- Regime 0 (Choppy): ADX < 20 -> Mean Reversion
- Regime 1 (Transition): ADX 20-25 -> Reduced position / Watch
- Regime 2 (Strong Trend): ADX > 25 -> Trend Following

Entry Logic:
- Long (Choppy): Close < BB_lower AND RSI < 35
- Long (Trend): EMA fast > slow AND Close > EMA fast AND ADX > 25
- Short: Inverse of long conditions

Exit Logic:
- ROI: Tiered take profit (3% -> 2% -> 1%)
- Stoploss: ATR-based dynamic stop loss
"""

import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IntParameter, IStrategy, RealParameter


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

    # === Bollinger Bands Parameters ===
    bb_length = IntParameter(10, 30, default=20, space="buy")
    bb_std = RealParameter(1.5, 3.0, default=2.0, space="buy")

    # === RSI Parameters ===
    rsi_length = IntParameter(10, 20, default=14, space="buy")
    rsi_oversold = IntParameter(20, 35, default=30, space="buy")
    rsi_overbought = IntParameter(65, 80, default=70, space="sell")

    # === ATR Parameters (Dynamic Stop Loss) ===
    atr_length = IntParameter(10, 20, default=14, space="sell")
    atr_multiplier = RealParameter(1.0, 2.0, default=1.5, space="sell")

    # === EMA Parameters (Trend Following) ===
    ema_fast_length = IntParameter(5, 15, default=9, space="buy")
    ema_slow_length = IntParameter(15, 30, default=21, space="buy")

    # === Volume MA Parameters ===
    volume_ma_length = IntParameter(15, 30, default=20, space="buy")

    # === Entry Threshold Parameters ===
    bb_touch_threshold = RealParameter(0.95, 1.0, default=0.99, space="buy")
    bb_upper_threshold = RealParameter(1.0, 1.05, default=1.01, space="sell")

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

        # BB %B (Price Position)
        bb_range = dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        dataframe["bb_pct"] = (dataframe["close"] - dataframe["bb_lowerband"]) / bb_range

        # === RSI ===
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_length.value)

        # === EMA Series (Trend Direction) ===
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_length.value)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_length.value)

        # EMA Alignment
        dataframe["ema_aligned_long"] = dataframe["ema_fast"] > dataframe["ema_slow"]
        dataframe["ema_aligned_short"] = dataframe["ema_fast"] < dataframe["ema_slow"]

        # === Volume MA ===
        dataframe["volume_ma"] = ta.SMA(
            dataframe,
            timeperiod=self.volume_ma_length.value,
            price="volume",
        )

        # === Regime Classification ===
        # Regime 2 (Strong Trend): ADX > strong_threshold
        dataframe["regime_strong"] = dataframe["adx"] > self.adx_strong_threshold.value

        # Regime 0 (Choppy): ADX < weak_threshold
        dataframe["regime_choppy"] = dataframe["adx"] < self.adx_weak_threshold.value

        # Regime 1 (Transition): Between choppy and strong
        dataframe["regime_transition"] = ~dataframe["regime_strong"] & ~dataframe["regime_choppy"]

        # Trend Direction
        dataframe["bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate entry signals based on market regime.
        ONLY enter when specific regime conditions are met (no OR mixing).
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # === Regime 0 (Choppy): Mean Reversion Entry ===
        # Long: Price below BB lower AND RSI oversold
        cond_mr_long = (
            dataframe["regime_choppy"]
            & (dataframe["close"] < dataframe["bb_lowerband"] * self.bb_touch_threshold.value)
            & (dataframe["rsi"] < self.rsi_oversold.value)
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        # Short: Price above BB upper AND RSI overbought
        cond_mr_short = (
            dataframe["regime_choppy"]
            & (dataframe["close"] > dataframe["bb_upperband"] * self.bb_upper_threshold.value)
            & (dataframe["rsi"] > self.rsi_overbought.value)
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        # === Regime 2 (Strong Trend): Trend Following Entry ===
        # Long: EMA aligned, price above fast EMA, ADX strong, bullish DI
        cond_tf_long = (
            dataframe["regime_strong"]
            & dataframe["bullish"]
            & dataframe["ema_aligned_long"]
            & (dataframe["close"] > dataframe["ema_fast"])
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        # Short: EMA aligned short, price below fast EMA, ADX strong, bearish DI
        cond_tf_short = (
            dataframe["regime_strong"]
            & dataframe["bearish"]
            & dataframe["ema_aligned_short"]
            & (dataframe["close"] < dataframe["ema_fast"])
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        # === Regime 1 (Transition): NO ENTRY ===
        # Transition regime is uncertain - do not trade

        # Apply entries
        dataframe.loc[cond_mr_long, "enter_long"] = 1
        dataframe.loc[cond_mr_short, "enter_short"] = 1
        dataframe.loc[cond_tf_long, "enter_long"] = 1
        dataframe.loc[cond_tf_short, "enter_short"] = 1

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
