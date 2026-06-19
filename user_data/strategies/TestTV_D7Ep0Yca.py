import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame


class TestTV_D7Ep0Yca(IStrategy):
    """
    RSI EMA Strategy - direction-agnostic (long + short).

    Pine Script logic (XWiseTrade):
      - Trend: EMA(20) vs EMA(50) crossover
      - Trigger: RSI(14) exit oversold/overbought
      - Regime (P0 fix): ADX > 20 + price vs EMA(200) macro filter
      - Long:  uptrend + RSI exit oversold + regime_long
      - Short: downtrend + RSI exit overbought + regime_short
      - Exit: EMA cross reversal
    """

    INTERFACE_VERSION = 3
    can_short = True
    timeframe = "1h"
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True
    minimal_roi = {"0": 0.10, "60": 0.05, "120": 0.02}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Trend EMAs (Pine: fastEma=20, slowEma=50)
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=50)

        # Macro regime EMA (P0 fix requirement #10)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        # RSI (Pine: rsiLen=14, rsiOS=30, rsiOB=70)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ATR (Pine: atrLen=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # ADX for trend-strength regime filter (P0 fix requirement #10)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Trend direction (Pine: upTrend = emaF > emaS, dnTrend = emaF < emaS)
        up_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        dn_trend = dataframe["ema_fast"] < dataframe["ema_slow"]

        # RSI triggers
        # Pine: rsiExitOS = ta.crossover(rsi, rsiOS) -> RSI crosses UP through 30
        rsi_exit_os = qtpylib.crossed_above(dataframe["rsi"], 30)
        # Pine: rsiExitOB = ta.crossunder(rsi, rsiOB) -> RSI crosses DOWN through 70
        rsi_exit_ob = qtpylib.crossed_below(dataframe["rsi"], 70)

        # Regime filter (P0 fix requirement #10): ADX trending + macro trend
        regime_long = (dataframe["adx"] > 20) & (dataframe["close"] > dataframe["ema200"])
        regime_short = (dataframe["adx"] > 20) & (dataframe["close"] < dataframe["ema200"])

        # LONG: uptrend + RSI exit oversold + regime_long
        long_cond = up_trend & rsi_exit_os & regime_long & (dataframe["volume"] > 0)
        dataframe.loc[long_cond, "enter_long"] = 1

        # SHORT: downtrend + RSI exit overbought + regime_short
        short_cond = dn_trend & rsi_exit_ob & regime_short & (dataframe["volume"] > 0)
        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Pine exit was ATR-based SL/TP via strategy.exit; freqtrade uses
        # stoploss + trailing_stop for that. Here we emit trend-reversal exits.

        # Exit long: EMA fast crosses below slow (trend reversal)
        ema_cross_down = qtpylib.crossed_below(dataframe["ema_fast"], dataframe["ema_slow"])
        dataframe.loc[ema_cross_down & (dataframe["volume"] > 0), "exit_long"] = 1

        # Exit short: EMA fast crosses above slow (trend reversal)
        ema_cross_up = qtpylib.crossed_above(dataframe["ema_fast"], dataframe["ema_slow"])
        dataframe.loc[ema_cross_up & (dataframe["volume"] > 0), "exit_short"] = 1

        return dataframe
