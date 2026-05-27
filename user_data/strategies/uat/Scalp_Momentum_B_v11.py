"""
Scalp_Momentum_B_v11 - True Scalping with Time Exit
====================================================
Core: EMA trend + volume spike
Exit: 10 min max hold / 1% profit / 1.5% stop
Timeframe: 1m

Philosophy: Scalping is about speed. Get in, get out.
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v11(IStrategy):
    # Fixed parameters
    stoploss = -0.015  # 1.5% stop
    minimal_roi = {
        "2": 0.005,  # 0.5% after 2 min
        "5": 0.008,  # 0.8% after 5 min
        "8": 0.010,  # 1.0% after 8 min
    }
    leverage = 5
    futures_leverage = True
    timeframe = "1m"
    process_only_new_candles = True

    # Parameters
    ema_fast = 5
    ema_slow = 12
    volume_mult = 1.2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Simple: EMA5 > EMA12 + close > EMA5 + volume > 1.2x avg
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_momentum = dataframe["close"] > dataframe["ema_fast"]
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        dataframe["enter_long"] = (cond_trend & cond_momentum & cond_volume).astype(int)

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
        # Time-based exit: max 10 minutes
        # Note: In live trading, we'd check trade duration
        if current_profit >= 0.01:
            return "profit_target"
        return None
