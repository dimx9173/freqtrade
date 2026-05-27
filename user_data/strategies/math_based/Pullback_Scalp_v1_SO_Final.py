# ADX18 + ROI5.5 - Best combination test
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import DecimalParameter, IStrategy


class Pullback_Scalp_v1_SO_Final(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {"0": 0.055, "360": 0.03, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")
    adx_threshold = DecimalParameter(15, 25, default=18, space="buy")

    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    def populate_indicators(self, dataframe, metadata):
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["at_ema"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["at_ema"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe
