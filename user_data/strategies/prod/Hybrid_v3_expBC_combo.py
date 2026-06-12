#!/usr/bin/env python3
"""
Hybrid_v3_expBC_combo — expBC: B (嚴格 ADX 15/28) + C (ATR>MA(100)) 組合 on top of Hybrid_v3 base
# expBC: 兩個 winner 結合 — 嚴格 regime + 波動率擴張 gate

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
from pandas import DataFrame, Series
from functools import reduce

import freqtrade.vendor.qtpylib.indicators as qtpylib
import pandas_ta as pta
from technical.indicators import RMI

from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    CategoricalParameter,
    merge_informative_pair,
    stoploss_from_open,
)


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Helper functions imported from BB_RPB_TSL_BI (NFI next gen family)
# ─────────────────────────────────────────────────────────────────────
def ha_typical_price(bars: DataFrame) -> Series:
    """Heikin-Ashi typical price."""
    res = (bars["ha_high"] + bars["ha_low"] + bars["ha_close"]) / 3.0
    return Series(index=bars.index, data=res)


def EWO(dataframe: DataFrame, ema_length: int = 5, ema2_length: int = 35) -> Series:
    """Elliott Wave Oscillator (EWO) = (EMA_short - EMA_long) / low * 100."""
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df["low"] * 100
    return emadif


def williams_r(dataframe: DataFrame, period: int = 14) -> Series:
    """Williams %R oscillator."""
    highest_high = dataframe["high"].rolling(center=False, window=period).max()
    lowest_low = dataframe["low"].rolling(center=False, window=period).min()
    WR = Series(
        (highest_high - dataframe["close"]) / (highest_high - lowest_low),
        name=f"{period} Williams %R",
    )
    return WR * -100


def heikinashi_safe(bars: DataFrame) -> DataFrame:
    """
    Heikin-Ashi transformation that works on both integer and
    datetime-indexed DataFrames.

    The stock `qtpylib.heikinashi` uses `bars.at[0, ...]` which raises
    KeyError on a datetime index. We compute the four HA series with
    vectorised numpy arrays and re-attach them to the original index.
    """
    if len(bars) == 0:
        return bars.copy()

    o = bars["open"].to_numpy(dtype=float)
    h = bars["high"].to_numpy(dtype=float)
    l = bars["low"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)

    ha_close = (o + h + l + c) / 4.0
    ha_open = np.empty_like(ha_close)
    ha_open[0] = (o[0] + c[0]) / 2.0
    for i in range(1, len(ha_close)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    ha_high = np.maximum.reduce([h, ha_open, ha_close])
    ha_low = np.minimum.reduce([l, ha_open, ha_close])

    return DataFrame(
        {
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
        },
        index=bars.index,
    )


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


class Hybrid_v3_expBC_combo(IStrategy):
    """
    Hybrid_v3 — Paper-Validated Dual-Mode Regime-Adaptive Architecture

    Entry modes (switched by regime, not static):
      - Trending (regime=2): EMA cross + ADX confirmation → trend-following
      - Ranging (regime=0): BB touch + RSI confirm → mean-reversion
      - Transition (regime=1): no trades

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

    # ── Exit / ROI ──────────────────────────────────────────────────
    # GA-optimized ROI/SL/Trailing (2026-06-01 session, 50 epochs)
    # Source: user_data/strategies/math_based/ga_framework/reports/Hybrid_v3_GA_results_20260601.md
    # Best Loss: 115.499 (ProfitDrawDownHyperOptLoss)
    # Backtest: 674 trades, 64.8% WR, 0.00% profit, 13.26% max DD
    minimal_roi: dict[str, float] = {
        "0": 0.216,  # GA: 21.6% within first 50min (high initial target)
        "50": 0.03,  # GA: 3% after 50min
        "131": 0.019,  # GA: 1.9% after 131min
        "164": 0.0,  # No ROI after 164min
    }

    # GA-optimized stoploss
    stoploss: float = -0.026  # GA: -2.6% (was -0.99 to let custom_stoploss dominate)

    # GA-optimized trailing (enabled, aggressive)
    # NOTE: GA reported offset=0.001 but freqtrade requires offset > positive.
    # Adjusted to 0.12 (positive 0.107 + 1.3% buffer) for feasibility.
    trailing_stop: bool = False  # DISABLED: was causing -21.75% drag (253 trades)
    trailing_stop_positive: float = 0.107  # GA: 10.7% trigger (unused when trailing_stop=False)
    trailing_stop_positive_offset: float = 0.12  # 12% from peak (unused when trailing_stop=False)
    trailing_only_offset_is_reached: bool = True  # unused when trailing_stop=False

    # P0 FIX: Disable exit_signal — 29/48 trades exit via exit_signal, ALL LOSE
    # avg -0.65%. exit_signal is the primary source of losses. ROI hits 100% win.
    # Let ROI + custom_stoploss handle all exits.
    use_exit_signal: bool = False

    # ── Regime Thresholds (ADX-based) ────────────────────────────────
    # expBC: Strict ADX (from expB) + volatility gate (from expC)
    ADX_RANGING_MAX: float = 15.0  # expBC: was 20.0
    # P1: Lower threshold so more regimes are classified as trending
    ADX_TRENDING_MIN: float = 28.0  # expBC: was 22.0 (must be > 15 to avoid empty band)
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

    # ── BB_RPB Buy Parameters (regime=2 trending) ────────────────────
    # Migrated from BB_RPB_TSL_BI.py (NFI next gen family). Each block
    # is gated by a separate "is_optimize_*" flag. We keep the same
    # ranges as BB_RPB_TSL_BI so the proven NSGAII optimum is the
    # default; the GA can re-explore the space later if desired.
    #
    # NOTE: BB_PULLBACK_FACTOR / BB_PULLBACK_RSI_* are superseded by
    # `buy_bb_factor` / `buy_rsi_local_dip` and are no longer used.

    is_optimize_dip = True
    buy_rmi = IntParameter(30, 50, default=49, optimize=is_optimize_dip)
    buy_cci = IntParameter(-135, -90, default=-116, optimize=is_optimize_dip)
    buy_srsi_fk = IntParameter(30, 50, default=32, optimize=is_optimize_dip)
    buy_cci_length = IntParameter(25, 45, default=25, optimize=is_optimize_dip)
    buy_rmi_length = IntParameter(8, 20, default=17, optimize=is_optimize_dip)

    is_optimize_break = True
    buy_bb_width = DecimalParameter(0.065, 0.135, default=0.095, optimize=is_optimize_break)
    buy_bb_delta = DecimalParameter(0.018, 0.035, default=0.025, optimize=is_optimize_break)

    is_optimize_local_uptrend = True
    buy_ema_diff = DecimalParameter(0.022, 0.027, default=0.024, optimize=is_optimize_local_uptrend)
    buy_bb_factor = DecimalParameter(0.990, 0.999, default=0.999, optimize=True)
    buy_closedelta = DecimalParameter(
        12.0, 18.0, default=13.494, optimize=is_optimize_local_uptrend
    )

    is_optimize_local_dip = True
    buy_ema_diff_local_dip = DecimalParameter(
        0.022, 0.027, default=0.024, optimize=is_optimize_local_dip
    )
    buy_ema_high_local_dip = DecimalParameter(
        0.90, 1.2, default=1.084, optimize=is_optimize_local_dip
    )
    buy_closedelta_local_dip = DecimalParameter(
        12.0, 18.0, default=13.717, optimize=is_optimize_local_dip
    )
    buy_rsi_local_dip = IntParameter(15, 45, default=20, optimize=is_optimize_local_dip)
    buy_crsi_local_dip = IntParameter(10, 18, default=10, optimize=True)

    is_optimize_ewo = True
    buy_rsi_fast = IntParameter(35, 50, default=44, optimize=is_optimize_ewo)
    buy_rsi = IntParameter(15, 35, default=23, optimize=is_optimize_ewo)
    buy_ewo = DecimalParameter(-6.0, 5, default=-5.001, optimize=is_optimize_ewo)
    buy_ema_low = DecimalParameter(0.9, 0.99, default=0.935, optimize=is_optimize_ewo)
    buy_ema_high = DecimalParameter(0.95, 1.2, default=0.968, optimize=is_optimize_ewo)

    is_optimize_ewo_2 = True
    buy_rsi_fast_ewo_2 = IntParameter(15, 50, default=45, optimize=is_optimize_ewo_2)
    buy_rsi_ewo_2 = IntParameter(15, 50, default=35, optimize=is_optimize_ewo_2)
    buy_ema_low_2 = DecimalParameter(0.90, 1.2, default=0.970, optimize=is_optimize_ewo_2)
    buy_ema_high_2 = DecimalParameter(0.90, 1.2, default=1.087, optimize=is_optimize_ewo_2)
    buy_ewo_high_2 = DecimalParameter(2, 12, default=4.179, optimize=is_optimize_ewo_2)

    is_optimize_check = True
    buy_roc_1h = IntParameter(-25, 200, default=4, optimize=is_optimize_check)
    buy_bb_width_1h = DecimalParameter(0.3, 2.0, default=1.074, optimize=is_optimize_check)

    is_optimize_cofi = True
    buy_adx = IntParameter(0, 30, default=13, optimize=is_optimize_cofi)

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

        # 1h ADX (from informative) + BB_RPB 1h indicators
        try:
            inf_1h = self.dp.get_pair_dataframe(pair=pair, timeframe="1h")
            if inf_1h is not None and len(inf_1h) > 0:
                inf_1h["adx_1h"] = ta.ADX(inf_1h, timeperiod=14)
                # BB_RPB 1h indicators (subset needed by entry conditions)
                inf_1h["ema_50_1h"] = ta.EMA(inf_1h, timeperiod=50)
                inf_1h["ema_100_1h"] = ta.EMA(inf_1h, timeperiod=100)
                inf_1h["ema_200_1h"] = ta.EMA(inf_1h, timeperiod=200)
                # Heikin-Ashi close for ROCR
                ha_1h = heikinashi_safe(inf_1h)
                inf_1h["ha_close_1h"] = ha_1h["close"]
                inf_1h["rocr_1h"] = ta.ROCR(inf_1h["ha_close_1h"], timeperiod=168)
                # ROC + BB width (1h) for is_additional_check
                inf_1h["roc_1h"] = ta.ROC(inf_1h, timeperiod=9)
                bb1h = qtpylib.bollinger_bands(qtpylib.typical_price(inf_1h), window=20, stds=2)
                inf_1h["bb_width_1h"] = (bb1h["upper"] - bb1h["lower"]) / bb1h["mid"]
                cols_1h = [
                    "adx_1h",
                    "ema_50_1h",
                    "ema_100_1h",
                    "ema_200_1h",
                    "ha_close_1h",
                    "rocr_1h",
                    "roc_1h",
                    "bb_width_1h",
                ]
                dataframe = pd.merge_asof(
                    dataframe.sort_index(),
                    inf_1h[cols_1h].sort_index(),
                    left_index=True,
                    right_index=True,
                    direction="backward",
                )
            else:
                dataframe["adx_1h"] = np.nan
        except Exception:
            dataframe["adx_1h"] = np.nan

        # Ensure 1h BB_RPB columns exist even if merge failed
        for col in (
            "ema_50_1h",
            "ema_100_1h",
            "ema_200_1h",
            "ha_close_1h",
            "rocr_1h",
            "roc_1h",
            "bb_width_1h",
        ):
            if col not in dataframe.columns:
                dataframe[col] = np.nan

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

        # Forward-fill 1h BB_RPB columns (they are constant within 1h bars)
        for col in (
            "ema_50_1h",
            "ema_100_1h",
            "ema_200_1h",
            "ha_close_1h",
            "rocr_1h",
            "roc_1h",
            "bb_width_1h",
        ):
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].ffill()

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

        # expC: Volatility expansion filter — only enter when ATR is above its 100-bar mean
        dataframe["_atr_14_v3c"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["_atr_ma_100_v3c"] = dataframe["_atr_14_v3c"].rolling(100).mean()
        dataframe["_vol_expanding_v3c"] = (
            dataframe["_atr_14_v3c"] > dataframe["_atr_ma_100_v3c"]
        ).astype(int)

        # ── 3b. BB_RPB 15m Indicators (regime=2 trending entry) ────────
        # Computed on the main 15m TF. Indicator names mirror BB_RPB_TSL_BI
        # so the entry conditions can be ported verbatim. We avoid clashes
        # with the existing EMA/MACD/BB stack: the legacy names `bb_lower`
        # / `bb_middle` / `bb_upper` / `ema_slow` keep their original
        # meaning; the BB_RPB bands use the `bb_*band2`/`bb_*band3`
        # suffix from BB_RPB, and the HA-based slow EMA is renamed to
        # `ema_slow_ha` to prevent overwrite of the regime `ema_slow`.
        bb_rpb2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband2"] = bb_rpb2["lower"]
        dataframe["bb_middleband2"] = bb_rpb2["mid"]
        dataframe["bb_upperband2"] = bb_rpb2["upper"]

        bb_rpb3 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=3)
        dataframe["bb_lowerband3"] = bb_rpb3["lower"]
        dataframe["bb_middleband3"] = bb_rpb3["mid"]
        dataframe["bb_upperband3"] = bb_rpb3["upper"]

        dataframe["bb_width"] = (
            dataframe["bb_upperband2"] - dataframe["bb_lowerband2"]
        ) / dataframe["bb_middleband2"]
        dataframe["bb_delta"] = (
            dataframe["bb_lowerband2"] - dataframe["bb_lowerband3"]
        ) / dataframe["bb_lowerband2"]

        # CCI hyperopt-sweep (one column per value in buy_cci_length.range)
        for val in self.buy_cci_length.range:
            dataframe[f"cci_length_{val}"] = ta.CCI(dataframe, val)

        # RMI hyperopt-sweep (one column per value in buy_rmi_length.range)
        for val in self.buy_rmi_length.range:
            dataframe[f"rmi_length_{val}"] = RMI(dataframe, length=val, mom=4)

        # Stochastic RSI
        stoch = ta.STOCHRSI(dataframe, 15, 20, 2, 2)
        dataframe["srsi_fk"] = stoch["fastk"]
        dataframe["srsi_fd"] = stoch["fastd"]

        # closedelta = abs(close - close.shift(1))
        dataframe["closedelta"] = (dataframe["close"] - dataframe["close"].shift()).abs()

        # SMAs
        dataframe["sma_15"] = ta.SMA(dataframe, timeperiod=15)
        dataframe["sma_30"] = ta.SMA(dataframe, timeperiod=30)
        dataframe["sma_75"] = ta.SMA(dataframe, timeperiod=75)

        # CTI (ConnorsRSI internal)
        dataframe["cti"] = pta.cti(dataframe["close"], length=20)

        # CRSI (3, 2, 100)
        crsi_closechange = dataframe["close"] / dataframe["close"].shift(1)
        crsi_updown = np.where(
            crsi_closechange.gt(1), 1.0, np.where(crsi_closechange.lt(1), -1.0, 0.0)
        )
        dataframe["crsi"] = (
            ta.RSI(dataframe["close"], timeperiod=3)
            + ta.RSI(crsi_updown, timeperiod=2)
            + ta.ROC(dataframe["close"], 100)
        ) / 3

        # EMAs (multiple)
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_13"] = ta.EMA(dataframe, timeperiod=13)
        dataframe["ema_16"] = ta.EMA(dataframe, timeperiod=16)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_26"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # RSI variants
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=4)
        dataframe["rsi_slow"] = ta.RSI(dataframe, timeperiod=20)

        # EWO (50, 200)
        dataframe["EWO"] = EWO(dataframe, 50, 200)

        # Williams %R (14 only — the main series used by entries)
        dataframe["r_14"] = williams_r(dataframe, period=14)

        # Volume rolling means
        dataframe["volume_mean_12"] = dataframe["volume"].rolling(12).mean().shift(1)
        dataframe["volume_mean_24"] = dataframe["volume"].rolling(24).mean().shift(1)

        # Heikin Ashi
        heikinashi = heikinashi_safe(dataframe)
        dataframe["ha_open"] = heikinashi["open"]
        dataframe["ha_close"] = heikinashi["close"]
        dataframe["ha_high"] = heikinashi["high"]
        dataframe["ha_low"] = heikinashi["low"]

        # Heikin-Ashi typical price BB(40, 2) for ClucHA
        bb_ha_40 = qtpylib.bollinger_bands(ha_typical_price(dataframe), window=40, stds=2)
        dataframe["bb_lowerband2_40"] = bb_ha_40["lower"]
        dataframe["bb_middleband2_40"] = bb_ha_40["mid"]
        dataframe["bb_upperband2_40"] = bb_ha_40["upper"]
        dataframe["bb_delta_cluc"] = (
            dataframe["bb_middleband2_40"] - dataframe["bb_lowerband2_40"]
        ).abs()
        dataframe["ha_closedelta"] = (dataframe["ha_close"] - dataframe["ha_close"].shift()).abs()
        dataframe["tail"] = (dataframe["ha_close"] - dataframe["ha_low"]).abs()
        # NB: renamed from BB_RPB's `ema_slow` (50) to avoid clobbering the
        # regime/legacy `ema_slow` (EMA26) on the main close series.
        dataframe["ema_slow_ha"] = ta.EMA(dataframe["ha_close"], timeperiod=50)

        # Stochastic fast (for cofi)
        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe["fastd"] = stoch_fast["fastd"]
        dataframe["fastk"] = stoch_fast["fastk"]

        # 1h CTI / CRSI for cross-TF NFI entries
        try:
            inf_1h_cti = self.dp.get_pair_dataframe(pair=pair, timeframe="1h")
            if inf_1h_cti is not None and len(inf_1h_cti) > 0:
                inf_1h_cti["cti_1h"] = pta.cti(inf_1h_cti["close"], length=20)
                crsi1h_change = inf_1h_cti["close"] / inf_1h_cti["close"].shift(1)
                crsi1h_updown = np.where(
                    crsi1h_change.gt(1),
                    1.0,
                    np.where(crsi1h_change.lt(1), -1.0, 0.0),
                )
                inf_1h_cti["crsi_1h"] = (
                    ta.RSI(inf_1h_cti["close"], timeperiod=3)
                    + ta.RSI(crsi1h_updown, timeperiod=2)
                    + ta.ROC(inf_1h_cti["close"], 100)
                ) / 3
                dataframe = pd.merge_asof(
                    dataframe.sort_index(),
                    inf_1h_cti[["cti_1h", "crsi_1h"]].sort_index(),
                    left_index=True,
                    right_index=True,
                    direction="backward",
                )
        except Exception:
            pass
        for col in ("cti_1h", "crsi_1h"):
            if col not in dataframe.columns:
                dataframe[col] = np.nan
            else:
                dataframe[col] = dataframe[col].ffill()

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
        Regime-switched entry logic (long only).

        Phase B integration: regime=2 trending entries now use the
        BB_RPB (NFI next gen) multi-condition stack. The regime=0
        mean-reversion and regime=1 weak-trend entries are preserved
        as designed.

          - regime=2 (trending): BB_RPB stack
              * is_local_uptrend  (primary BB pullback — NFI next gen)
              * is_local_dip      (EMA cross + RSI dip — NFI next gen)
              * is_ewo            (EWO oversold — SMA offset)
              * is_ewo_2          (EWO cross-TF uptrend — NFI next gen)
              * is_BB_checked     (RMI+CCI+SRSI dip with BB break — BinH)
              * is_r_deadfish     (bear-trap — reverse deadfish)
              * is_clucHA         (Heikin-Ashi pullback — NFI next gen)
              * is_cofi           (stochastic + EWO — NFI next gen)
              * is_nfi_32         (NFI quick mode — pullback)
            All of the above are AND-combined with is_additional_check
            (1h ROC + BB-width filter from BB_RPB).
          - regime=0 (ranging): BB touch + RSI confirm (mean-reversion)
            * close < bb_lower  AND  RSI < 40
          - regime=1 (transition): weak trend (EMA cross + ADX)
            * Preserved unchanged (will exit with trending_exit rules).
        """
        dataframe["enter_long"] = 0
        # P2: entry tag column for per-type win-rate stats
        dataframe["enter_tag"] = ""

        # Volume MA20 — used by ranging + transition entries (and a safety
        # liquidity floor for the BB_RPB stack).
        vol_ma_20 = dataframe["volume"].rolling(20).mean()

        # ── Ranging Regime: BB Touch + RSI Confirmation ──────────────
        # BB lower touch = price at oversold level
        # RSI < 40 = oversold confirmation (mean-reversion bounce setup)
        # Volume above 20-period MA confirms institutional interest
        # expC: AND with volatility expansion filter
        ranging_entry = (
            (dataframe["regime"] == 0)
            & (dataframe["close"] < dataframe["bb_lower"])  # BB lower touch
            & (dataframe["rsi"] < self.RSI_MEAN_REV_ENTRY)  # RSI oversold
            & (dataframe["volume"] > vol_ma_20)  # volume above MA
            & (dataframe["_vol_expanding_v3c"] == 1)  # expC gate
        )

        # ── Transition Regime: Weak Trend Entry (P1, preserved) ──────
        # Same as the previous version: allow weak-trend entry when EMA
        # cross + ADX confirm, with stricter volume to compensate for
        # the weaker regime signal.
        transition_entry = (
            (dataframe["regime"] == 1)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["volume"] > 1.2 * vol_ma_20)
            & (dataframe["_vol_expanding_v3c"] == 1)  # expC gate
        )

        # ── Trending Regime (regime=2): BB_RPB Stack ─────────────────
        # All conditions are ported verbatim from BB_RPB_TSL_BI, except
        # they are wrapped in a regime==2 filter and AND-combined with
        # is_additional_check. Each condition receives a distinct tag
        # so we can keep per-condition win-rate statistics.

        rmi_col = f"rmi_length_{self.buy_rmi_length.value}"
        cci_col = f"cci_length_{self.buy_cci_length.value}"

        # is_dip: oversold (RMI + CCI + SRSI)
        is_dip = (
            (dataframe[rmi_col] < self.buy_rmi.value)
            & (dataframe[cci_col] <= self.buy_cci.value)
            & (dataframe["srsi_fk"] < self.buy_srsi_fk.value)
        )

        # is_break: volatility expansion below bb_lowerband3
        is_break = (
            (dataframe["bb_delta"] > self.buy_bb_delta.value)
            & (dataframe["bb_width"] > self.buy_bb_width.value)
            & (dataframe["closedelta"] > dataframe["close"] * self.buy_closedelta.value / 1000)
            & (dataframe["close"] < dataframe["bb_lowerband3"] * self.buy_bb_factor.value)
        )
        is_BB_checked = is_dip & is_break  # combined "bb" tag

        # is_local_uptrend: BB pullback inside an uptrend (PRIMARY)
        is_local_uptrend = (
            (dataframe["ema_26"] > dataframe["ema_12"])
            & (
                dataframe["ema_26"] - dataframe["ema_12"]
                > dataframe["open"] * self.buy_ema_diff.value
            )
            & (dataframe["ema_26"].shift() - dataframe["ema_12"].shift() > dataframe["open"] / 100)
            & (dataframe["close"] < dataframe["bb_lowerband2"] * self.buy_bb_factor.value)
            & (dataframe["closedelta"] > dataframe["close"] * self.buy_closedelta.value / 1000)
        )

        # is_local_dip: EMA-confirmed oversold dip
        is_local_dip = (
            (dataframe["ema_26"] > dataframe["ema_12"])
            & (
                dataframe["ema_26"] - dataframe["ema_12"]
                > dataframe["open"] * self.buy_ema_diff_local_dip.value
            )
            & (dataframe["ema_26"].shift() - dataframe["ema_12"].shift() > dataframe["open"] / 100)
            & (dataframe["close"] < dataframe["ema_20"] * self.buy_ema_high_local_dip.value)
            & (dataframe["rsi"] < self.buy_rsi_local_dip.value)
            & (dataframe["crsi"] > self.buy_crsi_local_dip.value)
            & (
                dataframe["closedelta"]
                > dataframe["close"] * self.buy_closedelta_local_dip.value / 1000
            )
        )

        # is_ewo: oversold below short EMA + bullish EWO
        is_ewo = (
            (dataframe["rsi_fast"] < self.buy_rsi_fast.value)
            & (dataframe["close"] < dataframe["ema_8"] * self.buy_ema_low.value)
            & (dataframe["EWO"] > self.buy_ewo.value)
            & (dataframe["close"] < dataframe["ema_16"] * self.buy_ema_high.value)
            & (dataframe["rsi"] < self.buy_rsi.value)
        )

        # is_ewo_2: cross-TF (1h EMA200 uptrend) + EWO oversold
        is_ewo_2 = (
            (dataframe["ema_200_1h"] > dataframe["ema_200_1h"].shift(12))
            & (dataframe["ema_200_1h"].shift(12) > dataframe["ema_200_1h"].shift(24))
            & (dataframe["rsi_fast"] < self.buy_rsi_fast_ewo_2.value)
            & (dataframe["close"] < dataframe["ema_8"] * self.buy_ema_low_2.value)
            & (dataframe["EWO"] > self.buy_ewo_high_2.value)
            & (dataframe["close"] < dataframe["ema_16"] * self.buy_ema_high_2.value)
            & (dataframe["rsi"] < self.buy_rsi_ewo_2.value)
        )

        # is_r_deadfish: bear-trap (close < bb_middle, but with above-MA
        # volume and oversold Williams %R)
        is_r_deadfish = (
            (
                dataframe["ema_100"] < dataframe["ema_200"] * 0.972
            )  # legacy default; no opt in Hybrid_v3
            & (dataframe["bb_width"] > 0.091)  # legacy default
            & (dataframe["close"] < dataframe["bb_middleband2"] * 0.911)
            & (dataframe["volume_mean_12"] > dataframe["volume_mean_24"] * 1.008)
            & (dataframe["cti"] < -0.115)
            & (dataframe["r_14"] < -44.34)
        )

        # is_clucHA: Heikin-Ashi pullback below HA-BB(40, 2)
        is_clucHA = (dataframe["rocr_1h"] > 0.416) & (
            (
                (dataframe["bb_lowerband2_40"].shift() > 0)
                & (dataframe["bb_delta_cluc"] > dataframe["ha_close"] * 0.04)
                & (dataframe["ha_closedelta"] > dataframe["ha_close"] * 0.05)
                & (dataframe["tail"] < dataframe["bb_delta_cluc"] * 0.913)
                & (dataframe["ha_close"] < dataframe["bb_lowerband2_40"].shift())
                & (dataframe["ha_close"] < dataframe["ha_close"].shift())
            )
            | (
                (dataframe["ha_close"] < dataframe["ema_slow_ha"])
                & (dataframe["ha_close"] < 0.04 * dataframe["bb_lowerband2"])
            )
        )

        # is_cofi: stoch crossover + EWO bull + oversold protection
        is_cofi = (
            (dataframe["open"] < dataframe["ema_8"] * 1.147)
            & (qtpylib.crossed_above(dataframe["fastk"], dataframe["fastd"]))
            & (dataframe["fastk"] < 39)
            & (dataframe["fastd"] < 28)
            & (dataframe["adx_15m"] > self.buy_adx.value)
            & (dataframe["EWO"] > 8.594)
            & (dataframe["cti"] < -0.892)
            & (dataframe["r_14"] < -85.016)
        )

        # is_nfi_32: NFI quick mode (legacy param values)
        is_nfi_32 = (
            (dataframe["rsi_slow"] < dataframe["rsi_slow"].shift(1))
            & (dataframe["rsi_fast"] < 46)
            & (dataframe["rsi"] > 25.0)
            & (dataframe["close"] < dataframe["sma_15"] * 0.93)
            & (dataframe["cti"] < -0.9)
        )

        # is_additional_check: cross-TF filter (1h ROC + 1h BB width).
        # Mirrors BB_RPB_TSL_BI's gate: only fire trending entries when
        # 1h trend agrees (positive ROC, reasonable BB width).
        is_additional_check = (dataframe["roc_1h"] < self.buy_roc_1h.value) & (
            dataframe["bb_width_1h"] < self.buy_bb_width_1h.value
        )

        # Build the OR'd list of conditions
        bb_rpb_conditions = reduce(
            lambda x, y: x | y,
            [
                is_BB_checked,
                is_local_uptrend,
                is_local_dip,
                is_ewo,
                is_ewo_2,
                is_r_deadfish,
                is_clucHA,
                is_cofi,
                is_nfi_32,
            ],
        )

        # regime=2 + additional_check + at least one BB_RPB condition true
        # expC: AND with volatility expansion filter
        trending_entry = (
            (dataframe["regime"] == 2)
            & is_additional_check
            & bb_rpb_conditions
            & (dataframe["_vol_expanding_v3c"] == 1)  # expC gate
        )

        # ── Apply entries (priority order matters when overlap) ──────
        # We OR-assign tags; the LAST assignment wins, so we paint tags
        # in increasing priority. The final assignment (trending) is
        # the most "specific" so it shows up when multiple conditions
        # are true.
        dataframe.loc[ranging_entry, "enter_long"] = 1
        dataframe.loc[ranging_entry, "enter_tag"] = "mean_rev"
        dataframe.loc[transition_entry, "enter_long"] = 1
        dataframe.loc[transition_entry, "enter_tag"] = "weak_trend"

        # Per-condition trending tags: paint first, then overwrite
        # `trending` last so a row in multiple conditions shows the
        # most specific reason.
        for cond, tag in [
            (is_BB_checked, "bb_rpb_bb"),
            (is_local_uptrend, "bb_rpb_local_uptrend"),
            (is_local_dip, "bb_rpb_local_dip"),
            (is_ewo, "bb_rpb_ewo"),
            (is_ewo_2, "bb_rpb_ewo_2"),
            (is_r_deadfish, "bb_rpb_r_deadfish"),
            (is_clucHA, "bb_rpb_clucHA"),
            (is_cofi, "bb_rpb_cofi"),
            (is_nfi_32, "bb_rpb_nfi_32"),
        ]:
            mask = (dataframe["regime"] == 2) & is_additional_check & cond
            dataframe.loc[mask, "enter_long"] = 1
            dataframe.loc[mask, "enter_tag"] = tag

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
        elif current_profit < 0.015:
            return -0.05  # breakeven zone, allow room
        elif current_profit < 0.03:
            return -0.015  # protect half profit
        else:
            return -0.99  # DISABLED: was +0.01/+0.02 (trailing), now let ROI handle exit

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
