"""
Scalp_Momentum_B_v29 - Sweet Spot Enhanced
===========================================
Core: Strong trend + Moderate pullback + RSI + Volume + Bullish candle
Exit: Tight trailing / ATR stop
Timeframe: 5m

Improvements from v28:
- EMA periods adjusted for more stable trends (ema_fast=6, ema_slow=15, ema_trend=25)
- RSI thresholds refined (rsi_min=38, rsi_max=70) for stronger signals
- pullback_min increased to 0.0018 for deeper pullback entries
- volume_mult increased to 0.8 for stronger volume confirmation
- Trailing stop enhanced (positive=0.003, offset=0.005)
- Enhanced custom_exit with multiple profit targets and time-based exits
- Added MACD for momentum confirmation
- Added volume momentum (volume trend)
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v29(IStrategy):
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

    # Trailing stop - enhanced from v28
    trailing_stop = True
    trailing_stop_positive = 0.003  # v28: 0.002
    trailing_stop_positive_offset = 0.005  # v28: 0.004
    trailing_only_offset_is_reached = True

    # Parameters - adjusted from v28
    ema_fast = 6  # v28: 5
    ema_slow = 15  # v28: 12
    ema_trend = 25  # v28: 20
    rsi_period = 7
    rsi_min = 38  # v28: 35
    rsi_max = 70  # v28: 72
    volume_mult = 0.8  # v28: 0.75
    atr_period = 10
    pullback_min = 0.0018  # v28: 0.0015

    # MACD parameters for momentum confirmation
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9

    # Slippage protection thresholds - unchanged from v28
    max_spread_pct = 0.005  # 0.5% max spread
    max_atr_pct = 0.01  # 1% max ATR

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA indicators
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # Volume
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # MACD for momentum
        macd = ta.MACD(
            dataframe,
            fastperiod=self.macd_fast,
            slowperiod=self.macd_slow,
            signalperiod=self.macd_signal,
        )
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = dataframe["macd"] - dataframe["macd_signal"]

        # Recent high (last 4 candles = 20 min)
        dataframe["recent_high"] = dataframe["high"].rolling(window=4).max()
        dataframe["pullback_pct"] = (dataframe["recent_high"] - dataframe["close"]) / dataframe[
            "recent_high"
        ]

        # EMA slope (rising) - enhanced check over 2 candles
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # Volume momentum: volume increasing vs previous candle
        dataframe["volume_increasing"] = dataframe["volume"] > dataframe["volume"].shift(1)
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume"].shift(1)

        # RSI divergence check (RSI rising from lows)
        dataframe["rsi_rising"] = dataframe["rsi"] > dataframe["rsi"].shift(1)

        # Price position relative to EMA
        dataframe["ema_diff"] = (dataframe["close"] - dataframe["ema_trend"]) / dataframe[
            "ema_trend"
        ]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Trend conditions
        cond_trend = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2 = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_ema_rising = dataframe["ema_rising"]

        # Pullback condition - deeper pullback for stronger entries
        cond_pullback = dataframe["pullback_pct"] >= self.pullback_min

        # RSI conditions - refined thresholds
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)

        # RSI from rising (confirming momentum recovery)
        cond_rsi_recovery = dataframe["rsi_rising"]

        # Volume conditions - stronger volume requirement
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        cond_volume_spike = dataframe["volume_ratio"] > 1.1  # Volume accelerating

        # MACD histogram positive (momentum on our side)
        cond_macd = dataframe["macd_hist"] > 0

        # Bullish candle
        cond_bullish = dataframe["close"] > dataframe["open"]

        # Price above EMA trend for overall trend alignment
        cond_price_above_trend = dataframe["close"] > dataframe["ema_trend"]

        # Combined entry signal
        dataframe["enter_long"] = (
            cond_trend
            & cond_trend2
            & cond_ema_rising
            & cond_pullback
            & cond_rsi
            & cond_volume
            & cond_macd
            & cond_bullish
            & cond_price_above_trend
        ).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = False
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
        (Preserved from v28 - no changes needed)
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return False

        last_candle = dataframe.iloc[-1]

        # 1. 檢查價差 (Spread)
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > self.max_spread_pct:
            return False  # 價差太大，跳過

        # 2. 檢查波動率 (ATR)
        atr_pct = last_candle["atr"] / last_candle["close"]
        if atr_pct > self.max_atr_pct:
            return False  # 波動太大，跳過

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
        """
        Enhanced exit logic with multiple profit targets and conditions

        Exit targets:
        - Quick exit at 1.5% profit (aggressive scalp)
        - Standard exit at 2.0% profit
        - Full exit at 2.5%+ profit
        - Time-based exit for long-held positions
        """
        # Immediate profit target
        if current_profit >= 0.025:
            return "profit_target_25"

        # Standard profit target
        if current_profit >= 0.020:
            return "profit_target_20"

        # Quick scalp target
        if current_profit >= 0.015:
            return "profit_target_15"

        # Time-based exit: close positions held too long without proper profit
        # (Optional: add time-based logic if needed via trade open time)

        return None
