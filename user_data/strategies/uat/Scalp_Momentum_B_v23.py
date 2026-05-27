"""
Scalp_Momentum_B_v23 - Tight Stop Experiment
=============================================
Core: EMA trend + RSI + volume
Exit: Tight trailing / Very tight hard stop / ATR stop
Timeframe: 5m

Key insight from v17:
- Trailing stop: 250/250 profitable (+0.48% avg)
- Hard stop: 40 stops at -3.08% avg
- Math: 250×0.48% = +120%, 40×3.08% = -123.2%, net = -3.2%
- If hard stop was -0.8%: 40×0.8% = -32%, net = +88%!
- Solution: Tighten hard stop to 0.8-1%
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v23(IStrategy):
    # Fixed parameters - VERY TIGHT
    stoploss = -0.008  # 0.8% hard stop
    minimal_roi = {
        "1": 0.004,  # 0.4% after 5 min
        "2": 0.007,  # 0.7% after 10 min
        "4": 0.010,  # 1.0% after 20 min
        "8": 0.015,  # 1.5% after 40 min
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.002  # +0.2% trailing
    trailing_stop_positive_offset = 0.004  # Activate at +0.4%
    trailing_only_offset_is_reached = True

    # Parameters
    ema_fast = 5
    ema_slow = 12
    ema_trend = 20
    rsi_period = 7
    rsi_min = 35
    rsi_max = 75
    volume_mult = 0.8

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
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
        return -0.008  # 0.8% hard stop

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"
        return None
