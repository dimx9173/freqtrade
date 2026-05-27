"""
Scalp_Momentum_B_v13 - Trailing Stop Profit Lock
=================================================
Core: EMA trend + RSI filter + ATR stop + Trailing stop
Exit: ROI ladder / ATR stop / Trailing stop
Timeframe: 5m

Changes from v12:
- Added trailing_stop: when profit > 1.5%, lock at +0.5%
- Tighter RSI: 40-60 (more conservative)
- Slower EMA: 8/20 (more reliable trend)
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v13(IStrategy):
    # Fixed parameters
    stoploss = -0.05
    minimal_roi = {
        "1": 0.005,
        "3": 0.010,
        "6": 0.015,
        "10": 0.020,
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop settings
    trailing_stop = True
    trailing_stop_positive = 0.005  # +0.5% trailing
    trailing_stop_positive_offset = 0.015  # Activate at +1.5%
    trailing_only_offset_is_reached = True

    # Parameters
    ema_fast = 8
    ema_slow = 20
    atr_period = 10
    atr_mult = 2.0
    rsi_period = 7
    rsi_min = 40
    rsi_max = 60
    volume_mult = 0.8

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_momentum = dataframe["close"] > dataframe["ema_fast"]
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        dataframe["enter_long"] = (cond_trend & cond_momentum & cond_rsi & cond_volume).astype(int)

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
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return -0.05

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]
        stop_distance = (atr * self.atr_mult) / entry
        return max(-stop_distance, -0.05)

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.02:
            return "profit_target"
        return None
