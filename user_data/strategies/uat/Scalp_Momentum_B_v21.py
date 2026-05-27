"""
Scalp_Momentum_B_v21 - Pullback Entry
======================================
Core: EMA trend + RSI + volume + price pullback to EMA
Exit: Tight trailing / ATR stop
Timeframe: 5m

Key insight from v17-v20:
- Trailing stop is the money maker (100% win rate when triggered)
- Hard stops are the killer (-2.5% avg)
- Solution: Enter on PULLBACK to EMA, not on breakout
- Pullback entry = better risk/reward (closer stop, same target)
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v21(IStrategy):
    # Fixed parameters
    stoploss = -0.015  # 1.5% hard stop (tighter because entry is better)
    minimal_roi = {
        "1": 0.004,  # 0.4% after 5 min
        "2": 0.007,  # 0.7% after 10 min
        "4": 0.010,  # 1.0% after 20 min
        "8": 0.015,  # 1.5% after 40 min
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.002  # +0.2% trailing
    trailing_stop_positive_offset = 0.004  # Activate at +0.4%
    trailing_only_offset_is_reached = True

    # Parameters
    ema_fast = 8
    ema_slow = 21
    ema_trend = 50
    rsi_period = 7
    rsi_min = 30
    rsi_max = 65  # Lower max = avoid overbought
    volume_mult = 0.8
    atr_period = 14
    atr_mult = 1.2

    # Pullback: price was above EMA_fast, now within 0.3% below it
    pullback_pct = 0.003

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # Pullback conditions
        dataframe["above_ema_prev"] = dataframe["close"].shift(1) > dataframe["ema_fast"].shift(1)
        dataframe["near_ema_now"] = (
            dataframe["close"] >= dataframe["ema_fast"] * (1 - self.pullback_pct)
        ) & (dataframe["close"] <= dataframe["ema_fast"] * (1 + self.pullback_pct))
        dataframe["pullback"] = dataframe["above_ema_prev"] & dataframe["near_ema_now"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2 = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_pullback = dataframe["pullback"]  # Price pulling back to EMA
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        dataframe["enter_long"] = (
            cond_trend & cond_trend2 & cond_pullback & cond_rsi & cond_volume
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
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return -0.015

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]
        atr_stop = -(atr * self.atr_mult / current_rate)

        return max(-0.01, min(-0.025, atr_stop))

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"
        return None
