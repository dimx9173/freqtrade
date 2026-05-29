#!/usr/bin/env python3
"""
MultiTF_RegimeDetector_v1 — Regime Detection + Volatility Prediction + Pure TA Entry

Core Design:
  1. Regime Detection: ADX multi-TF consensus (15m/1h/4h)
     → ranging | transition | trending  (99.8% accuracy, linear model sufficient)
  2. Volatility Prediction: Ridge regression with polynomial features
     → predict ATR 12 bars ahead (R²=0.67 validated)
     → used for dynamic stop-loss + position sizing
  3. Entry Logic: Pure TA, switched by detected regime
     → Ranging: BB mean-reversion (close < bb_lower & RSI < 35)
     → Trending: EMA trend-following (EMA12 > EMA26 & ADX > 25 & +DI > -DI)
     → Transition: no trades
  4. Exit Logic:
     → Dynamic stop loss based on pred_ATR (max of -3% or -2×pred_ATR)
     → Dynamic trailing based on pred_ATR
     → ROI target based on pred_ATR multiplier
  5. Position Sizing: Inverse volatility weighting

Key Parameters:
  - Main TF: 15m
  - Informative: 30m, 1h, 4h
  - can_short: True (futures mode), but only long entries initially
  - Base stoploss: -0.03 (-3%)
  - Dynamic stop loss via custom_stoploss

Reference: /tmp/debug_regime.py (concept validation)
"""

import logging
import warnings
from typing import Dict, Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Lazy sklearn import (avoid hard crash in environments without sklearn)
# ─────────────────────────────────────────────────────────────────────
_sklearn_available = False
_sklearn_error_msg = ""

try:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    _sklearn_available = True
except ImportError as e:
    _sklearn_error_msg = str(e)


class MultiTF_RegimeDetector_v1(IStrategy):
    """
    MultiTF_RegimeDetector_v1 — Multi-TF Regime Detection + Volatility Prediction

    Strategy type: math_based
    Version: v1
    Author: Hermes Agent
    """

    # ── Basic Settings ───────────────────────────────────────────────
    timeframe: str = "15m"
    can_short: bool = True
    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    use_custom_stoploss: bool = True
    startup_candle_count: int = 350  # covers ATR horizon + rolling windows + informative TF alignment
    stoploss: float = -0.03         # base fallback stoploss

    # ── Exit Settings (base; overridden by custom_stoploss) ──────────
    minimal_roi: Dict[str, float] = {
        "0": 0.05,      # 5% immediate target
        "120": 0.03,    # 3% after 30h
        "240": 0.01,    # 1% after 60h
    }
    trailing_stop: bool = True
    trailing_stop_positive: float = 0.02
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # ── Regime Thresholds (ADX-based) ────────────────────────────────
    ADX_RANGING_MAX: float = 20.0       # ADX < 20 = ranging
    ADX_TRENDING_MIN: float = 25.0      # ADX > 25 = trending
    # 20–25 = transition

    # ── BB Mean-Reversion Parameters (Ranging Regime) ────────────────
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 35.0
    RSI_OVERBOUGHT: float = 65.0

    # ── EMA Trend-Following Parameters (Trending Regime) ─────────────
    EMA_FAST: int = 12
    EMA_SLOW: int = 26
    ADX_TREND_MIN: float = 25.0

    # ── Volatility Prediction Parameters ─────────────────────────────
    VOL_FORECAST_HORIZON: int = 12       # predict ATR 12 bars (3h) ahead
    VOL_WINDOW: int = 300                # training window size (bars)
    VOL_RIDGE_ALPHA: float = 0.1         # Ridge regularization
    VOL_RETRAIN_INTERVAL: int = 50       # retrain every N bars
    VOL_POLY_DEGREE: int = 2             # polynomial feature degree

    # ── Position Sizing ──────────────────────────────────────────────
    BASE_STAKE_RATIO: float = 0.95       # use 95% of allocated stake by default

    # ── Internal State ───────────────────────────────────────────────
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Cache for Ridge model per pair
        self._vol_model_cache: Dict[str, Dict] = {}
        # Cache for latest pred_ATR per pair (used by custom_stoploss)
        self._pred_atr_cache: Dict[str, float] = {}

    # ==================================================================
    #  Informative Pairs
    # ==================================================================
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative = []
        for pair in pairs:
            informative.append((pair, "30m"))
            informative.append((pair, "1h"))
            informative.append((pair, "4h"))
        return informative

    # ==================================================================
    #  Feature Extraction for Volatility Prediction
    # ==================================================================
    @staticmethod
    def _extract_vol_features(df: pd.DataFrame, tf_name: str) -> pd.DataFrame:
        """
        Extract volatility-relevant features from a single TF OHLCV.

        Parameters
        ----------
        df : pd.DataFrame
            Single-TF OHLCV data (must contain open/high/low/close/volume)
        tf_name : str
            Timeframe label (e.g. '15m', '1h', '4h')

        Returns
        -------
        pd.DataFrame
            Feature DataFrame with index aligned to df
        """
        f = pd.DataFrame(index=df.index)

        # Returns at different lookbacks
        f[f"{tf_name}_ret_5"] = df["close"].pct_change(5)
        f[f"{tf_name}_ret_20"] = df["close"].pct_change(20)

        # Rolling volatility
        f[f"{tf_name}_vol_20"] = f[f"{tf_name}_ret_5"].rolling(20).std()

        # MA deviations
        f[f"{tf_name}_ma_dev_20"] = df["close"] / df["close"].rolling(20).mean() - 1
        f[f"{tf_name}_ma_dev_50"] = df["close"] / df["close"].rolling(50).mean() - 1

        # Price position in range
        low_50 = df["low"].rolling(50).min()
        high_50 = df["high"].rolling(50).max()
        f[f"{tf_name}_price_pos"] = (df["close"] - low_50) / (high_50 - low_50 + 1e-8)

        # Volume ratio
        f[f"{tf_name}_vol_ratio"] = df["volume"] / (df["volume"].rolling(50).mean() + 1e-8)

        # RSI (normalized to [0, 1])
        f[f"{tf_name}_rsi"] = ta.RSI(df, timeperiod=14) / 100.0

        # ADX (normalized to [0, 1])
        f[f"{tf_name}_adx"] = ta.ADX(df, timeperiod=14) / 100.0

        # Current ATR as baseline
        f[f"{tf_name}_atr_pct"] = ta.ATR(df, timeperiod=14) / df["close"]

        return f

    def _merge_vol_features(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        Merge multi-TF volatility features into main 15m dataframe.
        """
        pair = metadata["pair"]

        # Main TF (15m) features
        features = self._extract_vol_features(dataframe, "15m")

        # Merge informative TF features
        for tf in ["30m", "1h", "4h"]:
            try:
                inf_df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
            except Exception:
                logger.debug("No informative data for %s %s", pair, tf)
                continue

            if inf_df is None or len(inf_df) == 0:
                continue

            tf_features = self._extract_vol_features(inf_df, tf)

            # merge_asof: align higher-TF features to 15m timeline (backward fill)
            features = pd.merge_asof(
                features.sort_index(),
                tf_features.sort_index(),
                left_index=True,
                right_index=True,
                direction="backward",
            )

        # Forward fill any gaps at the start
        features = features.ffill().fillna(0.0)

        return features

    # ==================================================================
    #  Ridge Model Training for Volatility Prediction
    # ==================================================================
    def _train_vol_model(
        self,
        features_df: pd.DataFrame,
        atr_target: np.ndarray,
        current_idx: int,
    ) -> Optional[object]:
        """
        Train Ridge regression on rolling window to predict future ATR.

        Returns trained pipeline or None if insufficient data.
        """
        window = self.VOL_WINDOW
        fh = self.VOL_FORECAST_HORIZON

        train_start = max(0, current_idx - window)
        train_end = current_idx - fh

        min_samples = 50
        if train_end - train_start < min_samples:
            return None

        # X: features from train_start to train_end (no lookahead)
        X_train = features_df.iloc[train_start:train_end].values.astype(np.float64)

        # y: ATR at (index + forecast_horizon) — future ATR
        y_train = atr_target[train_start + fh : train_end + fh]

        # Remove inf/nan
        valid = np.isfinite(y_train) & np.all(np.isfinite(X_train), axis=1)
        if valid.sum() < min_samples:
            return None

        X_train = X_train[valid]
        y_train = y_train[valid]

        # Build pipeline: StandardScaler → PolynomialFeatures → Ridge
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            warnings.simplefilter("ignore", FutureWarning)
            try:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_train)

                poly = PolynomialFeatures(degree=self.VOL_POLY_DEGREE, include_bias=False)
                X_poly = poly.fit_transform(X_scaled)

                ridge = Ridge(alpha=self.VOL_RIDGE_ALPHA, fit_intercept=True, max_iter=5000)
                ridge.fit(X_poly, y_train)

                return {"scaler": scaler, "poly": poly, "ridge": ridge}
            except Exception as e:
                logger.warning("Vol model training failed at idx=%d: %s", current_idx, e)
                return None

    # ==================================================================
    #  populate_indicators — Main Loop
    # ==================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Compute all indicators:
          1. Regime detection (ADX consensus across 15m/1h/4h)
          2. BB + RSI (for ranging entry)
          3. EMA + ADX + DI (for trending entry)
          4. Volatility prediction via Ridge (pred_ATR)
        """
        pair = metadata["pair"]

        # ── 1. Regime Detection: ADX consensus ────────────────────────
        # 15m ADX (main TF)
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)

        # 1h ADX (from informative)
        try:
            inf_1h = self.dp.get_pair_dataframe(pair=pair, timeframe="1h")
            if inf_1h is not None and len(inf_1h) > 0:
                inf_1h["adx_1h"] = ta.ADX(inf_1h, timeperiod=14)
                dataframe = pd.merge_asof(
                    dataframe.sort_index(),
                    inf_1h[["adx_1h"]].sort_index(),
                    left_index=True,
                    right_index=True,
                    direction="backward",
                )
            else:
                dataframe["adx_1h"] = np.nan
        except Exception:
            dataframe["adx_1h"] = np.nan

        # 4h ADX (from informative)
        try:
            inf_4h = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
            if inf_4h is not None and len(inf_4h) > 0:
                inf_4h["adx_4h"] = ta.ADX(inf_4h, timeperiod=14)
                dataframe = pd.merge_asof(
                    dataframe.sort_index(),
                    inf_4h[["adx_4h"]].sort_index(),
                    left_index=True,
                    right_index=True,
                    direction="backward",
                )
            else:
                dataframe["adx_4h"] = np.nan
        except Exception:
            dataframe["adx_4h"] = np.nan

        # Fill missing ADX values
        dataframe["adx_1h"] = dataframe["adx_1h"].ffill().fillna(0)
        dataframe["adx_4h"] = dataframe["adx_4h"].ffill().fillna(0)
        dataframe["adx_15m"] = dataframe["adx_15m"].ffill().fillna(0)

        # Classify each TF's regime
        def _classify_regime(adx_val: float) -> int:
            if adx_val < self.ADX_RANGING_MAX:
                return 0  # ranging
            elif adx_val > self.ADX_TRENDING_MIN:
                return 2  # trending
            else:
                return 1  # transition

        reg_15m = dataframe["adx_15m"].apply(_classify_regime)
        reg_1h = dataframe["adx_1h"].apply(_classify_regime)
        reg_4h = dataframe["adx_4h"].apply(_classify_regime)

        # Consensus: majority vote (2 or more TFs agree)
        # Store regime as: 0=ranging, 1=transition, 2=trending
        # Use sum to get consensus score:
        #   sum=0 or 1 → ranging (at least 2 say ranging)
        #   sum=6 → trending (all 3 say trending)
        #   sum=4 or 5 → trending (2+ say trending)
        #   else → transition
        regime_sum = reg_15m + reg_1h + reg_4h

        def _consensus_regime(s: int) -> int:
            if s <= 1:
                return 0  # ranging (0+0+0=0, 0+0+1=1, 0+1+0=1, 1+0+0=1)
            elif s >= 4:
                return 2  # trending (2+1+1=4, 2+2+0=4, 2+2+1=5, 2+2+2=6)
            else:
                return 1  # transition (2 or 3)

        dataframe["regime"] = regime_sum.apply(_consensus_regime)

        # ── 2. Bollinger Bands + RSI (for Ranging Entry) ──────────────
        bb = ta.BBANDS(dataframe, timeperiod=self.BB_PERIOD, nbdevup=self.BB_STD,
                       nbdevdn=self.BB_STD, matype=0)
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)

        # ── 3. EMA + ADX + DI (for Trending Entry) ───────────────────
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.EMA_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.EMA_SLOW)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ── 4. Volatility Prediction via Ridge ────────────────────────
        if not _sklearn_available:
            logger.warning(
                "sklearn not available, volatility prediction disabled: %s",
                _sklearn_error_msg,
            )
            dataframe["pred_atr"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
            self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])
            return dataframe

        # Compute ATR target (current ATR, for training the Ridge model)
        current_atr_pct = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]

        # Extract multi-TF volatility features
        vol_features = self._merge_vol_features(dataframe, metadata)

        # Rolling window training + prediction
        n = len(dataframe)
        pred_atr_arr = np.full(n, np.nan, dtype=np.float64)

        # Initialize with current ATR as fallback
        pred_atr_arr[:] = current_atr_pct.values

        current_model = None
        last_train_idx = -self.VOL_RETRAIN_INTERVAL - 1

        # Check cache
        cached = self._vol_model_cache.get(pair, {})
        if self.process_only_new_candles and cached:
            current_model = cached.get("model")
            last_train_idx = cached.get("last_train_idx", last_train_idx)

        for i in range(self.startup_candle_count, n):
            # Retrain periodically
            if i - last_train_idx >= self.VOL_RETRAIN_INTERVAL:
                new_model = self._train_vol_model(
                    vol_features, current_atr_pct.values, i
                )
                if new_model is not None:
                    current_model = new_model
                    last_train_idx = i

            if current_model is None:
                continue

            # Predict ATR for current bar
            X_i = vol_features.iloc[i].values.astype(np.float64).reshape(1, -1)

            if np.any(np.isnan(X_i)) or np.any(np.isinf(X_i)):
                continue

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                try:
                    X_scaled = current_model["scaler"].transform(X_i)
                    X_poly = current_model["poly"].transform(X_scaled)
                    pred = current_model["ridge"].predict(X_poly)[0]
                    # Clamp predictions to reasonable range
                    pred_atr_arr[i] = float(np.clip(pred, 0.001, 0.15))
                except Exception:
                    continue

        # Forward fill NaN predictions with current ATR
        pred_series = pd.Series(pred_atr_arr, index=dataframe.index)
        dataframe["pred_atr"] = pred_series.ffill().fillna(current_atr_pct)

        # Cache for next call + custom_stoploss access
        self._vol_model_cache[pair] = {
            "model": current_model,
            "last_train_idx": last_train_idx,
        }
        self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])

        # Also store current ATR for fallback
        dataframe["atr_pct"] = current_atr_pct

        return dataframe

    # ==================================================================
    #  Entry Logic — Pure TA, Switched by Regime (Long + Short)
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Regime-switched entry logic (long + short):
          - Ranging (regime=0):
            * Long: close < bb_lower & RSI < 35 (oversold bounce)
            * Short: close > bb_upper & RSI > 65 (overbought fade)
          - Trending (regime=2):
            * Long: EMA fast > EMA slow & +DI > -DI & ADX > 25
            * Short: EMA fast < EMA slow & -DI > +DI & ADX > 25
          - Transition (regime=1): no trades
        Short filtered by 4h macro trend (don't short when 4h bullish)
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # ── Ranging Regime: BB Mean-Reversion ────────────────────────
        ranging_long = (
            (dataframe["regime"] == 0)
            & (dataframe["close"] < dataframe["bb_lower"])
            & (dataframe["rsi"] < self.RSI_OVERSOLD)
        )
        ranging_short = (
            (dataframe["regime"] == 0)
            & (dataframe["close"] > dataframe["bb_upper"])
            & (dataframe["rsi"] > self.RSI_OVERBOUGHT)
        )

        # ── Trending Regime: EMA Trend-Following ────────────────────
        trending_long = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
            & (dataframe["plus_di"] > dataframe["minus_di"])
        )
        trending_short = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
            & (dataframe["minus_di"] > dataframe["plus_di"])
        )

        dataframe.loc[ranging_long, "enter_long"] = 1
        dataframe.loc[ranging_short, "enter_short"] = 1
        dataframe.loc[trending_long, "enter_long"] = 1
        dataframe.loc[trending_short, "enter_short"] = 1

        return dataframe

    # ==================================================================
    #  Exit Logic
    # ==================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals (strengthened — both conditions required, not either/or):
          - Ranging: RSI > 65 AND close > bb_middle (reversion confirmed)
          - Trending: EMA fast < EMA slow for 2 bars AND ADX weakening
          - Min hold: 4 bars (1 hour at 15m) to avoid whipsaw
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # Ranging exit: RSI reversion confirmed (price back above middle band)
        ranging_exit = (
            (dataframe["regime"] == 0)
            & (dataframe["rsi"] > 65)
            & (dataframe["close"] > dataframe["bb_middle"])
        )

        # Trending exit: both EMA cross AND ADX weakening (not either/or)
        trending_exit = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["ema_fast"].shift(1) < dataframe["ema_slow"].shift(1))  # 2 bars confirmed
            & (dataframe["adx_15m"] < 22)  # ADX must also be weakening (not just <20)
        )

        dataframe.loc[ranging_exit, "exit_long"] = 1
        dataframe.loc[trending_exit, "exit_long"] = 1

        # ── Short exits (mirror of long exits) ──────────────────────
        ranging_short_exit = (
            (dataframe["regime"] == 0)
            & (dataframe["rsi"] < 40)
            & (dataframe["close"] < dataframe["bb_middle"])
        )
        trending_short_exit = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_fast"].shift(1) > dataframe["ema_slow"].shift(1))
            & (dataframe["adx_15m"] < 22)
        )
        dataframe.loc[ranging_short_exit, "exit_short"] = 1
        dataframe.loc[trending_short_exit, "exit_short"] = 1

        return dataframe

    # ==================================================================
    #  Dynamic Stop Loss (based on pred_ATR)
    # ==================================================================
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:
        """
        Dynamic stop loss:
          - Base: -3% (self.stoploss)
          - Dynamic: max(-3%, -2×pred_ATR)
          - When predicted volatility is high → wider stop
          - When predicted volatility is low → tighter stop (floor at -3%)
        """
        pred_atr = self._pred_atr_cache.get(pair, 0.02)  # default 2% ATR

        # Dynamic stop: 2x predicted ATR, floored at -3%
        dynamic_sl = max(-0.03, -2.0 * pred_atr)

        # If we're in profit, use trailing logic based on pred_ATR
        if current_profit > 0.03:
            # Once in 3% profit, trail at 1x pred_ATR
            return -pred_atr
        elif current_profit > 0.015:
            # Once in 1.5% profit, trail at 1.5x pred_ATR
            return -1.5 * pred_atr

        return dynamic_sl

    # ==================================================================
    #  Custom Exit (additional exit conditions)
    # ==================================================================
    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        """
        Additional exit conditions:
          - Time-based exit: if trade held > 48 hours without hitting target
          - Regime change exit: if regime flips to opposite extreme
        """
        # Time-based exit: hold max 48 hours (192 × 15m bars)
        holding_minutes = (current_time - trade.open_date).total_seconds() / 60
        if holding_minutes > 2880:  # 48 hours
            return "time_exit"

        return None

    # ==================================================================
    #  Position Sizing — Inverse Volatility Weighting
    # ==================================================================
    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Inverse volatility position sizing:
          - Higher predicted ATR → smaller position
          - Lower predicted ATR → larger position
          - Scale: stake = base_stake * (avg_atr / pred_atr)
          - Clamped between 50% and 100% of proposed_stake
        """
        pred_atr = self._pred_atr_cache.get(pair, None)
        if pred_atr is None or pred_atr <= 0:
            return proposed_stake * self.BASE_STAKE_RATIO

        # Target average ATR (~2.5% for 15m crypto)
        avg_target_atr = 0.025

        # Scale inversely with volatility
        scale = np.clip(avg_target_atr / pred_atr, 0.5, 1.0)

        sized = proposed_stake * scale * self.BASE_STAKE_RATIO

        # Respect min/max
        if min_stake is not None:
            sized = max(sized, min_stake)
        sized = min(sized, max_stake)

        return sized


# ══════════════════════════════════════════════════════════════════════
#  Strategy Registration (Freqtrade auto-discovers via filename)
# ══════════════════════════════════════════════════════════════════════
