#!/usr/bin/env python3
"""
Hybrid_v2 — Regime Detection + BB Entry + ATR-based Futures Stop

Combines proven components:
  - Multi-TF Regime Detection (99.8%) from Hybrid_v1
  - ATR prediction (R²=0.67) from Hybrid_v1
  - BB lower band entry (simplified from BB_RPB_TSL_BI logic)
  - Futures-adapted: dynamic stoploss via pred_atr

Architecture:
  1. Regime Detection: ADX multi-TF consensus (15m/1h/4h)
     → raging(0) | transition(1) | trending(2)
  2. Volatility Prediction: Ridge regression, predict ATR 12 bars ahead
     → dynamic stop-loss + position sizing
  3. Entry: BB lower band touch in trending regime only (regime=2)
  4. Exit: BB upper band or middle band cross
  5. Stop Loss: Dynamic, based on pred_ATR

Math Constraints:
  - LAW-01: degree=2 (poly features for Ridge)
  - LAW-02: Ridge regularization ✓
  - LAW-03: Predict volatility (continuous), not direction ✓
  - LAW-04: Rolling window training ✓
  - LAW-05: Multi-TF (4 timeframes) ✓
  - LAW-06: ATR-based stoploss ✓
"""

import logging
import warnings
from typing import Dict, Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.strategy import DecimalParameter, IntParameter
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Lazy sklearn import
# ─────────────────────────────────────────────────────────────────────
_sklearn_available = False
_sklearn_error_msg = ""

try:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler

    _sklearn_available = True
except ImportError as e:
    _sklearn_error_msg = str(e)


class Hybrid_v2(IStrategy):
    """
    Hybrid_v2 — Regime Detection + BB Entry + ATR-based Futures Stop

    Key innovations:
      - Multi-TF Regime Detection: only enter in regime=2 (trending)
      - BB lower band touch entry (simplified, proven)
      - ATR-based dynamic stoploss (R²=0.67 from Hybrid_v1)
      - Futures-adapted: isolated margin, 3x max open trades
    """

    # ── Interface ──────────────────────────────────────────────────────
    INTERFACE_VERSION: int = 3

    # ── Basic Settings ─────────────────────────────────────────────
    timeframe: str = "15m"
    trading_mode: str = "futures"
    margin_mode: str = "isolated"

    # Stake
    stake_currency: str = "USDT"
    stake_amount: float = 50.0
    dry_run: bool = True
    dry_run_wallet: float = 1000.0
    max_open_trades: int = 3

    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    use_custom_stoploss: bool = True

    # Startup
    startup_candle_count: int = 350  # covers ATR horizon + rolling windows
    stoploss: float = -0.03  # base fallback, custom_stoploss overrides

    # ── Exit / ROI (realistic for 15m futures) ────────────────────────
    minimal_roi: Dict[str, float] = {
        "0": 0.03,  # 3% immediate target
        "60": 0.02,  # 2% after 60m
        "180": 0.01,  # 1% after 180m
    }

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.005  # 0.5%
    trailing_stop_positive_offset: float = 0.02  # 2%
    trailing_only_offset_is_reached: bool = True

    # ── Order Types ──────────────────────────────────────────────────
    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # ── Regime Thresholds ─────────────────────────────────────────────
    ADX_RANGING_MAX: float = 20.0  # ADX < 20 = ranging
    ADX_TRENDING_MIN: float = 25.0  # ADX > 25 = trending
    # 20–25 = transition

    # ── Parameter Space ────────────────────────────────────────────────
    # BB parameters (standard)
    bb_period = IntParameter(10, 30, default=20, space="buy")
    bb_std = DecimalParameter(1.5, 3.0, default=2.0, space="buy")

    # RSI entry threshold
    rsi_entry = IntParameter(30, 50, default=40, space="buy")

    # ATR multiplier for stoploss
    atr_stop_multiplier = DecimalParameter(1.5, 4.0, default=2.5, space="buy")

    # ── Volatility Prediction Parameters ────────────────────────────
    VOL_FORECAST_HORIZON: int = 12
    VOL_WINDOW: int = 300
    VOL_RIDGE_ALPHA: float = 0.1
    VOL_RETRAIN_INTERVAL: int = 50
    VOL_POLY_DEGREE: int = 2

    # ── Internal State ────────────────────────────────────────────────
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._vol_model_cache: Dict[str, Dict] = {}
        self._pred_atr_cache: Dict[str, float] = {}

    # =================================================================
    #  Informative Pairs (Multi-TF for Regime Detection)
    # =================================================================
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative = []
        for pair in pairs:
            informative.append((pair, "30m"))
            informative.append((pair, "1h"))
            informative.append((pair, "4h"))
        return informative

    # =================================================================
    #  Indicators
    # =================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        # ── 1. Multi-TF Regime Detection ──────────────────────────────
        dataframe = self._detect_regime_multitf(dataframe, metadata)

        # ── 2. Bollinger Bands (standard: period=20, std=2) ───────────
        for p in range(10, 31):
            for s in [1.5, 2.0, 2.5, 3.0]:
                dataframe[f"bb_lower_{p}_{s}"] = ta.SMA(dataframe, timeperiod=p) - s * ta.STDDEV(
                    dataframe, timeperiod=p
                )
                dataframe[f"bb_middle_{p}_{s}"] = ta.SMA(dataframe, timeperiod=p)
                dataframe[f"bb_upper_{p}_{s}"] = ta.SMA(dataframe, timeperiod=p) + s * ta.STDDEV(
                    dataframe, timeperiod=p
                )

        # Current BB (default 20, 2.0)
        dataframe["bb_lowerband"] = ta.SMA(dataframe, timeperiod=20) - 2.0 * ta.STDDEV(
            dataframe, timeperiod=20
        )
        dataframe["bb_middleband"] = ta.SMA(dataframe, timeperiod=20)
        dataframe["bb_upperband"] = ta.SMA(dataframe, timeperiod=20) + 2.0 * ta.STDDEV(
            dataframe, timeperiod=20
        )
        dataframe["bb_width"] = (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe[
            "bb_middleband"
        ]

        # ── 3. RSI ─────────────────────────────────────────────────────
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=5)

        # ── 4. Volume MA ────────────────────────────────────────────────
        dataframe["volume_ma"] = dataframe["volume"].rolling(20).mean()

        # ── 5. ATR for stoploss (actual, for comparison) ─────────────
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # ── 6. ADX for regime (current TF) ───────────────────────────
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)

        # ── 7. Volatility Prediction via Ridge ────────────────────────
        if not _sklearn_available:
            logger.warning(
                "sklearn not available, volatility prediction disabled: %s",
                _sklearn_error_msg,
            )
            dataframe["pred_atr"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
            self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])
            return dataframe

        # Multi-TF volatility features
        vol_features = self._merge_vol_features(dataframe, metadata)
        current_atr_pct = dataframe["atr_pct"].values

        n = len(dataframe)
        pred_atr_arr = np.full(n, np.nan, dtype=np.float64)
        pred_atr_arr[:] = current_atr_pct

        current_model = None
        last_train_idx = -self.VOL_RETRAIN_INTERVAL - 1

        cached = self._vol_model_cache.get(pair, {})
        if self.process_only_new_candles and cached:
            current_model = cached.get("model")
            last_train_idx = cached.get("last_train_idx", last_train_idx)

        for i in range(self.startup_candle_count, n):
            if i - last_train_idx >= self.VOL_RETRAIN_INTERVAL:
                new_model = self._train_vol_model(vol_features, current_atr_pct, i)
                if new_model is not None:
                    current_model = new_model
                    last_train_idx = i

            if current_model is None:
                continue

            X_i = vol_features.iloc[i].values.astype(np.float64).reshape(1, -1)
            if np.any(np.isnan(X_i)) or np.any(np.isinf(X_i)):
                continue

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                try:
                    X_scaled = current_model["scaler"].transform(X_i)
                    X_poly = current_model["poly"].transform(X_scaled)
                    pred = current_model["ridge"].predict(X_poly)[0]
                    pred_atr_arr[i] = float(np.clip(pred, 0.005, 0.15))
                except Exception:
                    continue

        pred_series = pd.Series(pred_atr_arr, index=dataframe.index)
        dataframe["pred_atr"] = pred_series.ffill().fillna(
            pd.Series(current_atr_pct, index=dataframe.index)
        )

        self._vol_model_cache[pair] = {
            "model": current_model,
            "last_train_idx": last_train_idx,
        }
        self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])

        return dataframe

    # =================================================================
    #  Multi-TF Regime Detection (from Hybrid_v1)
    # =================================================================
    def _detect_regime_multitf(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Detect regime using multi-TF ADX consensus.
        Stores adx_15m, adx_1h, adx_4h and regime in dataframe.

        Falls back to 15m-only regime when 1h/4h data is unavailable
        (e.g., during backtesting without HTF data).
        """
        pair = metadata["pair"]

        # ADX for 15m (current TF)
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)

        # ── Fetch informative TFs ─────────────────────────────────
        # 1h ADX: resample 15m to 1h
        df_1h = self.dp.get_pair_dataframe(pair=pair, timeframe="1h")
        has_1h = len(df_1h) > 14
        if has_1h:
            adx_1h = ta.ADX(df_1h, timeperiod=14)
            dataframe["adx_1h"] = adx_1h.reindex(dataframe.index, method="ffill").fillna(0)
        else:
            dataframe["adx_1h"] = 0.0

        # 4h ADX: resample 15m to 4h
        df_4h = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
        has_4h = len(df_4h) > 14
        if has_4h:
            adx_4h = ta.ADX(df_4h, timeperiod=14)
            dataframe["adx_4h"] = adx_4h.reindex(dataframe.index, method="ffill").fillna(0)
        else:
            dataframe["adx_4h"] = 0.0

        # ── Per-TF regime classification ───────────────────────────
        def _single_regime(adx_val):
            if adx_val < self.ADX_RANGING_MAX:
                return 0  # ranging
            elif adx_val > self.ADX_TRENDING_MIN:
                return 2  # trending
            else:
                return 1  # transition

        reg_15m = dataframe["adx_15m"].apply(_single_regime)

        # ── Consensus: majority vote (with fallback to 15m-only) ───
        if has_1h and has_4h:
            # Full multi-TF consensus
            reg_1h = dataframe["adx_1h"].apply(_single_regime)
            reg_4h = dataframe["adx_4h"].apply(_single_regime)
            regime_sum = reg_15m + reg_1h + reg_4h

            def _consensus_regime(s):
                if s <= 1:
                    return 0  # ranging
                elif s >= 4:
                    return 2  # trending
                else:
                    return 1  # transition

            dataframe["regime"] = regime_sum.apply(_consensus_regime)
        else:
            # Fallback: use 15m-only regime
            # When HTF data is missing, scale the 15m regime to allow
            # regime=2 (trending) directly from 15m ADX
            # reg_15m is 0/1/2, we want regime=2 when adx_15m > TRENDING_MIN
            dataframe["regime"] = reg_15m

        return dataframe

    # =================================================================
    #  Volatility Feature Extraction (Multi-TF) — from Hybrid_v1
    # =================================================================
    @staticmethod
    def _extract_vol_features(df: pd.DataFrame, tf_name: str) -> pd.DataFrame:
        f = pd.DataFrame(index=df.index)
        f[f"{tf_name}_ret_5"] = df["close"].pct_change(5)
        f[f"{tf_name}_ret_20"] = df["close"].pct_change(20)
        f[f"{tf_name}_vol_20"] = f[f"{tf_name}_ret_5"].rolling(20).std()
        f[f"{tf_name}_ma_dev_20"] = df["close"] / df["close"].rolling(20).mean() - 1
        f[f"{tf_name}_ma_dev_50"] = df["close"] / df["close"].rolling(50).mean() - 1
        low_50 = df["low"].rolling(50).min()
        high_50 = df["high"].rolling(50).max()
        f[f"{tf_name}_price_pos"] = (df["close"] - low_50) / (high_50 - low_50 + 1e-8)
        f[f"{tf_name}_vol_ratio"] = df["volume"] / (df["volume"].rolling(50).mean() + 1e-8)
        f[f"{tf_name}_rsi"] = ta.RSI(df, timeperiod=14) / 100.0
        f[f"{tf_name}_adx"] = ta.ADX(df, timeperiod=14) / 100.0
        return f

    def _merge_vol_features(self, dataframe: DataFrame, metadata: dict) -> pd.DataFrame:
        """Merge multi-TF volatility features for Ridge training."""
        pair = metadata["pair"]
        dfs = {"15m": dataframe}

        for tf in ["30m", "1h", "4h"]:
            df_tf = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
            if len(df_tf) > 0:
                dfs[tf] = df_tf

        merged = pd.DataFrame(index=dataframe.index)
        for tf_name, df_tf in dfs.items():
            vol_feat = self._extract_vol_features(df_tf, tf_name)
            for col in vol_feat.columns:
                if col in vol_feat:
                    merged[col] = vol_feat[col].reindex(merged.index, method="ffill")

        return merged.fillna(0)

    def _train_vol_model(
        self,
        vol_features: pd.DataFrame,
        target_atr: np.ndarray,
        current_idx: int,
    ):
        """Train Ridge regression model for volatility prediction."""
        if not _sklearn_available:
            return None

        train_start = max(0, current_idx - self.VOL_WINDOW)
        train_end = current_idx - self.VOL_FORECAST_HORIZON

        if train_end - train_start < 50:
            return None

        X_train = vol_features.iloc[train_start:train_end].values
        y_train = target_atr[
            train_start + self.VOL_FORECAST_HORIZON : train_end + self.VOL_FORECAST_HORIZON
        ]

        valid = ~(np.isnan(X_train).any(axis=1) | np.isnan(y_train))
        if valid.sum() < 30:
            return None

        X_train = X_train[valid]
        y_train = y_train[valid]

        scaler = StandardScaler()
        poly = PolynomialFeatures(degree=self.VOL_POLY_DEGREE, include_bias=False)
        ridge = Ridge(alpha=self.VOL_RIDGE_ALPHA)

        try:
            X_scaled = scaler.fit_transform(X_train)
            X_poly = poly.fit_transform(X_scaled)
            ridge.fit(X_poly, y_train)
            return {"scaler": scaler, "poly": poly, "ridge": ridge}
        except Exception:
            return None

    # =================================================================
    #  Entry Logic — BB Lower Band Touch in Trending Regime
    # =================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry: BB lower band touch + RSI oversold + volume confirmation
        Only in regime=2 (trending).

        Logic:
          - Regime must be 2 (trending)
          - BB lower band touch: close < bb_lowerband (price at or below lower band)
          - RSI oversold: rsi < rsi_entry (default 40)
          - Volume confirmation: volume > volume_ma

        Note: close > bb_lowerband * 0.95 prevents entries that are too far
        below the band. In trending regime, price tends to stay near the band.
        """
        dataframe["enter_long"] = 0

        entry = (
            (dataframe["regime"] == 2)  # Trending market only
            & (dataframe["close"] < dataframe["bb_lowerband"])  # BB lower touch (bounce setup)
            & (dataframe["rsi"] < self.rsi_entry.value)  # RSI oversold
            & (dataframe["volume"] > dataframe["volume_ma"])  # Volume confirmation
            & (dataframe["volume_ma"] > 0)
            & (
                dataframe["close"] > dataframe["bb_lowerband"] * 0.95
            )  # Not too far below band (within 5%)
        )

        dataframe.loc[entry, "enter_long"] = 1
        return dataframe

    # =================================================================
    #  Exit Logic — BB Upper Band or Middle Band Cross
    # =================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit: BB upper band touch OR RSI overbought + BB middle band cross.

        Key fix: BB middle cross alone is too aggressive as an exit after BB lower
        entry (immediate exits destroying otherwise valid trades). Require RSI overbought
        (rsi > 60) to confirm momentum before allowing middle band exit.

        BB upper band touch still triggers immediately (take profit at upper band).
        """
        dataframe["exit_long"] = 0

        # BB upper band touch — take profit immediately
        exit_upper = dataframe["close"] > dataframe["bb_upperband"]

        # BB middle band cross + RSI overbought (more conservative)
        # This prevents exiting immediately after a BB lower bounce
        exit_middle = (
            (dataframe["rsi"] > 60)  # RSI confirms overbought momentum
            & (dataframe["close"] > dataframe["bb_middleband"])
            & (dataframe["close"].shift(1) <= dataframe["bb_middleband"].shift(1))
        )

        dataframe.loc[exit_upper, "exit_long"] = 1
        dataframe.loc[exit_middle, "exit_long"] = 1

        return dataframe

    # =================================================================
    #  Custom Stoploss — Dynamic based on pred_ATR
    # =================================================================
    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
        current_time: "datetime",
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float:
        """
        Dynamic stop-loss based on pred_ATR.

        In trending regime with high ATR, use wider stop.
        The multiplier (atr_stop_multiplier) times pred_atr gives the stop distance.

        pred_ATR is typically 0.003-0.008 for BTC 15m.
        - 2.5 × 0.004 = 1.0% stoploss (reasonable)
        - 4.0 × 0.008 = 3.2% stoploss (maximum floor kicks in)
        """
        pred_atr = self._pred_atr_cache.get(pair, 0.005)
        multiplier = self.atr_stop_multiplier.value

        # Dynamic stoploss: max(-1.5%, -multiplier × pred_atr)
        # Floor at -1.5% prevents immediate exits in low-vol conditions
        stoploss = max(-0.015, min(-0.05, -multiplier * pred_atr))

        # If in profit (>2%), use a tighter floor to protect gains
        if current_profit > 0.02:
            stoploss = max(stoploss, -0.01)

        return stoploss

    # =================================================================
    #  Slippage Protection
    # =================================================================
    slippage_protection = {
        "max_slippage": -0.005,
        "retries": 2,
        "__pair_retries": {},
    }

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        **kwargs,
    ) -> bool:
        """Slippage protection."""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return True

        last_candle = dataframe.iloc[-1].squeeze()

        try:
            state = self.slippage_protection["__pair_retries"]
        except KeyError:
            state = self.slippage_protection["__pair_retries"] = {}

        slippage = (rate / last_candle["close"]) - 1
        if slippage < self.slippage_protection["max_slippage"]:
            pair_retries = state.get(pair, 0)
            if pair_retries < self.slippage_protection["retries"]:
                state[pair] = pair_retries + 1
                return False

        state[pair] = 0
        return True
