# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce
import numpy as np

# --------------------------------


class ScalpingStrategy_8937edfd(IStrategy):
    """
    Freqtrade Scalping Strategy

    Author: Gemini
    Version: 1.0

    Indicators:
    - Bollinger Bands (BB)
    - Momentum (MOM)
    - Volume Weighted Average Price (VWAP)
    - Average Directional Index (ADX) for trend filtering

    Strategy Logic:
    - Long: Enters a long position during a confirmed uptrend (ADX > 25, Price > VWAP)
            when the price pulls back towards the BB middle band and momentum is positive.
    - Short: Enters a short position during a confirmed downtrend (ADX > 25, Price < VWAP)
             when the price rallies towards the BB middle band and momentum is negative.

    Exit Logic:
    - ROI table for profit-taking.
    - Custom stoploss based on ATR.
    - Exits if the opposite signal appears.
    """

    # Strategy interface version - Required
    INTERFACE_VERSION = 3

    # --- Strategy Configuration ---
    timeframe = "5m"
    can_short = True

    # ROI table:
    minimal_roi = {
        "0": 0.015,  # 1.5% profit
        "20": 0.01,  # 1.0% profit after 20 minutes
        "40": 0.005,  # 0.5% profit after 40 minutes
    }

    # Stoploss:
    stoploss = -0.07  # 7% stoploss. Recommended to use custom_stoploss.

    # Trailing stop:
    trailing_stop = False

    # Run "populate_indicators()" only for new candles.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Optimal timeframe for the strategy.
    optimal_timeframe = "5m"

    # --- Hyperoptable Parameters ---
    # Define ranges for parameters that can be optimized.
    # Example: buy_adx = IntParameter(20, 30, default=25, space="buy")

    # --- Indicator Parameters ---
    # BB
    bb_window = 20
    bb_stddev = 2.0
    # MOM
    mom_period = 14
    # ADX
    adx_period = 14
    # ATR for stoploss
    atr_period = 14
    atr_multiplier = 3.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame
        """
        # -- Bollinger Bands --
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=self.bb_window, stds=self.bb_stddev
        )
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]

        # -- Momentum (MOM) --
        dataframe["mom"] = ta.MOM(dataframe, timeperiod=self.mom_period)

        # -- ADX for Trend Filter --
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_period)

        # -- ATR for Stoploss --
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # -- Volume Weighted Average Price (VWAP) with daily reset --
        # The VWAP calculation needs to reset each day.
        vwap_reset = dataframe["date"].dt.date != dataframe["date"].dt.date.shift(1)

        # Group by day and calculate VWAP
        df_vwap = dataframe.groupby(vwap_reset.cumsum()).apply(
            lambda x: (np.cumsum(x["volume"] * qtpylib.typical_price(x))) / np.cumsum(x["volume"])
        )

        # Reset index to align with the main dataframe
        dataframe["vwap"] = df_vwap.reset_index(level=0, drop=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for long and short positions.
        """
        # --- LONG ENTRY CONDITIONS ---
        # 1. Trend is active (ADX > 25)
        # 2. Price is above daily VWAP (Bullish intraday trend)
        # 3. Price pulls back below the BB middle band (Dip buying opportunity)
        # 4. Momentum is positive (Confirmation of upward strength)
        long_conditions = [
            (dataframe["adx"] > 25),
            (dataframe["close"] > dataframe["vwap"]),
            (dataframe["close"] < dataframe["bb_middleband"]),
            (dataframe["mom"] > 0),
        ]
        dataframe.loc[reduce(lambda x, y: x & y, long_conditions), "enter_long"] = 1

        # --- SHORT ENTRY CONDITIONS ---
        # 1. Trend is active (ADX > 25)
        # 2. Price is below daily VWAP (Bearish intraday trend)
        # 3. Price rallies above the BB middle band (Rally selling opportunity)
        # 4. Momentum is negative (Confirmation of downward strength)
        short_conditions = [
            (dataframe["adx"] > 25),
            (dataframe["close"] < dataframe["vwap"]),
            (dataframe["close"] > dataframe["bb_middleband"]),
            (dataframe["mom"] < 0),
        ]
        dataframe.loc[reduce(lambda x, y: x & y, short_conditions), "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for long and short positions.
        """
        # --- EXIT LONG CONDITIONS (based on short entry signal) ---
        exit_long_conditions = [
            (dataframe["adx"] > 25),
            (dataframe["close"] < dataframe["vwap"]),
            (dataframe["close"] > dataframe["bb_middleband"]),
            (dataframe["mom"] < 0),
        ]
        dataframe.loc[reduce(lambda x, y: x & y, exit_long_conditions), "exit_long"] = 1

        # --- EXIT SHORT CONDITIONS (based on long entry signal) ---
        exit_short_conditions = [
            (dataframe["adx"] > 25),
            (dataframe["close"] > dataframe["vwap"]),
            (dataframe["close"] < dataframe["bb_middleband"]),
            (dataframe["mom"] > 0),
        ]
        dataframe.loc[reduce(lambda x, y: x & y, exit_short_conditions), "exit_short"] = 1

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
        Custom stoploss based on ATR.
        The stoploss is placed at entry_price - (ATR * multiplier).
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if last_candle is None:
            return -1  # Defer decision

        atr_value = last_candle["atr"]

        # For long trades
        if trade.is_long:
            stoploss_price = trade.open_rate - (atr_value * self.atr_multiplier)
        # For short trades
        else:
            stoploss_price = trade.open_rate + (atr_value * self.atr_multiplier)

        # Convert price to a percentage-based stoploss
        # Freqtrade expects a negative percentage value.
        # e.g., if stoploss_price is 95 and open_rate is 100, the result is -0.05
        stoploss_pct = (stoploss_price / trade.open_rate) - 1

        return stoploss_pct
