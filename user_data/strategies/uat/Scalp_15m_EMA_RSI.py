"""
Scalp_15m_EMA_RSI - 15m時間框架策略
===================================
基於5m策略失敗的經驗，測試15m時間框架：
1. 進場：EMA多頭排列(5>12>20) + RSI 35-65
2. 出場：+1%止盈
3. 止損：-1%
4. 時間框架：15m

Timeframe: 15m
Backtest: 2025-01-01 ~ 2026-04-26
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
from datetime import datetime


class Scalp_15m_EMA_RSI(IStrategy):
    # === 止損止盈設定 ===
    stoploss = -0.01  # -1% 止損
    minimal_roi = {
        "0": 0.01  # +1% 止盈
    }

    futures_leverage = True
    timeframe = "15m"
    process_only_new_candles = True

    # === 移除trailing_stop ===
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

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """5x槓桿"""
        return 5.0

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
