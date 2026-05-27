"""
Scalp_EMA_RSI_ADX_Combo - 三指標組合測試：EMA + RSI + ADX
=========================================================
組合策略：EMA多頭排列 + RSI 35-65動量確認 + ADX > 25趨勢強度確認
- Entry: EMA5 > EMA12 > EMA20 (多頭排列) AND RSI 35-65 AND ADX > 25
- Exit: Trailing stop / ATR stop
Timeframe: 5m
Backtest: 12 months
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_EMA_RSI_ADX_Combo(IStrategy):
    # Fixed parameters
    stoploss = -0.02
    minimal_roi = {
        "1": 0.004,
        "2": 0.007,
        "4": 0.010,
        "8": 0.015,
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.004
    trailing_only_offset_is_reached = True

    # EMA parameters
    ema_fast = 5
    ema_slow = 12
    ema_trend = 20

    # RSI parameters (35-65 range for momentum confirmation)
    rsi_period = 7
    rsi_min = 35
    rsi_max = 65

    # ADX parameters (trend strength confirmation)
    adx_period = 14
    adx_threshold = 25  # ADX > 25 表示趨勢強度足夠

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA indicators
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)

        # EMA slope (rising)
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # RSI indicator
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # ADX indicator (trend strength)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_period)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.adx_period)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.adx_period)

        # ADX rising confirmation
        dataframe["adx_rising"] = dataframe["adx"] > dataframe["adx"].shift(2)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA multi-timeframe alignment: fast > slow > trend
        cond_ema_trend = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_slow"] > dataframe["ema_trend"])
            & dataframe["ema_rising"]
        )

        # RSI momentum confirmation: 35-65 range
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)

        # ADX trend strength confirmation: ADX > 25 and rising + DI > -DI
        cond_adx = (
            (dataframe["adx"] > self.adx_threshold)
            & dataframe["adx_rising"]
            & (dataframe["plus_di"] > dataframe["minus_di"])
        )

        # Entry: EMA alignment AND RSI confirmation AND ADX trend strength
        dataframe["enter_long"] = (cond_ema_trend & cond_rsi & cond_adx).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit on RSI overbought (exit signal) or ADX weakening
        cond_rsi_overbought = dataframe["rsi"] > 70
        cond_adx_weak = dataframe["adx"] < 20

        dataframe.loc[cond_rsi_overbought | cond_adx_weak, "exit_long"] = 1
        return dataframe
