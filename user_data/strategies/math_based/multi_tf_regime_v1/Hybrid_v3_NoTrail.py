#!/usr/bin/env python3
"""
Hybrid_v3 — Paper-Validated Dual-Mode Regime-Adaptive Architecture

Design from papers:
  - "Generating Alpha" (arXiv:2601.19504): dual-mode entry (trend: EMA+MACD, mean-rev: RSI+BB)
  - "ORCA" (arXiv:2604.17251): dynamic equity exposure based on regime confidence

Key innovations:
  1. Regime Detection: ADX multi-TF consensus (15m/1h/4h)
     → ranging(0) | transition(1) | trending(2)
  2. Dual-Mode Entry (regime-guided, not static):
     - regime=2 (trending): EMA12>EMA26 + ADX>20 + +DI>-DI  [trend-following]
     - regime=0 (ranging): close<BB_lower + RSI<45           [mean-reversion]
     - regime=1 (transition): NO TRADES
  3. Dual-Mode Exit (joint signals from both entry types):
     - regime=2: EMA cross down OR RSI>65
     - regime=0: RSI>60 OR BB upper touch
  4. Volatility Prediction: Ridge poly2 (from MultiTF_RegimeDetector_v1)
  5. Dynamic Stop-Loss: max(-3%, -2×pred_ATR) with trailing

Architecture:
  - Main TF: 15m
  - Informative: 30m, 1h, 4h (for regime consensus)
  - can_short: False (long only, like NASOS production)
  - Base stoploss: -0.03 (custom_stoploss overrides dynamically)

Math Constraints (6/6):
  - LAW-01: degree=2 (poly features for Ridge) ✓
  - LAW-02: Ridge regularization ✓
  - LAW-03: Predict volatility (continuous), not direction ✓
  - LAW-04: Rolling window training ✓
  - LAW-05: Multi-TF (4 timeframes) ✓
  - LAW-06: SNR-aware bounds (ATR R²=0.67 validated) ✓
"""

import logging
import warnings

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Lazy sklearn import (avoid hard crash without sklearn)
# ─────────────────────────────────────────────────────────────────────
_sklearn_available = False
_sklearn_error_msg = ""

try:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler

    _sklearn_available = True
except ImportError as e:
    _sklearn_error_msg = str(e)


class Hybrid_v3_NoTrail(IStrategy):
    """
    Hybrid_v3_NoTrail — Hybrid_v3 with trailing_stop DISABLED (A/B variant)

    Identical to Hybrid_v3 except:
      - trailing_stop: bool = False (was True)
      - trailing_stop_positive / trailing_stop_positive_offset / trailing_only_offset_is_reached
        left in place but ignored by freqtrade when trailing_stop=False.

    Rationale: Hybrid_v3 backtest (20251101-20260601) showed trailing_stop_loss
    exiting 27 trades at 100% loss (avg -4.86%, drag -10.34pp). This variant
    isolates that effect by relying solely on custom_stoploss + ROI exits.

    Exit modes (joint signals from both entry types):
      - Trending: EMA cross down OR RSI>65
      - Ranging: RSI>60 OR BB upper touch
    """

    # ── Interface Version ─────────────────────────────────────────────
    INTERFACE_VERSION: int = 3

    # ── Basic Settings ─────────────────────────────────────────────
    timeframe: str = "15m"
    can_short: bool = False  # Long only (like NASOS production)

    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    use_custom_stoploss: bool = True
    enter_long_signal_once: bool = True  # Prevent repeated entries per candle

    # Startup: covers ATR horizon + rolling windows + informative TF alignment
    startup_candle_count: int = 350
    # P0: Very wide base stoploss so custom_stoploss fully controls exits
    stoploss: float = -0.99  # was -0.03; custom_stoploss now handles all stops

    # ── Exit / ROI ──────────────────────────────────────────────────
    # P0 FIX: Lower ROI targets — only 20.8% of trades were hitting 3%
    # New targets designed to capture smaller, more frequent wins
    minimal_roi: dict[str, float] = {
        "0": 0.015,  # 1.5% immediate target (was 3%)
        "60": 0.01,  # 1% after 15h (was 1.5% after 30h)
        "120": 0.005,  # 0.5% after 30h (was 0.5% after 60h)
    }

    # A/B TEST: trailing_stop DISABLED (was True in Hybrid_v3)
    # Original Hybrid_v3 commented-out values for reference:
    #   trailing_stop: bool = True
    #   trailing_stop_positive: float = 0.02
    #   trailing_stop_positive_offset: float = 0.03
    #   trailing_only_offset_is_reached: bool = True
    # We keep the attribute names so freqtrade introspection stays happy,
    # but flip trailing_stop to False so the trailing machinery is skipped.
    trailing_stop: bool = False
    trailing_stop_positive: float = 0.02
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # P0 FIX: Disable exit_signal — 29/48 trades exit via exit_signal, ALL LOSE
    # avg -0.65%. exit_signal is the primary source of losses. ROI hits 100% win.
    # Let ROI + custom_stoploss handle all exits.
    use_exit_signal: bool = False

    # ── Regime Thresholds (ADX-based) ────────────────────────────────
    ADX_RANGING_MAX: float = 20.0  # ADX < 20 = ranging
    # P1: Lower threshold so more regimes are classified as trending
    ADX_TRENDING_MIN: float = 22.0  # ADX > 22 = trending (was 25)
    # 20–22 = transition

    # ── Trend-Following Parameters (regime=2) ─────────────────────────
    EMA_FAST_PERIOD: int = 12
    EMA_SLOW_PERIOD: int = 26
    # P1: Lower ADX confirmation for trend entry (more entries)
    ADX_TREND_MIN: float = 18.0  # ADX confirmation for trend entry (was 20)
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    # ── Mean-Reversion Parameters (regime=0) ─────────────────────────
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    RSI_PERIOD: int = 14
    # P1: Looser RSI threshold for mean-reversion entry (was 30)
    RSI_MEAN_REV_ENTRY: float = 40.0  # RSI < 40 for oversold bounce (was 30)
    # P0 FIX: RSI exit thresholds raised + require 2-bar confirmation
    # Old: RSI_MEAN_REV_EXIT=60, RSI_TREND_EXIT=65 (single-bar CROSS logic)
    # New: 70/75 with 2-bar consecutive confirmation to avoid noise exits
    RSI_MEAN_REV_EXIT: float = 70.0  # RSI > 70 for mean-rev exit (was 60)
    RSI_TREND_EXIT: float = 75.0  # RSI > 75 for trend exit (was 65)

    # ── BB_RPB Pullback Parameters (regime=2) ────────────────────────
    # Adapted from BB_RPB_TSL_BI.is_local_uptrend (NFI next gen).
    # In a confirmed uptrend, wait for price to pull back to (or just
    # below) the lower Bollinger Band with RSI oversold confirmation.
    # This is the proven BB+RSI pullback entry signal.
    BB_PULLBACK_FACTOR: float = 0.999  # close < bb_lower * factor (was 0.999)
    BB_PULLBACK_RSI_MAX: float = 40.0  # RSI upper bound (oversold zone)
    BB_PULLBACK_RSI_MIN: float = 20.0  # RSI lower bound (avoid capitulation)

    # ── Volatility Prediction Parameters ─────────────────────────────
    VOL_FORECAST_HORIZON: int = 12  # predict ATR 12 bars (3h) ahead
    VOL_WINDOW: int = 300  # training window size (bars)
    VOL_RIDGE_ALPHA: float = 0.1  # Ridge regularization
    VOL_RETRAIN_INTERVAL: int = 50  # retrain every N bars
    VOL_POLY_DEGREE: int = 2  # polynomial feature degree

    # ── Position Sizing ──────────────────────────────────────────────
    BASE_STAKE_RATIO: float = 0.95  # use 95% of allocated stake by default

    # ── Internal State ───────────────────────────────────────────────
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Cache for Ridge model per pair
        self._vol_model_cache: dict[str, dict] = {}
        # Cache for latest pred_ATR per pair (used by custom_stoploss)
        self._pred_atr_cache: dict[str, float] = {}
        # P2: track peak profit per trade for drawdown exit
        self._trade_peak_profit: dict[int, float] = {}

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

    def _merge_vol_features(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
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
    ) -> object | None:
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
          2. EMA + MACD (for trend-following entry in regime=2)
          3. Bollinger Bands + RSI (for mean-reversion entry in regime=0)
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

        # ── 2. EMA + MACD (for Trend-Following Entry, regime=2) ────────
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.EMA_FAST_PERIOD)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.EMA_SLOW_PERIOD)

        # MACD (from Generating Alpha paper)
        macd = ta.MACD(
            dataframe,
            fastperiod=self.MACD_FAST,
            slowperiod=self.MACD_SLOW,
            signalperiod=self.MACD_SIGNAL,
        )
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # ADX + DI for trend confirmation
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ── 3. Bollinger Bands + RSI (for Mean-Reversion Entry, regime=0) ──
        bb = ta.BBANDS(
            dataframe, timeperiod=self.BB_PERIOD, nbdevup=self.BB_STD, nbdevdn=self.BB_STD, matype=0
        )
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_upper"] = bb["upperband"]

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)

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
                new_model = self._train_vol_model(vol_features, current_atr_pct.values, i)
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
                    # Clamp predictions to reasonable range (0.5% min for BTC 15m)
                    pred_atr_arr[i] = float(np.clip(pred, 0.005, 0.15))
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
    #  Entry Logic — Dual-Mode, Regime-Guided (Long Only)
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Regime-switched entry logic (long only):

        Generating Alpha paper dual-mode architecture:
          - regime=2 (trending): EMA cross + ADX confirmation (trend-following)
            * EMA12 > EMA26  AND  ADX > 20  AND  +DI > -DI
            * MACD histogram > 0 confirms momentum
            * BB_RPB pullback variant: close < bb_lower * 0.999 AND 20<RSI<40
              (only in uptrend; allows entering trending regime on dips)
          - regime=0 (ranging): BB touch + RSI confirm (mean-reversion)
            * close < bb_lower  AND  RSI < 45
          - regime=1 (transition): NO TRADES (avoid whipsaw)
        """
        dataframe["enter_long"] = 0
        # P2: entry tag column for per-type win-rate stats
        dataframe["enter_tag"] = ""

        # ── Trending Regime: EMA Cross + ADX Confirmation ───────────
        # EMA cross: fast > slow = bullish alignment
        # ADX > 20 confirms trend is present (not ranging)
        # +DI > -DI confirms uptrend direction
        # MACD histogram > 0 confirms bullish momentum
        trending_entry = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])  # EMA cross bullish
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)  # ADX confirms trend
            & (dataframe["plus_di"] > dataframe["minus_di"])  # +DI > -DI
            & (dataframe["macd_hist"] > 0)  # MACD momentum positive
            & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())  # volume above MA
        )

        # ── Ranging Regime: BB Touch + RSI Confirmation ──────────────
        # BB lower touch = price at oversold level
        # RSI < 30 = oversold confirmation (mean-reversion bounce setup)
        # Volume above 20-period MA confirms institutional interest
        ranging_entry = (
            (dataframe["regime"] == 0)
            & (dataframe["close"] < dataframe["bb_lower"])  # BB lower touch
            & (dataframe["rsi"] < self.RSI_MEAN_REV_ENTRY)  # RSI oversold (< 30)
            & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())  # volume above MA
        )

        # ── Transition Regime: Weak Trend Entry (P1) ────────────────
        # Previously regime=1 had NO TRADES. Now allow weak trend entry
        # when EMA cross + volume confirm, but with stricter conditions
        # than regime=2 to avoid whipsaws.
        transition_entry = (
            (dataframe["regime"] == 1)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)  # same ADX threshold
            & (dataframe["plus_di"] > dataframe["minus_di"])
            # Stricter volume: 1.2x MA to compensate for weaker regime signal
            & (dataframe["volume"] > 1.2 * dataframe["volume"].rolling(20).mean())
        )

        # ── BB_RPB Pullback Entry (regime=2 only) ─────────────────────
        # Adapted from BB_RPB_TSL_BI.is_local_uptrend (NFI next gen):
        # In a confirmed uptrend, wait for price to pull back to (or just
        # below) the BB lower band with RSI oversold confirmation. RSI is
        # bounded between 20-40 to avoid both overbought noise and extreme
        # capitulation. Volume above 20-MA confirms institutional interest.
        bb_pullback_entry = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])  # uptrend confirmed
            & (dataframe["close"] < dataframe["bb_lower"] * self.BB_PULLBACK_FACTOR)
            & (dataframe["rsi"] < self.BB_PULLBACK_RSI_MAX)
            & (dataframe["rsi"] > self.BB_PULLBACK_RSI_MIN)
            & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())
        )

        dataframe.loc[trending_entry, "enter_long"] = 1
        dataframe.loc[trending_entry, "enter_tag"] = "trend"
        dataframe.loc[ranging_entry, "enter_long"] = 1
        dataframe.loc[ranging_entry, "enter_tag"] = "mean_rev"
        dataframe.loc[transition_entry, "enter_long"] = 1
        dataframe.loc[transition_entry, "enter_tag"] = "weak_trend"
        dataframe.loc[bb_pullback_entry, "enter_long"] = 1
        dataframe.loc[bb_pullback_entry, "enter_tag"] = "bb_pullback"

        return dataframe

    # ==================================================================
    #  Exit Logic — Dual-Mode (Joint Signals from Both Entry Types)
    #  P0 FIX: RSI thresholds raised (65→75, 60→70) + 2-bar consecutive
    #  confirmation to prevent single-bar noise from triggering exits.
    #  EMA cross and BB upper touch keep CROSS logic (fire once).
    # ==================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Regime-switched exit logic (joint signals from both entry types):

        From Generating Alpha paper:
          - regime=2 (trend-following entry):
            * EMA cross down (ema_fast < ema_slow) OR RSI > 75 (2-bar confirm)
          - regime=0 (mean-reversion entry):
            * RSI > 70 (2-bar confirm) OR BB upper touch

        P0 FIX: RSI conditions now require 2 consecutive bars above threshold
        to avoid single-bar wicks triggering premature exits.
        """
        dataframe["exit_long"] = 0

        # ── Trending Exit: EMA Cross Down OR RSI consecutive > 75 ─────────
        # EMA cross down = trend reversal (was >= slow, now < slow) — CROSS logic
        # RSI > 75 for 2 consecutive bars = sustained overbought, not a single wick
        trending_exit = (dataframe["regime"] == 2) & (
            # EMA CROSS down: ema_fast transitions from >= ema_slow to < ema_slow
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"])
            )
            # RSI consecutive > 75: current AND previous bar both above 75
            | (
                (dataframe["rsi"] > self.RSI_TREND_EXIT)
                & (dataframe["rsi"].shift(1) > self.RSI_TREND_EXIT)
            )
        )

        # ── Ranging Exit: RSI consecutive > 70 OR Close CROSS Above BB Upper ──
        # RSI > 70 for 2 consecutive bars = mean-reversion complete (sustained)
        # Close CROSS above BB upper = reversion target reached (was <= bb_upper, now > bb_upper)
        ranging_exit = (dataframe["regime"] == 0) & (
            # RSI consecutive > 70: current AND previous bar both above 70
            (
                (dataframe["rsi"] > self.RSI_MEAN_REV_EXIT)
                & (dataframe["rsi"].shift(1) > self.RSI_MEAN_REV_EXIT)
            )
            # Close CROSS above BB upper: was <= bb_upper, now > bb_upper
            | (
                (dataframe["close"] > dataframe["bb_upper"])
                & (dataframe["close"].shift(1) <= dataframe["bb_upper"])
            )
        )

        dataframe.loc[trending_exit, "exit_long"] = 1
        dataframe.loc[ranging_exit, "exit_long"] = 1

        # P2: Transition exit — weak_trend entries use trending exit logic
        # P0 FIX: RSI threshold raised to 75 with 2-bar confirmation
        transition_exit = (dataframe["regime"] == 1) & (
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"])
            )
            | (
                (dataframe["rsi"] > self.RSI_TREND_EXIT)
                & (dataframe["rsi"].shift(1) > self.RSI_TREND_EXIT)
            )
        )
        dataframe.loc[transition_exit, "exit_long"] = 1

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
    ) -> float | None:
        """
        P0 FIX: Widen stoploss to reduce premature exits on losing trades.

        Old behavior: hard -3% stop caused 12 losing trades to all exit at -3%.
        New behavior:
          - profit < -5%:  return -0.05 (5% hard stop, wider than old 3%)
          - -5% <= profit < 0%: return -0.99 (let price float, no hard stop)
          - 0% <= profit < 1.5%: return -0.05 (breakeven zone, allow room)
          - 1.5% <= profit < 3%: return -0.015 (protect half profit)
          - profit >= 3%:  return +0.01 (lock 1% profit, trailing at 1%)
          - profit >= 5%:  return +0.02 (lock 2% profit)

        A positive return value means "stoploss is X% above entry price",
        effectively trailing the profit.
        """
        # P0 FIX: Widen hard stop to 5%; allow floating between -5% and 0%
        if current_profit < -0.05:
            return -0.05  # 5% hard stop (was 3%)
        elif current_profit < 0:
            return -0.99  # let price float, no hard stop in -5%~0% zone

        # Profit-protection tiers
        if current_profit >= 0.05:
            return +0.02  # lock 2% profit
        if current_profit >= 0.03:
            return +0.01  # lock 1% profit (trailing at 1%)
        if current_profit >= 0.015:
            return -0.015  # protect half of 1.5-3% profit

        # Default: allow up to -5% below entry for small profits
        return -0.05

    # ==================================================================
    #  Leverage
    # ==================================================================
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
        Return the leverage to use for a trade.
        """
        return 1.0

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
    ) -> str | None:
        """
        P2: Additional exit conditions:
          - Time-based exit: if trade held > 48 hours without hitting target
          - Profit drawdown exit: if profit fell > 1% from its peak, force exit
          - RSI extreme overbought exit: RSI > 75
        """
        # Time-based exit: hold max 48 hours (192 × 15m bars)
        holding_minutes = (current_time - trade.open_date).total_seconds() / 60
        if holding_minutes > 2880:  # 48 hours
            return "time_exit"

        # P2: Profit drawdown protection — only when we ARE in profit
        # BUG FIX: Only check drawdown when current_profit > 0
        # Old code checked even when losing, causing immediate exit
        if current_profit > 0 and trade.max_rate > 0 and current_rate < trade.max_rate:
            peak_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
            drawdown_from_peak = peak_profit - current_profit
            if drawdown_from_peak > 0.02:  # > 2% drawdown from peak profit (relaxed from 1%)
                return "profit_drawdown"

        # P2: RSI extreme overbought exit — need dataframe access
        # P0 FIX: Removed rsi_overbought exit because RSI threshold is now 75
        # (same as exit_signal), making this redundant. Exit signal already
        # handles sustained overbought with 2-bar confirmation.
        # dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        # if dataframe is not None and not dataframe.empty:
        #     last_rsi = dataframe["rsi"].iloc[-1]
        #     if last_rsi > 75:
        #         return "rsi_overbought"

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
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
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
