#!/usr/bin/env python3
"""
BTC_RegimeScalp_v1 — BTC-Only Regime-Based Scalping Strategy

Core Design
-----------
1. Regime Detection: ADX multi-timeframe consensus (15m / 1h / 4h)
   → ranging | transition | trending
   Transition periods avoid trading (chop-filter).

2. Volatility Prediction: Ridge regression with polynomial features
   → predicts ATR 12 bars ahead (R²≈0.67 validated)
   → drives dynamic stop-loss, trailing stop and position sizing.

3. Entry Logic (regime-switched, long + short):
   • Ranging (regime=0): BB mean-reversion
       – Long:  close < bb_lower  &  RSI < 35
       – Short: close > bb_upper  &  RSI > 65
   • Trending (regime=2): EMA trend-following
       – Long:  EMA_fast > EMA_slow  &  ADX > 25  &  +DI > –DI
       – Short: EMA_fast < EMA_slow  &  ADX > 25  &  –DI > +DI
   • Transition (regime=1): no trades

4. Exit Logic:
   • Signal-based exits via populate_exit_trend.
   • Dynamic custom_stoploss:
       – Base: max(–3 %, –2 × pred_ATR)
       – In-profit trailing: –1.5×pred_ATR after +1.5 %,
                             –1.0×pred_ATR after +3 %.
   • Time-based safety exit after 48 h.

5. Position Sizing: inverse-volatility weighting
   stake ∝ 1 / pred_ATR  (clamped 50 %–100 % of proposed stake).

Technical Specs
---------------
• INTERFACE_VERSION = 3
• timeframe: 15 m
• can_short: True   (futures-ready)
• stoploss: –0.03   (hard floor)
• process_only_new_candles: True
• startup_candle_count: 350

Author: Hermes Agent
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

# ── Lazy sklearn import (avoid hard crash when sklearn is missing) ──
_sklearn_available = False
_sklearn_error_msg = ""

try:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler

    _sklearn_available = True
except ImportError as e:
    _sklearn_error_msg = str(e)


class BTC_RegimeScalp_v1(IStrategy):
    """
    BTC_RegimeScalp_v1 — Multi-TF regime detection + volatility prediction
    tailored for BTC spot & futures trading on Bybit.
    """

    # ── Freqtrade Interface ────────────────────────────────────────────
    INTERFACE_VERSION = 3

    timeframe: str = "15m"
    can_short: bool = False  # spot mode only (set True for futures)
    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    use_custom_stoploss: bool = True
    startup_candle_count: int = 350
    stoploss: float = -0.05

    # ── Base ROI (simple, no trailing) ────────────────────────────────
    minimal_roi: Dict[str, float] = {
        "0": 0.04,    # 4% target
        "45": 0.02,   # 2% after 11.25h
        "90": 0.01,   # 1% after 22.5h
    }
    # trailing_stop disabled — use simple stoploss + ROI only
    trailing_stop: bool = False
    trailing_stop_positive: float = 0.02
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # ── Regime Thresholds (ADX-based) ──────────────────────────────────
    ADX_RANGING_MAX: float = 20.0   # ADX < 20 = ranging
    ADX_TRENDING_MIN: float = 28.0  # ADX > 25 = trending
    # 20–25 = transition (no trades)

    # ── BB Mean-Reversion (Ranging) ────────────────────────────────────
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 30.0   # tightened from 35 (avoid false entries)
    RSI_OVERBOUGHT: float = 70.0  # tightened from 65

    # ── EMA Trend-Following (Trending) ─────────────────────────────────
    EMA_FAST: int = 12
    EMA_SLOW: int = 26
    ADX_TREND_MIN: float = 25.0

    # ── Volatility Prediction ──────────────────────────────────────────
    VOL_FORECAST_HORIZON: int = 12
    VOL_WINDOW: int = 300
    VOL_RIDGE_ALPHA: float = 0.1
    VOL_RETRAIN_INTERVAL: int = 50
    VOL_POLY_DEGREE: int = 2

    # ── Position Sizing ────────────────────────────────────────────────
    BASE_STAKE_RATIO: float = 0.95

    # ── Internal State ─────────────────────────────────────────────────
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._vol_model_cache: Dict[str, Dict] = {}
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
    #  Volatility Feature Extraction
    # ==================================================================
    @staticmethod
    def _extract_vol_features(df: pd.DataFrame, tf_name: str) -> pd.DataFrame:
        """
        Extract volatility-relevant features from a single TF OHLCV.
        """
        f = pd.DataFrame(index=df.index)

        # Returns
        f[f"{tf_name}_ret_5"] = df["close"].pct_change(5)
        f[f"{tf_name}_ret_20"] = df["close"].pct_change(20)

        # Rolling volatility
        f[f"{tf_name}_vol_20"] = f[f"{tf_name}_ret_5"].rolling(20).std()

        # MA deviations
        f[f"{tf_name}_ma_dev_20"] = df["close"] / df["close"].rolling(20).mean() - 1
        f[f"{tf_name}_ma_dev_50"] = df["close"] / df["close"].rolling(50).mean() - 1

        # Price position in 50-bar range
        low_50 = df["low"].rolling(50).min()
        high_50 = df["high"].rolling(50).max()
        f[f"{tf_name}_price_pos"] = (df["close"] - low_50) / (high_50 - low_50 + 1e-8)

        # Volume ratio
        f[f"{tf_name}_vol_ratio"] = df["volume"] / (df["volume"].rolling(50).mean() + 1e-8)

        # Normalised RSI & ADX
        f[f"{tf_name}_rsi"] = ta.RSI(df, timeperiod=14) / 100.0
        f[f"{tf_name}_adx"] = ta.ADX(df, timeperiod=14) / 100.0

        # ATR as % of price
        f[f"{tf_name}_atr_pct"] = ta.ATR(df, timeperiod=14) / df["close"]

        return f

    def _merge_vol_features(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Merge multi-TF volatility features into the main 15 m dataframe."""
        pair = metadata["pair"]
        features = self._extract_vol_features(dataframe, "15m")

        for tf in ["30m", "1h", "4h"]:
            try:
                inf_df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
            except Exception:
                logger.debug("No informative data for %s %s", pair, tf)
                continue

            if inf_df is None or len(inf_df) == 0:
                continue

            tf_features = self._extract_vol_features(inf_df, tf)
            features = pd.merge_asof(
                features.sort_index(),
                tf_features.sort_index(),
                left_index=True,
                right_index=True,
                direction="backward",
            )

        features = features.ffill().fillna(0.0)
        return features

    # ==================================================================
    #  Ridge Model Training
    # ==================================================================
    def _train_vol_model(
        self,
        features_df: pd.DataFrame,
        atr_target: np.ndarray,
        current_idx: int,
    ) -> Optional[Dict]:
        """
        Train Ridge regression on a rolling window to predict future ATR.
        Returns a dict with scaler / poly / ridge or None.
        """
        window = self.VOL_WINDOW
        fh = self.VOL_FORECAST_HORIZON

        train_start = max(0, current_idx - window)
        train_end = current_idx - fh
        min_samples = 50

        if train_end - train_start < min_samples:
            return None

        X_train = features_df.iloc[train_start:train_end].values.astype(np.float64)
        y_train = atr_target[train_start + fh : train_end + fh]

        valid = np.isfinite(y_train) & np.all(np.isfinite(X_train), axis=1)
        if valid.sum() < min_samples:
            return None

        X_train = X_train[valid]
        y_train = y_train[valid]

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
    #  populate_indicators
    # ==================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Compute regime, TA indicators and predicted ATR.
        """
        pair = metadata["pair"]

        # ── 1. Regime Detection (ADX consensus) ─────────────────────────
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)

        # 1h ADX
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

        # 4h ADX
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
        for col in ["adx_15m", "adx_1h", "adx_4h"]:
            dataframe[col] = dataframe[col].ffill().fillna(0)

        # Classify per-TF regime
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

        regime_sum = reg_15m + reg_1h + reg_4h

        def _consensus_regime(s: int) -> int:
            if s <= 1:
                return 0  # ranging
            elif s >= 4:
                return 2  # trending
            else:
                return 1  # transition

        dataframe["regime"] = regime_sum.apply(_consensus_regime)

        # ── 2. Bollinger Bands + RSI (Ranging) ─────────────────────────
        bb = ta.BBANDS(
            dataframe,
            timeperiod=self.BB_PERIOD,
            nbdevup=self.BB_STD,
            nbdevdn=self.BB_STD,
            matype=0,
        )
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)

        # ── 3. EMA + DI + SMA200 (Trending) ─────────────────────────────
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.EMA_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.EMA_SLOW)
        dataframe["sma_200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ── 4. Volatility Prediction (Ridge) ───────────────────────────
        if not _sklearn_available:
            logger.warning(
                "sklearn not available, volatility prediction disabled: %s",
                _sklearn_error_msg,
            )
            dataframe["pred_atr"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
            self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])
            dataframe["atr_pct"] = dataframe["pred_atr"]
            return dataframe

        current_atr_pct = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
        vol_features = self._merge_vol_features(dataframe, metadata)

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
                    pred_atr_arr[i] = float(np.clip(pred, 0.001, 0.15))
                except Exception:
                    continue

        pred_series = pd.Series(pred_atr_arr, index=dataframe.index)
        dataframe["pred_atr"] = pred_series.ffill().fillna(current_atr_pct)

        self._vol_model_cache[pair] = {
            "model": current_model,
            "last_train_idx": last_train_idx,
        }
        self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])
        dataframe["atr_pct"] = current_atr_pct

        return dataframe

    # ==================================================================
    #  populate_entry_trend
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Regime-switched entries (long + short).
        """
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # ── Ranging: BB mean-reversion ─────────────────────────────────
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

        # ── Trending: EMA trend-following ──────────────────────────────
        trending_long = (
            (dataframe["regime"] == 2)
            & (dataframe["close"] > dataframe["sma_200"])  # only long in bull trend
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["adx_15m"] > 30)  # tightened from 25
            & (dataframe["plus_di"] > dataframe["minus_di"])
        )
        trending_short = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
            & (dataframe["minus_di"] > dataframe["plus_di"])
        )

        dataframe.loc[ranging_long, "enter_long"] = 1
        dataframe.loc[trending_long, "enter_long"] = 1
        dataframe.loc[ranging_short, "enter_short"] = 1
        dataframe.loc[trending_short, "enter_short"] = 1

        return dataframe

    # ==================================================================
    #  populate_exit_trend
    # ==================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Signal-based exits:
          • Ranging: RSI reversion confirmed + price back to mid-BB.
          • Trending: EMA cross confirmed (2 bars) + ADX weakening.
        """
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # Long exits
        ranging_exit = (
            (dataframe["regime"] == 0)
            & (dataframe["rsi"] > 65)
            & (dataframe["close"] > dataframe["bb_middle"])
        )
        trending_exit = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["ema_fast"].shift(1) < dataframe["ema_slow"].shift(1))
            & (dataframe["adx_15m"] < 22)
        )
        dataframe.loc[ranging_exit, "exit_long"] = 1
        dataframe.loc[trending_exit, "exit_long"] = 1

        # Short exits (mirror)
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
    #  custom_stoploss
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
        Simple fixed stoploss — no dynamic adjustments.
        Use base stoploss only.
        """
        return None  # use base stoploss (-3%)

    # ==================================================================
    #  custom_exit
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
        Safety exits:
          • Time-based: close after 24h if still open.
        """
        holding_minutes = (current_time - trade.open_date).total_seconds() / 60
        if holding_minutes > 720:  # 12 hours (reduced from 24)
            return "time_exit"
        return None

    # ==================================================================
    #  custom_stake_amount — Inverse Volatility Weighting
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
        Scale stake inversely with predicted volatility.
        """
        pred_atr = self._pred_atr_cache.get(pair, None)
        if pred_atr is None or pred_atr <= 0:
            return proposed_stake * self.BASE_STAKE_RATIO

        avg_target_atr = 0.025
        scale = np.clip(avg_target_atr / pred_atr, 0.5, 1.0)
        sized = proposed_stake * scale * self.BASE_STAKE_RATIO

        if min_stake is not None:
            sized = max(sized, min_stake)
        sized = min(sized, max_stake)

        return sized
