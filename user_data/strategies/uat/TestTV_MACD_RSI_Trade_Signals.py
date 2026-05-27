# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Dict, Optional, Union
from functools import reduce

from freqtrade.strategy import IStrategy, Trade, informative, stoploss_from_open

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

"""
TestTV_MACD_RSI_Trade_Signals Strategy

Based on TradingView Pine Script "Oscillators" (MACD_RSI_Trade_Signals)

Core Logic (MACD mode with trend filter):
- Uses normalized MACD: 10000 * (fast_ma - slow_ma) / slow_ma
- EMA 200 trend filter for trade direction
- Buy: MACD crosses over signal, MACD below zero zone, price above EMA 200
- Sell: MACD crosses under signal, MACD above zero zone, price below EMA 200

Parameters:
- MACD Fast: 12, Slow: 26, Signal: 9
- Trend EMA: 200
- Stoploss: 2.5%
- ROI: Multiple targets
"""


class TestTV_MACD_RSI_Trade_Signals(IStrategy):
    INTERFACE_VERSION = 3
    can_short: bool = True  # Enable both long and short for futures

    # MACD parameters from Pine Script
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9
    ema_trend_period = 200

    # Risk management
    stoploss = -0.025  # 2.5% stop loss
    trailing_stop = False
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # ROI table - gradual profit targets
    minimal_roi = {
        "0": 0.08,  # 8% target
        "30": 0.05,  # After 30 min, target 5%
        "60": 0.03,  # After 1 hour, target 3%
        "120": 0.02,  # After 2 hours, target 2%
        "240": 0.01,  # After 4 hours, target 1%
    }

    # Timeframe
    timeframe = "1h"
    process_only_new_candles = True
    startup_candle_count: int = 200

    # Position adjustment disabled
    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate MACD indicators normalized like Pine Script

        Pine Script normalization:
        outmacd = 10000 * (fast_ma - slow_ma) / slow_ma
        """
        # EMA calculations
        dataframe["ema_fast"] = ta.EMA(dataframe["close"], timeperiod=self.macd_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe["close"], timeperiod=self.macd_slow)

        # Normalized MACD (like Pine Script)
        dataframe["macd_normalized"] = (
            10000 * (dataframe["ema_fast"] - dataframe["ema_slow"]) / dataframe["ema_slow"]
        )

        # Signal line (EMA of normalized MACD)
        dataframe["macd_signal"] = ta.EMA(dataframe["macd_normalized"], timeperiod=self.macd_signal)

        # Histogram
        dataframe["macd_hist"] = dataframe["macd_normalized"] - dataframe["macd_signal"]

        # Previous MACD values for "was below/above zero" condition
        dataframe["macd_prev"] = dataframe["macd_normalized"].shift(1)

        # Trend filter: EMA 200
        dataframe["ema_200"] = ta.EMA(dataframe["close"], timeperiod=self.ema_trend_period)

        # HLC3 for trend comparison (like Pine Script uses hlc3)
        dataframe["hlc3"] = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3

        # ATR for potential dynamic stoploss
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry signals based on Pine Script MACD logic

        MACDBuySignal conditions:
        - hlc3 > TrendEMA (price above 200 EMA)
        - MACD crosses over signal line
        - MACD < 0 or MACD[1] < 0 (in or was in negative zone)

        MACDSellSignal conditions:
        - hlc3 < TrendEMA (price below 200 EMA)
        - MACD crosses under signal line
        - MACD > 0 or MACD[1] > 0 (in or was in positive zone)
        """

        # Long entry: MACD crossover while in negative zone, price above trend
        long_conditions = [
            # Price above EMA 200 (trend filter)
            (dataframe["hlc3"] > dataframe["ema_200"]),
            # MACD crosses over signal (crossover)
            (
                (dataframe["macd_normalized"] > dataframe["macd_signal"])
                & (dataframe["macd_prev"] <= dataframe["macd_signal"].shift(1))
            ),
            # MACD in or was in negative zone (below zero)
            ((dataframe["macd_normalized"] < 0) | (dataframe["macd_prev"] < 0)),
            # Basic volume check
            (dataframe["volume"] > 0),
        ]

        dataframe.loc[reduce(lambda x, y: x & y, long_conditions), ["enter_long", "enter_tag"]] = (
            1,
            "macd_cross_up",
        )

        # Short entry: MACD crossunder while in positive zone, price below trend
        short_conditions = [
            # Price below EMA 200 (trend filter)
            (dataframe["hlc3"] < dataframe["ema_200"]),
            # MACD crosses under signal (crossunder)
            (
                (dataframe["macd_normalized"] < dataframe["macd_signal"])
                & (dataframe["macd_prev"] >= dataframe["macd_signal"].shift(1))
            ),
            # MACD in or was in positive zone (above zero)
            ((dataframe["macd_normalized"] > 0) | (dataframe["macd_prev"] > 0)),
            # Basic volume check
            (dataframe["volume"] > 0),
        ]

        dataframe.loc[
            reduce(lambda x, y: x & y, short_conditions), ["enter_short", "enter_tag"]
        ] = (1, "macd_cross_down")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals

        Exit on opposite MACD cross or trend reversal
        """

        # Exit long: MACD crosses under signal OR price drops below EMA 200
        exit_long_conditions = [
            # MACD crosses under signal
            (
                (dataframe["macd_normalized"] < dataframe["macd_signal"])
                & (dataframe["macd_prev"] >= dataframe["macd_signal"].shift(1))
            ),
            # Volume check
            (dataframe["volume"] > 0),
        ]

        dataframe.loc[
            reduce(lambda x, y: x & y, exit_long_conditions), ["exit_long", "exit_tag"]
        ] = (1, "macd_cross_down")

        # Exit short: MACD crosses over signal
        exit_short_conditions = [
            # MACD crosses over signal
            (
                (dataframe["macd_normalized"] > dataframe["macd_signal"])
                & (dataframe["macd_prev"] <= dataframe["macd_signal"].shift(1))
            ),
            # Volume check
            (dataframe["volume"] > 0),
        ]

        dataframe.loc[
            reduce(lambda x, y: x & y, exit_short_conditions), ["exit_short", "exit_tag"]
        ] = (1, "macd_cross_up")

        return dataframe
