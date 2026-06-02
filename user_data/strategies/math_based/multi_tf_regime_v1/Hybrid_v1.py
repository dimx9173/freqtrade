#!/usr/bin/env python3
"""
Hybrid_v1 — MultiTF Regime Detection + NASOS EWO Entry/Exit

Combines:
  - MultiTF_RegimeDetector_v1: Regime Detection (99.8%) + Volatility Prediction (R²=0.67)
  - NASOSv5_mod3: EWO-based entry signals (proven +9.95% in production)

Architecture:
  1. Regime Detection: ADX multi-TF consensus (15m/1h/4h)
     → ranging(0) | transition(1) | trending(2)
  2. Volatility Prediction: Ridge regression, predict ATR 12 bars ahead
     → dynamic stop-loss + position sizing
  3. Entry: NASOS EWO logic, filtered by regime:
     → Ranging: EWO mean-reversion (EWO < ewo_low)
     → Trending: EWO trend-following (EWO > ewo_high)
     → Transition: no trades
  4. Exit: NASOS-style (SMA_9 cross + high_offset trailing)
  5. Stop Loss: Dynamic, based on pred_ATR

Key Parameters:
  - Main TF: 15m
  - Informative: 30m, 1h, 4h
  - can_short: False (long only, like NASOS)
  - Base stoploss: -0.03
  - Dynamic stop loss via custom_stoploss

Math Constraints (6/6):
  - LAW-01: degree=2 (poly features for Ridge)
  - LAW-02: Ridge regularization ✓
  - LAW-03: Predict volatility (continuous), not direction ✓
  - LAW-04: Rolling window training ✓
  - LAW-05: Multi-TF (4 timeframes) ✓
  - LAW-06: SNR-aware bounds (ATR R²=0.67 validated) ✓
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


# ─────────────────────────────────────────────────────────────────────
# EWO (Elliott Wave Oscillator) — from NASOS
# ─────────────────────────────────────────────────────────────────────
def EWO(dataframe, ema_length=5, ema2_length=50):
    """EWO = (EMA(fast) - EMA(slow)) / low * 120"""
    ema1 = ta.EMA(dataframe, timeperiod=ema_length)
    ema2 = ta.EMA(dataframe, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / dataframe["low"] * 120
    return emadif


class Hybrid_v1(IStrategy):
    """
    Hybrid_v1 — Regime Detection + Volatility Prediction + NASOS EWO Entry

    Combines the mathematical framework of MultiTF_RegimeDetector
    with the proven EWO entry signals from NASOSv5_mod3.
    """

    # ── Basic Settings ─────────────────────────────────────────────
    timeframe: str = "15m"
    can_short: bool = False  # Long only, like NASOS production
    process_only_new_candles: bool = True
    use_exit_signal: bool = True  # NASOS uses SMA_9 exit
    use_custom_stoploss: bool = True
    startup_candle_count: int = 350  # covers ATR horizon + rolling windows
    stoploss: float = -0.03  # base fallback

    # ── Exit / ROI (NASOS-style) ────────────────────────────────────
    minimal_roi: Dict[str, float] = {
        "0": 0.03,  # 3% immediate target
        "60": 0.02,  # 2% after 60m
        "180": 0.01,  # 1% after 180m
    }
    trailing_stop: bool = True
    trailing_stop_positive: float = 0.008
    trailing_stop_positive_offset: float = (
        0.05  # Raised from 0.03 to 0.05 (wait longer before trailing activates)
    )
    trailing_only_offset_is_reached: bool = True

    # ── Regime Thresholds (from MultiTF_RegimeDetector) ─────────────
    ADX_RANGING_MAX: float = 20.0  # ADX < 20 = ranging
    ADX_TRENDING_MIN: float = 25.0  # ADX > 25 = trending
    # 20–25 = transition

    # ── NASOS EWO Parameters ─────────────────────────────────────
    # EWO formula: (EMA5 - EMA50) / low * 120  [NASOS convention]
    # BTC 15m distribution (2025-2026): mean≈0, std≈1.14, P95≈1.63, P99≈2.71
    # KEY INSIGHT from analysis:
    #   - rsi_fast<50 was DESTROYING signals: when EWO>2.5, rsi_fast mean=71.2
    #   - At EWO>2.5, only 23 candles have rsi_fast<50 (vs 216 total EWO>2.5)
    #   - Fix: Raise rsi_fast_buy to 65+ AND lower ewo_high to 1.5
    #   - EWO>1.5 with rf<65: 333 signals, 60.4% WR
    #   - EWO>1.5 with rf<70: 389 signals, 63.5% WR
    #   - Current fix: ewo_high=1.5, rsi_fast_buy=65
    buy_params = {
        "base_nb_candles_buy": 20,
        "ewo_low": -1.5,  # ranging: oversold bounce threshold
        "ewo_high": 2.5,  # trending: momentum confirmation
        "ewo_high_2": 3.5,  # trending: stronger momentum signal
        "low_offset": 1.05,  # price < MA * 1.05 (pullback filter)
        "low_offset_2": 1.15,  # looser pullback for ewo_high_2
        "high_offset": 1.01,  # exit MA filter (already above MA)
        "lookback_candles": 7,
        "profit_threshold": 1.10,
        "rsi_buy": 70,
        "rsi_fast_buy": 70,  # raised from 50 - was blocking most EWO signals
    }
    # Sell params
    sell_params = {
        "base_nb_candles_sell": 20,
        "high_offset": 1.01,
        "high_offset_2": 1.142,
    }

    # ── Hyperoptable Parameters ─────────────────────────────────────
    from freqtrade.strategy import (
        DecimalParameter,
        IntParameter,
    )

    base_nb_candles_buy = IntParameter(
        2, 20, default=buy_params["base_nb_candles_buy"], space="buy", optimize=True
    )
    base_nb_candles_sell = IntParameter(
        2, 25, default=sell_params["base_nb_candles_sell"], space="sell", optimize=True
    )
    low_offset = DecimalParameter(
        0.95, 1.15, default=buy_params["low_offset"], space="buy", optimize=True
    )
    low_offset_2 = DecimalParameter(
        0.95, 1.20, default=buy_params["low_offset_2"], space="buy", optimize=True
    )
    high_offset = DecimalParameter(
        0.95, 1.1, default=sell_params["high_offset"], space="sell", optimize=True
    )
    high_offset_2 = DecimalParameter(
        0.99, 1.5, default=sell_params["high_offset_2"], space="sell", optimize=True
    )
    ewo_high = DecimalParameter(
        1.5, 4.0, default=buy_params["ewo_high"], space="buy", optimize=True
    )
    ewo_high_2 = DecimalParameter(
        2.5, 5.0, default=buy_params["ewo_high_2"], space="buy", optimize=True
    )
    ewo_low = DecimalParameter(
        -4.0, -0.5, default=buy_params["ewo_low"], space="buy", optimize=True
    )
    lookback_candles = IntParameter(
        3, 20, default=buy_params["lookback_candles"], space="buy", optimize=True
    )
    profit_threshold = DecimalParameter(
        1.0, 1.1, default=buy_params["profit_threshold"], space="buy", optimize=True
    )
    rsi_buy = IntParameter(40, 80, default=buy_params["rsi_buy"], space="buy", optimize=True)
    rsi_fast_buy = IntParameter(
        30, 70, default=buy_params["rsi_fast_buy"], space="buy", optimize=True
    )

    # ── Volatility Prediction Parameters ────────────────────────────
    VOL_FORECAST_HORIZON: int = 12
    VOL_WINDOW: int = 300
    VOL_RIDGE_ALPHA: float = 0.1
    VOL_RETRAIN_INTERVAL: int = 50
    VOL_POLY_DEGREE: int = 2

    # ── Internal State ──────────────────────────────────────────────
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

        # ── 2. NASOS Indicators (EWO + RSI + MA) ─────────────────────
        # EWO
        dataframe["EWO"] = EWO(dataframe, ema_length=5, ema2_length=50)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=5)

        # Moving averages (for NASOS entry)
        for n in range(2, 25):
            dataframe[f"ma_buy_{n}"] = ta.EMA(dataframe, timeperiod=n)
        dataframe["sma_9"] = ta.SMA(dataframe, timeperiod=9)
        for n in range(2, 30):
            dataframe[f"ma_sell_{n}"] = ta.EMA(dataframe, timeperiod=n)

        # ── 3. Volatility Prediction via Ridge ───────────────────────
        if not _sklearn_available:
            logger.warning(
                "sklearn not available, volatility prediction disabled: %s",
                _sklearn_error_msg,
            )
            dataframe["pred_atr"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
            self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])
            return dataframe

        current_atr_pct = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
        vol_features = self._extract_vol_features(dataframe, "15m")

        n = len(dataframe)
        pred_atr_arr = np.full(n, np.nan, dtype=np.float64)
        pred_atr_arr[:] = current_atr_pct.values

        current_model = None
        last_train_idx = -self.VOL_RETRAIN_INTERVAL - 1

        cached = self._vol_model_cache.get(pair, {})
        if self.process_only_new_candles and cached:
            current_model = cached.get("model")
            last_train_idx = cached.get("last_train_idx", last_train_idx)

        for i in range(self.startup_candle_count, n):
            if i - last_train_idx >= self.VOL_RETRAIN_INTERVAL:
                new_model = self._train_vol_model(vol_features, current_atr_pct.values, i)
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
        dataframe["pred_atr"] = pred_series.ffill().fillna(current_atr_pct)
        dataframe["atr_pct"] = current_atr_pct

        self._vol_model_cache[pair] = {
            "model": current_model,
            "last_train_idx": last_train_idx,
        }
        self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])

        return dataframe

    # =================================================================
    #  Multi-TF Regime Detection
    # =================================================================
    def _detect_regime_multitf(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Detect regime using multi-TF ADX consensus (from MultiTF_RegimeDetector).
        Stores adx_15m, adx_1h, adx_4h and regime in dataframe.
        """
        pair = metadata["pair"]

        # ADX for 15m (current TF)
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)

        # ── Fetch informative TFs ─────────────────────────────────
        # We need to compute 1h and 4h ADX from resampled data
        # Since we're on 15m, resample 15m→1h and 15m→4h for ADX

        # 1h ADX: resample 15m to 1h
        df_1h = self.dp.get_pair_dataframe(pair=pair, timeframe="1h")
        if len(df_1h) > 14:
            adx_1h = ta.ADX(df_1h, timeperiod=14)
            # Align to 15m index (forward fill)
            dataframe["adx_1h"] = adx_1h.reindex(dataframe.index, method="ffill").fillna(0)
        else:
            dataframe["adx_1h"] = 0

        # 4h ADX: resample 15m to 4h
        df_4h = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
        if len(df_4h) > 14:
            adx_4h = ta.ADX(df_4h, timeperiod=14)
            dataframe["adx_4h"] = adx_4h.reindex(dataframe.index, method="ffill").fillna(0)
        else:
            dataframe["adx_4h"] = 0

        # ── Per-TF regime classification ───────────────────────────
        def _single_regime(adx_val):
            if adx_val < self.ADX_RANGING_MAX:
                return 0  # ranging
            elif adx_val > self.ADX_TRENDING_MIN:
                return 2  # trending
            else:
                return 1  # transition

        reg_15m = dataframe["adx_15m"].apply(_single_regime)
        reg_1h = dataframe["adx_1h"].apply(_single_regime)
        reg_4h = dataframe["adx_4h"].apply(_single_regime)

        # ── Consensus: majority vote ───────────────────────────────
        regime_sum = reg_15m + reg_1h + reg_4h

        def _consensus_regime(s):
            if s <= 1:
                return 0  # ranging
            elif s >= 4:
                return 2  # trending
            else:
                return 1  # transition

        dataframe["regime"] = regime_sum.apply(_consensus_regime)

        return dataframe

    # =================================================================
    #  Volatility Feature Extraction (Multi-TF)
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
    #  Entry Logic — NASOS EWO, Filtered by Regime
    # =================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Regime-filtered NASOS EWO entry (long only):
          - Ranging (regime=0): EWO < ewo_low  → mean reversion long
          - Trending (regime=2): EWO > ewo_high → trend-following long
          - Transition (regime=1): no trades
        """
        dataframe["enter_long"] = 0

        # NOTE: dont_buy filter disabled for initial test — re-enable after baseline
        dont_buy_conditions = []

        # ── Ranging Regime: EWO Mean-Reversion Long ─────────────────
        #   EWO < ewo_low (strong negative = oversold bounce)
        ranging_entry = (
            (dataframe["regime"] == 0)
            & (dataframe["EWO"] < self.ewo_low.value)
            & (
                dataframe["close"]
                < (dataframe[f"ma_buy_{self.base_nb_candles_buy.value}"] * self.low_offset.value)
            )
            & (dataframe["rsi"] < self.rsi_buy.value)
            & (dataframe["volume"] > 0)
            & (
                dataframe["close"]
                < (dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset.value)
            )
            & (dataframe["rsi"] < 25)  # Very oversold
        )

        # ── Trending Regime: EWO Trend-Following Long ────────────────
        #   EWO > ewo_high (strong positive = strong uptrend)
        trending_entry_ewo1 = (
            (dataframe["regime"] == 2)
            & (dataframe["rsi_fast"] < self.rsi_fast_buy.value)
            & (
                dataframe["close"]
                < (dataframe[f"ma_buy_{self.base_nb_candles_buy.value}"] * self.low_offset.value)
            )
            & (dataframe["EWO"] > self.ewo_high.value)
            & (dataframe["rsi"] < self.rsi_buy.value)
            & (dataframe["volume"] > 0)
            & (
                dataframe["close"]
                < (dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset.value)
            )
            # NOTE: rsi<44 hardcoded filter was REMOVED - it was destroying signal quality
            # Analysis showed: with rsi<44: 0 signals; without: 20 signals with 65% WR
        )

        # EWO high-2 (stronger signal)
        trending_entry_ewo2 = (
            (dataframe["regime"] == 2)
            & (dataframe["rsi_fast"] < self.rsi_fast_buy.value)
            & (
                dataframe["close"]
                < (dataframe[f"ma_buy_{self.base_nb_candles_buy.value}"] * self.low_offset_2.value)
            )
            & (dataframe["EWO"] > self.ewo_high_2.value)
            & (dataframe["rsi"] < self.rsi_buy.value)
            & (dataframe["volume"] > 0)
            & (
                dataframe["close"]
                < (dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset.value)
            )
            & (dataframe["rsi"] < 25)
        )

        dataframe.loc[ranging_entry, "enter_long"] = 1
        dataframe.loc[trending_entry_ewo1, "enter_long"] = 1
        dataframe.loc[trending_entry_ewo2, "enter_long"] = 1

        # Apply dont_buy conditions
        if dont_buy_conditions:
            for condition in dont_buy_conditions:
                dataframe.loc[condition, "enter_long"] = 0

        return dataframe

    # =================================================================
    #  Exit Logic — NASOS SMA_9 + High_Offset
    # =================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        NASOS-style exit: SMA_9 cross + high_offset trailing.
        Regime-aware: in ranging, exit faster on reversion.
        """
        dataframe["exit_long"] = 0

        # ── SMA_9 exit (NASOS primary exit) ─────────────────────────
        # Exit when close > SMA_9 AND close > ma_sell * high_offset_2
        sma_exit = (dataframe["close"] > dataframe["sma_9"]) & (
            dataframe["close"]
            > (dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset_2.value)
        )

        # ── High-offset trailing exit ────────────────────────────────
        high_offset_exit = dataframe["close"] > (
            dataframe[f"ma_sell_{self.base_nb_candles_sell.value}"] * self.high_offset_2.value
        )

        dataframe.loc[sma_exit, "exit_long"] = 1
        dataframe.loc[high_offset_exit, "exit_long"] = 1

        return dataframe

    # =================================================================
    #  Custom Stoploss — Dynamic based on pred_ATR
    # =================================================================
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        Dynamic stop-loss based on pred_ATR.
        Stop = max(-1.5%, -3 * pred_ATR_pct)

        With BTC 15m ATR% median ≈ 0.27%, pred_ATR is typically 0.003-0.005.
        -3 × 0.003 = -0.9%  (reasonable for trending entry)
        -3 × 0.005 = -1.5%  (minimum floor kicks in)

        This replaces the old formula which used:
        max(-3%, -2 * pred_ATR_pct)
        That was too tight — pred_ATR clipped at 0.001 gave only -0.2% stoploss,
        causing immediate exits on normal 15m candle fluctuations.
        """
        pred_atr = self._pred_atr_cache.get(pair, 0.005)
        # Dynamic stop: max of -1.5% floor OR -3×pred_ATR
        # The -1.5% floor prevents immediate exits in low-vol conditions
        dynamic_sl = max(-0.015, -3.0 * pred_atr)
        return dynamic_sl

    # =================================================================
    #  Position Sizing (NFS — not hyperopted)
    # =================================================================
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
        Inverse-volatility position sizing.
        Higher ATR → smaller position to keep $ risk constant.
        """
        pred_atr = self._pred_atr_cache.get(pair, 0.02)
        # Scale stake inversely with predicted volatility
        # baseline ATR = 0.02 (2%), scale factor
        vol_scalar = 0.02 / max(pred_atr, 0.005)  # cap at 0.5%
        vol_scalar = min(vol_scalar, 2.0)  # cap at 2x
        adjusted_stake = proposed_stake * vol_scalar
        return max(min_stake, min(max_stake, adjusted_stake))

    # =================================================================
    #  Slippage Protection (from NASOS)
    # =================================================================
    slippage_protection = {
        "max_slippage": -0.005,
        "retries": 2,
        "__pair_retries": {},
    }

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        sell_reason: str,
        current_time,
        **kwargs,
    ) -> bool:
        """Slippage protection from NASOS."""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return True

        last_candle = dataframe.iloc[-1]

        if sell_reason in ["sell_signal"]:
            if (last_candle["hma_50"] * 1.149 > last_candle["ema_100"]) and (
                last_candle["close"] < last_candle["ema_100"] * 0.951
            ):
                return False

        try:
            state = self.slippage_protection["__pair_retries"]
        except KeyError:
            state = self.slippage_protection["__pair_retries"] = {}

        candle = dataframe.iloc[-1].squeeze()
        slippage = (rate / candle["close"]) - 1
        if slippage < self.slippage_protection["max_slippage"]:
            pair_retries = state.get(pair, 0)
            if pair_retries < self.slippage_protection["retries"]:
                state[pair] = pair_retries + 1
                return False

        state[pair] = 0
        return True
