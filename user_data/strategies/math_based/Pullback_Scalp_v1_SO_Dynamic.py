# Pullback_Scalp_v1_SO_Dynamic - Dynamic ADX-Based Parameter Strategy
# ========================================================
# Task: Dynamically adjust parameters based on market state (ADX)
# Logic:
#   1. ADX > 30 (Strong Trend): Relax ADX to 15, ROI 7%
#   2. ADX 15-25 (Normal Trend): Standard ADX 18, ROI 5.5%
#   3. ADX < 15 (No Trend): Tighten ADX to 20, ROI 3%
# ========================================================
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IStrategy


class Pullback_Scalp_v1_SO_Dynamic(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # === Dynamic Parameter Ranges ===
    # Standard (Normal Trend) Parameters
    std_adx_threshold = 18.0
    std_roi = 0.055  # 5.5%

    # === Base Stoploss Settings ===
    stoploss = -0.02  # 2% hard stoploss

    # Static minimal_roi (required by freqtrade)
    minimal_roi = {
        "0": 0.055,
        "360": 0.03,
        "720": 0.02,
    }

    # === Entry Parameters ===
    buy_rsi_pullback_max = DecimalParameter(40, 50, default=45, space="buy")
    buy_rsi_pullback_min = DecimalParameter(30, 45, default=35, space="buy")
    sell_rsi_pullback_min = DecimalParameter(50, 60, default=55, space="sell")
    sell_rsi_pullback_max = DecimalParameter(60, 70, default=65, space="sell")

    startup_candle_count: int = 100
    process_only_new_candles = True
    use_exit_signal = True  # Enable exits for custom_exit

    # Custom exit configuration
    use_custom_exit = True
    ignore_roi_if_entry_signal = False

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

    def get_dynamic_adx_threshold(self, dataframe: DataFrame) -> float:
        """
        Calculate dynamic ADX threshold based on market state.
        Uses 1h ADX if available, otherwise falls back to 15m.
        """
        adx_1h = dataframe["adx_1h"] if "adx_1h" in dataframe.columns else None
        adx_col = adx_1h if adx_1h is not None else dataframe["adx"]
        current_adx = adx_col.iloc[-1] if len(dataframe) > 0 else 25

        if current_adx > 30:
            # Strong Trend: Relax ADX threshold to 15
            return 15.0
        elif current_adx < 15:
            # No Trend: Tighten ADX to 20
            return 20.0
        else:
            # Normal Trend: Standard ADX 18
            return self.std_adx_threshold

    def get_dynamic_roi(self, dataframe: DataFrame) -> float:
        """
        Calculate dynamic ROI based on market state.
        """
        adx_1h = dataframe["adx_1h"] if "adx_1h" in dataframe.columns else None
        adx_col = adx_1h if adx_1h is not None else dataframe["adx"]
        current_adx = adx_col.iloc[-1] if len(dataframe) > 0 else 25

        if current_adx > 30:
            # Strong Trend: ROI 7%
            return 0.07
        elif current_adx < 15:
            # No Trend: ROI 3%
            return 0.03
        else:
            # Normal Trend: ROI 5.5%
            return self.std_roi

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

        # === Dynamic ADX threshold per candle ===
        # Calculate dynamic thresholds for each candle based on ADX
        adx_1h = dataframe["adx_1h"] if "adx_1h" in dataframe.columns else dataframe["adx"]

        # Strong trend (ADX > 30): threshold = 15
        # Normal trend (15 <= ADX <= 25): threshold = 18
        # No trend (ADX < 15): threshold = 20
        dataframe["dynamic_adx_threshold"] = adx_1h.apply(
            lambda x: 15.0 if x > 30 else (20.0 if x < 15 else 18.0)
        )

        # === Dynamic ROI per candle ===
        dataframe["dynamic_roi"] = adx_1h.apply(
            lambda x: 0.07 if x > 30 else (0.03 if x < 15 else 0.055)
        )

        # === Signal Scoring ===
        # Long pullback signal score
        dataframe["bull_pullback_score"] = (
            # EMA bullish alignment
            (dataframe["ema9"] > dataframe["ema21"]).astype(float) * 0.25
            + (
                # ADX > dynamic threshold confirms trend strength
                (dataframe["adx"] > dataframe["dynamic_adx_threshold"]).astype(float) * 0.25
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
                # ADX > dynamic threshold confirms trend strength
                (dataframe["adx"] > dataframe["dynamic_adx_threshold"]).astype(float) * 0.25
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
        # === Long Entry Conditions ===
        long_conditions = (
            # 1. EMA bullish alignment (15m)
            (dataframe["ema9"] > dataframe["ema21"])
            &
            # 2. ADX > dynamic threshold confirms trend strength
            (dataframe["adx"] > dataframe["dynamic_adx_threshold"])
            &
            # 3. +DI > -DI long direction
            (dataframe["plus_di"] > dataframe["minus_di"])
            &
            # 4. RSI pulls back to 40-50 range
            dataframe["rsi_pullback_long"]
            &
            # 5. Price near EMA 9/21
            dataframe["at_ema"]
            &
            # 6. Price above EMA200
            (dataframe["close"] > dataframe["ema200"])
            &
            # 7. 1h EMA bullish alignment (from informative)
            (dataframe["ema_1h_bullish"] if "ema_1h_bullish" in dataframe.columns else True)
            &
            # 8. 1h ADX > dynamic threshold
            (
                dataframe["adx_1h"] > dataframe["dynamic_adx_threshold"]
                if "adx_1h" in dataframe.columns
                else True
            )
        )

        # === Short Entry Conditions ===
        short_conditions = (
            # 1. EMA bearish alignment (15m)
            (dataframe["ema9"] < dataframe["ema21"])
            &
            # 2. ADX > dynamic threshold confirms trend strength
            (dataframe["adx"] > dataframe["dynamic_adx_threshold"])
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
            # 8. 1h ADX > dynamic threshold
            (
                dataframe["adx_1h"] > dataframe["dynamic_adx_threshold"]
                if "adx_1h" in dataframe.columns
                else True
            )
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Custom exit signals will be handled by custom_exit method
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time,
        current_rate,
        current_profit: float,
        dataframe: DataFrame,
        **kwargs,
    ) -> str:
        """
        Dynamic exit based on ADX market state:
        - Strong trend (ADX > 30): Exit at 7% profit
        - Normal trend (ADX 15-25): Exit at 5.5% profit
        - No trend (ADX < 15): Exit at 3% profit
        """
        adx_1h = dataframe["adx_1h"] if "adx_1h" in dataframe.columns else dataframe["adx"]
        current_adx = adx_1h.iloc[-1] if len(dataframe) > 0 else 25

        # Determine target ROI based on ADX
        if current_adx > 30:
            # Strong Trend: Take 7% profit
            target_roi = 0.07
        elif current_adx < 15:
            # No Trend: Take 3% profit
            target_roi = 0.03
        else:
            # Normal Trend: Take 5.5% profit
            target_roi = 0.055

        # Exit if profit target is reached
        if current_profit >= target_roi:
            return f"dynamic_roi_{target_roi:.3f}"

        return None

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
