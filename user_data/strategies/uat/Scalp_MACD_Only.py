"""
Scalp_MACD_Only - 單指標測試：MACD動量策略
==========================================
Core: MACD histogram direction + trend confirmation only
Timeframe: 5m

Purpose: 隔離測試MACD指標的盈利能力，移除所有其他指標干扰
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import pandas as pd
import numpy as np


class Scalp_MACD_Only(IStrategy):
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

    # MACD parameters (standard)
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9

    # MACD histogram thresholds
    hist_min = 0.0  # Require positive histogram
    hist_rising = True  # Require rising histogram (momentum building)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate MACD using close price directly
        close = dataframe["close"].values
        macd, signal, hist = ta.MACD(
            close,
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal,
        )

        dataframe["macd_val"] = macd
        dataframe["macd_sig"] = signal
        dataframe["macd_histo"] = hist

        # EMA for trend confirmation
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=20)

        # MACD histogram rising (current > previous)
        dataframe["hist_rising"] = dataframe["macd_histo"] > dataframe["macd_histo"].shift(1)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Trend: price above EMA trend line
        cond_trend = dataframe["close"] > dataframe["ema_trend"]

        # MACD histogram positive and rising
        cond_macd = (dataframe["macd_histo"] >= self.hist_min) & dataframe["hist_rising"].fillna(
            False
        )

        # MACD line above signal line (bullish alignment)
        cond_macd_bullish = dataframe["macd_val"] > dataframe["macd_sig"]

        dataframe["enter_long"] = (cond_trend & cond_macd & cond_macd_bullish).astype(int)

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
