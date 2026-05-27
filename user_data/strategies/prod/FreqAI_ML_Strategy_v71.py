# FreqAI_ML_Strategy V70 - All-Weather Strategy with Market Regime Detection
#
# V70 Key Features:
# ✅ Market Regime Detection: Uptrend, Downtrend, Sideways, High Volatility
# ✅ Different logic per regime (entries, exits, stops, position sizing)
# ✅ 4-period testing: up, down, sideways, full year
# ✅ Regime-adaptive ML thresholds
# ✅ Multi-signal confirmation per regime
#
# Regime Detection Logic:
# - Uptrend: EMA fast > EMA slow, ADX > 25, low volatility
# - Downtrend: EMA fast < EMA slow, ADX > 25
# - Sideways: ADX < 25, low volatility, EMA converging
# - High Volatility: ATR high relative to history, volatility > 80th percentile

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    BooleanParameter,
    CategoricalParameter,
)
import freqtrade.vendor.qtpylib.indicators as qtpylib
import logging
from pandas import DataFrame
from typing import Dict, List, Optional, Union
from datetime import datetime, timezone
import warnings

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class FreqAI_ML_Strategy_v71(IStrategy):
    # FORCE RELOAD - v70.3.1
    """
    FreqAI ML Strategy V70 - All-Weather with Regime Detection

    V70 Mission: Different logic per market regime
    - Uptrend: Follow trends, wider stops, trail gains
    - Downtrend: Mean reversion, tighter stops, smaller size
    - Sideways: Range-bound play, scalping, quick exits
    - High Volatility: Defensive, minimal exposure, news-driven

    Regime Detection:
    - Uptrend: ema_fast > ema_slow AND ADX > 25 AND close > ema_medium
    - Downtrend: ema_fast < ema_slow AND ADX > 25 AND close < ema_medium
    - Sideways: ADX < 25 AND abs(ema_fast - ema_slow) / ema_slow < 0.01
    - High Volatility: ATR percentile > 80 OR volatility > 2x median
    """

    INTERFACE_VERSION = 3

    # ===========================================
    # FREQAI CONFIGURATION
    # ===========================================
    freqai_enabled = True

    # ===========================================
    # TIMEFRAME & CONFIG
    # ===========================================
    timeframe = "15m"
    informative_timeframes = ["1h", "4h"]

    # ===========================================
    # STOPLOSS & TRAILING - REGIME ADAPTED
    # ===========================================
    stoploss = -0.12

    trailing_stop = True
    trailing_stop_positive = 0.005  # 0.5% base
    trailing_stop_positive_offset = 0.015  # 1.5% offset
    trailing_only_offset_is_reached = True

    minimal_roi = {
        "0": 0.10,  # 10% in 0 min (aggressive)
        "60": 0.05,  # 5% in 60 min
        "120": 0.03,  # 3% in 120 min
        "240": 0.02,  # 2% in 240 min (fallback)
    }

    can_short = True
    startup_candle_count = 80
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # ===========================================
    # REGIME-SPECIFIC PARAMETERS
    # ===========================================

    # Uptrend parameters
    uptrend_confidence_threshold = DecimalParameter(
        0.50, 0.80, default=0.55, decimals=2, space="buy"
    )
    uptrend_prediction_threshold = DecimalParameter(
        0.50, 0.75, default=0.55, decimals=2, space="buy"
    )
    uptrend_adx_min = DecimalParameter(20, 35, default=20, decimals=0, space="buy")

    # Downtrend parameters
    downtrend_confidence_threshold = DecimalParameter(
        0.55, 0.85, default=0.65, decimals=2, space="buy"
    )
    downtrend_prediction_threshold = DecimalParameter(
        0.55, 0.80, default=0.65, decimals=2, space="buy"
    )
    downtrend_adx_min = DecimalParameter(20, 35, default=20, decimals=0, space="buy")

    # Sideways parameters
    sideways_confidence_threshold = DecimalParameter(
        0.60, 0.90, default=0.70, decimals=2, space="buy"
    )
    sideways_prediction_threshold = DecimalParameter(
        0.60, 0.85, default=0.70, decimals=2, space="buy"
    )

    # High Volatility parameters
    volatile_confidence_threshold = DecimalParameter(
        0.65, 0.90, default=0.75, decimals=2, space="buy"
    )
    volatile_prediction_threshold = DecimalParameter(
        0.65, 0.85, default=0.72, decimals=2, space="buy"
    )

    # ===========================================
    # REGIME DETECTION SETTINGS
    # ===========================================
    regime_detection_enabled = BooleanParameter(default=True, space="buy")
    regime_lookback_period = IntParameter(50, 200, default=100, space="buy")
    regime_adx_period = IntParameter(10, 20, default=14, space="buy")

    # ===========================================
    # POSITION SIZING BY REGIME
    # ===========================================
    dynamic_position_sizing = BooleanParameter(default=True, space="buy")
    base_risk_factor = DecimalParameter(0.5, 2.0, default=1.0, decimals=1, space="buy")

    # Position sizing multipliers per regime
    uptrend_position_mult = DecimalParameter(1.0, 2.0, default=1.3, decimals=1, space="buy")
    downtrend_position_mult = DecimalParameter(0.3, 0.8, default=0.5, decimals=1, space="buy")
    sideways_position_mult = DecimalParameter(0.5, 1.0, default=0.7, decimals=1, space="buy")
    volatile_position_mult = DecimalParameter(0.2, 0.6, default=0.4, decimals=1, space="buy")

    # ===========================================
    # TRAILING STOP BY REGIME
    # ===========================================
    uptrend_trailing_offset = DecimalParameter(0.015, 0.04, default=0.025, decimals=3, space="buy")
    downtrend_trailing_offset = DecimalParameter(
        0.008, 0.02, default=0.012, decimals=3, space="buy"
    )
    sideways_trailing_offset = DecimalParameter(
        0.005, 0.015, default=0.008, decimals=3, space="buy"
    )
    volatile_trailing_offset = DecimalParameter(0.01, 0.025, default=0.015, decimals=3, space="buy")

    def informative_pairs(self):
        """Expand informative pairs"""
        pairs = self.dp.current_whitelist()
        informative_pairs = []

        for tf in self.informative_timeframes:
            informative_pairs.extend([(pair, tf) for pair in pairs])

        # Add major correlated assets
        major_pairs = ["BTC/USDT", "ETH/USDT", "SPY/USDT"]
        for pair in major_pairs:
            if pair not in [p[0] for p in informative_pairs]:
                for tf in self.informative_timeframes:
                    informative_pairs.append((pair, tf))

        return informative_pairs

    def calc_smma(self, series, period=20):
        """Calculate Smoothed Moving Average"""
        return series.ewm(alpha=1 / period, min_periods=period).mean()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        V70 All-Weather Indicator System
        Includes regime detection and regime-specific features
        """

        # ===========================================
        # BASIC TECHNICAL INDICATORS
        # ===========================================

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_sma"] = ta.SMA(dataframe["rsi"], timeperiod=14)

        # EMA System
        for period in [8, 12, 21, 26, 50, 200]:
            dataframe[f"ema_{period}"] = ta.EMA(dataframe, timeperiod=period)

        dataframe["ema_fast"] = dataframe["ema_12"]
        dataframe["ema_slow"] = dataframe["ema_26"]
        dataframe["ema_medium"] = dataframe["ema_50"]

        # MACD
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # Bollinger Bands
        bbands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bbands["upperband"]
        dataframe["bb_middle"] = bbands["middleband"]
        dataframe["bb_lower"] = bbands["lowerband"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe[
            "bb_middle"
        ]
        dataframe["bb_percent"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"] + 1e-10
        )

        # ATR (Volatility)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_percentile"] = (
            dataframe["atr"]
            .rolling(100)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
        )

        # ADX (Trend Strength)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # CCI
        dataframe["cci"] = ta.CCI(dataframe, timeperiod=20)

        # Stochastic
        dataframe["stoch_k"], dataframe["stoch_d"] = ta.STOCH(
            dataframe,
            fastk_period=14,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=3,
            slowd_matype=0,
        )

        # VWAP
        dataframe["vwap"] = qtpylib.rolling_vwap(dataframe, window=8, min_periods=8)

        # ===========================================
        # VOLUME INDICATORS (V70: SMMA-based)
        # ===========================================
        dataframe["volume_smma"] = self.calc_smma(dataframe["volume"], 20)
        dataframe["volume_ratio"] = dataframe["volume"] / (dataframe["volume_smma"] + 1e-10)
        dataframe["obv"] = ta.OBV(dataframe)
        dataframe["ad"] = ta.AD(dataframe)
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)

        # ===========================================
        # VOLATILITY INDICATORS
        # ===========================================
        dataframe["atr_ratio"] = dataframe["atr"] / self.calc_smma(dataframe["atr"], 20)
        dataframe["realized_volatility"] = dataframe["close"].rolling(20).std()
        dataframe["volatility_ratio"] = dataframe["atr"] / (
            dataframe["realized_volatility"] + 1e-10
        )
        dataframe["high_volatility"] = dataframe["volatility_ratio"] > dataframe[
            "volatility_ratio"
        ].rolling(50).quantile(0.80)

        # ===========================================
        # PRICE ACTION INDICATORS
        # ===========================================
        dataframe["price_momentum"] = dataframe["close"].pct_change(5)
        dataframe["price_acceleration"] = dataframe["price_momentum"].diff()

        # Higher highs / lower lows
        dataframe["higher_high"] = dataframe["high"] > dataframe["high"].shift(1)
        dataframe["lower_low"] = dataframe["low"] < dataframe["low"].shift(1)

        # ===========================================
        # MICROSTRUCTURE FEATURES
        # ===========================================
        dataframe["buy_pressure"] = np.where(
            dataframe["close"] > dataframe["open"],
            dataframe["volume"]
            * (dataframe["close"] - dataframe["open"])
            / (dataframe["high"] - dataframe["low"] + 1e-10),
            0,
        )
        dataframe["sell_pressure"] = np.where(
            dataframe["close"] < dataframe["open"],
            dataframe["volume"]
            * (dataframe["open"] - dataframe["close"])
            / (dataframe["high"] - dataframe["low"] + 1e-10),
            0,
        )
        dataframe["pressure_ratio"] = dataframe["buy_pressure"] / (
            dataframe["sell_pressure"] + 1e-10
        )
        dataframe["liquidity_proxy"] = dataframe["volume"] / (dataframe["atr"] + 1e-10)

        # ===========================================
        # MULTI-TIMEFRAME FEATURES
        # ===========================================
        dataframe = self.add_multi_timeframe_features(dataframe, metadata)

        # ===========================================
        # CORE: MARKET REGIME DETECTION
        # ===========================================
        dataframe = self.detect_market_regime(dataframe)

        # ===========================================
        # SIGNAL QUALITY
        # ===========================================
        dataframe = self.calculate_signal_quality(dataframe)

        # ===========================================
        # FREQAI ML FEATURES
        # ===========================================
        try:
            if self.freqai_enabled and hasattr(self, "freqai"):
                dataframe = self.freqai.start(dataframe, metadata, self)
            else:
                dataframe["&ml_prediction"] = 0.50
                dataframe["&ml_confidence"] = 0.50
        except Exception as e:
            dataframe["&ml_prediction"] = 0.50
            dataframe["&ml_confidence"] = 0.50

        return dataframe

    def add_multi_timeframe_features(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Multi-timeframe confirmation features"""

        for tf in self.informative_timeframes:
            try:
                informative = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=tf)

                informative[f"rsi_{tf}"] = ta.RSI(informative, timeperiod=14)
                informative[f"ema_21_{tf}"] = ta.EMA(informative, timeperiod=21)
                informative[f"volume_ratio_{tf}"] = informative["volume"] / self.calc_smma(
                    informative["volume"], 20
                )
                informative[f"adx_{tf}"] = ta.ADX(informative, timeperiod=14)

                # Trend detection on higher TF
                informative[f"trend_up_{tf}"] = informative["ema_21_{tf}"] > informative[
                    "ema_21_{tf}"
                ].shift(5)

                dataframe = self.merge_informative_pair_safe(
                    dataframe, informative, self.timeframe, tf, ffill=True
                )

            except Exception as e:
                logger.warning(f"Failed to add {tf} timeframe data: {e}")
                continue

        return dataframe

    def merge_informative_pair_safe(
        self, dataframe, informative, timeframe, tf, ffill=True, bm_append=False
    ):
        """Safe merge for informative pairs"""
        from freqtrade.strategy import merge_informative_pair

        return merge_informative_pair(
            dataframe, informative, timeframe, tf, ffill=ffill, bm_append=bm_append
        )

    def detect_market_regime(self, dataframe: DataFrame) -> DataFrame:
        """
        V70 CORE: Multi-Factor Market Regime Detection

        Regimes:
        1. UPTREND: Bullish, trending upward
        2. DOWNTREND: Bearish, trending downward
        3. SIDEWAYS: Ranging, low ADX, converging EMAs
        4. HIGH_VOLATILITY: Elevated volatility, uncertain direction
        """

        lookback = self.regime_lookback_period.value
        adx_period = self.regime_adx_period.value

        # ---- Calculate regime indicators ----

        # EMA Trend
        dataframe["ema_trend_strength"] = (
            dataframe["ema_fast"] - dataframe["ema_slow"]
        ) / dataframe["ema_slow"]
        dataframe["ema_convergence"] = (
            np.abs(dataframe["ema_fast"] - dataframe["ema_slow"]) / dataframe["ema_slow"]
        )

        # Price vs EMAs
        dataframe["price_vs_ema_medium"] = (
            dataframe["close"] - dataframe["ema_medium"]
        ) / dataframe["ema_medium"]
        dataframe["price_vs_vwap"] = (dataframe["close"] - dataframe["vwap"]) / dataframe["vwap"]

        # ADX-based trend strength
        dataframe["adx_strong"] = dataframe["adx"] > self.uptrend_adx_min.value

        # DI-based direction
        dataframe["di_bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["di_bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        # Volatility percentile
        dataframe["volatility_percentile"] = (
            dataframe["volatility_ratio"]
            .rolling(lookback)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
        )

        # ---- Regime Classification ----

        # Initialize as neutral
        dataframe["market_regime"] = "neutral"

        # SIDEWAYS (low ADX, EMAs converging)
        sideways_condition = (
            (dataframe["adx"] < 20)
            & (dataframe["ema_convergence"] < 0.01)
            & (dataframe["volatility_percentile"] < 0.7)
        )
        dataframe.loc[sideways_condition, "market_regime"] = "sideways"

        # HIGH VOLATILITY (high volatility even if trending) - lowered to 90th percentile
        high_vol_condition = (dataframe["volatility_percentile"] > 0.90) | (
            dataframe["high_volatility"] == True
        )
        dataframe.loc[high_vol_condition, "market_regime"] = "volatile"

        # UPTREND (EMA bullish, ADX strong, price above EMAs)
        uptrend_condition = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["close"] > dataframe["ema_medium"])
            & (dataframe["adx"] >= self.uptrend_adx_min.value)
            & (dataframe["di_bullish"] == True)
        )
        dataframe.loc[uptrend_condition, "market_regime"] = "uptrend"

        # DOWNTREND (EMA bearish, ADX strong, price below EMAs)
        downtrend_condition = (
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["close"] < dataframe["ema_medium"])
            & (dataframe["adx"] >= self.downtrend_adx_min.value)
            & (dataframe["di_bearish"] == True)
        )
        dataframe.loc[downtrend_condition, "market_regime"] = "downtrend"

        # Override with high volatility if present
        high_vol_override = (
            dataframe["market_regime"].isin(["uptrend", "downtrend", "sideways"])
            & high_vol_condition
        )
        dataframe.loc[high_vol_override, "market_regime"] = "volatile"

        # ---- Regime-specific indicators ----
        dataframe["regime_is_uptrend"] = (dataframe["market_regime"] == "uptrend").astype(int)
        dataframe["regime_is_downtrend"] = (dataframe["market_regime"] == "downtrend").astype(int)
        dataframe["regime_is_sideways"] = (dataframe["market_regime"] == "sideways").astype(int)
        dataframe["regime_is_volatile"] = (dataframe["market_regime"] == "volatile").astype(int)

        return dataframe

    def calculate_signal_quality(self, dataframe: DataFrame) -> DataFrame:
        """Calculate comprehensive signal quality scores"""

        # SMC Score
        dataframe["smc_score"] = (
            (dataframe["close"] > dataframe["vwap"]).astype(float) * 0.30
            + (dataframe["ema_fast"] > dataframe["ema_slow"]).astype(float) * 0.25
            + ((dataframe["rsi"] > 30) & (dataframe["rsi"] < 70)).astype(float) * 0.20
            + (dataframe["volume_ratio"] > 1.0).astype(float) * 0.15
            + (dataframe["adx"] > 20).astype(float) * 0.10
        )

        # Signal Quality (normalized)
        dataframe["signal_quality"] = (
            dataframe["smc_score"] * 0.5
            + ((dataframe["rsi"] - 30) / 40).clip(0, 1) * 0.25
            + (dataframe["volume_ratio"] / 2).clip(0, 1) * 0.25
        )

        # Momentum Score
        dataframe["momentum_score"] = (
            (dataframe["price_momentum"] > 0).astype(float) * 0.30
            + (dataframe["macdhist"] > 0).astype(float) * 0.30
            + (dataframe["cci"] > -100).astype(float) * 0.20
            + (dataframe["stoch_k"] > dataframe["stoch_d"]).astype(float) * 0.20
        )

        return dataframe

    def populate_entry_trend(self, DataFrame: DataFrame, metadata: dict) -> DataFrame:
        """
        V70 REGIME-ADAPTIVE ENTRY LOGIC

        Uptrend: Trend-following entries with momentum confirmation
        Downtrend: Mean reversion or short selling with tight stops
        Sideways: Range-bound entries at boundaries
        Volatile: Minimal exposure, high threshold entries
        """

        # ML signals
        if self.freqai_enabled:
            ml_prediction = DataFrame.get("&ml_prediction", 0.5)
            ml_confidence = DataFrame.get("&ml_confidence", 0.5)
        else:
            ml_prediction = 0.50
            ml_confidence = 0.50

        regime = DataFrame["market_regime"]

        # ===========================================
        # SELECT THRESHOLDS BY REGIME
        # ===========================================
        confidence_thresh = np.where(
            regime == "uptrend",
            self.uptrend_confidence_threshold.value,
            np.where(
                regime == "downtrend",
                self.downtrend_confidence_threshold.value,
                np.where(
                    regime == "sideways",
                    self.sideways_confidence_threshold.value,
                    self.volatile_confidence_threshold.value,
                ),
            ),
        )

        prediction_thresh = np.where(
            regime == "uptrend",
            self.uptrend_prediction_threshold.value,
            np.where(
                regime == "downtrend",
                self.downtrend_prediction_threshold.value,
                np.where(
                    regime == "sideways",
                    self.sideways_prediction_threshold.value,
                    self.volatile_prediction_threshold.value,
                ),
            ),
        )

        # ===========================================
        # BASE CONDITIONS (Universal)
        # ===========================================
        # V70.3 FIX: Detect if ML model is active (not fallback values)
        has_ml_signal = (ml_prediction != 0.50) | (ml_confidence != 0.50)

        base_condition = (
            (DataFrame["volume"] > 0) & (DataFrame["volume_ratio"] > 0.8) & (DataFrame["atr"] > 0)
        )

        # Price relative to VWAP
        price_above_vwap = DataFrame["close"] > DataFrame["vwap"]
        price_below_vwap = DataFrame["close"] < DataFrame["vwap"]

        # ===========================================
        # UPTREND ENTRIES (Long) - V70.1 FIX
        # Added momentum confirmation to avoid false uptrend entries
        # ===========================================
        uptrend_momentum = (
            (DataFrame["macdhist"] > 0)  # MACD bullish
            & (DataFrame["rsi"] < 70)  # Not overbought
            & (DataFrame["ema_fast"] > DataFrame["ema_slow"])  # EMA confirmation
            & (DataFrame["plus_di"] > DataFrame["minus_di"] + 5)  # Strong DI+ lead
        )

        uptrend_entry = (
            (regime == "uptrend")
            & base_condition
            & price_above_vwap
            & (DataFrame["volume_ratio"] > 1.2)
            & (DataFrame["smc_score"] >= 0.50)
            & (DataFrame["adx"] >= self.uptrend_adx_min.value)
            & uptrend_momentum
            &
            # V70.3: Uptrend requires ML signal - skip if no model
            (has_ml_signal & (ml_prediction > prediction_thresh))
            & (has_ml_signal & (ml_confidence > confidence_thresh))
        )

        # ===========================================
        # DOWNTREND ENTRIES (Short) - V70.2 FIX
        # Relaxed ML threshold + added bearish momentum confirmation
        # ===========================================
        downtrend_momentum = (
            (DataFrame["macdhist"] < 0)  # MACD bearish
            & (DataFrame["rsi"] > 30)  # Not oversold (room to fall)
            & (DataFrame["ema_fast"] < DataFrame["ema_slow"])  # EMA death cross
            & (DataFrame["minus_di"] > DataFrame["plus_di"] + 5)  # Strong DI- lead
        )

        # ===========================================
        # DOWNTREND ENTRIES (Short) - V70.3 FIX
        # Without ML model: use fixed threshold of 0.5 (neutral)
        # With ML model: use configured threshold
        # ===========================================
        # Use effective threshold: if no ML model, require prediction < 0.5 (neutral/bearish)
        effective_pred_thresh = np.where(has_ml_signal, (1 - prediction_thresh), 0.50)
        effective_conf_thresh = np.where(has_ml_signal, confidence_thresh, 0.50)

        downtrend_entry = (
            (regime == "downtrend")
            & base_condition
            & price_below_vwap
            & (DataFrame["volume_ratio"] > 1.2)
            & (DataFrame["smc_score"] >= 0.50)
            & (DataFrame["adx"] >= self.downtrend_adx_min.value)
            & downtrend_momentum
            & (ml_prediction < effective_pred_thresh)
            & (ml_confidence > effective_conf_thresh)
        )

        # ===========================================
        # SIDEWAYS ENTRIES (Range-bound)
        # ===========================================
        # Long at lower band, short at upper band
        near_lower_band = DataFrame["close"] < (DataFrame["bb_lower"] * 1.02)
        near_upper_band = DataFrame["close"] > (DataFrame["bb_upper"] * 0.98)

        sideways_entry_long = (
            (regime == "sideways")
            & base_condition
            & near_lower_band
            & (DataFrame["volume_ratio"] > 1.1)
            & (DataFrame["bb_percent"] < 0.25)
            & (DataFrame["smc_score"] >= 0.45)
        )

        sideways_entry_short = (
            (regime == "sideways")
            & base_condition
            & near_upper_band
            & (DataFrame["volume_ratio"] > 1.1)
            & (DataFrame["bb_percent"] > 0.75)
            & (DataFrame["smc_score"] >= 0.45)
        )

        # ===========================================
        # HIGH VOLATILITY ENTRIES (Minimal exposure)
        # ===========================================
        volatile_entry = (
            (regime == "volatile")
            & base_condition
            & (ml_prediction > (prediction_thresh + 0.05))
            & (ml_confidence > (confidence_thresh + 0.05))
            & (DataFrame["volume_ratio"] > 1.5)
            & (DataFrame["smc_score"] >= 0.60)
            & (DataFrame["adx"] >= self.downtrend_adx_min.value)
        )

        # ===========================================
        # APPLY ENTRIES
        # ===========================================
        DataFrame.loc[uptrend_entry, "enter_long"] = 1
        DataFrame.loc[downtrend_entry, "enter_short"] = 1
        DataFrame.loc[sideways_entry_long, "enter_long"] = 1
        DataFrame.loc[sideways_entry_short, "enter_short"] = 1
        DataFrame.loc[volatile_entry, "enter_long"] = 1

        return DataFrame

    def populate_exit_trend(self, DataFrame: DataFrame, metadata: dict) -> DataFrame:
        """
        V70.3 REGIME-ADAPTIVE EXIT LOGIC

        Key fixes:
        - Separate long/short exit logic per regime
        - Short exits on bullish reversal signals (not bearish continuation)
        - Sideways: Long exit at upper band, Short exit at lower band
        """

        regime = DataFrame["market_regime"]

        # ===========================================
        # UNIVERSAL TIME-BASED EXIT (all regimes)
        # ===========================================
        # Exit any trade after 4 hours to prevent overholding
        # This is handled by ROI table: 0: 10%, 60: 5%, 120: 3%, 240: 2%

        # ===========================================
        # UPTREND EXITS (Long only)
        # Exit when trend reverses: price below VWAP + EMA death cross
        # ===========================================
        uptrend_exit = (
            (regime == "uptrend")
            & (DataFrame["close"] < DataFrame["vwap"])
            & (DataFrame["ema_fast"] < DataFrame["ema_slow"])
        )

        # ===========================================
        # DOWNTREND EXITS (Short only)
        # Exit short when: MACD turns bullish OR EMA crosses up OR oversold bounce
        # ===========================================
        downtrend_exit_short = (regime == "downtrend") & (
            (DataFrame["macdhist"] > 0)
            | (DataFrame["ema_fast"] > DataFrame["ema_slow"])
            | (DataFrame["rsi"] < 25)
        )

        # ===========================================
        # SIDEWAYS EXITS
        # Long: exit at upper band (profit target)
        # Short: exit at lower band (profit target)
        # Both: exit if trend emerging (ADX > 30)
        # ===========================================
        sideways_exit_long = (regime == "sideways") & (
            (DataFrame["bb_percent"] > 0.75) | (DataFrame["adx"] > self.downtrend_adx_min.value)
        )

        sideways_exit_short = (regime == "sideways") & (
            (DataFrame["bb_percent"] < 0.25) | (DataFrame["adx"] > self.downtrend_adx_min.value)
        )

        # ===========================================
        # HIGH VOLATILITY EXITS
        # ===========================================
        volatile_exit_long = (regime == "volatile") & (
            (DataFrame["rsi"] > 80) | (DataFrame["volume_ratio"] > 2.5)
        )

        volatile_exit_short = (regime == "volatile") & (
            (DataFrame["rsi"] < 20) | (DataFrame["volume_ratio"] > 2.5)
        )

        # ===========================================
        # APPLY EXITS
        # ===========================================
        DataFrame.loc[uptrend_exit, "exit_long"] = 1
        DataFrame.loc[downtrend_exit_short, "exit_short"] = 1
        DataFrame.loc[sideways_exit_long, "exit_long"] = 1
        DataFrame.loc[sideways_exit_short, "exit_short"] = 1
        DataFrame.loc[volatile_exit_long, "exit_long"] = 1
        DataFrame.loc[volatile_exit_short, "exit_short"] = 1

        return DataFrame

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> bool:
        """Trade entry confirmation with regime check"""

        try:
            DataFrame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(DataFrame) == 0:
                return False

            current_candle = DataFrame.iloc[-1].squeeze()

            # Volume check
            if current_candle.get("volume", 0) == 0:
                return False

            # Regime-based confirmation
            regime = current_candle.get("market_regime", "neutral")

            # High volatility = need extra confirmation
            if regime == "volatile":
                if current_candle.get("volume_ratio", 1) < 1.5:
                    return False

            # Sideways = need band confirmation
            if regime == "sideways":
                pressure = current_candle.get("pressure_ratio", 1.0)
                if pressure < 1.2:
                    return False

            return True

        except Exception as e:
            logger.warning(f"Trade confirmation failed for {pair}: {e}")
            return False

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ) -> Optional[Union[str, bool]]:
        """
        V70 Custom exit - Regime-aware exit logic

        Exits based on:
        1. Regime change
        2. Profit targets per regime
        3. Max duration
        4. Hard stop loss
        """

        try:
            DataFrame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(DataFrame) == 0:
                return None

            current_candle = DataFrame.iloc[-1].squeeze()
            regime = current_candle.get("market_regime", "neutral")

            # Trade duration
            if hasattr(trade, "open_date_utc"):
                open_date = trade.open_date_utc
            else:
                open_date = trade.open_date

            if open_date.tzinfo is None:
                open_date = open_date.replace(tzinfo=timezone.utc)
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)

            duration_minutes = (current_time - open_date).total_seconds() / 60

            # Regime-specific profit targets
            if regime == "uptrend":
                # Hold for larger gains in uptrend
                if current_profit >= 0.08:  # 8%
                    return f"UPTREND_TARGET: {current_profit:.3f}"
                if duration_minutes >= 360:  # 6 hours
                    return f"UPTREND_MAX_TIME: {current_profit:.3f}"

            elif regime == "downtrend":
                # Quick exits in downtrend
                if current_profit >= 0.04:  # 4%
                    return f"DOWNTREND_TARGET: {current_profit:.3f}"
                if duration_minutes >= 120:  # 2 hours
                    return f"DOWNTREND_MAX_TIME: {current_profit:.3f}"

            elif regime == "sideways":
                # Scalp in sideways
                if current_profit >= 0.02:  # 2%
                    return f"SIDEWAYS_TARGET: {current_profit:.3f}"
                if duration_minutes >= 90:  # 90 min
                    return f"SIDEWAYS_MAX_TIME: {current_profit:.3f}"

            elif regime == "volatile":
                # Minimal gains, quick exits
                if current_profit >= 0.03:  # 3%
                    return f"VOLATILE_TARGET: {current_profit:.3f}"
                if duration_minutes >= 60:  # 1 hour
                    return f"VOLATILE_MAX_TIME: {current_profit:.3f}"

            # Regime change exit
            if regime == "volatile":
                return f"REGIME_VOLATILE: {current_profit:.3f}"

            # ML exit in strong move against
            if self.freqai_enabled:
                ml_prediction = current_candle.get("&ml_prediction", 0.5)
                ml_confidence = current_candle.get("&ml_confidence", 0.5)

                if (ml_prediction < 0.35 and ml_confidence > 0.70) or (
                    ml_prediction > 0.65 and ml_confidence > 0.70
                ):
                    return f"ML_REVERSAL: {current_profit:.3f}"

            # Hard stop loss
            if current_profit <= -0.10:
                return f"HARD_STOP: {current_profit:.3f}"

            return None

        except Exception as e:
            logger.warning(f"Custom exit error for {pair}: {e}")
            return None

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake: float,
        max_stake: float,
        **kwargs,
    ) -> float:
        """
        V70 Dynamic Position Sizing by Regime
        """

        if not self.dynamic_position_sizing.value:
            return proposed_stake

        try:
            DataFrame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(DataFrame) == 0:
                return proposed_stake

            current_candle = DataFrame.iloc[-1].squeeze()
            regime = current_candle.get("market_regime", "neutral")

            # Base multiplier
            base = self.base_risk_factor.value

            # Regime-specific position sizing
            if regime == "uptrend":
                position_mult = self.uptrend_position_mult.value
            elif regime == "downtrend":
                position_mult = self.downtrend_position_mult.value
            elif regime == "sideways":
                position_mult = self.sideways_position_mult.value
            elif regime == "volatile":
                position_mult = self.volatile_position_mult.value
            else:
                position_mult = 0.5

            # Confidence adjustment
            if self.freqai_enabled:
                ml_confidence = current_candle.get("&ml_confidence", 0.5)
                conf_adj = 0.5 + ml_confidence * 1.0
            else:
                conf_adj = 1.0

            stake = proposed_stake * base * position_mult * conf_adj

            # Clamp to allowed range
            return max(min_stake, min(max_stake, stake))

        except Exception as e:
            logger.warning(f"Stake amount calculation failed: {e}")
            return proposed_stake

    def adjust_trade_position(
        self,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        min_stake: float,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        **kwargs,
    ) -> Optional[float]:
        """
        V70 Dynamic position adjustment per regime

        Uptrend: Add to winners
        Downtrend: Reduce exposure
        Sideways: No adding
        Volatile: Reduce fast
        """

        try:
            DataFrame, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
            if len(DataFrame) == 0:
                return None

            current_candle = DataFrame.iloc[-1].squeeze()
            regime = current_candle.get("market_regime", "neutral")

            # Only in uptrend add to winners
            if regime == "uptrend" and current_profit > 0.05:
                add_amount = min_stake * 0.5
                return add_amount

            # In volatile, reduce exposure
            if regime == "volatile" and current_profit > 0.02:
                return -min_stake * 0.5  # Take partial profit

            return None

        except Exception as e:
            logger.warning(f"Position adjustment failed: {e}")
            return None
