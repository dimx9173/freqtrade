from freqtrade.strategy import IStrategy
import pandas as pd
import numpy as np
import talib.abstract as ta


class TestRSI(IStrategy):
    minimal_roi = {"0": 0.1}
    stoploss = -0.1
    timeframe = "5m"

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # RSI with different periods to see what values look like
        dataframe["rsi_8"] = ta.RSI(dataframe["close"], timeperiod=8)
        dataframe["rsi_14"] = ta.RSI(dataframe["close"], timeperiod=14)
        dataframe["rsi_20"] = ta.RSI(dataframe["close"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Just use RSI crossover - cross above 30 from below
        prev_rsi = dataframe["rsi_8"].shift(1)
        curr_rsi = dataframe["rsi_8"]

        # Entry: RSI crosses above 30 (from below)
        dataframe["enter_long"] = ((prev_rsi < 30) & (curr_rsi >= 30)).astype(bool)
        dataframe["enter_short"] = False
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Exit: RSI crosses below 70
        prev_rsi = dataframe["rsi_8"].shift(1)
        curr_rsi = dataframe["rsi_8"]
        dataframe["exit_long"] = ((prev_rsi > 70) & (curr_rsi <= 70)).astype(bool)
        dataframe["exit_short"] = False
        return dataframe
