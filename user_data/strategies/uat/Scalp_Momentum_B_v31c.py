"""
Scalp_Momentum_B_v31c - 3m Bidirectional Scalping + Pin Bar Detection
=====================================================================
v31 base: 1m bidirectional → need adjustment for 3m
v31c: 3m version with scaled parameters

Key adjustments for 3m vs 1m:
1. Larger pullback_min (3x since candle is 3x longer)
2. Slightly larger pin_bar_threshold
3. ATR period slightly longer for smoothing
4. Volume rolling window adjustment
5. recent_high/low window adjustment (was 4 candles = 4 min, now 4 candles = 12 min)
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v31c(IStrategy):
    # Fixed parameters
    stoploss = -0.015  # Tighter for scalping (same as v31)
    minimal_roi = {
        "1": 0.004,  # Slightly higher than 1m (0.003) since 3m moves more
        "3": 0.006,  # 3 candles
        "6": 0.010,  # 6 candles
        "12": 0.015,  # 12 candles
    }
    leverage = 5
    futures_leverage = True
    timeframe = "3m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.006
    trailing_only_offset_is_reached = True

    # Parameters - LONG (scaled for 3m from v31 1m values)
    ema_fast = 5  # Same candles, more time
    ema_slow = 12  # Same candles
    ema_trend = 20  # Same candles
    rsi_period = 8  # Slightly higher than 1m (was 7)
    rsi_min_long = 35
    rsi_max_long = 72
    rsi_min_short = 30
    rsi_max_short = 65
    volume_mult = 0.75
    atr_period = 14  # Slightly longer (was 10)
    pullback_min = 0.003  # 0.30% (was 0.001 for 1m, scaled 3x)

    # Pin bar parameters (scaled for 3m)
    pin_bar_threshold = 0.003  # 0.30% pin bar body vs wick (was 0.0015)
    pin_bar_min_wick = 1.5  # wick must be 1.5x body minimum

    # Slippage protection
    max_spread_pct = 0.006  # 0.6% max spread (higher for 3m)
    max_atr_pct = 0.010  # 1.0% max ATR (higher for 3m)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMAs
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # Volume
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # === LONG indicators ===
        # Recent high (last 4 candles = 12 min for 3m)
        dataframe["recent_high"] = dataframe["high"].rolling(window=4).max()
        dataframe["pullback_pct"] = (dataframe["recent_high"] - dataframe["close"]) / dataframe[
            "recent_high"
        ]
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # === SHORT indicators (mirror) ===
        # Recent low for short pullback
        dataframe["recent_low"] = dataframe["low"].rolling(window=4).min()
        dataframe["pullback_pct_short"] = (
            dataframe["close"] - dataframe["recent_low"]
        ) / dataframe["recent_low"]
        dataframe["ema_falling"] = dataframe["ema_fast"] < dataframe["ema_fast"].shift(2)

        # === Pin bar detection ===
        # Pin bar: small body, long wick in one direction
        # Bullish pin bar: lower wick >= 1.5x body, close near high
        body = abs(dataframe["close"] - dataframe["open"])
        upper_wick = dataframe["high"] - dataframe[["close", "open"]].max(axis=1)
        lower_wick = dataframe[["close", "open"]].min(axis=1) - dataframe["low"]

        # Bullish pin bar: lower wick dominates, body at top, close > open
        dataframe["pin_bar_bull"] = (
            (lower_wick >= body * self.pin_bar_min_wick)
            & (upper_wick <= body * 0.5)
            & (body > 0)
            & (dataframe["close"] > dataframe["open"])
        ).astype(int)

        # Bearish pin bar: upper wick dominates, body at bottom, close < open
        dataframe["pin_bar_bear"] = (
            (upper_wick >= body * self.pin_bar_min_wick)
            & (lower_wick <= body * 0.5)
            & (body > 0)
            & (dataframe["close"] < dataframe["open"])
        ).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ========== LONG entry ==========
        cond_trend_long = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2_long = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_ema_rising = dataframe["ema_rising"]
        cond_pullback = dataframe["pullback_pct"] >= self.pullback_min
        cond_rsi_long = (dataframe["rsi"] >= self.rsi_min_long) & (
            dataframe["rsi"] <= self.rsi_max_long
        )
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_bullish = dataframe["close"] > dataframe["open"]

        dataframe["enter_long"] = (
            cond_trend_long
            & cond_trend2_long
            & cond_ema_rising
            & cond_pullback
            & cond_rsi_long
            & cond_volume
            & cond_bullish
        ).astype(int)

        # ========== SHORT entry (mirror) ==========
        cond_trend_short = dataframe["ema_fast"] < dataframe["ema_slow"]
        cond_trend2_short = dataframe["ema_slow"] < dataframe["ema_trend"]
        cond_ema_falling = dataframe["ema_falling"]
        cond_pullback_short = dataframe["pullback_pct_short"] >= self.pullback_min
        cond_rsi_short = (dataframe["rsi"] >= self.rsi_min_short) & (
            dataframe["rsi"] <= self.rsi_max_short
        )
        cond_volume_short = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_bearish = dataframe["close"] < dataframe["open"]

        # Short entries prefer bearish pin bars
        cond_pin_bar_short = dataframe["pin_bar_bear"].astype(bool)

        dataframe["enter_short"] = (
            cond_trend_short
            & cond_trend2_short
            & cond_ema_falling
            & cond_pullback_short
            & cond_rsi_short
            & cond_volume_short
            & cond_bearish
            & cond_pin_bar_short
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
        """
        進場前確認：檢查價差和波動率，避免高滑價環境
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return False

        last_candle = dataframe.iloc[-1]

        # 1. 檢查價差 (Spread)
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > self.max_spread_pct:
            return False

        # 2. 檢查波動率 (ATR)
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
        return -0.015

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.012:
            return "profit_target"
        return None
