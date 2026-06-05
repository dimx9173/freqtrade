#!/usr/bin/env python3
"""
Hybrid_v3_MSI — Hybrid_v3 + Cross-Asset MSI Filter

Design ref: user_data/reports/hybrid_v3_msi_integration_design.md

Differences from Hybrid_v3 (parent class):
  1. informative_pairs() — adds 8 cross-asset pairs (1h)
  2. populate_indicators() — adds `msi` (Market Structure Index from 9-asset corr matrix)
  3. populate_entry_trend() — applies MSI gate:
       - MSI < msi_low (low dispersion, strong trend): ENABLE all entry types
       - MSI in [low, high]: NORMAL (Hybrid_v3 default)
       - MSI > msi_high (high dispersion, regime chaos): DISABLE BB_RPB trending entries
  4. Other logic INHERITED from Hybrid_v3

MSI Theory (from "ORCA" paper):
  - Eigenvalue-based Market Structure Index: effective rank of correlation matrix
  - High MSI = asset returns uncorrelated = high dispersion (crisis/recovery)
  - Low MSI = asset returns highly correlated (one-factor market)
  - Hypothesis: in high-dispersion regimes, BB_RPB trend-following entries
    have lower WR because market is "noisy" / regime-shifting
"""
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IntParameter
from Hybrid_v3 import Hybrid_v3

logger = logging.getLogger(__name__)


# ====================================================================
# Cross-Asset Symbol List (8 non-BTC, must match bybit data folder)
# ====================================================================
# We will compute MSI from 9 symbols: BTC (subject) + 8 others
# BTC is loaded as the main pair, the 8 others are loaded via informative_pairs
CROSS_ASSET_SYMBOLS = ["ETH", "SOL", "BNB", "LINK", "DOGE", "ADA", "AVAX", "SUI"]


class Hybrid_v3_MSI(Hybrid_v3):
    """
    Hybrid_v3 augmented with cross-asset Market Structure Index (MSI) gate.

    MSI is computed from the 9-asset correlation matrix's eigenvalue structure.
    Trades in trending regime (BB_RPB stack) are gated by MSI:
      - MSI < 6.5  → low dispersion, strong trend → ALLOW
      - 6.5 ≤ MSI ≤ 8.0 → normal → Hybrid_v3 default behavior
      - MSI > 8.0  → high dispersion, regime chaos → BLOCK trending entries
    """

    # ── MSI Filter Parameters (Optuna/Hyperopt candidates) ──────────
    # NOTE: 8-asset MSI (no BTC) range typically 1.0~3.5
    # Calibration (2026-06-05): empirical mean=1.56, range=[1.07, 3.58]
    is_optimize_msi = True
    msi_low_threshold = IntParameter(
        1, 2, default=1, space="buy", optimize=is_optimize_msi
    )  # below = low dispersion
    msi_high_threshold = IntParameter(
        2, 4, default=3, space="buy", optimize=is_optimize_msi
    )  # above = high dispersion (block)

    # MSI rolling window (in 1h bars)
    # 24 = 24h lookback, 72 = 3 days, 168 = 1 week
    MSI_WINDOW = 24

    # Minimum bars required to compute MSI (skip if not enough history)
    MSI_MIN_BARS = 24

    # ==================================================================
    #  Informative Pairs — add 8 cross-asset 1h pairs
    # ==================================================================
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative = []
        for pair in pairs:
            # Original 3 timeframes
            informative.append((pair, "30m"))
            informative.append((pair, "1h"))
            informative.append((pair, "4h"))
        # Add 8 cross-asset 1h pairs for MSI calculation
        # These are loaded even if not in current_whitelist()
        for sym in CROSS_ASSET_SYMBOLS:
            cross_pair = f"{sym}/USDT"
            if cross_pair not in pairs:
                informative.append((cross_pair, "1h"))
        return informative

    # ==================================================================
    #  MSI Computation
    # ==================================================================
    @staticmethod
    def _compute_msi(close_df: pd.DataFrame, window: int = 24) -> pd.Series:
        """
        Compute Market Structure Index (Participation Ratio) from rolling
        correlation matrix of multi-asset log returns.

        Parameters
        ----------
        close_df : pd.DataFrame
            Columns = asset symbols, index = datetime, values = close prices
        window : int
            Rolling lookback in bars (24 = 24h for 1h TF)

        Returns
        -------
        pd.Series
            MSI values, indexed by datetime (same as close_df)
        """
        if close_df.empty or len(close_df) < window + 1:
            return pd.Series(dtype=float, index=close_df.index)

        # Log returns
        log_ret = np.log(close_df / close_df.shift(1))

        # Rolling MSI
        msi_series = pd.Series(np.nan, index=close_df.index)
        # Convert to numpy for speed
        log_ret_arr = log_ret.values
        n_assets = log_ret.shape[1]
        idx_arr = log_ret.index.to_numpy()

        for i in range(window, len(log_ret)):
            window_data = log_ret_arr[i - window : i]
            # Skip if any NaN in window
            if np.isnan(window_data).any():
                continue
            try:
                # Compute correlation matrix
                corr = np.corrcoef(window_data.T)
                # Replace NaN with 0 (constant series)
                corr = np.nan_to_num(corr, nan=0.0)
                # Eigenvalues
                eigvals = np.linalg.eigvalsh(corr)
                eigvals = np.maximum(eigvals, 0)
                # Participation Ratio: (sum λ)² / sum(λ²)
                # Bounded: 1 ≤ PR ≤ N
                eig_sum = eigvals.sum()
                eig_sq_sum = (eigvals ** 2).sum()
                if eig_sq_sum < 1e-10:
                    continue
                pr = (eig_sum ** 2) / eig_sq_sum
                msi_series.iloc[i] = pr
            except Exception:
                continue

        return msi_series

    # ==================================================================
    #  Override populate_indicators — add MSI
    # ==================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Call parent to get all Hybrid_v3 indicators
        dataframe = super().populate_indicators(dataframe, metadata)

        # Now compute MSI from cross-asset 1h data
        try:
            # Load 8 cross-asset 1h closes (8 assets is enough for MSI)
            # Note: dataframe.index is plain Index, not DatetimeIndex
            all_closes = {}

            for sym in CROSS_ASSET_SYMBOLS:
                cross_pair = f"{sym}/USDT"
                try:
                    cross_df = self.dp.get_pair_dataframe(pair=cross_pair, timeframe="1h")
                    if cross_df is not None and not cross_df.empty:
                        all_closes[sym] = cross_df["close"]
                except Exception as e:
                    logger.debug("MSI: failed to load %s: %s", cross_pair, e)
                    continue

            if len(all_closes) < 3:
                logger.warning("MSI: insufficient cross-asset data (%d symbols), skipping",
                               len(all_closes))
                dataframe["msi"] = np.nan
                return dataframe

            # Build aligned close DataFrame
            close_df = pd.DataFrame(all_closes)
            # Inner-join to common timestamps
            close_df = close_df.dropna(how="any")

            if len(close_df) < self.MSI_MIN_BARS:
                logger.warning("MSI: insufficient history (%d bars), need %d",
                               len(close_df), self.MSI_MIN_BARS)
                dataframe["msi"] = np.nan
                return dataframe

            # Compute MSI (1h frequency)
            msi_1h = self._compute_msi(close_df, window=self.MSI_WINDOW)

            # Map 1h MSI back to 15m index via forward-fill
            # Force both indexes to DatetimeIndex for safe merge_asof
            if not isinstance(dataframe.index, pd.DatetimeIndex):
                df_ts = pd.DatetimeIndex(dataframe.index)
            else:
                df_ts = dataframe.index

            if not isinstance(msi_1h.index, pd.DatetimeIndex):
                msi_1h.index = pd.DatetimeIndex(msi_1h.index)

            # Build temp dataframes for merge_asof
            msi_temp = pd.DataFrame({"msi": msi_1h.values}, index=msi_1h.index)
            df_temp = pd.DataFrame({"_idx": range(len(dataframe))}, index=df_ts)

            # Sort both by index (required for merge_asof)
            msi_temp = msi_temp.sort_index()
            df_temp = df_temp.sort_index()

            merged = pd.merge_asof(
                df_temp,
                msi_temp,
                left_index=True,
                right_index=True,
                direction="backward",
            )

            # Backfill any leading NaN
            merged["msi"] = merged["msi"].ffill().bfill()

            # Sort by original order (_idx) and assign back
            merged_sorted = merged.sort_values("_idx")
            dataframe["msi"] = merged_sorted["msi"].values

            logger.info(
                "MSI computed: mean=%.2f, range=[%.2f, %.2f], n=%d",
                np.nanmean(merged["msi"].values),
                np.nanmin(merged["msi"].values),
                np.nanmax(merged["msi"].values),
                np.isfinite(merged["msi"].values).sum()
            )

        except Exception as e:
            logger.warning("MSI computation failed: %s", e)
            dataframe["msi"] = np.nan

        return dataframe

    # ==================================================================
    #  Override populate_entry_trend — apply MSI gate
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Call parent to compute all Hybrid_v3 entry conditions
        dataframe = super().populate_entry_trend(dataframe, metadata)

        # Apply MSI gate
        msi_low = self.msi_low_threshold.value
        msi_high = self.msi_high_threshold.value

        # MSI condition 1: high dispersion (regime chaos) — block trending entries
        # Only block when MSI is not NaN (i.e., we have enough data)
        msi_chaos = (
            (dataframe["msi"].notna())
            & (dataframe["msi"] > msi_high)
        )

        # Block trending entries in chaos regime
        # Original enter_long=1 → keep only if not in chaos
        # (Hybrid_v3 also sets enter_tag, so we preserve it)
        in_chaos = msi_chaos & (dataframe["regime"] == 2)
        dataframe.loc[in_chaos, "enter_long"] = 0
        # Don't clear enter_tag — keep for analysis

        # Note: low-dispersion (MSI < low) does NOT block — it allows all entries
        # (we want to enable in low-dispersion regime, which is the default)

        return dataframe
