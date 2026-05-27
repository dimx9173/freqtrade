#!/usr/bin/env python3
"""
FreqTrade Strategy: RegimeAware_v2
Simple regime-adaptive strategy

Core insight from data analysis:
- In BULL (uptrend): RSI<30 -> 55% win rate, +0.17% avg 24h return
- In BEAR (downtrend): This strategy goes SHORT on RSI>65

Regime detection: Use simple 50 EMA direction on 5m
- If close > EMA50 for 10+ consecutive candles = BULL
- If close < EMA50 for 10+ consecutive candles = BEAR
- Otherwise = NEUTRAL (no trades)
"""

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade


class RegimeAware_v2(IStrategy):
    timeframe = "5m"
    can_short = True  # Keep shorts but be more selective

    # Conservative profit targets
    minimal_roi = {
        "0": 0.015,
        "60": 0.02,
    }
    stoploss = -0.012
    use_exit_signal = True
    trailing_stop = False

    RSI_PERIOD = 14
    EMA_PERIOD = 50
    REGIME_THRESHOLD = 16  # Very strict - 16 of last 20

    default_stake_amount = 0.95
    startup_candle_count = 100

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)
        dataframe["ema"] = ta.EMA(dataframe, timeperiod=self.EMA_PERIOD)

        # Regime: consecutive closes above/below EMA
        dataframe["above_ema"] = dataframe["close"] > dataframe["ema"]

        # Rolling count of consecutive above/below
        dataframe["above_count"] = dataframe["above_ema"].rolling(20).sum()
        dataframe["below_count"] = (1 - dataframe["above_ema"].astype(int)).rolling(20).sum()

        # Regime flags
        dataframe["is_bull"] = dataframe["above_count"] >= self.REGIME_THRESHOLD
        dataframe["is_bear"] = dataframe["below_count"] >= self.REGIME_THRESHOLD

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bull: Long on RSI oversold in uptrend
        bull_long = dataframe["is_bull"] & (dataframe["rsi"] < 30)

        # Bear: Short on RSI overbought in downtrend
        bear_short = dataframe["is_bear"] & (dataframe["rsi"] > 65)

        dataframe.loc[bull_long, "enter_long"] = 1
        dataframe.loc[bear_short, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit on RSI mean reversion
        dataframe.loc[dataframe["rsi"] > 55, "exit_long"] = 1
        dataframe.loc[dataframe["rsi"] < 45, "exit_short"] = 1
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
