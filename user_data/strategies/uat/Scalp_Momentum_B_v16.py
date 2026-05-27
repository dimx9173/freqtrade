"""
Scalp_Momentum_B_v16 - High Frequency Scalping
==============================================
Core: EMA trend + RSI momentum + volume burst
Exit: Tight ROI / Trailing / Time-based
Timeframe: 5m

Goal: Sharpe > 30, Calmar > 100
- High frequency (15+ trades/day)
- Tight stops (1.5%)
- Quick exits (5-15 min targets)
- No BB squeeze filter (too restrictive)
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v16(IStrategy):
    # Fixed parameters - AGGRESSIVE
    stoploss = -0.015  # 1.5% hard stop
    minimal_roi = {
        "1": 0.006,  # 0.6% after 1 candle (5 min)
        "2": 0.010,  # 1.0% after 2 candles (10 min)
        "3": 0.014,  # 1.4% after 3 candles (15 min)
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop - very tight
    trailing_stop = True
    trailing_stop_positive = 0.003  # +0.3% trailing
    trailing_stop_positive_offset = 0.006  # Activate at +0.6%
    trailing_only_offset_is_reached = True

    # Parameters
    ema_fast = 5
    ema_slow = 12
    ema_trend = 20
    rsi_period = 7
    rsi_min = 35
    rsi_max = 75  # Very permissive
    volume_mult = 0.7  # Low volume requirement

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # Price vs EMA position
        dataframe["above_fast"] = dataframe["close"] > dataframe["ema_fast"]
        dataframe["above_slow"] = dataframe["close"] > dataframe["ema_slow"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Very simple: EMA5 > EMA12 > EMA20 + price > EMA5 + RSI not extreme + any volume
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2 = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_momentum = dataframe["close"] > dataframe["ema_fast"]
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        dataframe["enter_long"] = (
            cond_trend & cond_trend2 & cond_momentum & cond_rsi & cond_volume
        ).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = False
        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade,
        entry: float,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        return -0.015

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.014:
            return "profit_target"
        return None
