#!/usr/bin/env python3
"""
BTC_TrendFollow_v1 — Pure Trend Following Strategy (Long Only)

Core Design:
  1. Trend Filter: SMA200 confirms the macro bullish trend
  2. Entry Signal: EMA12/26 golden cross (bullish momentum)
  3. Trend Strength: ADX > 30 filters out weak/ranging markets
  4. Risk Management: Fixed -3% stoploss + tiered ROI (5%/3%/1%)
  5. Only long positions — no shorting

Key Parameters:
  - Main TF: 15m
  - can_short: False
  - INTERFACE_VERSION: 3
  - Base stoploss: -0.03 (-3%)
  - ROI: 5% immediate / 3% after 2h / 1% after 4h

Reference: /home/brian/freqtrade/user_data/strategies/math_based/multi_tf_regime_v1/MultiTF_RegimeDetector_v1.py
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)


class BTC_TrendFollow_v1(IStrategy):
    """
    BTC_TrendFollow_v1 — Pure Trend Following Strategy (Long Only)

    Strategy type: trend_following
    Version: v1
    Author: Hermes Agent
    """

    INTERFACE_VERSION = 3

    # ── Basic Settings ───────────────────────────────────────────────
    timeframe: str = "15m"
    can_short: bool = False
    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    startup_candle_count: int = 250  # covers SMA200 + EMA26 warm-up
    stoploss: float = -0.03  # -3% hard stoploss

    # ── Exit Settings ────────────────────────────────────────────────
    minimal_roi: Dict[str, float] = {
        "0": 0.05,      # 5% immediate target
        "120": 0.03,    # 3% after 2 hours (120 × 15m)
        "240": 0.01,    # 1% after 4 hours (240 × 15m)
    }
    trailing_stop: bool = True
    trailing_stop_positive: float = 0.015
    trailing_stop_positive_offset: float = 0.025
    trailing_only_offset_is_reached: bool = True

    # ── Trend Filter Parameters ──────────────────────────────────────
    SMA_TREND: int = 200        # SMA period for macro trend
    EMA_FAST: int = 12          # Fast EMA for entry signal
    EMA_SLOW: int = 26          # Slow EMA for entry signal
    ADX_PERIOD: int = 14        # ADX lookback
    ADX_MIN: float = 30.0       # Minimum ADX for strong trend

    # ==================================================================
    #  populate_indicators
    # ==================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Compute all indicators:
          1. SMA200 — macro trend direction
          2. EMA12 / EMA26 — entry signal
          3. ADX — trend strength confirmation
          4. +DI / -DI — directional bias
        """
        # ── 1. Macro Trend Filter ─────────────────────────────────────
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=self.SMA_TREND)

        # ── 2. EMA Crossover ──────────────────────────────────────────
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.EMA_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.EMA_SLOW)

        # ── 3. Trend Strength ─────────────────────────────────────────
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.ADX_PERIOD)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.ADX_PERIOD)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.ADX_PERIOD)

        # ── 4. Helper: price above SMA200 ─────────────────────────────
        dataframe["above_sma200"] = dataframe["close"] > dataframe["sma200"]

        # ── 5. Helper: EMA golden cross ───────────────────────────────
        dataframe["ema_bull"] = dataframe["ema_fast"] > dataframe["ema_slow"]

        # ── 6. Helper: ADX strong trend ───────────────────────────────
        dataframe["adx_strong"] = dataframe["adx"] > self.ADX_MIN

        # ── 7. Helper: bullish DI bias ────────────────────────────────
        dataframe["di_bull"] = dataframe["plus_di"] > dataframe["minus_di"]

        return dataframe

    # ==================================================================
    #  populate_entry_trend
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Long entry conditions (pure trend following):
          1. Price > SMA200  (bullish macro trend)
          2. EMA12 > EMA26   (bullish momentum cross)
          3. ADX > 30        (strong trend confirmed)
          4. +DI > -DI       (bullish directional bias)
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        enter_long_conditions = (
            dataframe["above_sma200"]      # macro trend filter
            & dataframe["ema_bull"]        # EMA golden cross
            & dataframe["adx_strong"]      # strong trend
            & dataframe["di_bull"]         # bullish directional bias
        )

        dataframe.loc[enter_long_conditions, "enter_long"] = 1

        return dataframe

    # ==================================================================
    #  populate_exit_trend
    # ==================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit conditions (trend reversal signals):
          - EMA12 crosses below EMA26 (momentum reversal)
          - OR ADX drops below 25 (trend weakening)
          - OR -DI crosses above +DI (bearish directional shift)
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        exit_long_conditions = (
            (dataframe["ema_fast"] < dataframe["ema_slow"])   # EMA death cross
            | (dataframe["adx"] < 25.0)                       # trend weakening
            | (dataframe["minus_di"] > dataframe["plus_di"])  # bearish DI shift
        )

        dataframe.loc[exit_long_conditions, "exit_long"] = 1

        return dataframe
