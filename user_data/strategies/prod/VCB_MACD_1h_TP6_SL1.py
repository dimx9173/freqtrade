"""
VCB_MACD_1h_TP6_SL1 - VCB + MACD with TP=6%, SL=1.0%
======================================================
TP6/SL1.0 variant: 勝率 29.4%, Ann +20.9%, DD -6.8%, Sortino 0.94
"""

import talib.abstract as ta
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from typing import Optional


class VCB_MACD_1h_TP6_SL1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"

    can_short = False
    can_long = True

    stoploss = -0.010

    minimal_roi = {
        "0": 0.06,
        "1440": 0.01,
    }

    max_exit_age = 24
    exit_profit_only = False

    use_exit_signal = True
    trailing_stop = False
    trailing_stop_positive = 0.0
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

    startup_candle_count = 200
    process_only_new_candles = False

    # ========== 策略參數 ==========
    atr_compression_threshold = 0.30
    vrank_threshold = 0.10
    atr_ma_period = 200
    vrank_period = 48
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"] * 100.0
        dataframe["atr_pct_ma"] = dataframe["atr_pct"].rolling(window=self.atr_ma_period).mean()
        dataframe["vrank"] = (
            dataframe["volume"]
            .rolling(window=self.vrank_period)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        )
        macd = ta.MACD(
            dataframe,
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal,
        )
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        dataframe["atr_filter"] = (
            dataframe["atr_pct"] < dataframe["atr_pct_ma"] * self.atr_compression_threshold
        )
        dataframe["vrank_filter"] = dataframe["vrank"] < self.vrank_threshold
        dataframe["macd_bullish"] = dataframe["macdhist"] > 0
        dataframe["vcb_entry"] = (
            dataframe["atr_filter"] & dataframe["vrank_filter"] & dataframe["macd_bullish"]
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["vcb_entry"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def leverage(
        self,
        pair: str,
        current_time: "datetime",
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> float:
        return 2.0
