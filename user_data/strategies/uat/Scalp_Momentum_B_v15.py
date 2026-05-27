"""
Scalp_Momentum_B_v15 - ITG Scalper Inspired
=============================================
Core: EMA ribbon + RSI momentum + Bollinger squeeze
Exit: Tight ROI / Trailing / Time-based
Timeframe: 5m

ITG Scalper Philosophy:
- Enter on momentum burst (price crossing above EMA ribbon)
- Exit quickly (5-15 min target)
- Tight risk control (1-2% max loss)
- High frequency (10+ trades/day)
- Use Bollinger Bands squeeze as volatility filter
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v15(IStrategy):
    # Fixed parameters - TIGHT
    stoploss = -0.02  # 2% hard stop
    minimal_roi = {
        "1": 0.008,  # 0.8% after 1 candle (5 min) - aggressive
        "2": 0.012,  # 1.2% after 2 candles (10 min)
        "3": 0.015,  # 1.5% after 3 candles (15 min)
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop - tight
    trailing_stop = True
    trailing_stop_positive = 0.003  # +0.3% trailing
    trailing_stop_positive_offset = 0.008  # Activate at +0.8%
    trailing_only_offset_is_reached = True

    # Parameters
    ema_fast = 3  # Very fast
    ema_slow = 8  # Fast
    ema_trend = 20  # Trend context
    bb_period = 20
    bb_std = 2.0
    rsi_period = 7
    rsi_min = 40
    rsi_max = 70  # Allow more upside
    volume_mult = 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA Ribbon
        dataframe["ema_3"] = ta.EMA(dataframe, timeperiod=3)
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # Bollinger Bands
        bbands = ta.BBANDS(
            dataframe, timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        dataframe["bb_upper"] = bbands["upperband"]
        dataframe["bb_middle"] = bbands["middleband"]
        dataframe["bb_lower"] = bbands["lowerband"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe[
            "bb_middle"
        ]
        dataframe["bb_squeeze"] = dataframe["bb_width"] < 0.03  # Squeeze = low volatility

        # Volume
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # Momentum burst: price crossing above EMA ribbon
        dataframe["cross_above"] = (dataframe["close"] > dataframe["ema_3"]) & (
            dataframe["close"].shift(1) <= dataframe["ema_3"].shift(1)
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry: Momentum burst + trend aligned + not overbought + volume
        cond_trend = dataframe["ema_3"] > dataframe["ema_8"]  # Short-term uptrend
        cond_trend2 = dataframe["ema_8"] > dataframe["ema_20"]  # Medium-term uptrend
        cond_cross = dataframe["cross_above"]  # Price just crossed above EMA3
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_not_squeeze = ~dataframe["bb_squeeze"]  # Avoid low volatility (no movement)

        dataframe["enter_long"] = (
            cond_trend & cond_trend2 & cond_cross & cond_rsi & cond_volume & cond_not_squeeze
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
