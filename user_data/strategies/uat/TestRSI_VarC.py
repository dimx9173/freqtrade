from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


# Variant C: RSI + MACD confirmation filter
class TestRSI_VarC(IStrategy):
    rsi_period = 14
    rsi_entry = 30
    rsi_exit = 70

    minimal_roi = {"0": 0.1}
    stoploss = -0.1
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
        # MACD confirmation
        dataframe["macd"], dataframe["macdsignal"], dataframe["macdhist"] = ta.MACD(
            dataframe["close"], fastperiod=12, slowperiod=26, signalperiod=9
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prev = dataframe["rsi"].shift(1)
        curr = dataframe["rsi"]
        # MACD bullish: histogram positive or crossing up
        macd_bullish = dataframe["macd"] > dataframe["macdsignal"]
        dataframe.loc[
            (prev < self.rsi_entry) & (curr >= self.rsi_entry) & macd_bullish, "enter_long"
        ] = 1
        # Short: RSI overbought AND MACD bearish
        macd_bearish = dataframe["macd"] < dataframe["macdsignal"]
        dataframe.loc[
            (prev > self.rsi_exit) & (curr <= self.rsi_exit) & macd_bearish, "enter_short"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
