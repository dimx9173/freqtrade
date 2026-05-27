"""
Scalp_Momentum_B_v18 - Precision Entry
========================================
Core: EMA trend + RSI + volume + price proximity to EMA
Exit: Tight trailing / ATR-based dynamic stop / Time limit
Timeframe: 5m

Key insight from v17:
- Trailing stop is profitable (250/250, avg +0.48%)
- Hard stoploss is the killer (40 stops at -3.08%)
- Solution: Tighten entry to EMA proximity + ATR-based stop
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v18(IStrategy):
    # Fixed parameters
    stoploss = -0.025  # 2.5% hard stop
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
    ema_proximity = 0.005  # Price within 0.5% of EMA_fast
    atr_period = 14
    atr_mult = 1.5  # ATR-based dynamic stop

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # EMA proximity: price within 0.5% of EMA_fast
        dataframe["ema_dist"] = (
            abs(dataframe["close"] - dataframe["ema_fast"]) / dataframe["ema_fast"]
        )
        dataframe["near_ema"] = dataframe["ema_dist"] <= self.ema_proximity

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2 = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_momentum = dataframe["close"] > dataframe["ema_fast"]
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_proximity = dataframe["near_ema"]  # Price close to EMA = good entry

        dataframe["enter_long"] = (
            cond_trend & cond_trend2 & cond_momentum & cond_rsi & cond_volume & cond_proximity
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
        # ATR-based dynamic stoploss
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return -0.025

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]
        atr_stop = -(atr * self.atr_mult / current_rate)

        # Cap between 1.5% and 3%
        return max(-0.015, min(-0.03, atr_stop))

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"
        return None
