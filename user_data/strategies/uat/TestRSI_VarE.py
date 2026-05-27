from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


# Variant E: Combine RSI with Gann Sq9 logic from 8HVjvV3B
class TestRSI_VarE(IStrategy):
    rsi_period = 14
    rsi_entry = 30
    rsi_exit = 70

    minimal_roi = {"0": 0.05}
    stoploss = -0.05
    timeframe = "1h"
    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    exchange = "binance"
    can_short = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=self.rsi_period)
        # Gann Sq9 from 8HVjvV3B
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["sess_high"] = dataframe["high"].rolling(window=24).max()
        dataframe["sess_low"] = dataframe["low"].rolling(window=24).min()
        dataframe["sq9_base"] = (dataframe["sess_high"] + dataframe["sess_low"]) / 2
        dataframe["tol"] = dataframe["atr"] * 0.3
        sqrt_base = np.sqrt(dataframe["sq9_base"])
        dataframe["r1"] = (sqrt_base + 0.25) ** 2
        dataframe["s1"] = (sqrt_base - 0.25) ** 2
        dataframe["near_res"] = np.abs(dataframe["close"] - dataframe["r1"]) < dataframe["tol"]
        dataframe["near_sup"] = np.abs(dataframe["close"] - dataframe["s1"]) < dataframe["tol"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prev = dataframe["rsi"].shift(1)
        curr = dataframe["rsi"]
        # Long: RSI cross up + near support
        dataframe.loc[
            (prev < self.rsi_entry) & (curr >= self.rsi_entry) & dataframe["near_sup"], "enter_long"
        ] = 1
        # Short: RSI cross down + near resistance
        dataframe.loc[
            (prev > self.rsi_exit) & (curr <= self.rsi_exit) & dataframe["near_res"], "enter_short"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
