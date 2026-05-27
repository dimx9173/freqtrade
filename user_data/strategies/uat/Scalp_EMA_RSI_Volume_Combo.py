"""
Scalp_EMA_RSI_Volume_Combo - 三指標組合測試：EMA + RSI + Volume
===============================================================
組合策略：EMA多頭排列 + RSI 35-65 + Volume > 1.2x均量確認
- Entry: EMA5 > EMA12 > EMA20 (多頭排列) AND RSI 35-65 AND Volume > 1.2x SMA20(Volume)
- Exit: Trailing stop / ATR stop
Timeframe: 5m
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_EMA_RSI_Volume_Combo(IStrategy):
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

    # Volume parameter (1.2x average volume confirmation)
    volume_sma_period = 20
    volume_multiplier = 1.2

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        # EMA indicators
        df["ema_fast"] = ta.EMA(df, timeperiod=self.ema_fast)
        df["ema_slow"] = ta.EMA(df, timeperiod=self.ema_slow)
        df["ema_trend"] = ta.EMA(df, timeperiod=self.ema_trend)

        # EMA slope (rising)
        df["ema_rising"] = df["ema_fast"] > df["ema_fast"].shift(2)

        # RSI indicator
        df["rsi"] = ta.RSI(df, timeperiod=self.rsi_period)

        # Volume indicators: SMA and volume confirmation
        df["volume_sma"] = ta.SMA(df, timeperiod=self.volume_sma_period, price="volume")
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        df["volume_confirmed"] = df["volume_ratio"] > self.volume_multiplier

        return df

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        # EMA multi-timeframe alignment: fast > slow > trend
        cond_ema_trend = (
            (df["ema_fast"] > df["ema_slow"])
            & (df["ema_slow"] > df["ema_trend"])
            & df["ema_rising"]
        )

        # RSI momentum confirmation: 35-65 range
        cond_rsi = (df["rsi"] >= self.rsi_min) & (df["rsi"] <= self.rsi_max)

        # Volume confirmation: volume > 1.2x average volume
        cond_volume = df["volume_confirmed"]

        # Entry: EMA alignment AND RSI confirmation AND Volume confirmation
        df["enter_long"] = (cond_ema_trend & cond_rsi & cond_volume).astype(int)

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["exit_long"] = False
        return df
