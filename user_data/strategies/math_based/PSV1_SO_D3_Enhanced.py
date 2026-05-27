"""
Enhanced D3 Short Only strategies - Target: Win Rate > 60%
Based on D3e (SL1.5, TP6) which had 53.38% win rate

Key changes to improve win rate:
1. Tighter RSI range (60-70 instead of 50-65) - more overbought = better short signals
2. Stricter ADX requirement (25+ instead of 18+)
3. Enhanced DI filter (-DI > +DI * 1.5)
4. Volume confirmation
5. Bollinger Band upper band touch
6. MACD histogram negative and falling
"""

import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import DecimalParameter, IStrategy


# ============================================================
# ENHANCED D3 - VERSION 1: Tighter RSI + Higher ADX
# ============================================================
class PSV1_SO_D3_v1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.015  # Tighter stop
    minimal_roi = {"0": 0.06, "360": 0.035, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    # Tighter RSI range for more overbought confirmation
    sell_rsi_pullback_min = DecimalParameter(60, 70, default=63, space="sell")
    sell_rsi_pullback_max = DecimalParameter(70, 80, default=72, space="sell")
    # Higher ADX for stronger trend
    adx_threshold = DecimalParameter(20, 30, default=25, space="buy")

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
        # RSI pullback in overbought zone
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Price pullback within 2% of EMA
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"] * 1.5)
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe


# ============================================================
# ENHANCED D3 - VERSION 2: Add Bollinger Bands
# ============================================================
class PSV1_SO_D3_v2(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.015
    minimal_roi = {"0": 0.06, "360": 0.035, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(60, 70, default=63, space="sell")
    sell_rsi_pullback_max = DecimalParameter(70, 80, default=72, space="sell")
    adx_threshold = DecimalParameter(20, 30, default=25, space="buy")

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
        # Bollinger Bands
        dataframe["bb_upper"], dataframe["bb_middle"], dataframe["bb_lower"] = ta.BBANDS(
            dataframe, timeperiod=20, nbdevup=2, nbdevdn=2
        )
        dataframe["bb_position"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )
        # RSI pullback
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Price pullback
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        # Price near upper Bollinger Band (>80th percentile)
        bb_touch = dataframe["bb_position"] > 0.8
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"] * 1.5)
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & bb_touch
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe


# ============================================================
# ENHANCED D3 - VERSION 3: Add Volume filter
# ============================================================
class PSV1_SO_D3_v3(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.015
    minimal_roi = {"0": 0.06, "360": 0.035, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(60, 70, default=63, space="sell")
    sell_rsi_pullback_max = DecimalParameter(70, 80, default=72, space="sell")
    adx_threshold = DecimalParameter(20, 30, default=25, space="buy")

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
        dataframe["volume"] = dataframe["volume"]
        # Volume SMA for comparison
        dataframe["volume_sma"] = ta.SMA(dataframe, timeperiod=20)
        # RSI pullback
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Price pullback
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        # Volume confirmation (above average)
        dataframe["high_volume"] = dataframe["volume"] > dataframe["volume_sma"]
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"] * 1.5)
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & dataframe["high_volume"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe


# ============================================================
# ENHANCED D3 - VERSION 4: Add MACD histogram filter
# ============================================================
class PSV1_SO_D3_v4(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.015
    minimal_roi = {"0": 0.06, "360": 0.035, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(60, 70, default=63, space="sell")
    sell_rsi_pullback_max = DecimalParameter(70, 80, default=72, space="sell")
    adx_threshold = DecimalParameter(20, 30, default=25, space="buy")

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
        # MACD
        dataframe["macd"], dataframe["macd_signal"], dataframe["macd_hist"] = ta.MACD(
            dataframe, fastperiod=12, slowperiod=26, signalperiod=9
        )
        # RSI pullback
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Price pullback
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        # MACD histogram negative and falling
        macd_bearish = (dataframe["macd_hist"] < 0) & (
            dataframe["macd_hist"] < dataframe["macd_hist"].shift(1)
        )
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"] * 1.5)
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & macd_bearish
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe


# ============================================================
# ENHANCED D3 - VERSION 5: All filters combined
# ============================================================
class PSV1_SO_D3_v5(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.015
    minimal_roi = {"0": 0.06, "360": 0.035, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(60, 70, default=63, space="sell")
    sell_rsi_pullback_max = DecimalParameter(70, 80, default=72, space="sell")
    adx_threshold = DecimalParameter(20, 30, default=25, space="buy")

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
        # Bollinger Bands
        dataframe["bb_upper"], dataframe["bb_middle"], dataframe["bb_lower"] = ta.BBANDS(
            dataframe, timeperiod=20, nbdevup=2, nbdevdn=2
        )
        dataframe["bb_position"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )
        # MACD
        dataframe["macd"], dataframe["macd_signal"], dataframe["macd_hist"] = ta.MACD(
            dataframe, fastperiod=12, slowperiod=26, signalperiod=9
        )
        # Volume
        dataframe["volume_sma"] = ta.SMA(dataframe, timeperiod=20)
        # RSI pullback
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Price pullback
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.02
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
        # Volume confirmation
        dataframe["high_volume"] = dataframe["volume"] > dataframe["volume_sma"]
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        # All filters
        macd_bearish = (dataframe["macd_hist"] < 0) & (
            dataframe["macd_hist"] < dataframe["macd_hist"].shift(1)
        )
        bb_touch = dataframe["bb_position"] > 0.8

        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"] * 1.5)
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & bb_touch
            & macd_bearish
            & dataframe["high_volume"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe


# ============================================================
# ENHANCED D3 - VERSION 6: Ultra tight entry - only strongest signals
# ============================================================
class PSV1_SO_D3_v6(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.012  # Even tighter stop loss
    minimal_roi = {"0": 0.07, "360": 0.04, "720": 0.025}  # Wider TP to compensate
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # Very tight RSI range - only strongest overbought
    sell_rsi_pullback_min = DecimalParameter(65, 75, default=68, space="sell")
    sell_rsi_pullback_max = DecimalParameter(75, 85, default=78, space="sell")
    # Very high ADX - only very strong trends
    adx_threshold = DecimalParameter(25, 35, default=30, space="buy")

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
        # Bollinger Bands
        dataframe["bb_upper"], dataframe["bb_middle"], dataframe["bb_lower"] = ta.BBANDS(
            dataframe, timeperiod=20, nbdevup=2, nbdevdn=2
        )
        dataframe["bb_position"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )
        # MACD
        dataframe["macd"], dataframe["macd_signal"], dataframe["macd_hist"] = ta.MACD(
            dataframe, fastperiod=12, slowperiod=26, signalperiod=9
        )
        # RSI pullback
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )
        # Price pullback - stricter 1%
        dataframe["price_pullback"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.01
        ) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.01)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        # Very strong bearish signals only
        macd_bearish = (dataframe["macd_hist"] < 0) & (
            dataframe["macd_hist"] < dataframe["macd_hist"].shift(1)
        )
        bb_touch = dataframe["bb_position"] > 0.85
        # Very strong DI filter
        strong_di = dataframe["minus_di"] > dataframe["plus_di"] * 2.0

        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & strong_di
            & dataframe["rsi_pullback_short"]
            & dataframe["price_pullback"]
            & bb_touch
            & macd_bearish
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe
