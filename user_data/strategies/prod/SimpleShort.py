# pragma pylint: disable=missing-docstring,invalid-name
import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from freqtrade.optimize.space import Categorical, Real, Integer


class SimpleShort(IStrategy):
    stoploss = -0.04
    timeframe = "5m"

    minimal_roi = {
        "0": 0.02,
        "60": 0.01,
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
        dataframe["bb_lower"] = sma20 - (2.0 * std20)

        dataframe["ema_dist"] = (dataframe["ema_fast"] - dataframe["ema_slow"]) / dataframe["close"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["adx"] >= 25)
                & (dataframe["minus_di"] > dataframe["plus_di"])
                & (dataframe["rsi"] > 32)
                & (dataframe["rsi"] < 72)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["adx"] >= 25)
                & (dataframe["minus_di"] > dataframe["plus_di"])
                & (dataframe["rsi"] > 32)
                & (dataframe["rsi"] < 72)
                & (dataframe["volume"] > 0)
            ),
            "enter_short",
        ] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            ((dataframe["rsi"] > 70) | (dataframe["close"] < dataframe["bb_lower"])), "exit_long"
        ] = 1
        dataframe.loc[
            ((dataframe["rsi"] < 30) | (dataframe["close"] > dataframe["bb_upper"])), "exit_short"
        ] = 1
        return dataframe
