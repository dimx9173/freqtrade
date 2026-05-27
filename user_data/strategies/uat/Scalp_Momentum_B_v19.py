"""
Scalp_Momentum_B_v19 - Time-Based Exit
========================================
Core: EMA trend + RSI + volume
Exit: Tight trailing / Time-based emergency exit / ATR stop
Timeframe: 5m

Key insight from v18:
- Trailing stop: 321/321 profitable (+0.38% avg)
- Hard stoploss: 50 stops at -2.58% avg (avg duration 9:47)
- Problem: Trades that don't move immediately get stuck and hit big stop
- Solution: Time-based exit after 30 min if not profitable
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
from datetime import timedelta


class Scalp_Momentum_B_v19(IStrategy):
    # Fixed parameters
    stoploss = -0.02  # 2% hard stop
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
    atr_period = 14
    atr_mult = 1.5

    # Time-based exit
    max_hold_time = 30  # minutes
    emergency_exit_profit = -0.005  # -0.5% emergency exit

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
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
        # Time-based emergency exit
        trade_duration = current_time - trade.open_date_utc
        if trade_duration >= timedelta(minutes=self.max_hold_time):
            if current_profit < 0:
                # Force exit at -0.5% instead of waiting for -2% stop
                return -0.005

        # ATR-based dynamic stop
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return -0.02

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]
        atr_stop = -(atr * self.atr_mult / current_rate)

        # Cap between 1.5% and 2.5%
        return max(-0.015, min(-0.025, atr_stop))

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"

        # Time-based exit: if held > 30 min and not profitable, exit
        trade_duration = current_time - trade.open_date_utc
        if trade_duration >= timedelta(minutes=self.max_hold_time):
            if current_profit < 0:
                return "time_exit"

        return None
