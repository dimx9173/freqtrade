#!/usr/bin/env python3
"""
BTC_MeanReversion_v1 — Pure Mean-Reversion Strategy for BTC

Core Design:
  1. Entry: Only extreme oversold conditions
     - RSI < 25 (strict oversold)
     - Close touches or breaks below BB lower band (2.5 std)
  2. Exit:
     - Simple stop loss: -3%
     - ROI target: 3% / 2% / 1% (decaying by hold time)
     - Time exit: 12 hours max hold
  3. Only long positions (can_short = False)
  4. Timeframe: 15m

Key Parameters:
  - Main TF: 15m
  - can_short: False
  - stoploss: -0.03 (-3%)
  - minimal_roi: {"0": 0.03, "240": 0.02, "480": 0.01}
  - custom_exit: time_exit after 12 hours (720 × 15m bars)

Reference: /home/brian/freqtrade/user_data/strategies/math_based/multi_tf_regime_v1/MultiTF_RegimeDetector_v1.py
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class BTC_MeanReversion_v1(IStrategy):
    """
    BTC_MeanReversion_v1 — Pure Mean-Reversion Strategy

    Strategy type: test
    Version: v1
    Author: Hermes Agent
    """

    # ── Interface Version ────────────────────────────────────────────
    INTERFACE_VERSION = 3

    # ── Basic Settings ───────────────────────────────────────────────
    timeframe: str = "15m"
    can_short: bool = False
    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    startup_candle_count: int = 100  # covers BB period + RSI period

    # ── Stop Loss ────────────────────────────────────────────────────
    stoploss: float = -0.03  # -3% hard stop loss

    # ── ROI Targets ──────────────────────────────────────────────────
    # 0 bars (immediate): 3%
    # 240 bars (6 hours): 2%
    # 480 bars (12 hours): 1%
    minimal_roi: dict = {
        "0": 0.03,
        "240": 0.02,
        "480": 0.01,
    }

    # ── Trailing Stop (disabled for clean mean-reversion) ────────────
    trailing_stop: bool = False

    # ── Indicator Parameters ─────────────────────────────────────────
    BB_PERIOD: int = 20
    BB_STD: float = 2.5  # 2.5 standard deviations for extreme conditions
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 25.0  # strict oversold threshold

    # ── Time Exit ────────────────────────────────────────────────────
    TIME_EXIT_MINUTES: int = 720  # 12 hours = 720 minutes

    # ==================================================================
    #  populate_indicators
    # ==================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Compute indicators:
          1. Bollinger Bands (20, 2.5)
          2. RSI (14)
        """
        # ── Bollinger Bands ───────────────────────────────────────────
        bb = ta.BBANDS(
            dataframe,
            timeperiod=self.BB_PERIOD,
            nbdevup=self.BB_STD,
            nbdevdn=self.BB_STD,
            matype=0,
        )
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_upper"] = bb["upperband"]

        # ── RSI ───────────────────────────────────────────────────────
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)

        return dataframe

    # ==================================================================
    #  populate_entry_trend
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic (long only):
          - RSI < 25 (strict oversold)
          - Close <= BB lower band (touches or breaks below)
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        long_condition = (
            (dataframe["rsi"] < self.RSI_OVERSOLD)
            & (dataframe["close"] <= dataframe["bb_lower"])
        )

        dataframe.loc[long_condition, "enter_long"] = 1

        return dataframe

    # ==================================================================
    #  populate_exit_trend
    # ==================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals:
          - RSI > 55 (mild recovery from extreme oversold)
          - Close > BB middle band (price back to mean)
        Both conditions must be met for exit.
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        exit_condition = (
            (dataframe["rsi"] > 55)
            & (dataframe["close"] > dataframe["bb_middle"])
        )

        dataframe.loc[exit_condition, "exit_long"] = 1

        return dataframe

    # ==================================================================
    #  Custom Exit — Time-based Exit
    # ==================================================================
    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        """
        Time-based exit:
          - If trade held > 12 hours without hitting target, force exit.
        """
        holding_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if holding_minutes > self.TIME_EXIT_MINUTES:
            return "time_exit"

        return None


# ══════════════════════════════════════════════════════════════════════
#  Strategy Registration (Freqtrade auto-discovers via filename)
# ══════════════════════════════════════════════════════════════════════
