"""
Scalp_Momentum_B_v12 - RSI Filter + Wider ATR Stop
==================================================
Core: EMA trend + RSI momentum filter + ATR-based stop
Exit: ROI ladder / ATR stop
Timeframe: 5m

Changes from v10:
- Added RSI(7) filter: only enter when RSI 35-65 (avoid extreme)
- Wider ATR multiplier: 2.0 (was 1.0) for fewer stoploss hits
- Faster EMA: 5/12 (was 5/15)
- Relaxed volume requirement: 0.8x SMA
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v12(IStrategy):
    # Fixed parameters
    stoploss = -0.05  # Wide hard stop, actual is ATR-based
    minimal_roi = {
        "1": 0.005,  # 0.5% after 5 min
        "3": 0.010,  # 1.0% after 15 min
        "6": 0.015,  # 1.5% after 30 min
        "10": 0.020,  # 2.0% after 50 min
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Parameters
    ema_fast = 5
    ema_slow = 12
    atr_period = 10
    atr_mult = 2.0  # Wider stop = fewer whipsaws
    rsi_period = 7
    rsi_min = 35  # Avoid extremely oversold (might keep falling)
    rsi_max = 65  # Avoid overbought
    volume_mult = 0.8

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_momentum = dataframe["close"] > dataframe["ema_fast"]
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        dataframe["enter_long"] = (cond_trend & cond_momentum & cond_rsi & cond_volume).astype(int)

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
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return -0.05

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]
        stop_distance = (atr * self.atr_mult) / entry
        return max(-stop_distance, -0.05)

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.02:
            return "profit_target"
        return None
