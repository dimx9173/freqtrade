# Pullback_Scalp_v1_ShortOnly - Short Only Version
# ========================================================
# Task: Short only version of Pullback_Scalp_v1
# Logic: Same as Pullback_Scalp_v1 but LONG entries disabled
# ========================================================
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IStrategy


class Pullback_Scalp_v1_ShortOnly(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True  # Enable shorting

    # === Stoploss/Takeprofit Settings ===
    stoploss = -0.02  # 2% hard stoploss
    minimal_roi = {
        "0": 0.06,  # 6% takeprofit (let winners run)
        "360": 0.03,  # After 6 hours, take 3%
        "720": 0.02,  # After 12 hours, take 2%
    }
    trailing_stop = True
    trailing_stop_positive = 0.015  # 1.5% trailing
    trailing_stop_positive_offset = 0.025  # Activate after 2.5% profit
    trailing_only_offset_is_reached = True

    # === Entry Parameters ===
    buy_rsi_pullback_max = DecimalParameter(40, 50, default=45, space="buy")
    buy_rsi_pullback_min = DecimalParameter(30, 45, default=35, space="buy")
    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")
    adx_threshold = DecimalParameter(20, 35, default=25, space="buy")

    startup_candle_count: int = 100
    process_only_new_candles = True
    use_exit_signal = False  # NO RSI exit - let ROI/trailing handle exits

    @staticmethod
    def informative_1h_indicator(dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1h timeframe indicators - Trend confirmation
        df = dataframe.copy()

        # EMA (1h)
        df["ema9"] = ta.EMA(df, timeperiod=9)
        df["ema21"] = ta.EMA(df, timeperiod=21)
        df["ema50"] = ta.EMA(df, timeperiod=50)
        df["ema200"] = ta.EMA(df, timeperiod=200)

        # ADX (1h)
        df["adx"] = ta.ADX(df, timeperiod=14)
        df["plus_di"] = ta.PLUS_DI(df, timeperiod=14)
        df["minus_di"] = ta.MINUS_DI(df, timeperiod=14)

        # 1h EMA bullish alignment
        df["ema_bullish"] = df["ema9"] > df["ema21"]
        # 1h EMA bearish alignment
        df["ema_bearish"] = df["ema9"] < df["ema21"]

        # 1h price above EMA200 (bull market)
        df["above_ema200"] = df["close"] > df["ema200"]

        return df

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === 15m timeframe indicators ===
        # EMA (15m)
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        # RSI (15m)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=7)

        # ADX + DI (15m)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ATR (15m)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Bollinger Bands (15m) - For pullback low/high detection
        dataframe["bb_middle"] = ta.BBANDS(dataframe, timeperiod=20)["middleband"]
        dataframe["bb_upper"] = ta.BBANDS(dataframe, timeperiod=20)["upperband"]
        dataframe["bb_lower"] = ta.BBANDS(dataframe, timeperiod=20)["lowerband"]

        # === Signal Scoring ===
        # Long pullback signal score
        dataframe["bull_pullback_score"] = (
            # EMA bullish alignment
            (dataframe["ema9"] > dataframe["ema21"]).astype(float) * 0.25
            + (
                # ADX > 25 confirms trend strength
                (dataframe["adx"] > self.adx_threshold.value).astype(float) * 0.25
            )
            + (
                # +DI > -DI long direction
                (dataframe["plus_di"] > dataframe["minus_di"]).astype(float) * 0.20
            )
            + (
                # RSI in healthy pullback range
                (
                    (dataframe["rsi"] > self.buy_rsi_pullback_min.value)
                    & (dataframe["rsi"] < self.buy_rsi_pullback_max.value)
                ).astype(float)
                * 0.15
            )
            + (
                # Price near EMA50 (pullback location)
                (
                    (dataframe["close"] > dataframe["ema50"] * 0.98)
                    & (dataframe["close"] < dataframe["ema50"] * 1.02)
                ).astype(float)
                * 0.15
            )
        )

        # Short pullback signal score
        dataframe["bear_pullback_score"] = (
            # EMA bearish alignment
            (dataframe["ema9"] < dataframe["ema21"]).astype(float) * 0.25
            + (
                # ADX > 25 confirms trend strength
                (dataframe["adx"] > self.adx_threshold.value).astype(float) * 0.25
            )
            + (
                # -DI > +DI short direction
                (dataframe["minus_di"] > dataframe["plus_di"]).astype(float) * 0.20
            )
            + (
                # RSI in healthy bounce range
                (
                    (dataframe["rsi"] > self.sell_rsi_pullback_min.value)
                    & (dataframe["rsi"] < self.sell_rsi_pullback_max.value)
                ).astype(float)
                * 0.15
            )
            + (
                # Price near EMA50 (bounce location)
                (
                    (dataframe["close"] > dataframe["ema50"] * 0.98)
                    & (dataframe["close"] < dataframe["ema50"] * 1.02)
                ).astype(float)
                * 0.15
            )
        )

        # === Entry Signal Enhancement ===
        # Price near EMA for pullback/bounce
        dataframe["at_ema9"] = (
            abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005
        )
        dataframe["at_ema21"] = (
            abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005
        )
        dataframe["at_ema"] = dataframe["at_ema9"] | dataframe["at_ema21"]

        # RSI pulling back from overbought/oversold
        dataframe["rsi_pullback_long"] = (dataframe["rsi"] > self.buy_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.buy_rsi_pullback_max.value
        )
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (
            dataframe["rsi"] < self.sell_rsi_pullback_max.value
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === LONG ENTRY DISABLED - Short Only Mode ===
        # Long conditions defined but NOT applied (commented out)
        # long_conditions = (
        #     # 1. EMA bullish alignment (15m)
        #     (dataframe["ema9"] > dataframe["ema21"])
        #     &
        #     # 2. ADX > 25 confirms trend strength
        #     (dataframe["adx"] > self.adx_threshold.value)
        #     &
        #     # 3. +DI > -DI long direction
        #     (dataframe["plus_di"] > dataframe["minus_di"])
        #     &
        #     # 4. RSI pulls back to 40-50 range
        #     dataframe["rsi_pullback_long"]
        #     &
        #     # 5. Price near EMA 9/21
        #     dataframe["at_ema"]
        #     &
        #     # 6. Price above EMA200
        #     (dataframe["close"] > dataframe["ema200"])
        #     &
        #     # 7. 1h EMA bullish alignment (from informative)
        #     (dataframe["ema_1h_bullish"] if "ema_1h_bullish" in dataframe.columns else True)
        #     &
        #     # 8. 1h ADX > 25
        #     (
        #         dataframe["adx_1h"] > self.adx_threshold.value
        #         if "adx_1h" in dataframe.columns
        #         else True
        #     )
        # )

        # === Short Entry Conditions ===
        short_conditions = (
            # 1. EMA bearish alignment (15m)
            (dataframe["ema9"] < dataframe["ema21"])
            &
            # 2. ADX > 25 confirms trend strength
            (dataframe["adx"] > self.adx_threshold.value)
            &
            # 3. -DI > +DI short direction
            (dataframe["minus_di"] > dataframe["plus_di"])
            &
            # 4. RSI bounces to 50-60 range
            dataframe["rsi_pullback_short"]
            &
            # 5. Price near EMA 9/21
            dataframe["at_ema"]
            &
            # 6. Price below EMA200
            (dataframe["close"] < dataframe["ema200"])
            &
            # 7. 1h EMA bearish alignment
            (dataframe["ema_1h_bearish"] if "ema_1h_bearish" in dataframe.columns else True)
            &
            # 8. 1h ADX > 25
            (
                dataframe["adx_1h"] > self.adx_threshold.value
                if "adx_1h" in dataframe.columns
                else True
            )
        )

        # dataframe.loc[long_conditions, "enter_long"] = 1  # DISABLED
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # NO exit signals - let ROI and trailing stop handle all exits
        # This allows profits to run to 4% instead of being cut at RSI 70/30
        return dataframe

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 2,
                "stop_duration_candles": 4,
                "refresh_period_candles": 480,
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 24,
                "trade_limit": 1,
                "stop_duration_candles": 2,
                "required_profit": 0.01,
            },
        ]
