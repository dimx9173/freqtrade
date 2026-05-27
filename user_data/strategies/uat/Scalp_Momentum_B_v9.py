"""
Scalp_Momentum_B_v9 - Simple Momentum Scalping
===============================================
Core: EMA cross + RSI filter
Exit: ROI ladder / stoploss
Timeframe: 1m

Philosophy: Keep it stupid simple. Trend + momentum.
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v9(IStrategy):
    # Fixed parameters
    stoploss = -0.01
    minimal_roi = {
        "3": 0.006,
        "7": 0.010,
        "12": 0.015,
    }
    leverage = 5
    futures_leverage = True
    timeframe = "1m"
    process_only_new_candles = True

    # Parameters
    ema_fast = 5
    ema_slow = 15
    rsi_period = 7
    rsi_max = 60  # Not overbought
    rsi_min = 30  # Not oversold

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Simple: EMA5 > EMA15 (uptrend) + RSI 30-60 (healthy) + volume > avg + green candle
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= dataframe["volume_sma"]
        cond_green = dataframe["close"] > dataframe["open"]

        dataframe["enter_long"] = (cond_trend & cond_rsi & cond_volume & cond_green).astype(int)

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
        return -0.01

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"
        return None
