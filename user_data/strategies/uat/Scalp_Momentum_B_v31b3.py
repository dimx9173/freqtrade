"""
Scalp_Momentum_B_v31b3 - Minimal Short Test
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class Scalp_Momentum_B_v31b3(IStrategy):
    stoploss = -0.02
    minimal_roi = {"1": 0.004}
    leverage = 5
    futures_leverage = True
    timeframe = "5m"

    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.004
    trailing_only_offset_is_reached = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=5)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=7)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long only - very simple
        dataframe["enter_long"] = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_slow"] > dataframe["ema_trend"])
            & (dataframe["rsi"] > 35)
            & (dataframe["rsi"] < 70)
        ).astype(int)

        # Short - minimal conditions
        dataframe["enter_short"] = (
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["ema_slow"] < dataframe["ema_trend"])
            & (dataframe["rsi"] > 55)
        ).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = False
        dataframe["exit_short"] = False
        return dataframe
