"""
Scalp_Momentum_B_v24 - ATR Channel Pullback
============================================
Core: ATR channel (like v10) + EMA trend + RSI
Exit: Tight trailing / ATR stop
Timeframe: 5m

Inspired by v10 (the only profitable version):
- ATR channel for dynamic support/resistance
- Enter near channel middle (not breakout)
- Tight trailing to lock small profits
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v24(IStrategy):
    # Fixed parameters
    stoploss = -0.02  # 2% hard stop
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

    # Parameters
    ema_fast = 8
    ema_slow = 21
    rsi_period = 7
    rsi_min = 35
    rsi_max = 70
    volume_mult = 0.8
    atr_period = 10
    atr_mult = 1.0  # Channel width multiplier

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # ATR Channel
        dataframe["channel_mid"] = dataframe["ema_fast"]
        dataframe["channel_upper"] = dataframe["channel_mid"] + (dataframe["atr"] * self.atr_mult)
        dataframe["channel_lower"] = dataframe["channel_mid"] - (dataframe["atr"] * self.atr_mult)

        # Position within channel (0 = lower, 1 = upper)
        dataframe["channel_pos"] = (dataframe["close"] - dataframe["channel_lower"]) / (
            dataframe["channel_upper"] - dataframe["channel_lower"]
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        # Enter in lower half of channel (pullback to support)
        cond_pullback = dataframe["channel_pos"] <= 0.5
        # But not too low (avoid falling knife)
        cond_not_too_low = dataframe["channel_pos"] >= 0.2

        dataframe["enter_long"] = (
            cond_trend & cond_rsi & cond_volume & cond_pullback & cond_not_too_low
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
        return -0.02

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"
        return None
