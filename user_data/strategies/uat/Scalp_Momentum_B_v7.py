"""
Scalp_Momentum_B_v7 - High Win-Rate Scalping
============================================
Core: Price near recent low + small bullish candle + volume
Exit: 1% TP / 0.5% SL / 15min max
Timeframe: 1m

Philosophy: Simple = Robust. Fewer conditions = higher win rate.
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v7(IStrategy):
    # Fixed parameters
    stoploss = -0.01  # 1% stoploss (wider for 1m noise)
    minimal_roi = {
        "3": 0.008,  # 0.8% after 3 min
        "7": 0.012,  # 1.2% after 7 min
        "12": 0.015,  # 1.5% after 12 min
    }
    leverage = 5
    futures_leverage = True
    timeframe = "1m"
    process_only_new_candles = True

    # Parameters
    lookback = 15  # Shorter lookback for faster reaction
    body_min_pct = 0.005  # Very small body allowed
    body_max_pct = 0.3  # Tighter max body
    lower_wick_ratio = 2.0  # Stronger wick requirement (better reversal signal)
    volume_mult = 1.0  # Volume >= average

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Recent low
        dataframe["recent_low"] = (
            dataframe["low"].rolling(window=self.lookback, min_periods=1).min()
        )
        dataframe["dist_from_low"] = (
            (dataframe["close"] - dataframe["recent_low"]) / dataframe["recent_low"] * 100
        )

        # EMA for micro trend
        dataframe["ema_10"] = ta.EMA(dataframe, timeperiod=10)

        # Candle components
        dataframe["body"] = abs(dataframe["close"] - dataframe["open"])
        dataframe["body_pct"] = dataframe["body"] / dataframe["close"] * 100
        dataframe["upper_wick"] = dataframe["high"] - np.maximum(
            dataframe["close"], dataframe["open"]
        )
        dataframe["lower_wick"] = (
            np.minimum(dataframe["close"], dataframe["open"]) - dataframe["low"]
        )
        dataframe["green"] = dataframe["close"] > dataframe["open"]

        # Volume
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Relaxed conditions:
        # 1. Price within 0.5% of recent low (near support)
        # 2. Green candle
        # 3. Lower wick >= 1.0x body (buying pressure)
        # 4. Body size reasonable
        # 5. Volume >= 80% of average
        # 6. Price above EMA10 (not in freefall)

        cond_near_low = dataframe["dist_from_low"] <= 1.0  # Within 1% of recent low
        cond_green = dataframe["green"]
        cond_wick = dataframe["lower_wick"] >= (dataframe["body"] * self.lower_wick_ratio)
        cond_body_min = dataframe["body_pct"] >= self.body_min_pct
        cond_body_max = dataframe["body_pct"] <= self.body_max_pct
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_trend = dataframe["close"] > dataframe["ema_10"]

        dataframe["enter_long"] = (
            cond_near_low
            & cond_green
            & cond_wick
            & cond_body_min
            & cond_body_max
            & cond_volume
            & cond_trend
        ).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Only exit on minimal_roi or stoploss
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
        return -0.01

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.01:
            return "profit_target"
        return None
