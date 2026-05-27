# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Hybrid_v1(IStrategy):
    """
    Hybrid_v1: EMA trend + RSI pullback entry + Gann ATR trailing

    Key insight: In an UPTREND, RSI pulls back to 45-50 then bounces.
    We catch this bounce rather than waiting for RSI < 30 (extreme oversold).

    Entry: EMA bullish + RSI crosses UP through 50 (from below)
    Exit: RSI > 65 OR price hits Gann upper band
    """

    timeframe = "1h"

    # EMA 參數
    ema_fast_len = 9
    ema_slow_len = 21

    # RSI 參數 - 調整為適合多頭市場的 threshold
    rsi_len = 8
    rsi_entry = 50  # 在多頭市場用 50 而不是 30
    rsi_exit = 70

    # ATR/Gann 參數
    atr_len = 14
    sens_factor = 2.0

    # 風控參數
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    minimal_roi = {
        "0": 0.03,
        "60": 0.015,
        "180": 0.01,
    }

    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "forces_entry": "market",
        "forces_exit": "market",
        "emergency_exit": "market",
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe["close"], timeperiod=self.ema_fast_len)
        dataframe["ema_slow"] = ta.EMA(dataframe["close"], timeperiod=self.ema_slow_len)
        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=self.rsi_len)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_len)
        dataframe["gann_upper"] = dataframe["close"] + (dataframe["atr"] * self.sens_factor * 1.5)
        dataframe["gann_middle"] = dataframe["close"] + (dataframe["atr"] * self.sens_factor * 0.5)
        dataframe["gann_lower"] = dataframe["close"] - (dataframe["atr"] * self.sens_factor * 1.0)
        dataframe["volume_ma"] = dataframe["volume"].rolling(20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        prev = dataframe["rsi"].shift(1)
        curr = dataframe["rsi"]

        # Long: RSI crosses UP through 50 + EMA bullish
        # This catches the pullback bounce in an uptrend
        long_cond = (
            (prev < self.rsi_entry)
            & (curr >= self.rsi_entry)  # RSI cross up through 50
            & (dataframe["ema_fast"] > dataframe["ema_slow"])  # EMA still bullish
            & (dataframe["volume_ratio"] > 1.0)  # Volume confirmation
        )
        dataframe.loc[long_cond, "enter_long"] = 1

        # Short: RSI crosses DOWN through 50 + EMA bearish
        short_cond = (
            (prev > 50)
            & (curr <= 50)  # RSI cross down through 50
            & (dataframe["ema_fast"] < dataframe["ema_slow"])  # EMA bearish
            & (dataframe["volume_ratio"] > 1.0)
        )
        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # Exit long: RSI overbought OR price hits Gann upper band
        dataframe.loc[
            (dataframe["rsi"] > self.rsi_exit) | (dataframe["close"] > dataframe["gann_upper"]),
            "exit_long",
        ] = 1

        # Exit short: RSI oversold OR price hits Gann lower band
        dataframe.loc[
            (dataframe["rsi"] < self.rsi_entry) | (dataframe["close"] < dataframe["gann_lower"]),
            "exit_short",
        ] = 1

        return dataframe
