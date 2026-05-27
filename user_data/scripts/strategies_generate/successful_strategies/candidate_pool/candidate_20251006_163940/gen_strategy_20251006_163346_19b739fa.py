# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce
import numpy as np

# --------------------------------


class ScalpingStrategy_b1e6e93e(IStrategy):
    """
    Scalping Strategy using MFI, ROC and ADX
    author: Gemini
    version: 1.0
    """

    # --- Strategy Configuration ---
    INTERFACE_VERSION = 3

    # Strategy timeframe
    timeframe = "5m"

    # Set to True to enable short trading
    can_short = True

    # Minimal ROI designed for the strategy.
    minimal_roi = {
        "0": 0.025,  # 2.5% profit
        "10": 0.015,  # After 10 mins, 1.5%
        "30": 0.01,  # After 30 mins, 1%
        "60": 0.005,  # After 60 mins, 0.5%
    }

    # Stoploss
    stoploss = -0.07  # 7% stoploss

    # Trailing stoploss
    trailing_stop = False

    # Custom stoploss using ATR
    use_custom_stoploss = True

    # --- Hyperparameters ---
    # Entry
    adx_threshold = 25
    mfi_long_threshold = 30
    mfi_short_threshold = 70
    roc_long_threshold = 0.5
    roc_short_threshold = -0.5

    # Custom Stoploss
    atr_stoploss_multiplier = 2.5

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        # --- Momentum Indicators ---
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["roc"] = ta.ROC(dataframe, timeperiod=9)

        # --- Trend Indicator ---
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # --- Volatility Indicator for Stoploss ---
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the enter_long and enter_short signals
        """
        # --- Long Entry Conditions (3 conditions) ---
        long_conditions = [
            dataframe["adx"] > self.adx_threshold,
            dataframe["mfi"] < self.mfi_long_threshold,
            dataframe["roc"] > self.roc_long_threshold,
        ]
        # Combine conditions using reduce and logical AND
        dataframe.loc[reduce(lambda x, y: x & y, long_conditions), "enter_long"] = 1

        # --- Short Entry Conditions (3 conditions) ---
        short_conditions = [
            dataframe["adx"] > self.adx_threshold,
            dataframe["mfi"] > self.mfi_short_threshold,
            dataframe["roc"] < self.roc_short_threshold,
        ]
        # Combine conditions using reduce and logical AND
        dataframe.loc[reduce(lambda x, y: x & y, short_conditions), "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit_long and exit_short signals
        """
        # --- Exit Long on Opposite Signal ---
        dataframe.loc[(dataframe["enter_short"] == 1), "exit_long"] = 1

        # --- Exit Short on Opposite Signal ---
        dataframe.loc[(dataframe["enter_long"] == 1), "exit_short"] = 1

        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
        current_time: "datetime",
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        Custom stoploss logic, returning the new distance relative to current_rate.
        e.g. returning -0.05 would create a stoploss 5% below current_rate.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if last_candle is None:
            return -self.stoploss

        atr_value = last_candle["atr"]

        # Ensure atr_value is a valid number
        if atr_value is None or np.isnan(atr_value) or atr_value == 0:
            return -self.stoploss

        # Calculate stoploss based on ATR
        stoploss_price = atr_value * self.atr_stoploss_multiplier

        # For long trades, stoploss is below the current rate
        if trade.is_long:
            stoploss_amount = stoploss_price / current_rate
        # For short trades, stoploss is above the current rate
        else:
            stoploss_amount = stoploss_price / current_rate

        # Return as a negative percentage
        return -stoploss_amount
