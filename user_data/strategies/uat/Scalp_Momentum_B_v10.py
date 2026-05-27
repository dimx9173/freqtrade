"""
Scalp_Momentum_B_v10 - ATR-Based Dynamic Scalping
=================================================
Core: ATR trailing stop + EMA trend + volume
Exit: ATR-based stop / ROI ladder
Timeframe: 5m

Philosophy: Let the market breathe. ATR-based stops adapt to volatility.
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v10(IStrategy):
    # Fixed parameters
    stoploss = -0.03  # 3% hard stop
    minimal_roi = {
        "1": 0.005,  # 0.5% after 1 candle (5 min)
        "3": 0.010,  # 1.0% after 3 candles (15 min)
        "6": 0.015,  # 1.5% after 6 candles (30 min)
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Parameters
    ema_fast = 5  # Faster EMA
    ema_slow = 15  # Faster slow EMA
    atr_period = 10
    atr_mult = 1.0  # Tighter ATR stop
    volume_mult = 0.8

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # ATR stop level (for reference)
        dataframe["atr_stop"] = dataframe["close"] - (dataframe["atr"] * self.atr_mult)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry: EMA8 > EMA21 (uptrend) + close > EMA8 (momentum) + volume > avg
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_momentum = dataframe["close"] > dataframe["ema_fast"]
        cond_volume = dataframe["volume"] >= dataframe["volume_sma"]

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
        """
        ATR-based trailing stop - adaptive to volatility.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return -0.03

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        # Stop distance as percentage
        stop_distance = (atr * self.atr_mult) / entry
        # Cap at 3%
        return max(-stop_distance, -0.03)

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.02:
            return "profit_target"
        return None
