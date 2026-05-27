"""
Scalp_Momentum_B_v28 - Sweet Spot
====================================
Core: Strong trend + Moderate pullback + RSI + Volume + Bullish candle
Exit: Tight trailing / ATR stop
Timeframe: 5m

From v26 (profitable, 1 trade/day) and v27 (unprofitable, 14 trades/day):
- Sweet spot: 3-6 trades/day, <15% stop rate, >85% win rate
- Key: Keep pullback_min at 0.3%, add bullish candle back
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v28(IStrategy):
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

    # Parameters
    ema_fast = 5
    ema_slow = 12
    ema_trend = 20
    rsi_period = 7
    rsi_min = 35
    rsi_max = 72
    volume_mult = 0.75
    atr_period = 10
    pullback_min = 0.0015  # 0.15% pullback

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # Recent high (last 4 candles = 20 min)
        dataframe["recent_high"] = dataframe["high"].rolling(window=4).max()
        dataframe["pullback_pct"] = (dataframe["recent_high"] - dataframe["close"]) / dataframe[
            "recent_high"
        ]

        # EMA slope (rising)
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2 = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_ema_rising = dataframe["ema_rising"]

        cond_pullback = dataframe["pullback_pct"] >= self.pullback_min

        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)

        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        cond_bullish = dataframe["close"] > dataframe["open"]

        dataframe["enter_long"] = (
            cond_trend
            & cond_trend2
            & cond_ema_rising
            & cond_pullback
            & cond_rsi
            & cond_volume
            & cond_bullish
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
