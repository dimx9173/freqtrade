"""
Scalp_EMA_RSI_Combo - 雙指標組合測試：EMA + RSI
==============================================
組合策略：EMA多頭排列 + RSI 35-65動量確認
- Entry: EMA5 > EMA12 > EMA20 (多頭排列) AND RSI 35-65
- Exit: Trailing stop / ATR stop
Timeframe: 5m
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_EMA_RSI_Combo(IStrategy):
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

    # EMA parameters
    ema_fast = 5
    ema_slow = 12
    ema_trend = 20

    # RSI parameters (35-65 range for momentum confirmation)
    rsi_period = 7
    rsi_min = 35
    rsi_max = 65

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA indicators
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)

        # EMA slope (rising)
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # RSI indicator
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA multi-timeframe alignment: fast > slow > trend
        cond_ema_trend = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_slow"] > dataframe["ema_trend"])
            & dataframe["ema_rising"]
        )

        # RSI momentum confirmation: 35-65 range
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)

        # Entry: EMA alignment AND RSI confirmation
        dataframe["enter_long"] = (cond_ema_trend & cond_rsi).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = False
        return dataframe
