#!/usr/bin/env python3
"""Generate leverage test strategies"""

leverage = 1
stoploss = -0.02
roi_mult = 1.0

roi = {
    "0": round(0.06 * roi_mult, 4),
    "360": round(0.03 * roi_mult, 4),
    "720": round(0.02 * roi_mult, 4),
}

roi_str = (
    """{
    "0": """
    + str(roi["0"])
    + """,    # """
    + str(int(roi["0"] * 100))
    + """% immediate
    "360": """
    + str(roi["360"])
    + """,  # After 6h, """
    + str(int(roi["360"] * 100))
    + """%
    "720": """
    + str(roi["720"])
    + """   # After 12h, """
    + str(int(roi["720"] * 100))
    + """%
}"""
)

code = (
    """# Pullback_Scalp_v1_ShortOnly_Leverage_1x
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import DecimalParameter, IStrategy

class Pullback_Scalp_v1_ShortOnly_Leverage_1x(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # Stoploss/Takeprofit - Adjusted for 1x leverage
    stoploss = """
    + str(stoploss)
    + """
    minimal_roi = """
    + roi_str
    + """
    trailing_stop = False
    trailing_stop_positive = 0
    trailing_stop_positive_offset = 0
    trailing_only_offset_is_reached = False

    # Entry Parameters (same as base)
    buy_rsi_pullback_max = DecimalParameter(40, 50, default=45, space="buy")
    buy_rsi_pullback_min = DecimalParameter(30, 45, default=35, space="buy")
    sell_rsi_pullback_min = DecimalParameter(55, 65, default=60, space="sell")
    sell_rsi_pullback_max = DecimalParameter(75, 80, default=65, space="sell")
    adx_threshold = DecimalParameter(20, 35, default=25, space="buy")

    startup_candle_count: int = 100
    process_only_new_candles = True
    use_exit_signal = False

    @staticmethod
    def informative_1h_indicator(dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["ema9"] = ta.EMA(df, timeperiod=9)
        df["ema21"] = ta.EMA(df, timeperiod=21)
        df["ema50"] = ta.EMA(df, timeperiod=50)
        df["ema200"] = ta.EMA(df, timeperiod=200)
        df["adx"] = ta.ADX(df, timeperiod=14)
        df["plus_di"] = ta.PLUS_DI(df, timeperiod=14)
        df["minus_di"] = ta.MINUS_DI(df, timeperiod=14)
        df["ema_bullish"] = df["ema9"] > df["ema21"]
        df["ema_bearish"] = df["ema9"] < df["ema21"]
        df["above_ema200"] = df["close"] > df["ema200"]
        return df

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=7)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["bb_middle"] = ta.BBANDS(dataframe, timeperiod=20)["middleband"]
        dataframe["bb_upper"] = ta.BBANDS(dataframe, timeperiod=20)["upperband"]
        dataframe["bb_lower"] = ta.BBANDS(dataframe, timeperiod=20)["lowerband"]

        dataframe["bull_pullback_score"] = (
            (dataframe["ema9"] > dataframe["ema21"]).astype(float) * 0.25
            + (dataframe["adx"] > self.adx_threshold.value).astype(float) * 0.25
            + (dataframe["plus_di"] > dataframe["minus_di"]).astype(float) * 0.20
            + ((dataframe["rsi"] > self.buy_rsi_pullback_min.value) & (dataframe["rsi"] < self.buy_rsi_pullback_max.value)).astype(float) * 0.15
            + (((dataframe["close"] > dataframe["ema50"] * 0.98) & (dataframe["close"] < dataframe["ema50"] * 1.02))).astype(float) * 0.15
        )

        dataframe["bear_pullback_score"] = (
            (dataframe["ema9"] < dataframe["ema21"]).astype(float) * 0.25
            + (dataframe["adx"] > self.adx_threshold.value).astype(float) * 0.25
            + (dataframe["minus_di"] > dataframe["plus_di"]).astype(float) * 0.20
            + ((dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (dataframe["rsi"] < self.sell_rsi_pullback_max.value)).astype(float) * 0.15
            + (((dataframe["close"] > dataframe["ema50"] * 0.98) & (dataframe["close"] < dataframe["ema50"] * 1.02))).astype(float) * 0.15
        )

        dataframe["at_ema9"] = (abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005)
        dataframe["at_ema21"] = (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["at_ema"] = dataframe["at_ema9"] | dataframe["at_ema21"]
        dataframe["rsi_pullback_long"] = (dataframe["rsi"] > self.buy_rsi_pullback_min.value) & (dataframe["rsi"] < self.buy_rsi_pullback_max.value)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (dataframe["rsi"] < self.sell_rsi_pullback_max.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["at_ema"]
            & (dataframe["close"] < dataframe["ema200"])
            & (dataframe["ema_1h_bearish"] if "ema_1h_bearish" in dataframe.columns else True)
            & (dataframe["adx_1h"] > self.adx_threshold.value if "adx_1h" in dataframe.columns else True)
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    @property
    def protections(self):
        return [
            {"method": "StoplossGuard", "lookback_period_candles": 24, "trade_limit": 2, "stop_duration_candles": 4, "refresh_period_candles": 480},
            {"method": "LowProfitPairs", "lookback_period_candles": 24, "trade_limit": 1, "stop_duration_candles": 2, "required_profit": 0.01},
        ]
"""
)

with open("user_data/strategies/test/LeverageTest_1x.py", "w") as f:
    f.write(code)
print("Strategy written")
