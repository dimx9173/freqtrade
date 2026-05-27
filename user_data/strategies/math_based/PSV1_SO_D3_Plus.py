"""
D3+ Variants testing - Based on PSV1_SO_VarD3 (Price pullback ±2%)
4 new variants to test against D3 baseline (+15.29%):
  1. D3_Kelly17: D3 + Kelly 17% position sizing
  2. D3_Kelly25: D3 + Kelly 25% position sizing
  3. D3_SL1.5_TP6: D3 + tighter SL 1.5%, wider TP 6%
  4. D3_Kelly17_SL1.5_TP6: D3 + Kelly 17% + tighter SL 1.5% + wider TP 6%
"""

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import DecimalParameter, IStrategy


# ============================================================
# BASELINE: D3 (VarD3) - Price pullback ±2%
# Original parameters: SL 2%, TP 5.5%/3%/2%, no Kelly sizing
# ============================================================
class PSV1_SO_D3_Baseline(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {"0": 0.055, "360": 0.03, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")
    adx_threshold = DecimalParameter(15, 25, default=18, space="buy")

    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    def populate_indicators(self, dataframe, metadata):
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["at_ema"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Pullback: price within ±2% of EMA
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe


# ============================================================
# VARIANT 1: D3 + Kelly 17% position sizing
# Same SL/TP as D3, but with Kelly-based position sizing
# ============================================================
class PSV1_SO_D3_Kelly17(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {"0": 0.055, "360": 0.03, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # Kelly position sizing - fixed 17%
    kelly_position_size = 0.17

    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")
    adx_threshold = DecimalParameter(15, 25, default=18, space="buy")

    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    def populate_indicators(self, dataframe, metadata):
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["at_ema"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Pullback: price within ±2% of EMA
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe

    def custom_stake_amount(
        self,
        pair,
        current_time,
        current_rate,
        proposed_stake,
        min_stake,
        max_stake,
        entry_tag,
        side,
        leverage,
    ):
        return proposed_stake * self.kelly_position_size


# ============================================================
# VARIANT 2: D3 + Kelly 25% position sizing
# Same SL/TP as D3, but with Kelly-based position sizing
# ============================================================
class PSV1_SO_D3_Kelly25(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {"0": 0.055, "360": 0.03, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # Kelly position sizing - fixed 25%
    kelly_position_size = 0.25

    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")
    adx_threshold = DecimalParameter(15, 25, default=18, space="buy")

    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    def populate_indicators(self, dataframe, metadata):
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["at_ema"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Pullback: price within ±2% of EMA
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe

    def custom_stake_amount(
        self,
        pair,
        current_time,
        current_rate,
        proposed_stake,
        min_stake,
        max_stake,
        entry_tag,
        side,
        leverage,
    ):
        return proposed_stake * self.kelly_position_size


# ============================================================
# VARIANT 3: D3 + tighter SL 1.5%, wider TP 6%
# Original Kelly sizing (100%), but tighter stop loss and wider take profit
# ============================================================
class PSV1_SO_D3_SL1_TP6(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.015  # Tighter stop loss: 1.5% vs original 2%
    minimal_roi = {"0": 0.06, "360": 0.035, "720": 0.02}  # Wider TP: 6% initial vs 5.5%
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")
    adx_threshold = DecimalParameter(15, 25, default=18, space="buy")

    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    def populate_indicators(self, dataframe, metadata):
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["at_ema"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Pullback: price within ±2% of EMA
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe


# ============================================================
# VARIANT 4: D3 + Kelly 17% + tighter SL 1.5% + wider TP 6%
# Combined changes
# ============================================================
class PSV1_SO_D3_Kelly17_SL1_TP6(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.015  # Tighter stop loss: 1.5% vs original 2%
    minimal_roi = {"0": 0.06, "360": 0.035, "720": 0.02}  # Wider TP: 6% initial vs 5.5%
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # Kelly position sizing - fixed 17%
    kelly_position_size = 0.17

    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")
    adx_threshold = DecimalParameter(15, 25, default=18, space="buy")

    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    def populate_indicators(self, dataframe, metadata):
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["at_ema"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Pullback: price within ±2% of EMA
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe

    def custom_stake_amount(
        self,
        pair,
        current_time,
        current_rate,
        proposed_stake,
        min_stake,
        max_stake,
        entry_tag,
        side,
        leverage,
    ):
        return proposed_stake * self.kelly_position_size
