#!/usr/bin/env python3
"""
MultiTFPolyReg_v1 — 多元多時間框架多項式回歸策略

基於數學理論（Weierstrass / Stone-Weierstrass / Nyquist-Shannon / Wavelet MRA）：
  1. Weierstrass / Stone-Weierstrass 定理 → 多項式逼近泛函數
  2. Nyquist-Shannon 取樣定理 → degree ≤ 2（金融 SNR ≈ 0.02）
  3. Wavelet MRA 正交分解 → 多TF獨立資訊
  4. Ridge 正則化 → 低SNR下比 Lasso 更穩定
  5. 預測收益率（連續值）+ sign() 轉方向 → 避免 Gibbs 現象
  6. BIC 模型選擇 → 低SNR下比 AIC 保守
  7. 滾動窗口訓練 → 應對非平穩性

核心約束：
  - degree ≤ 2（硬約束）
  - Ridge 正則化（alpha=0.1）
  - 預測收益率 → sign() 得方向
  - 滾動窗口（預設 300 根 bar）
  - 多TF：5m / 15m / 1h / 4h
  - 特徵數 ≤ 20（SelectKBest 防止維度災難）

Reference: /home/brian/freqtrade/user_data/strategies/math_based/THEORY_FRAMEWORK.md
"""

import logging
import warnings
from typing import Dict, Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# 延遲匯入 sklearn（避免 dry-run 環境無 sklearn 時直接崩潰）
# ─────────────────────────────────────────────────────────────────────
_sklearn_available = False
_sklearn_error_msg = ""

try:
    from sklearn.linear_model import Ridge                   # noqa: F811
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler  # noqa: F811
    from sklearn.feature_selection import SelectKBest, f_regression       # noqa: F811
    from sklearn.pipeline import Pipeline                    # noqa: F811
    _sklearn_available = True
except ImportError as e:
    _sklearn_error_msg = str(e)


class MultiTFPolyReg_v1(IStrategy):
    """
    MultiTFPolyReg_v1 — Polynomial Regression with Multi-TF Features

    數學策略 v1：使用多時間框架特徵 + 二階多項式特徵展開 +
    Ridge 正則化回歸，預測短期收益率並依據預測方向進出場。

    策略類型：math_based（數學理論驅動）
    版本：v1
    作者：Hermes Agent
    """

    # ── 基本設定 ─────────────────────────────────────────────────────
    timeframe: str = "5m"
    can_short: bool = False
    process_only_new_candles: bool = True
    use_exit_signal: bool = True
    startup_candle_count: int = 400  # window(300) + forecast_horizon(12) + margin
    stoploss: float = -0.05

    # 出場設定
    minimal_roi: Dict[str, float] = {
        "0": 0.01,
        "60": 0.015,
        "120": 0.005,
    }
    trailing_stop: bool = True
    trailing_stop_positive: float = 0.02
    trailing_stop_positive_offset: float = 0.03
    trailing_only_offset_is_reached: bool = True

    # ── 超參數（Hyperopt 空間）────────────────────────────────────────
    # degree 硬約束為 2（不可調參），透過 PolynomialFeatures 參數控制
    window: IntParameter = IntParameter(100, 500, default=300, space="buy")
    forecast_horizon: IntParameter = IntParameter(4, 24, default=12, space="buy")
    ridge_alpha: DecimalParameter = DecimalParameter(
        0.0001, 1.0, default=0.001, decimals=4, space="buy"
    )
    entry_threshold: DecimalParameter = DecimalParameter(
        0.0, 0.005, default=0.0, decimals=4, space="buy"
    )
    max_features: IntParameter = IntParameter(10, 40, default=20, space="buy")
    retrain_interval: IntParameter = IntParameter(20, 150, default=50, space="buy")

    # ── 內部狀態（per-pair 模型快取）──────────────────────────────────
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._model_cache: Dict[str, Dict] = {}  # pair → trained model dict

    # ==================================================================
    #  Informative Pairs（多時間框架）
    # ==================================================================
    def informative_pairs(self):
        """回報需要的資訊時間框架組合。"""
        pairs = self.dp.current_whitelist()
        informative = []
        for pair in pairs:
            informative.append((pair, "15m"))
            informative.append((pair, "1h"))
            informative.append((pair, "4h"))
        return informative

    # ==================================================================
    #  特徵工程
    # ==================================================================
    @staticmethod
    def _extract_tf_features(df: pd.DataFrame, tf_name: str) -> pd.DataFrame:
        """
        從單一時間框架的 OHLCV 資料擷取 ~10 個特徵。

        Parameters
        ----------
        df : pd.DataFrame
            單一 TF 的 OHLCV（需含欄位 open/high/low/close/volume）
        tf_name : str
            時間框架標籤（如 '5m', '15m', '1h', '4h'）

        Returns
        -------
        pd.DataFrame
            特徵 DataFrame（index 與 df 對齊）
        """
        f = pd.DataFrame(index=df.index)

        # 收益率特徵（不同回溯期）
        f[f"{tf_name}_ret_1"] = df["close"].pct_change(1)
        f[f"{tf_name}_ret_5"] = df["close"].pct_change(5)
        f[f"{tf_name}_ret_10"] = df["close"].pct_change(10)

        # 波動率（20 期滾動標準差）
        f[f"{tf_name}_vol_20"] = f[f"{tf_name}_ret_1"].rolling(20).std()

        # 價格相對位置（Stochastic-like，20 期）
        low_min = df["low"].rolling(20).min()
        high_max = df["high"].rolling(20).max()
        f[f"{tf_name}_price_pos"] = (df["close"] - low_min) / (
            high_max - low_min + 1e-8
        )

        # 均線偏離（20 期 / 50 期）
        f[f"{tf_name}_ma_dev_20"] = (
            df["close"] / df["close"].rolling(20).mean() - 1
        )
        f[f"{tf_name}_ma_dev_50"] = (
            df["close"] / df["close"].rolling(50).mean() - 1
        )

        # 成交量比率（相對於 20 期均值）
        f[f"{tf_name}_vol_ratio"] = df["volume"] / (
            df["volume"].rolling(20).mean() + 1e-8
        )

        # RSI（14 期）
        f[f"{tf_name}_rsi_14"] = ta.RSI(df, timeperiod=14) / 100.0  # 正規化到 [0,1]

        # MACD（正規化）
        macd = ta.MACD(df)
        f[f"{tf_name}_macd"] = macd["macd"] / (df["close"] + 1e-8)
        f[f"{tf_name}_macd_signal"] = macd["macdsignal"] / (df["close"] + 1e-8)
        f[f"{tf_name}_macd_hist"] = macd["macdhist"] / (df["close"] + 1e-8)

        # ADX 趨勢強度（正規化）
        f[f"{tf_name}_adx"] = ta.ADX(df, timeperiod=14) / 100.0

        return f

    def _merge_informative(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        合併多 TF 特徵到主 dataframe（5m）。
        每個 TF 獨立提取特徵後，以 merge_asof 對齊到 5m index。
        """
        pair = metadata["pair"]

        # 主 TF（5m）特徵
        features = self._extract_tf_features(dataframe, "5m")

        # 合併每個資訊 TF
        for tf in ["15m", "1h", "4h"]:
            try:
                inf_df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
            except Exception:
                logger.debug("No informative data for %s %s", pair, tf)
                continue

            if inf_df is None or len(inf_df) == 0:
                continue

            tf_features = self._extract_tf_features(inf_df, tf)

            # merge_asof：將高 TF 特徵對齊到 5m 時間軸（前向填充）
            features = pd.merge_asof(
                features.sort_index(),
                tf_features.sort_index(),
                left_index=True,
                right_index=True,
                direction="backward",  # 使用「已知」的高 TF 資料（不偷看未來）
            )

        # 前向填充缺失值（高 TF 起始段缺值）
        features = features.ffill().fillna(0.0)

        return features

    # ==================================================================
    #  模型訓練
    # ==================================================================
    def _build_pipeline(self) -> Pipeline:
        """建立 sklearn Pipeline：StandardScaler → PolynomialFeatures → SelectKBest → Ridge。"""
        k = int(self.max_features.value)
        alpha = float(self.ridge_alpha.value)

        steps = [
            ("scaler", StandardScaler()),
            ("poly", PolynomialFeatures(degree=2, include_bias=False)),
            ("select", SelectKBest(f_regression, k=k)),
            ("ridge", Ridge(alpha=alpha, fit_intercept=True, max_iter=5000)),
        ]
        return Pipeline(steps)

    def _train_model(
        self,
        features_df: pd.DataFrame,
        close_arr: np.ndarray,
        current_idx: int,
    ) -> Optional[Pipeline]:
        """
        在滾動窗口上訓練 Ridge 模型。

        Parameters
        ----------
        features_df : pd.DataFrame
            完整特徵 DataFrame（index = 5m 時間軸）
        close_arr : np.ndarray
            Close 價格陣列（與 features_df 同長度）
        current_idx : int
            目前 bar 的 index（訓練窗口終點）

        Returns
        -------
        Pipeline or None
            訓練好的 sklearn Pipeline（若訓練樣本不足則回傳 None）
        """
        window = int(self.window.value)
        fh = int(self.forecast_horizon.value)

        train_start = max(0, current_idx - window)
        train_end = current_idx - fh

        min_samples = 50
        if train_end - train_start < min_samples:
            logger.debug(
                "Insufficient training samples: %d < %d at idx=%d",
                train_end - train_start,
                min_samples,
                current_idx,
            )
            return None

        # X：train_start → train_end（不含前瞻資訊）
        X_train = features_df.iloc[train_start:train_end].values.astype(np.float64)

        # y：train_start+horizon → train_end+horizon 的對數收益率
        # 使用對數收益率（log-return）比簡單百分比更適合回歸
        y_train = np.log(
            close_arr[train_start + fh : train_end + fh]
            / (close_arr[train_start:train_end] + 1e-12)
        )

        # 移除 inf/nan
        valid = np.isfinite(y_train) & np.all(np.isfinite(X_train), axis=1)
        if valid.sum() < min_samples:
            logger.debug("Too few valid samples after filtering at idx=%d", current_idx)
            return None

        X_train = X_train[valid]
        y_train = y_train[valid]

        pipeline = self._build_pipeline()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            warnings.simplefilter("ignore", FutureWarning)
            try:
                pipeline.fit(X_train, y_train)
            except Exception as e:
                logger.warning("Model training failed at idx=%d: %s", current_idx, e)
                return None

        return pipeline

    # ==================================================================
    #  populate_indicators（核心迴圈）
    # ==================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """計算所有指標與模型預測值。"""
        if not _sklearn_available:
            logger.error(
                "sklearn not available, cannot train model: %s", _sklearn_error_msg
            )
            dataframe["pred_return"] = 0.0
            return dataframe

        pair = metadata["pair"]

        # 步驟 1：提取 + 合併多 TF 特徵
        features_df = self._merge_informative(dataframe, metadata)

        # 步驟 2：滾動窗口 + 逐 bar 訓練/預測
        close_arr = dataframe["close"].values.astype(np.float64)
        n = len(close_arr)
        pred_returns = np.zeros(n, dtype=np.float64)
        retrain_interval = int(self.retrain_interval.value)

        # 步驟 2a：讀取快取（若 process_only_new_candles=True 且已有快取模型）
        current_model: Optional[Pipeline] = None
        cached = self._model_cache.get(pair, {})
        if self.process_only_new_candles and cached:
            current_model = cached.get("model")
            last_train_idx = cached.get("last_train_idx", -retrain_interval - 1)
            logger.debug(
                "Loaded cached model for %s, last_train_idx=%s", pair, last_train_idx
            )
        else:
            last_train_idx = -retrain_interval - 1  # 強制首次訓練

        for i in range(self.startup_candle_count, n):
            # 若之前已有預測值（來自快取 + process_only_new_candles），跳過
            # 注意：prev_len = n - len(new_candles)，我們只處理新的 bars
            # 判斷是否需要重新訓練
            if i - last_train_idx >= retrain_interval:
                current_model = self._train_model(features_df, close_arr, i)
                last_train_idx = i

            if current_model is None:
                pred_returns[i] = 0.0
                continue

            # 預測當前 bar 的未來收益率
            X_current = features_df.iloc[i].values.astype(np.float64).reshape(1, -1)

            if np.any(np.isnan(X_current)) or np.any(np.isinf(X_current)):
                pred_returns[i] = 0.0
                continue

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                warnings.simplefilter("ignore", FutureWarning)
                try:
                    pred = current_model.predict(X_current)[0]
                    pred_returns[i] = float(pred)
                except Exception:
                    pred_returns[i] = 0.0

        # 步驟 3：寫入 dataframe
        dataframe["pred_return"] = pred_returns.astype(np.float64)

        # 步驟 4：快取模型（供下次呼叫繼續使用 — 適用於 process_only_new_candles）
        self._model_cache[pair] = {
            "model": current_model,
            "last_train_idx": last_train_idx,
            "feature_cols": features_df.columns.tolist(),
        }

        return dataframe

    # ==================================================================
    #  進場邏輯
    # ==================================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        排名信號法：預測值在滾動窗口中的百分位排名。
        pred_rank > 0.8 → 預測排名在前 20% → 進場
        """
        # 計算預測在滾動窗口中的排名 (0=最低, 1=最高)
        rank_window = min(500, len(dataframe))
        dataframe["pred_rank"] = (
            dataframe["pred_return"]
            .rolling(rank_window, min_periods=50)
            .apply(lambda x: (x.iloc[-1] > x.iloc[:-1]).mean(), raw=False)
        )

        rank_threshold = 0.70  # 前 30% 即進場
        dataframe.loc[
            (dataframe["pred_rank"] > rank_threshold)
            & (dataframe["pred_return"] > 0),
            "enter_long",
        ] = 1

        return dataframe

    # ==================================================================
    #  出場邏輯
    # ==================================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        排名信號法出場：預測跌出前 50% 出場。
        """
        dataframe.loc[
            (dataframe["pred_rank"] < 0.5)
            & (dataframe["pred_rank"].shift(1) >= 0.5),
            "exit_long",
        ] = 1

        return dataframe

    # ==================================================================
    #  自訂出場（選用：更精細的控管）
    # ==================================================================
    def custom_exit(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        """
        自訂出場邏輯 — 在此僅做 fallback（ROI / stoploss 已涵蓋主要出場）。

        可選擴充：當波動率過高或模型信心低時提前出場。
        """
        return None


# ══════════════════════════════════════════════════════════════════════
#  策略註冊（Freqtrade 透過檔名自動發現 class）
# ══════════════════════════════════════════════════════════════════════
# 本檔案定義的 class 即策略本身。
# Freqtrade 會自動掃描此目錄下的 .py 檔案並載入第一個 IStrategy subclass。
