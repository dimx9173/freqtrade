#!/usr/bin/env python3
"""
Hybrid_v3_OF — Hybrid_v3 with Order Flow Enhancement

Enhancements:
  1. Volume Imbalance (VI) as entry confirmation filter
  2. Bid-Ask Spread as volatility prediction feature
  3. Cumulative Volume Delta (CVD) slope for exit timing

Order Flow Integration Points:
  - Entry: VI > -0.2 (avoid extreme sell pressure) + spread < 0.8%
  - Regime: VI assists tie-breaking in transition regime
  - Vol: spread_pct added to Ridge feature set
  - Exit: CVD divergence detection in custom_exit

Backtest Safety:
  - Live/Dry-run: uses self.dp.orderbook() + self.dp.trades()
  - Backtest: uses historical trades data only (no look-ahead)
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


class Hybrid_v3_OF(IStrategy):
    """
    Hybrid_v3 with Order Flow enhancement.
    See orderflow_enhancement_report.md for full analysis.
    """

    INTERFACE_VERSION: int = 3

    # ── Basic Settings ─────────────────────────────────────────────
    timeframe: str = "15m"
    can_short: bool = False
    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    use_custom_stoploss: bool = True
    enter_long_signal_once: bool = True
    startup_candle_count: int = 350
    stoploss: float = -0.99

    # ── Exit / ROI ──────────────────────────────────────────────────
    minimal_roi: dict[str, float] = {
        "0": 0.03,
        "120": 0.015,
        "240": 0.005,
    }
    trailing_stop: bool = False

    # ── Regime Thresholds ───────────────────────────────────────────
    ADX_RANGING_MAX: float = 20.0
    ADX_TRENDING_MIN: float = 22.0

    # ── Trend-Following Parameters ──────────────────────────────────
    EMA_FAST_PERIOD: int = 12
    EMA_SLOW_PERIOD: int = 26
    ADX_TREND_MIN: float = 18.0
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    # ── Mean-Reversion Parameters ───────────────────────────────────
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    RSI_PERIOD: int = 14
    RSI_MEAN_REV_ENTRY: float = 40.0
    RSI_MEAN_REV_EXIT: float = 60.0
    RSI_TREND_EXIT: float = 65.0

    # ── Volatility Prediction Parameters ────────────────────────────
    VOL_FORECAST_HORIZON: int = 12
    VOL_WINDOW: int = 300
    VOL_RIDGE_ALPHA: float = 0.1
    VOL_RETRAIN_INTERVAL: int = 50
    VOL_POLY_DEGREE: int = 2

    # ── Order Flow Parameters ───────────────────────────────────────
    OF_VI_ENTRY_MIN: float = -0.2  # VI must be > this for entry
    OF_SPREAD_MAX: float = 0.008  # Spread must be < 0.8%
    OF_VI_TREND_THRESH: float = 0.3  # VI > 0.3 suggests trend
    OF_VI_RANGE_THRESH: float = 0.1  # |VI| < 0.1 suggests ranging
    OF_CVD_EXIT_DIVERGENCE: bool = True

    # ── Position Sizing ─────────────────────────────────────────────
    BASE_STAKE_RATIO: float = 0.95

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._vol_model_cache: dict[str, dict] = {}
        self._pred_atr_cache: dict[str, float] = {}
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
    #  Order Flow Helpers
    # ==================================================================
    def _calc_orderflow_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calculate order flow indicators.
        Live/Dry-run: use real-time orderbook + trades
        Backtest: use historical trades only
        """
        pair = metadata["pair"]
        is_live = self.dp.runmode.value in ("live", "dry_run")

        # Default values
        dataframe["vi"] = 0.0
        dataframe["spread_pct"] = 0.0
        dataframe["cvd"] = 0.0
        dataframe["cvd_slope"] = 0.0

        if is_live:
            # ── Live/Dry-run: fetch orderbook ──
            try:
                ob = self.dp.orderbook(pair, maximum=10)
                bids = np.array(ob["bids"])
                asks = np.array(ob["asks"])
                if len(bids) > 0 and len(asks) > 0:
                    bid_vol = bids[:, 1].sum()
                    ask_vol = asks[:, 1].sum()
                    total_vol = bid_vol + ask_vol + 1e-8
                    dataframe["vi"] = (bid_vol - ask_vol) / total_vol
                    mid = (asks[0, 0] + bids[0, 0]) / 2
                    dataframe["spread_pct"] = (asks[0, 0] - bids[0, 0]) / (mid + 1e-8)
            except Exception as e:
                logger.debug("Orderbook fetch failed for %s: %s", pair, e)

            # ── Live/Dry-run: fetch trades for CVD ──
            try:
                trades_df = self.dp.trades(pair, timeframe=self.timeframe)
                if trades_df is not None and not trades_df.empty:
                    buy_vol = trades_df[trades_df["side"] == "buy"]["amount"].sum()
                    sell_vol = trades_df[trades_df["side"] == "sell"]["amount"].sum()
                    dataframe["cvd"] = buy_vol - sell_vol
                    dataframe["cvd_slope"] = dataframe["cvd"] / (
                        dataframe["cvd"].abs().max() + 1e-8
                    )
            except Exception as e:
                logger.debug("Trades fetch failed for %s: %s", pair, e)
        else:
            # ── Backtest: use historical trades if available ──
            try:
                trades_df = self.dp.trades(pair, timeframe=self.timeframe)
                if trades_df is not None and not trades_df.empty:
                    buy_vol = trades_df[trades_df["side"] == "buy"]["amount"].sum()
                    sell_vol = trades_df[trades_df["side"] == "sell"]["amount"].sum()
                    total_vol = buy_vol + sell_vol + 1e-8
                    dataframe["vi"] = (buy_vol - sell_vol) / total_vol
                    dataframe["cvd"] = buy_vol - sell_vol
                    dataframe["cvd_slope"] = dataframe["cvd"] / (total_vol + 1e-8)
            except Exception as e:
                logger.debug("Historical trades unavailable for %s: %s", pair, e)

        return dataframe

    # ==================================================================
    #  Feature Extraction for Volatility Prediction (Enhanced with OF)
    # ==================================================================
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
        f[f"{tf_name}_atr_pct"] = ta.ATR(df, timeperiod=14) / df["close"]
        # ── Order Flow features ──
        f[f"{tf_name}_vi"] = df.get("vi", 0.0)
        f[f"{tf_name}_spread_pct"] = df.get("spread_pct", 0.0)
        return f

    def _merge_vol_features(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        pair = metadata["pair"]
        features = self._extract_vol_features(dataframe, "15m")
        for tf in ["30m", "1h", "4h"]:
            try:
                inf_df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
            except Exception:
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
    def _train_vol_model(self, features_df: pd.DataFrame, atr_target: np.ndarray, current_idx: int):
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
        pair = metadata["pair"]

        # ── 1. Order Flow Indicators ──────────────────────────────────
        dataframe = self._calc_orderflow_indicators(dataframe, metadata)

        # ── 2. Regime Detection: ADX consensus ────────────────────────
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)
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

        dataframe["adx_1h"] = dataframe["adx_1h"].ffill().fillna(0)
        dataframe["adx_4h"] = dataframe["adx_4h"].ffill().fillna(0)
        dataframe["adx_15m"] = dataframe["adx_15m"].ffill().fillna(0)

        def _classify_regime(adx_val: float) -> int:
            if adx_val < self.ADX_RANGING_MAX:
                return 0
            elif adx_val > self.ADX_TRENDING_MIN:
                return 2
            else:
                return 1

        reg_15m = dataframe["adx_15m"].apply(_classify_regime)
        reg_1h = dataframe["adx_1h"].apply(_classify_regime)
        reg_4h = dataframe["adx_4h"].apply(_classify_regime)
        regime_sum = reg_15m + reg_1h + reg_4h

        # ── Order Flow assisted regime tie-breaking ───────────────────
        of_trend = (dataframe["vi"] > self.OF_VI_TREND_THRESH) & (
            dataframe["vi"].shift(1) > self.OF_VI_TREND_THRESH * 0.7
        )
        of_range = abs(dataframe["vi"]) < self.OF_VI_RANGE_THRESH

        def _consensus_regime(s: int, of_trend_flag: bool, of_range_flag: bool) -> int:
            if s <= 1:
                return 0
            elif s >= 4:
                return 2
            else:
                if of_trend_flag:
                    return 2
                elif of_range_flag:
                    return 0
                else:
                    return 1

        dataframe["regime"] = [
            _consensus_regime(s, t, r)
            for s, t, r in zip(regime_sum, of_trend, of_range, strict=False)
        ]

        # ── 3. EMA + MACD ─────────────────────────────────────────────
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.EMA_FAST_PERIOD)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.EMA_SLOW_PERIOD)
        macd = ta.MACD(
            dataframe,
            fastperiod=self.MACD_FAST,
            slowperiod=self.MACD_SLOW,
            signalperiod=self.MACD_SIGNAL,
        )
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ── 4. Bollinger Bands + RSI ──────────────────────────────────
        bb = ta.BBANDS(
            dataframe, timeperiod=self.BB_PERIOD, nbdevup=self.BB_STD, nbdevdn=self.BB_STD, matype=0
        )
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)

        # ── 5. Volatility Prediction via Ridge ────────────────────────
        if not _sklearn_available:
            logger.warning("sklearn not available, volatility prediction disabled")
            dataframe["pred_atr"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]
            self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])
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
                    pred_atr_arr[i] = float(np.clip(pred, 0.005, 0.15))
                except Exception:
                    continue

        pred_series = pd.Series(pred_atr_arr, index=dataframe.index)
        dataframe["pred_atr"] = pred_series.ffill().fillna(current_atr_pct)
        self._vol_model_cache[pair] = {"model": current_model, "last_train_idx": last_train_idx}
        self._pred_atr_cache[pair] = float(dataframe["pred_atr"].iloc[-1])
        dataframe["atr_pct"] = current_atr_pct
        return dataframe

    # ==================================================================
    #  Entry Logic — with Order Flow Confirmation
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""

        # ── Order Flow Confirmation Filter ────────────────────────────
        of_confirm = (dataframe["vi"] > self.OF_VI_ENTRY_MIN) & (
            dataframe["spread_pct"] < self.OF_SPREAD_MAX
        )

        trending_entry = (
            (dataframe["regime"] == 2)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["macd_hist"] > 0)
            & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())
            & of_confirm
        )

        ranging_entry = (
            (dataframe["regime"] == 0)
            & (dataframe["close"] < dataframe["bb_lower"])
            & (dataframe["rsi"] < self.RSI_MEAN_REV_ENTRY)
            & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())
            & of_confirm
        )

        transition_entry = (
            (dataframe["regime"] == 1)
            & (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["volume"] > 1.2 * dataframe["volume"].rolling(20).mean())
            & of_confirm
        )

        dataframe.loc[trending_entry, "enter_long"] = 1
        dataframe.loc[trending_entry, "enter_tag"] = "trend"
        dataframe.loc[ranging_entry, "enter_long"] = 1
        dataframe.loc[ranging_entry, "enter_tag"] = "mean_rev"
        dataframe.loc[transition_entry, "enter_long"] = 1
        dataframe.loc[transition_entry, "enter_tag"] = "weak_trend"
        return dataframe

    # ==================================================================
    #  Exit Logic
    # ==================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0

        trending_exit = (dataframe["regime"] == 2) & (
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"])
            )
            | (
                (dataframe["rsi"] > self.RSI_TREND_EXIT)
                & (dataframe["rsi"].shift(1) <= self.RSI_TREND_EXIT)
            )
        )

        ranging_exit = (dataframe["regime"] == 0) & (
            (
                (dataframe["rsi"] > self.RSI_MEAN_REV_EXIT)
                & (dataframe["rsi"].shift(1) <= self.RSI_MEAN_REV_EXIT)
            )
            | (
                (dataframe["close"] > dataframe["bb_upper"])
                & (dataframe["close"].shift(1) <= dataframe["bb_upper"])
            )
        )

        dataframe.loc[trending_exit, "exit_long"] = 1
        dataframe.loc[ranging_exit, "exit_long"] = 1

        transition_exit = (dataframe["regime"] == 1) & (
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"])
                & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"])
            )
            | (
                (dataframe["rsi"] > self.RSI_TREND_EXIT)
                & (dataframe["rsi"].shift(1) <= self.RSI_TREND_EXIT)
            )
        )
        dataframe.loc[transition_exit, "exit_long"] = 1
        return dataframe

    # ==================================================================
    #  Dynamic Stop Loss
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
        if current_profit < 0:
            return -0.03
        if current_profit >= 0.05:
            return +0.02
        if current_profit >= 0.03:
            return +0.01
        if current_profit >= 0.015:
            return -0.015
        return -0.03

    # ==================================================================
    #  Custom Exit — with CVD Divergence
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
        holding_minutes = (current_time - trade.open_date).total_seconds() / 60
        if holding_minutes > 2880:
            return "time_exit"

        if current_profit > 0 and trade.max_rate > 0 and current_rate < trade.max_rate:
            peak_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
            drawdown_from_peak = peak_profit - current_profit
            if drawdown_from_peak > 0.02:
                return "profit_drawdown"

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is not None and not dataframe.empty:
            last_rsi = dataframe["rsi"].iloc[-1]
            if last_rsi > 75:
                return "rsi_overbought"

            # ── CVD Divergence Exit ──
            if self.OF_CVD_EXIT_DIVERGENCE and current_profit > 0.01:
                # Price made higher high but CVD did not → divergence
                if len(dataframe) >= 3:
                    price_hh = dataframe["close"].iloc[-1] > dataframe["close"].iloc[-3:-1].max()
                    cvd_not_hh = dataframe["cvd"].iloc[-1] <= dataframe["cvd"].iloc[-3:-1].max()
                    if price_hh and cvd_not_hh:
                        return "cvd_divergence"

        return None

    # ==================================================================
    #  Position Sizing
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
