# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

"""
BiDirectional_BB_Scalp - Bollinger Bands Mean Reversion Strategy
- Timeframe: 5m
- Trading Mode: Futures (long/short)
- Leverage: 5x
- Symmetric long/short design with ATR dynamic stop loss
"""

import talib.abstract as ta
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IntParameter, IStrategy, RealParameter


class BiDirectional_BB_Scalp(IStrategy):
    """
    BiDirectional_BB_Scalp Strategy
    Pure Bollinger Bands mean reversion with symmetric long/short entries.
    """

    # === Timeframe Settings ===
    timeframe = "5m"

    # === Futures / Short Settings ===
    can_short = True
    process_only_new_candles = True
    stoploss = -0.05  # Maximum stop loss: 5%

    # === ROI Settings ===
    minimal_roi = {
        "0": 0.03,  # 3% at 0 minutes
        "60": 0.02,  # 2% after 60 minutes
        "120": 0.01,  # 1% after 120 minutes
    }

    # === Stop Loss Settings ===
    use_custom_stoploss = True

    # === Bollinger Bands Parameters ===
    bb_length = IntParameter(10, 30, default=20, space="buy")
    bb_std = RealParameter(1.5, 3.0, default=2.0, space="buy")

    # === RSI Parameters ===
    rsi_length = IntParameter(10, 20, default=14, space="buy")
    rsi_long_threshold = IntParameter(25, 40, default=35, space="buy")
    rsi_short_threshold = IntParameter(60, 75, default=65, space="sell")

    # === ATR Parameters ===
    atr_length = IntParameter(10, 20, default=14, space="sell")
    atr_multiplier = RealParameter(1.5, 3.0, default=2.0, space="sell")

    # === Volume MA Parameters ===
    volume_ma_length = IntParameter(15, 30, default=20, space="buy")

    # === Exit Signal Parameters ===
    bb_long_threshold = RealParameter(0.95, 0.999, default=0.99, space="buy")
    bb_short_threshold = RealParameter(1.001, 1.05, default=1.01, space="sell")

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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators required for strategy.
        """
        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe),
            window=self.bb_length.value,
            stds=self.bb_std.value,
        )
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_length.value)

        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_length.value)

        # Volume MA
        dataframe["volume_ma"] = ta.SMA(
            dataframe,
            timeperiod=self.volume_ma_length.value,
            price="volume",
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate entry signals.
        Long: Close < BB_lowerband * 0.99 AND RSI < 35
              AND Volume > Volume_MA(20)
        Short: Close > BB_upperband * 1.01 AND RSI > 65
               AND Volume > Volume_MA(20)
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # Long entry conditions
        long_conditions = qtpylib.crossed_below(
            dataframe["close"],
            dataframe["bb_lowerband"] * self.bb_long_threshold.value,
        ) | (
            (dataframe["close"] < dataframe["bb_lowerband"] * self.bb_long_threshold.value)
            & (dataframe["rsi"] < self.rsi_long_threshold.value)
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        # Short entry conditions
        short_conditions = qtpylib.crossed_above(
            dataframe["close"],
            dataframe["bb_upperband"] * self.bb_short_threshold.value,
        ) | (
            (dataframe["close"] > dataframe["bb_upperband"] * self.bb_short_threshold.value)
            & (dataframe["rsi"] > self.rsi_short_threshold.value)
            & (dataframe["volume"] > dataframe["volume_ma"])
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate exit signals.
        Exit signals are handled by ROI and custom_stoploss.
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float:
        """
        Custom stoploss using 2x ATR.
        Returns the stoploss percentage relative to entry price.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss

        last_candle = dataframe.iloc[-1]
        atr = last_candle["atr"]

        # Calculate stoploss based on 2x ATR
        stoploss_distance = (atr * self.atr_multiplier.value) / current_rate
        return -stoploss_distance
