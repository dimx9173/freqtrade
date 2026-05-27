"""
Scalp_Momentum_B_v31b2 - Bearish Addition (Simplified)
=======================================================
Based on v28 (profitable, sweet spot)

Changes from v28:
+ Added short entry logic (5m timeframe)
+ Simplified short conditions for testing

Short entry conditions:
1. EMA bearish: ema_fast < ema_slow < ema_trend
2. RSI > 55 (rebound high point)
3. EMA falling
4. Bearish candle: close < open
5. Volume confirm
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v31b2(IStrategy):
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
    rsi_short_min = 55
    volume_mult = 0.75
    atr_period = 10
    pullback_min = 0.0015

    max_spread_pct = 0.005
    max_atr_pct = 0.01

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        dataframe["recent_high"] = dataframe["high"].rolling(window=4).max()
        dataframe["pullback_pct"] = (dataframe["recent_high"] - dataframe["close"]) / dataframe[
            "recent_high"
        ]

        dataframe["recent_low"] = dataframe["low"].rolling(window=4).min()
        dataframe["pullback_up_pct"] = (dataframe["close"] - dataframe["recent_low"]) / dataframe[
            "recent_low"
        ]

        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)
        dataframe["ema_falling"] = dataframe["ema_fast"] < dataframe["ema_fast"].shift(2)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === LONG ENTRY CONDITIONS (from v28) ===
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

        # === SHORT ENTRY CONDITIONS ===
        # EMA bearish
        cond_short_ema = (dataframe["ema_fast"] < dataframe["ema_slow"]) & (
            dataframe["ema_slow"] < dataframe["ema_trend"]
        )
        # RSI > 55
        cond_short_rsi = dataframe["rsi"] > self.rsi_short_min
        # EMA falling
        cond_ema_falling = dataframe["ema_falling"]
        # Bearish candle
        cond_bearish = dataframe["close"] < dataframe["open"]
        # Volume
        cond_short_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)

        # All conditions must be met
        dataframe["enter_short"] = (
            cond_short_ema & cond_short_rsi & cond_ema_falling & cond_bearish & cond_short_volume
        ).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = False
        dataframe["exit_short"] = False
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return False

        last_candle = dataframe.iloc[-1]
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > self.max_spread_pct:
            return False
        atr_pct = last_candle["atr"] / last_candle["close"]
        if atr_pct > self.max_atr_pct:
            return False
        return True

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
