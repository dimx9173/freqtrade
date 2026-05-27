"""
Scalp_EMA_RSI_Optimized_v1 - 止損止盈優化版策略
==============================================
優化重點：
1. 止損：-0.5%（5x槓桿下=-2.5%本金）
2. 止盈：+1%（5x槓桿下=+5%本金）
3. 移除trailing_stop，改用硬止盈
4. 進場：EMA多頭排列(5>12>20) + RSI 35-65

Timeframe: 5m
Backtest: 2025-01-01 ~ 2026-04-26
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_EMA_RSI_Optimized_v1(IStrategy):
    # === 止損止盈設定（優化版）===
    stoploss = -0.005  # -0.5% 止損（5x槓桿 = -2.5%本金）
    minimal_roi = {
        "0": 0.01  # +1% 止盈（5x槓桿 = +5%本金）
    }

    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # === 移除trailing_stop（改用硬止盈）===
    trailing_stop = False
    trailing_stop_positive = 0.0
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

    # EMA parameters
    ema_fast = 5
    ema_slow = 12
    ema_trend = 20

    # RSI parameters (35-65 range for momentum confirmation)
    rsi_period = 7
    rsi_min = 35
    rsi_max = 65

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA indicators
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)

        # EMA slope (rising)
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # RSI indicator
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

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

        # Entry: EMA alignment AND RSI confirmation
        dataframe["enter_long"] = (cond_ema_trend & cond_rsi).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No custom exit - rely on stoploss + minimal_roi
        dataframe["exit_long"] = False
        return dataframe
