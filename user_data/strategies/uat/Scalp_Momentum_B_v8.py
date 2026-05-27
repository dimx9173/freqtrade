"""
Scalp_Momentum_B_v8 - Trend-Following Scalping
=============================================
Core: EMA pullback + RSI bounce + volume
Exit: 1% TP / 0.8% SL / 15min max
Timeframe: 1m

Philosophy: Follow the trend, scalp the pullbacks.
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v8(IStrategy):
    # Fixed parameters
    stoploss = -0.008  # 0.8% stoploss
    minimal_roi = {
        "2": 0.005,  # 0.5% after 2 min
        "5": 0.008,  # 0.8% after 5 min
        "10": 0.010,  # 1.0% after 10 min
        "15": 0.012,  # 1.2% after 15 min
    }
    leverage = 5
    futures_leverage = True
    timeframe = "1m"
    process_only_new_candles = True

    # Parameters
    ema_fast = 8
    ema_slow = 20
    rsi_period = 7
    rsi_entry_max = 45  # RSI must be below 45 (oversold bounce)
    rsi_entry_min = 20  # But not extremely oversold
    volume_mult = 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMAs
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # Trend direction
        dataframe["uptrend"] = dataframe["ema_fast"] > dataframe["ema_slow"]

        # Pullback: price below EMA_fast but above EMA_slow
        dataframe["pullback"] = (dataframe["close"] < dataframe["ema_fast"]) & (
            dataframe["close"] > dataframe["ema_slow"]
        )

        # Volume
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # Candle components
        dataframe["body"] = abs(dataframe["close"] - dataframe["open"])
        dataframe["body_pct"] = dataframe["body"] / dataframe["close"] * 100
        dataframe["green"] = dataframe["close"] > dataframe["open"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry conditions:
        # 1. Uptrend (EMA8 > EMA20)
        # 2. Pullback to EMA20 area (price < EMA8 but > EMA20)
        # 3. RSI between 20-45 (oversold bounce, not extreme)
        # 4. Green candle (momentum turning up)
        # 5. Volume >= average
        # 6. Body size reasonable

        cond_uptrend = dataframe["uptrend"]
        cond_pullback = dataframe["pullback"]
        cond_rsi = (dataframe["rsi"] >= self.rsi_entry_min) & (
            dataframe["rsi"] <= self.rsi_entry_max
        )
        cond_green = dataframe["green"]
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_body = dataframe["body_pct"] <= 0.3  # Not too big

        dataframe["enter_long"] = (
            cond_uptrend & cond_pullback & cond_rsi & cond_green & cond_volume & cond_body
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
        return -0.008

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.01:
            return "profit_target"
        return None
