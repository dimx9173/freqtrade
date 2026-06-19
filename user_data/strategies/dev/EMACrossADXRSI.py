#!/usr/bin/env python3
"""
FreqTrade Strategy: EMA_Cross_ADX_RSI
Pure Technical Indicator Strategy (NO FreqAI)
Best performing variant: Long Only

EMA (12/26) Crossover + ADX Trend Confirmation + RSI Filter
Designed for bull market conditions - long bias

Backtest Results on 2026-01-16 to 2026-04-30:
  - Return: +10.68%
  - vs V70 (-1.88%): +12.56% outperformance
  - Trades: 24
  - Win Rate: 58.3%
"""

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

# from freqtrade.data.converter import trade_util_to_df  # removed - not needed
import freqtrade.vendor.qtpylib as qtpylib


class EMACrossADXRSI(IStrategy):
    # Strategy parameters
    minimal_roi = {
        "0": 0.06,  # 6% profit target
    }

    timeframe = "15m"

    stoploss = -0.025  # -2.5% stop loss

    # Technical indicators
    EMA_FAST_PERIOD = 12
    EMA_SLOW_PERIOD = 26
    ADX_PERIOD = 14
    RSI_PERIOD = 14

    # Entry thresholds
    ADX_MIN = 25  # ADX must be above this to confirm trend
    RSI_MAX_LONG = 68  # RSI must be below this for long (not overbought)
    RSI_MIN_LONG = 38  # RSI must be above this (not oversold)

    # Position sizing
    default_stake_amount = 0.95  # 95% of capital per trade

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.EMA_FAST_PERIOD)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.EMA_SLOW_PERIOD)

        # ADX
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.ADX_PERIOD)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.ADX_PERIOD)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.ADX_PERIOD)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bullish EMA crossover
        dataframe["ema_bullish_cross"] = (dataframe["ema_fast"] > dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) <= dataframe["ema_slow"].shift(1)
        )

        # Entry conditions
        conditions = (
            dataframe["ema_bullish_cross"]
            & (dataframe["adx"] >= self.ADX_MIN)
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["rsi"] >= self.RSI_MIN_LONG)
            & (dataframe["rsi"] <= self.RSI_MAX_LONG)
        )

        dataframe.loc[conditions, "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA reversal (fast crosses below slow)
        dataframe["ema_bearish_cross"] = (dataframe["ema_fast"] < dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"].shift(1)
        )

        # Exit conditions
        conditions = (
            dataframe["ema_bearish_cross"] | (dataframe["rsi"] > 75)  # RSI overbought
        )

        dataframe.loc[conditions, "exit_long"] = 1

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
        # Use 95% of available capital
        return self.default_stake_amount
