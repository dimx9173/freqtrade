#!/usr/bin/env python3
"""
FreqTrade Strategy: RegimeAware_Minimal
Minimal regime-adaptive: only ROI + Stoploss, no custom exit

Strategy logic:
- Bull regime: Long on RSI<30, let ROI/stoploss handle exit
- Bear regime: Short on RSI>65, let ROI/stoploss handle exit

No custom exit signals to avoid interference with ROI mechanism.
"""

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade


class RegimeAware_Minimal(IStrategy):
    timeframe = "5m"
    can_short = True

    # 1.5:1 reward:risk
    minimal_roi = {
        "0": 0.015,  # 1.5% profit → exit
        "120": 0.01,  # After 2h, 1% → exit
    }
    stoploss = -0.01  # -1% hard stop

    RSI_PERIOD = 14
    EMA_PERIOD = 50

    default_stake_amount = 0.95
    startup_candle_count = 100
    use_exit_signal = False  # No custom exit signals

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)
        dataframe["ema"] = ta.EMA(dataframe, timeperiod=self.EMA_PERIOD)

        # Regime detection
        dataframe["above_ema"] = dataframe["close"] > dataframe["ema"]
        dataframe["above_count"] = dataframe["above_ema"].rolling(20).sum()
        dataframe["below_count"] = (1 - dataframe["above_ema"].astype(int)).rolling(20).sum()

        dataframe["is_bull"] = dataframe["above_count"] >= 10
        dataframe["is_bear"] = dataframe["below_count"] >= 10

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bull_long = dataframe["is_bull"] & (dataframe["rsi"] < 30)
        bear_short = dataframe["is_bear"] & (dataframe["rsi"] > 65)

        dataframe.loc[bull_long, "enter_long"] = 1
        dataframe.loc[bear_short, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No custom exits - let ROI/stoploss handle everything
        return dataframe

    def adjust_position_size(
        self,
        market,
        current_time,
        current_rate,
        propose_rate,
        current_balance,
        max_stake,
        open_trades,
        trade: Trade,
        entry_rate,
        current_time_since,
        current_dt,
        **kwargs,
    ) -> float:
        return self.default_stake_amount
