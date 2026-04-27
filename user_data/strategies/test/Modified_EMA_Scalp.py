# pragma pylint: disable=missing-docstring

"""
Modified_EMA_Scalp - Freqtrade Strategy
========================================
Timeframe: 5m
Mode: Futures (long/short)
Leverage: 5x

Entry Logic:
- Long:  Close < BB_lowerband AND RSI < 30 AND ADX > 20
- Short: Close > BB_upperband AND RSI > 70 AND ADX > 20

Exit Logic:
- ROI: 2% (0min) / 1% (30min)
- Stoploss: 3%

Indicators:
- Bollinger Bands (20, 2)
- RSI (14)
- ADX (14)
"""

import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class Modified_EMA_Scalp(IStrategy):
    """
    Modified EMA Scalp strategy using ADX trend strength filter instead of EMA direction.
    This allows trading in both bull and bear markets as long as trend strength is present.
    """

    # ------------------------------
    # Minimal ROI Table
    # ------------------------------
    minimal_roi = {
        "0": 0.02,  # 2% profit after 0 minutes
        "30": 0.01,  # 1% profit after 30 minutes
    }

    # ------------------------------
    # Stoploss
    # ------------------------------
    stoploss = -0.03  # 3% stoploss

    # ------------------------------
    # Timeframe
    # ------------------------------
    timeframe = "5m"

    # Futures / Short Settings
    can_short = True
    margin_mode = "isolated"

    # ------------------------------
    # Process buy signals before
    # ------------------------------
    process_only_new_candles = False

    # ------------------------------
    # Indicators
    # ------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands (20, 2)
        bollinger = qtpylib.bollinger_bands(dataframe["close"], window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]

        # RSI (14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ADX (14) - Average Directional Index
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        return dataframe

    # ------------------------------
    # Entry Signal Logic
    # ------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = (
            (dataframe["close"] < dataframe["bb_lowerband"])  # Price below lower BB
            & (dataframe["rsi"] < 30)  # RSI oversold
            & (dataframe["adx"] > 20)  # ADX trend strength > 20
        )

        dataframe["enter_short"] = (
            (dataframe["close"] > dataframe["bb_upperband"])  # Price above upper BB
            & (dataframe["rsi"] > 70)  # RSI overbought
            & (dataframe["adx"] > 20)  # ADX trend strength > 20
        )

        return dataframe

    # ------------------------------
    # Exit Signal Logic (using ROI)
    # ------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit signals are handled by minimal_roi and stoploss
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        return dataframe
