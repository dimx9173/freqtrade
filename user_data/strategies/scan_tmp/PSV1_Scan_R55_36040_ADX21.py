import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy


class PSV1_ATR_Scan_R55_36040_ADX21(IStrategy):
    """
    PSV1_ATR_Filter variant for parameter scanning
    ROI main: 5.5%, ROI 360: 4.0%, ADX: 21
    """

    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {"0": 0.0055, "360": 0.0040, "720": 0.023}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

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

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_ma"] = dataframe["atr"].rolling(window=20).mean()
        dataframe["atr_filter"] = dataframe["atr"] > dataframe["atr_ma"] * 0.9

        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > 21)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["rsi"] > 55)
            & (dataframe["rsi"] < 65)
            & dataframe["at_ema"]
            & (dataframe["close"] < dataframe["ema200"])
            & dataframe["atr_filter"]
        )

        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe
