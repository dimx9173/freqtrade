"""
D3e Strategy with Exact Manual Logic Matching
Uses custom exit to implement exact TP/SL/Time exit rules from manual backtest
"""

import talib.abstract as ta
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade


class D3e_Strategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # D3e parameters (match manual script exactly)
    fast_ema = 21
    slow_ema = 50
    adx_threshold = 25
    rsi_low = 32
    rsi_high = 72

    # Exit parameters - match manual script exactly
    tp_pct = 0.06  # 6% profit target
    sl_pct = 0.015  # 1.5% stop loss
    max_bars = 24  # max holding time (15m candles)

    # Position sizing
    position_size = 0.50

    # Required IStrategy fields
    stoploss = -0.015  # Set to match our SL
    minimal_roi = {"0": 0.06}  # 6% initial ROI target
    trailing_stop = False
    use_exit_signal = True  # Enable to trigger custom_exit
    exit_profit_only = False
    process_only_new_candles = True
    startup_candle_count = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.fast_ema)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.slow_ema)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Track entry price for exit logic
        dataframe["entry_price"] = 0.0
        dataframe["entry_idx"] = 0

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # D3e short entry signal
        cond = (
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["adx"] >= self.adx_threshold)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["rsi"] > self.rsi_low)
            & (dataframe["rsi"] < self.rsi_high)
        )
        dataframe.loc[cond, "enter_short"] = 1

        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str:
        """
        Custom exit logic matching manual backtest:
        - TP: exit when profit >= tp_pct (6%)
        - SL: exit when profit <= -sl_pct (-1.5%)
        - TIME: exit when held >= max_bars (24 candles)
        """
        if trade.enter_tag == "short":
            # For short trades, current_profit is already calculated
            # Check time-based exit
            holding_minutes = (current_time - trade.open_date).total_seconds() / 60
            max_holding_minutes = self.max_bars * 15  # 15m candles

            if holding_minutes >= max_holding_minutes:
                return "time_exit"

            # Check TP (positive profit)
            if current_profit >= self.tp_pct:
                return "tp_exit"

            # Check SL (negative profit)
            if current_profit <= -self.sl_pct:
                return "sl_exit"

        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit signals based on our custom logic
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
