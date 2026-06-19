# pragma pylint: disable=missing-docstring,invalid-name
import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy


class SimpleLong(IStrategy):
    stoploss = -0.03
    timeframe = "5m"

    minimal_roi = {
        "0": 0.015,
        "30": 0.01,
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        sma20 = dataframe["close"].rolling(window=20).mean()
        std20 = dataframe["close"].rolling(window=20).std()
        dataframe["bb_upper"] = sma20 + (2.0 * std20)
        dataframe["bb_middle"] = sma20
        dataframe["bb_lower"] = sma20 - (2.0 * std20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = "none"

        long_cond = (
            (dataframe["close"] <= dataframe["bb_lower"] * 1.01)
            & (dataframe["rsi"] < 45)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[long_cond, "enter_tag"] = "bb_long"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0

        exit_cond = (dataframe["rsi"] > 65) | (dataframe["close"] >= dataframe["bb_upper"] * 0.99)
        dataframe.loc[exit_cond, "exit_long"] = 1

        return dataframe
