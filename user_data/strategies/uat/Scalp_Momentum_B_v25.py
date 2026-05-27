"""
Scalp_Momentum_B_v25 - High Precision Entry
============================================
Core: Strong trend + Deep pullback + RSI recovery + Volume confirmation
Exit: Tight trailing / ATR stop
Timeframe: 5m

Philosophy: Fewer trades, higher quality
- Only enter in strong uptrend
- Only enter after clear pullback + recovery
- Accept lower frequency for higher win rate

Goal: Reduce stop_loss count from ~20% to <10%
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v25(IStrategy):
    # Fixed parameters
    stoploss = -0.02
    minimal_roi = {
        "1": 0.004,
        "2": 0.007,
        "4": 0.010,
        "8": 0.015,
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.004
    trailing_only_offset_is_reached = True

    # Parameters
    ema_fast = 8
    ema_slow = 21
    ema_trend = 50
    rsi_period = 7
    rsi_min = 40  # Higher min = stronger momentum
    rsi_max = 60  # Lower max = avoid overbought
    volume_mult = 1.0  # Higher volume requirement
    atr_period = 10
    pullback_min = 0.005  # Minimum 0.5% pullback from recent high

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # Recent high (last 6 candles = 30 min)
        dataframe["recent_high"] = dataframe["high"].rolling(window=6).max()
        # Pullback depth from recent high
        dataframe["pullback_pct"] = (dataframe["recent_high"] - dataframe["close"]) / dataframe[
            "recent_high"
        ]
        # RSI recovery: RSI was higher 2 candles ago, now lower but still strong
        dataframe["rsi_prev"] = dataframe["rsi"].shift(2)
        dataframe["rsi_recovery"] = (dataframe["rsi_prev"] > 60) & (
            dataframe["rsi"] >= self.rsi_min
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Strong trend
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2 = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_trend_slope = dataframe["ema_fast"] > dataframe["ema_fast"].shift(3)  # Rising

        # Deep pullback (at least 0.5% from recent high)
        cond_pullback = dataframe["pullback_pct"] >= self.pullback_min

        # RSI recovery (was high, now cooled but still strong)
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_rsi_recovery = dataframe["rsi_recovery"]

        # Volume confirmation
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        # Price action: current candle bullish
        cond_bullish = dataframe["close"] > dataframe["open"]

        dataframe["enter_long"] = (
            cond_trend
            & cond_trend2
            & cond_trend_slope
            & cond_pullback
            & cond_rsi
            & cond_rsi_recovery
            & cond_volume
            & cond_bullish
        ).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = False
        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade,
        entry: float,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        return -0.02

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"
        return None
