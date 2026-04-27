# pragma pylint: disable=missing-docstring
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy


class BinHV45_Contract(IStrategy):
    """
    BinHV45_Contract - Bollinger Bands Mean Reversion Strategy for Futures

    Timeframe: 1m
    Mode: Futures (long/short)
    Leverage: 5x

    Entry Logic:
      - Long: Price touches BB lower band (40,2) with bbdelta/closedelta/tail conditions
      - Short: Price touches BB upper band (40,2) with symmetric conditions

    Exit Logic:
      - ROI: 1.25% immediate exit
      - Stop Loss: 5%
    """

    # Strategy version
    minimal_roi = {
        "0": 0.0125  # 1.25% ROI
    }

    # Stop loss configuration
    stoploss = -0.05  # 5% stop loss

    # Timeframe
    timeframe = "1m"

    # Futures mode
    can_short = True

    # Leverage setting - must use method, not property
    def leverage(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """
        Set leverage to 5x for all trades.
        """
        return 5.0

    # Process only new candles
    process_only_new_candles = False

    # Buy parameters
    buy_bbdelta = 7
    buy_closedelta = 17
    buy_tail = 25

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate Bollinger Bands and derived indicators
        """

        # Bollinger Bands (40, 2)
        bollinger = qtpylib.bollinger_bands(dataframe["close"], window=40, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]

        # BB Delta (distance between upper and lower band)
        dataframe["bb_delta"] = (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe[
            "bb_middleband"
        ]

        # Price Delta (current close vs BB middle band)
        dataframe["price_delta"] = (dataframe["close"] - dataframe["bb_middleband"]) / dataframe[
            "bb_middleband"
        ]

        # Close Delta (current close vs previous close)
        dataframe["closedelta"] = (dataframe["close"] - dataframe["close"].shift(1)) / dataframe[
            "close"
        ].shift(1)

        # Tail (distance from close to BB lower band for long, or BB upper band for short)
        dataframe["tail"] = (dataframe["close"] - dataframe["bb_lowerband"]) / (
            dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry signal logic based on Bollinger Bands and delta conditions
        """

        # Long entry conditions
        # Price touches BB lower band AND satisfies bbdelta/closedelta/tail conditions
        long_conditions = (
            qtpylib.crossed_below(dataframe["close"], dataframe["bb_lowerband"])
            & (dataframe["bb_delta"] > self.buy_bbdelta / 10000)
            & (dataframe["closedelta"] > self.buy_closedelta / 10000)
            & (dataframe["tail"] < self.buy_tail / 100)
        )

        # Short entry conditions
        # Price touches BB upper band AND satisfies symmetric conditions
        short_conditions = (
            qtpylib.crossed_above(dataframe["close"], dataframe["bb_upperband"])
            & (dataframe["bb_delta"] > self.buy_bbdelta / 10000)
            & (dataframe["closedelta"] < -self.buy_closedelta / 10000)
            & ((1 - dataframe["tail"]) < self.buy_tail / 100)
        )

        # Set entry signals
        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signal logic
        ROI and stop loss are handled automatically by minimal_roi and stoploss settings
        """

        # No explicit exit signal needed - uses ROI and stop loss
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        return dataframe
        return False
