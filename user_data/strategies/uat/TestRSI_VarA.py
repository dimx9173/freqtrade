from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


# Variant A: RSI length=8, tighter stoploss (-0.05)
class TestRSI_VarA(IStrategy):
    rsi_period = 8
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
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prev = dataframe["rsi"].shift(1)
        curr = dataframe["rsi"]
        dataframe.loc[(prev < self.rsi_entry) & (curr >= self.rsi_entry), "enter_long"] = 1
        dataframe.loc[(prev > self.rsi_exit) & (curr <= self.rsi_exit), "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
