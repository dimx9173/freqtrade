"""
Scalp_Momentum_B_v33 - Simplified Volatility Breakout Strategy
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v33(IStrategy):
    # ========== Core Parameters ==========
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.004
    trailing_stop_positive_offset = 0.006
    trailing_only_offset_is_reached = True
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = False  # Changed to False to avoid cache issues

    # ========== Volatility Breakout Parameters ==========
    donchian_period = 12
    atr_period = 14
    keltner_ema_period = 20
    keltner_multiplier = 2.0
    trail_multiplier = 2.0
    volume_ratio_min = 1.0  # Removed: was 1.2, now no volume filter
    bb_width_min = 0.01  # Relaxed from 0.03 to 0.01 (1%)

    # ATR range filter (relaxed further)
    max_atr_pct = 0.20  # 20% max ATR (was 10%)
    min_atr_pct = 0.0005  # 0.05% min ATR (was 0.1%)

    # Spread filter (relaxed)
    max_spread_pct = 0.10  # 10% max spread (was 5%)

    # ========== ROI Settings ==========
    minimal_roi = {
        "0": 0.003,
        "5": 0.006,
        "10": 0.010,
        "15": 0.015,
    }

    # ========== Indicators ==========
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # === Donchian Channel (Price Breakout) ===
        dataframe["dc_high"] = dataframe["high"].rolling(window=self.donchian_period).max()
        dataframe["dc_low"] = dataframe["low"].rolling(window=self.donchian_period).min()
        dataframe["dc_mid"] = (dataframe["dc_high"] + dataframe["dc_low"]) / 2

        # === Keltner Channel (ATR-based) ===
        dataframe["keltner_ema"] = ta.EMA(dataframe, timeperiod=self.keltner_ema_period)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe["keltner_upper"] = (
            dataframe["keltner_ema"] + dataframe["atr"] * self.keltner_multiplier
        )
        dataframe["keltner_lower"] = (
            dataframe["keltner_ema"] - dataframe["atr"] * self.keltner_multiplier
        )

        # === ATR Expansion Detection ===
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["atr_sma"] = dataframe["atr"].rolling(window=10).mean()
        dataframe["atr_expansion"] = dataframe["atr"] > dataframe["atr_sma"]

        # === Bollinger Bands Width (Volatility Filter) ===
        close = dataframe["close"].values
        bb_upper, bb_middle, bb_lower = talib.BBANDS(close, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb_upper
        dataframe["bb_middle"] = bb_middle
        dataframe["bb_lower"] = bb_lower
        dataframe["bb_width"] = (bb_upper - bb_lower) / bb_middle

        # === Volume Ratio ===
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"]

        # === Spread (Slippage Protection) ===
        dataframe["spread"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]

        return dataframe

    # ========== Entry Trend ==========
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # === Filter Conditions ===
        # Simplified: Only keep essential filters
        cond_atr_range = (dataframe["atr_pct"] >= self.min_atr_pct) & (
            dataframe["atr_pct"] <= self.max_atr_pct
        )
        cond_spread = dataframe["spread"] < self.max_spread_pct
        # Removed: cond_volatility (bb_width), cond_vol_expansion (atr_expansion), cond_volume
        # Keep only: breakout + ATR range + spread

        # === Long Entry: Price breaks above Donchian high ===
        cond_breakout_up = dataframe["close"] > dataframe["dc_high"].shift(1)

        dataframe["enter_long"] = (cond_breakout_up & cond_atr_range & cond_spread).astype(int)

        # === Short Entry: Price breaks below Donchian low ===
        cond_breakout_down = dataframe["close"] < dataframe["dc_low"].shift(1)

        dataframe["enter_short"] = (cond_breakout_down & cond_atr_range & cond_spread).astype(int)

        return dataframe

    # ========== Exit Trend ==========
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        cond_reverse_long = dataframe["close"] < dataframe["dc_mid"]
        cond_reverse_short = dataframe["close"] > dataframe["dc_mid"]

        dataframe["exit_long"] = cond_reverse_long.astype(int)
        dataframe["exit_short"] = cond_reverse_short.astype(int)

        return dataframe

    # ========== Trade Confirmation ==========
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
        return True

    # ========== Custom Stoploss ==========
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

    # ========== Custom Exit ==========
    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target_1.5%"
        return None

    # ========== Pair_whitelist ==========
    def get_timeframe(self) -> str:
        return self.timeframe

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period": 60,
                "stop_duration_candles": 2,
                "trade_limit": 3,
                "required_profit": -0.01,
            },
            {
                "method": "LowProfitPairs",
                "lookback_period": 60,
                "trade_limit": 2,
                "min_profit": 0.005,
            },
        ]
