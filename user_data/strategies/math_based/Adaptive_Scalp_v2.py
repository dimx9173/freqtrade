# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

"""
Adaptive_Scalp_v2 - Trend-Following Scalping Strategy (15m)
==========================================================
Timeframe: 15m
Mode: Futures (long/short)
Leverage: 5x

Strategy Philosophy:
- Pure trend following ONLY (no mean reversion)
- Only enter when market regime is strong (Regime 2: ADX > 25)
- Let profits run in strong trends
- Tight stop loss for quick cut

Entry Conditions:
- EMA 9/21 crossover confirmation
- ADX > 25 (strong trend required)
- Price breakout of recent swing high/low
- Volume confirmation (> 1.5x MA)

Exit Logic:
- Tiered ROI: 8% -> 5% -> 3% -> 2%
- Trailing stop: 5% callback
- Stop loss: ATR x 1.0 (~2.5%)
- Risk:Reward target 1:3 (2.5% stop -> 8% profit)
"""

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy


class Adaptive_Scalp_v2(IStrategy):
    """
    Trend-Following Scalping Strategy v2
    Optimized for 15m timeframe with larger moves (5-10%)
    Only trades in strong trending markets (Regime 2)
    """

    # === Timeframe Settings ===
    timeframe = "15m"

    # === Futures / Short Settings ===
    can_short = True
    process_only_new_candles = True

    # === Stop Loss Settings ===
    stoploss = -0.025  # 2.5% max stop loss
    use_custom_stoploss = True

    # === ROI Settings (Tiered for larger moves) ===
    minimal_roi = {
        "0": 0.08,  # 8% at 0 minutes
        "30": 0.05,  # 5% after 30 minutes
        "60": 0.03,  # 3% after 60 minutes
        "120": 0.02,  # 2% after 120 minutes
    }

    # === Trailing Stop Settings ===
    trailing_stop = True
    trailing_stop_only_offset_is_reached = True
    trailing_stop_offset = 0.05  # 5% trailing stop
    trailing_positive_offset = 0.05

    # === ADX Parameters (Trend Detection) ===
    adx_period = 14
    adx_threshold = 25

    # === EMA Parameters (Trend Direction) ===
    ema_fast_period = 9
    ema_slow_period = 21

    # === Volume Parameters ===
    volume_ma_period = 20
    volume_multiplier = 1.5

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
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_period)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.adx_period)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.adx_period)

        # === ATR (Dynamic Stop Loss) ===
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.adx_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # === EMA Series (Trend Direction) ===
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_period)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_period)

        # EMA Crossover Signals
        dataframe["ema_cross_up"] = (dataframe["ema_fast"] > dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) <= dataframe["ema_slow"].shift(1)
        )
        dataframe["ema_cross_down"] = (dataframe["ema_fast"] < dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"].shift(1)
        )

        # EMA Alignment (trend direction)
        dataframe["ema_bullish"] = dataframe["ema_fast"] > dataframe["ema_slow"]
        dataframe["ema_bearish"] = dataframe["ema_fast"] < dataframe["ema_slow"]

        # === Volume MA ===
        dataframe["volume_ma"] = ta.SMA(
            dataframe,
            timeperiod=self.volume_ma_period,
            price="volume",
        )
        dataframe["volume_confirmed"] = dataframe["volume"] > (
            dataframe["volume_ma"] * self.volume_multiplier
        )

        # === Swing High/Low (Breakout Detection) ===
        # Lookback period for swing detection
        swing_window = 12  # ~3 hours on 15m chart

        dataframe["swing_high"] = dataframe["high"].rolling(window=swing_window).max().shift(1)
        dataframe["swing_low"] = dataframe["low"].rolling(window=swing_window).min().shift(1)

        # Price breakout signals
        dataframe["breakout_up"] = dataframe["close"] > dataframe["swing_high"]
        dataframe["breakout_down"] = dataframe["close"] < dataframe["swing_low"]

        # === Regime Classification ===
        # Regime 2 (Strong Trend): ADX > 25
        dataframe["regime_strong"] = dataframe["adx"] > self.adx_threshold

        # Trend Direction (DI based)
        dataframe["bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate entry signals based on pure trend following (Regime 2 ONLY).
        No mean reversion entries.
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # === Long Entry Conditions ===
        # 1. Strong trend regime (ADX > 25)
        # 2. EMA bullish alignment (fast > slow)
        # 3. EMA bullish crossover (recent)
        # 4. Price breakout above swing high
        # 5. Bullish DI confirmation
        # 6. Volume confirmation

        cond_long = (
            dataframe["regime_strong"]
            & dataframe["ema_bullish"]
            & dataframe["ema_cross_up"]
            & dataframe["breakout_up"]
            & dataframe["bullish"]
            & dataframe["volume_confirmed"]
        )

        # === Short Entry Conditions ===
        # 1. Strong trend regime (ADX > 25)
        # 2. EMA bearish alignment (fast < slow)
        # 3. EMA bearish crossover (recent)
        # 4. Price breakout below swing low
        # 5. Bearish DI confirmation
        # 6. Volume confirmation

        cond_short = (
            dataframe["regime_strong"]
            & dataframe["ema_bearish"]
            & dataframe["ema_cross_down"]
            & dataframe["breakout_down"]
            & dataframe["bearish"]
            & dataframe["volume_confirmed"]
        )

        # Apply entries
        dataframe.loc[cond_long, "enter_long"] = 1
        dataframe.loc[cond_short, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate exit signals.
        Exit signals handled primarily by ROI and custom_stoploss.
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
        Custom dynamic stoploss using ATR x 1.0.
        Tight stop for quick loss cut.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        # ATR-based stop distance (~2-3% depending on volatility)
        stoploss_distance = atr / current_rate
        return -stoploss_distance

    @property
    def protections(self):
        return [
            {
                "method": "CooldownPeriod",
                "lookback_period_candles": 30,
                "stop_duration_candles": 5,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 60,
                "trade_limit": 15,
                "stop_duration_candles": 20,
                "max_allowed_drawdown": 0.15,
            },
        ]
