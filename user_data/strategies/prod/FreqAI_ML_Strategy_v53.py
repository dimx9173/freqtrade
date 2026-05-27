# FreqAI_ML_Strategy V53 - NO ROI Test Version
# Mission: Test if ROI is cutting winners short by using ONLY trailing stop and stoploss
#
# V53 changes from V43:
# ✅ REMOVED all ROI exits (minimal_roi = {}) - only trailing stop + stoploss
# ✅ This tests if ROI is cutting winners short
# ✅ Keep trailing_stop parameters identical to V43
# ✅ Keep stoploss at -0.12
# ✅ Enable can_short for futures 3x testing
#
# V43 was using:
# ✅ SMMA instead of SMA for volume_ratio, atr_ratio, and volume_sma
# ✅ EMA multi-market regime filtering
# ✅ FreqAI enabled with XGBoost
# ✅ Trailing stop: 0.5% positive, 1.5% offset

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    BooleanParameter,
    CategoricalParameter,
    merge_informative_pair,
)
import freqtrade.vendor.qtpylib.indicators as qtpylib
import logging
from pandas import DataFrame
from typing import Dict, List, Optional, Union
from datetime import datetime, timezone
import warnings

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class FreqAI_ML_Strategy_v53(IStrategy):
    """
    FreqAI ML Strategy V53 "NO_ROI_TEST"

    V53 Mission: Test if ROI is cutting winners short
    - REMOVE all ROI exits (minimal_roi = {})
    - ONLY use trailing stop + stoploss for exits
    - If profit improves, it confirms ROI was cutting winners short

    V43 Base Features:
    ✅ SMMA instead of SMA for volume_ratio, atr_ratio, and volume_sma
    ✅ EMA multi-market regime filtering
    ✅ FreqAI enabled with XGBoost
    ✅ 15m timeframe
    """

    INTERFACE_VERSION = 3

    # ===========================================
    # FREQAI CONFIGURATION - 啟用 ML 引擎
    # ===========================================

    freqai_enabled = True  # ✅ 啟用 FreqAI

    # ===========================================
    # TIMEFRAME & CONFIG - 時間框架
    # ===========================================
    timeframe = "15m"
    informative_timeframes = ["1h", "4h"]

    # ===========================================
    # SCALPOPT_UAT 風控參數（已驗證成功）
    # ===========================================
    stoploss = -0.12  # 12% 止損（高勝率策略）

    # Trailing Stop（核心！）- V53: Keep identical to V43
    trailing_stop = True
    trailing_stop_positive = 0.005  # 0.5% 啟動 trailing
    trailing_stop_positive_offset = 0.015  # 1.5% offset
    trailing_only_offset_is_reached = True

    # ===========================================
    # V53 KEY CHANGE: NO ROI - ONLY trailing stop
    # ===========================================
    minimal_roi = {}  # EMPTY - no ROI exits, only trailing stop + stoploss

    # 系統參數
    can_short = True  # V53: Enable short for futures testing
    startup_candle_count = 80
    process_only_new_candles = True
    use_exit_signal = False  # ❌ V30.2: 關閉 FreqAI exit_signal（42 trades 全輸 = 主要虧損源）
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # ===========================================
    # ML 信心閾值參數（方向B: 制度適應閾值）
    # ===========================================
    # 預設通用閾值
    ml_confidence_threshold = DecimalParameter(
        0.50, 0.80, default=0.60, decimals=2, space="buy", optimize=True
    )
    ml_prediction_threshold = DecimalParameter(
        0.50, 0.75, default=0.60, decimals=2, space="buy", optimize=True
    )

    # 趨勢市場閾值（較寬鬆）
    ml_confidence_threshold_trend = DecimalParameter(
        0.55, 0.85, default=0.58, decimals=2, space="buy", optimize=True
    )
    ml_prediction_threshold_trend = DecimalParameter(
        0.55, 0.80, default=0.58, decimals=2, space="buy", optimize=True
    )

    # 高波動市場閾值（較嚴格）
    ml_confidence_threshold_volatile = DecimalParameter(
        0.65, 0.90, default=0.72, decimals=2, space="buy", optimize=True
    )
    ml_prediction_threshold_volatile = DecimalParameter(
        0.65, 0.85, default=0.70, decimals=2, space="buy", optimize=True
    )

    # 市場制度適應
    regime_detection_enabled = BooleanParameter(default=True, space="buy", optimize=True)

    # 微觀結構權重（已放寬）
    microstructure_weight = DecimalParameter(
        0.1, 0.3, default=0.20, decimals=2, space="buy", optimize=True
    )

    # 動態倉位管理
    dynamic_position_sizing = BooleanParameter(default=True, space="buy", optimize=True)
    risk_scaling_factor = DecimalParameter(
        0.5, 2.0, default=1.0, decimals=1, space="buy", optimize=True
    )

    def informative_pairs(self):
        """擴展信息對"""
        pairs = self.dp.current_whitelist()
        informative_pairs = []

        for tf in self.informative_timeframes:
            informative_pairs.extend([(pair, tf) for pair in pairs])

        # 添加主要相關資產
        major_pairs = ["BTC/USDT", "ETH/USDT"]
        for pair in major_pairs:
            if pair not in [p[0] for p in informative_pairs]:
                for tf in self.informative_timeframes:
                    informative_pairs.append((pair, tf))

        return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        V30.0 特徵工程系統
        結合 FreqAI 自動特徵與手動市場結構特徵
        """

        # ===========================================
        # 🕐 基礎技術指標（FreqAI 特徵輸入）
        # ===========================================

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # EMA 系統（市場制度核心）
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["ema_medium"] = ta.EMA(dataframe, timeperiod=50)

        for period in [12, 26, 50, 200]:  # 簡化：只保留關鍵週期（方向C）
            dataframe[f"ema_{period}"] = ta.EMA(dataframe, timeperiod=period)

        # MACD
        dataframe["macd"], dataframe["macdsignal"], dataframe["macdhist"] = ta.MACD(dataframe)

        # Bollinger Bands（在新位置重新計算，避免 merge_informative_pair 覆蓋）
        dataframe["bb_upper"], dataframe["bb_middle"], dataframe["bb_lower"] = ta.BBANDS(
            dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0
        )

        # ATR（波動性）
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # ADX（趨勢強度）
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # CCI
        dataframe["cci"] = ta.CCI(dataframe, timeperiod=20)

        # Stochastic
        dataframe["stoch_k"], dataframe["stoch_d"] = ta.STOCH(dataframe)

        # VWAP（SMC 結構）
        dataframe["vwap"] = qtpylib.rolling_vwap(dataframe, window=8, min_periods=8)

        # ===========================================
        # 📊 成交量特徵 (V38: SMMA instead of SMA)
        # SMMA formula: SMMA[i] = (SMMA[i-1] * (period-1) + price[i]) / period
        # ===========================================
        def calc_smma(series, period=20):
            """Calculate Smoothed Moving Average using pandas ewm with alpha=1/period"""
            return series.ewm(alpha=1 / period, min_periods=period).mean()

        dataframe["volume_smma"] = calc_smma(dataframe["volume"], 20)
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_smma"]
        dataframe["obv"] = ta.OBV(dataframe)
        dataframe["ad"] = ta.AD(dataframe)

        # ===========================================
        # 📊 微觀結構特徵（已放寬閾值）
        # ===========================================
        dataframe = self.add_microstructure_features(dataframe)

        # ===========================================
        # 🌐 多時間框架特徵
        # ===========================================
        dataframe = self.add_multi_timeframe_features(dataframe, metadata)

        # ===========================================
        # 🎯 市場制度識別（EMA 多頭過濾）
        # ===========================================
        dataframe = self.detect_market_regime(dataframe)

        # V38: SMMA instead of SMA for ATR ratio
        def calc_smma(series, period=20):
            """Calculate Smoothed Moving Average using pandas ewm with alpha=1/period"""
            return series.ewm(alpha=1 / period, min_periods=period).mean()

        dataframe["atr_ratio"] = dataframe["atr"] / calc_smma(dataframe["atr"], 20)

        # ===========================================
        # 📊 信號品質計算（ScalpOpt_UAT 邏輯）
        # ===========================================
        dataframe = self.calculate_signal_quality(dataframe)

        # ===========================================
        # 🧠 FREQAI 機器學習特徵
        # ===========================================
        # 注意：FreqAI 需要在 config 中啟用，這裡提供 fallback
        try:
            if self.freqai_enabled and hasattr(self, "freqai"):
                dataframe = self.freqai.start(dataframe, metadata, self)
            else:
                # FreqAI 不可用時，模擬 ML 信號用於回測
                dataframe["&ml_prediction"] = 0.55
                dataframe["&ml_confidence"] = 0.55
        except Exception as e:
            # Fallback：模擬基本 ML 信號
            dataframe["&ml_prediction"] = 0.55
            dataframe["&ml_confidence"] = 0.55

        return dataframe

    def add_microstructure_features(self, dataframe: DataFrame) -> DataFrame:
        """微觀結構特徵（放寬版本）"""

        # 價格動量
        dataframe["price_momentum"] = dataframe["close"].pct_change(5)
        dataframe["price_acceleration"] = dataframe["price_momentum"].diff()

        # 成交量價格趨勢
        dataframe["volume_price_trend"] = (
            (dataframe["close"] - dataframe["close"].shift(1))
            / dataframe["close"].shift(1)
            * dataframe["volume"]
        ).fillna(0)

        # 量價背離
        dataframe["volume_divergence"] = (
            (dataframe["close"].pct_change() > 0) & (dataframe["volume"].pct_change() < 0)
        ).astype(int)

        # 買賣壓力（已放寬閾值）
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

        # ✅ 放寬：1.2 → 1.0
        dataframe["pressure_ratio"] = dataframe["buy_pressure"] / (
            dataframe["sell_pressure"] + 1e-10
        )

        # 波動率特徵
        dataframe["realized_volatility"] = dataframe["close"].rolling(20).std()
        dataframe["volatility_ratio"] = dataframe["atr"] / (
            dataframe["realized_volatility"] + 1e-10
        )

        # 流動性代理
        dataframe["liquidity_proxy"] = dataframe["volume"] / (dataframe["atr"] + 1e-10)

        return dataframe

    def add_multi_timeframe_features(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """多時間框架特徵"""

        def calc_smma(series, period=20):
            """Calculate Smoothed Moving Average using pandas ewm with alpha=1/period"""
            return series.ewm(alpha=1 / period, min_periods=period).mean()

        for tf in self.informative_timeframes:
            try:
                informative = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=tf)

                informative[f"rsi_{tf}"] = ta.RSI(informative, timeperiod=14)
                informative[f"ema_21_{tf}"] = ta.EMA(informative, timeperiod=21)
                # V38: SMMA instead of SMA for volume_ratio in multi-timeframe
                informative[f"volume_ratio_{tf}"] = informative["volume"] / calc_smma(
                    informative["volume"], 20
                )

                dataframe = merge_informative_pair(
                    dataframe, informative, self.timeframe, tf, ffill=True
                )

            except Exception as e:
                logger.warning(f"Failed to add {tf} timeframe data: {e}")
                continue

        return dataframe

    def detect_market_regime(self, dataframe: DataFrame) -> DataFrame:
        """
        市場制度檢測（基於 ScalpOpt_UAT EMA 多頭過濾）
        """

        # EMA 多頭制度：ema_fast > ema_slow 且價格在 EMA 中期均線上方
        dataframe["trend_up"] = (dataframe["ema_fast"] > dataframe["ema_slow"]) & (
            dataframe["close"] > dataframe["ema_medium"]
        )

        # 強趨勢制度
        trend_strength = (dataframe["ema_fast"] - dataframe["ema_slow"]) / dataframe["ema_slow"]
        volatility = dataframe["atr"] / dataframe["close"]

        dataframe["market_regime"] = "neutral"

        strong_trend_condition = (
            (abs(trend_strength) > 0.02)
            & (dataframe["trend_up"] == True)
            & (volatility < volatility.rolling(50).quantile(0.7))
        )
        dataframe.loc[strong_trend_condition, "market_regime"] = "strong_trend"

        # 高波動制度
        high_vol_condition = volatility > volatility.rolling(50).quantile(0.8)
        dataframe.loc[high_vol_condition, "market_regime"] = "high_volatility"

        # 橫盤制度
        ranging_condition = (abs(trend_strength) < 0.01) & (dataframe["trend_up"] == False)
        dataframe.loc[ranging_condition, "market_regime"] = "ranging"

        return dataframe

    def calculate_signal_quality(self, dataframe: DataFrame) -> DataFrame:
        """
        信號品質計算（基於 ScalpOpt_UAT）
        """

        # SMC 分數
        dataframe["smc_score"] = (
            # 價格在 VWAP 上方（40%權重）
            (dataframe["close"] > dataframe["vwap"]).astype(float) * 0.4
            +
            # EMA 多頭趨勢（30%權重）
            (dataframe["trend_up"]).astype(float) * 0.3
            +
            # RSI 健康（15%權重）
            (dataframe["rsi"] < 70).astype(float) * 0.15
            +
            # 成交量放大（15%權重）
            (dataframe["volume_ratio"] > 1.0).astype(float) * 0.15
        )

        # 標準化信號品質
        dataframe["signal_quality"] = (
            dataframe["smc_score"] * 0.4
            + ((dataframe["rsi"] - 30) / 40).clip(0, 1) * 0.3
            + (dataframe["volume_ratio"] / 2).clip(0, 1) * 0.3
        )

        return dataframe

    def populate_entry_trend(self, DataFrame: DataFrame, metadata: dict) -> DataFrame:
        """
        V30.1 入場邏輯（方向B: 制度適應ML閾值）
        結合 FreqAI 預測與市場結構確認
        """

        # ===========================================
        # 🧠 FreqAI 預測信號
        # ===========================================
        if self.freqai_enabled:
            ml_prediction = DataFrame.get("&ml_prediction", 0.5)
            ml_confidence = DataFrame.get("&ml_confidence", 0.5)
        else:
            ml_prediction = 0.5
            ml_confidence = 0.5

        # ===========================================
        # 🎯 市場制度識別（用於動態閾值）
        # ===========================================
        regime = DataFrame["market_regime"]

        # 方向B: 根據市場制度選擇閾值
        # 強強趨勢：寬鬆閾值捕捉機會
        # 高波動：嚴格閾值過濾假信號
        ml_confidence_thresh = np.where(
            regime == "strong_trend",
            self.ml_confidence_threshold_trend.value,
            np.where(
                regime == "high_volatility",
                self.ml_confidence_threshold_volatile.value,
                self.ml_confidence_threshold.value,
            ),
        )
        ml_prediction_thresh = np.where(
            regime == "strong_trend",
            self.ml_prediction_threshold_trend.value,
            np.where(
                regime == "high_volatility",
                self.ml_prediction_threshold_volatile.value,
                self.ml_prediction_threshold.value,
            ),
        )

        # ===========================================
        # 🎯 市場制度過濾（EMA 多頭）
        # ===========================================
        regime_condition = DataFrame["trend_up"]

        # ===========================================
        # 📊 微觀結構確認（已放寬）
        # ===========================================
        microstructure_confirm = (
            (DataFrame["pressure_ratio"] > 1.0)  # ✅ 放寬：1.2 → 1.0
            & (DataFrame["liquidity_proxy"] > DataFrame["liquidity_proxy"].rolling(10).median())
            & (DataFrame["volume_ratio"] > 1.2)  # ✅ 放寬：1.5 → 1.2
        )

        # ===========================================
        # 📊 信號品質確認
        # ===========================================
        quality_confirm = DataFrame["signal_quality"] >= 0.25

        # ===========================================
        # 📈 價格位置確認
        # ===========================================
        price_confirm = (
            (DataFrame["close"] > DataFrame["vwap"])
            & (DataFrame["rsi"] < 70)
            & (DataFrame["rsi"] > 30)
        )

        # ===========================================
        # 🚀 多級入場邏輯（使用動態閾值）
        # ===========================================

        # 高信心入場（AI + 結構確認）- V36: 移除 regime 限制
        high_confidence_entry = (
            (ml_prediction > ml_prediction_thresh)
            & (ml_confidence > ml_confidence_thresh)
            & regime_condition
            & microstructure_confirm
            & quality_confirm
            & price_confirm
        )

        # 標準入場（結構為主）- V36: 移除 regime 限制
        standard_entry = (
            regime_condition
            & microstructure_confirm
            & quality_confirm
            & price_confirm
            & (DataFrame["volume_ratio"] > 1.2)  # 降低到 1.2
        ) & ~high_confidence_entry

        # 應用入場信號
        DataFrame.loc[high_confidence_entry, "enter_long"] = 1
        DataFrame.loc[standard_entry, "enter_long"] = 1

        return DataFrame

    def populate_exit_trend(self, DataFrame: DataFrame, metadata: dict) -> DataFrame:
        """
        V53 出場邏輯 - NO ROI TEST
        市場制度轉變退出（趨勢反轉時離開）
        ROI exits removed - only trailing stop + stoploss
        """

        # 只保留市場制度轉變退出（趨勢反轉時離開）
        DataFrame.loc[
            (DataFrame["trend_up"] == False) & (DataFrame["close"] < DataFrame["vwap"]), "exit_long"
        ] = 1

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
        """
        交易確認鉤子
        """

        try:
            DataFrame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(DataFrame) == 0:
                return False

            current_candle = DataFrame.iloc[-1].squeeze()

            # 基礎確認
            if current_candle.get("volume", 0) == 0:
                return False

            # EMA 多頭確認
            if not current_candle.get("trend_up", False):
                return False

            # 微觀結構確認（已放寬）
            pressure_ratio = current_candle.get("pressure_ratio", 1.0)
            volume_ratio = current_candle.get("volume_ratio", 1.0)

            if pressure_ratio < 0.9 or volume_ratio < 1.0:
                return False

            return True

        except Exception as e:
            logger.warning(f"Trade confirmation failed for {pair}: {e}")
            return False

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ) -> Optional[Union[str, bool]]:
        """
        V53 自定義退出邏輯 - MINIMAL
        Only used for edge cases. Main exits: trailing_stop + stoploss
        """

        try:
            DataFrame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(DataFrame) == 0:
                return None

            current_candle = DataFrame.iloc[-1].squeeze()

            # 持倉時間
            if hasattr(trade, "open_date_utc"):
                open_date = trade.open_date_utc
            else:
                open_date = trade.open_date

            if open_date.tzinfo is None:
                open_date = open_date.replace(tzinfo=timezone.utc)
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)

            duration_minutes = (current_time - open_date).total_seconds() / 60

            # V53: Keep AI exit but simplify - test if this helps or hurts
            if self.freqai_enabled:
                ml_prediction = current_candle.get("&ml_prediction", 0.5)
                ml_confidence = current_candle.get("&ml_confidence", 0.5)

                if ml_prediction < 0.35 and ml_confidence > 0.65:
                    return f"AI_EXIT: {current_profit:.3f}"

            # 市場制度轉變退出
            if not current_candle.get("trend_up", True):
                return f"REGIME_CHANGE: {current_profit:.3f}"

            # 硬止損
            if current_profit <= -0.12:
                return f"STOP_LOSS: {current_profit:.3f}"

            # 最大持倉時間（4小時）
            if duration_minutes >= 240:
                return f"MAX_DURATION: {current_profit:.3f}"

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
        動態倉位管理
        """

        if not self.dynamic_position_sizing.value:
            return proposed_stake

        try:
            DataFrame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(DataFrame) == 0:
                return proposed_stake

            current_candle = DataFrame.iloc[-1].squeeze()

            # 基礎倍數
            base_multiplier = self.risk_scaling_factor.value

            # FreqAI 信心調整
            if self.freqai_enabled:
                ml_confidence = current_candle.get("&ml_confidence", 0.5)
                confidence_multiplier = 0.5 + ml_confidence * 1.5
            else:
                confidence_multiplier = 1.0

            stake = proposed_stake * base_multiplier * confidence_multiplier
            return stake

        except Exception as e:
            logger.warning(f"Stake amount calculation failed: {e}")
            return proposed_stake
