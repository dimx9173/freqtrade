"""
Scalp_Momentum_B_v6 - High Win-Rate Scalping
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


class Scalp_Momentum_B_v6(IStrategy):
    # Fixed parameters
    stoploss = -0.005
    minimal_roi = {
        "5": 0.005,
        "10": 0.008,
        "15": 0.010,
    }
    leverage = 5
    futures_leverage = True
    timeframe = "1m"
    process_only_new_candles = True

    # Parameters
    lookback = 20  # Recent low lookback
    body_min_pct = 0.05  # Min body size as % of price
    body_max_pct = 0.3  # Max body size (avoid big candles)
    lower_wick_ratio = 1.5  # Lower wick >= 1.5x body
    volume_mult = 1.0  # Volume >= SMA (no spike requirement)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Recent low
        dataframe["recent_low"] = (
            dataframe["low"].rolling(window=self.lookback, min_periods=1).min()
        )
        dataframe["dist_from_low"] = (
            (dataframe["close"] - dataframe["recent_low"]) / dataframe["recent_low"] * 100
        )

        # EMA for micro trend
        dataframe["ema_5"] = ta.EMA(dataframe, timeperiod=5)
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

        # Micro trend direction (5m context via resample)
        dataframe["trend_5m"] = dataframe["close"] > dataframe["ema_10"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Simple conditions:
        # 1. Price within 0.3% of recent low (near support)
        # 2. Green candle
        # 3. Lower wick >= 1.5x body (buying pressure)
        # 4. Body size reasonable (not too big, not too small)
        # 5. Volume normal or above average
        # 6. Micro trend: 5m EMA not strongly bearish

        cond_near_low = dataframe["dist_from_low"] <= 0.3
        cond_green = dataframe["green"]
        cond_wick = dataframe["lower_wick"] >= (dataframe["body"] * self.lower_wick_ratio)
        cond_body_min = dataframe["body_pct"] >= self.body_min_pct
        cond_body_max = dataframe["body_pct"] <= self.body_max_pct
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_trend = dataframe["trend_5m"] | (dataframe["close"] > dataframe["ema_10"])

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
        dataframe["exit_long"] = 0
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
        return -0.005

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.01:
            return "profit_target"
        return None
