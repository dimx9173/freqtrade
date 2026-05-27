"""
PSV3_Regime_Adaptive - 市場狀態路由系統
=========================================
整合3種市場狀態的動態策略切換：
- TREND (動量突破): ADX強趨勢 + Parabolic SAR + Donchian Channel
- RANGE (均值回歸): CCI + Williams %R + Z-Score統計套利
- VOLATILITY (波動率擴張): BB Width + Keltner Channel + CMO

核心設計：
1. 狀態檢測：在populate_indicators計算市場狀態指標
2. 策略路由：根據即時狀態選擇對應進場條件
3. 狀態緩衝：連續N根K線確認才切換，避免頻繁震盪
4. 獨立參數：每個狀態有專屬stoploss和ROI配置

作者: Brian's Regime Router v3.0
時間框架: 15m
多空支援: 雙向
"""

import talib.abstract as ta
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from typing import Optional


# ==================== 市場狀態枚舉 ====================
class MarketRegime:
    """市場狀態常量"""

    UNKNOWN = 0
    TREND = 1  # 動量突破型 - 強趨勢市場
    RANGE = 2  # 均值回歸型 - 區間震盪市場
    VOLATILITY = 3  # 波動率擴張型 - 高波動市場


class PSV3_Regime_Adaptive(IStrategy):
    """
    Market Regime Adaptive Strategy

    根據即時市場狀態動態選擇最佳交易邏輯：
    - TREND mode: 趨勢追逐，適用於ADX強趨勢市場
    - RANGE mode: 均值回歸，適用於區間震盪市場
    - VOLATILITY mode: 波動突破，適用於波動率擴張市場
    """

    # ==================== 基本設定 ====================
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # 強制使用exit_signal讓我們的狀態路由exit生效
    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 60

    # ==================== 狀態切換緩衝設定 ====================
    # 狀態確認所需連續K線數（避免頻繁切換）
    REGIME_CONFIRM_CANDLES = 3

    # 狀態檢測窗口（用於計算市場特徵）
    ADX_PERIOD = 14
    BB_PERIOD = 20
    CCI_PERIOD = 14
    DONCHIAN_PERIOD = 20

    # ==================== TREND狀態參數（動量突破型）====================
    # 適用於：強趨勢、趨勢延續市場
    TREND_STOP_LOSS = -0.025
    TREND_ROI = {"0": 0.08, "360": 0.04, "720": 0.02}
    TREND_TRAILING_POSITIVE = 0.018
    TREND_TRAILING_OFFSET = 0.03

    # Trend進場 threshold
    TREND_ADX_THRESHOLD = 25.0
    TREND_MOMENTUM_PERIOD = 10

    # ==================== RANGE狀態參數（均值回歸型）====================
    # 適用於：區間震盪、反彈行情
    RANGE_STOP_LOSS = -0.03
    RANGE_ROI = {"0": 0.06, "360": 0.035, "720": 0.018}
    RANGE_TRAILING_POSITIVE = 0.015
    RANGE_TRAILING_OFFSET = 0.025

    # Range進場 threshold
    RANGE_ADX_MAX = 20.0
    RANGE_CCI_OVERSOLD = -100
    RANGE_CCI_OVERBOUGHT = 100
    RANGE_ZSCORE_THRESHOLD = 1.5
    RANGE_WILLIAMS_THRESHOLD = 80.0

    # ==================== VOLATILITY狀態參數（波動率擴張型）====================
    # 適用於：消息面驱动、波动爆发市场
    VOLATILITY_STOP_LOSS = -0.028
    VOLATILITY_ROI = {"0": 0.075, "360": 0.04, "720": 0.02}
    VOLATILITY_TRAILING_POSITIVE = 0.02
    VOLATILITY_TRAILING_OFFSET = 0.035

    # Volatility進場 threshold
    VOLATILITY_BB_WIDTH_RATIO = 1.3
    VOLATILITY_CMO_THRESHOLD = 0.0

    # ==================== 內部狀態追蹤 ====================
    # 使用類變數追蹤當前確認的市場狀態
    _confirmed_regime = MarketRegime.UNKNOWN
    _regime_candle_count = 0
    _last_regime = MarketRegime.UNKNOWN

    # ==================== 固定參數（freqtrade需要）====================
    stoploss = -0.025
    minimal_roi = {"0": 0.08, "360": 0.04, "720": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.018
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # ==================== 狀態統計（用於分析）====================
    _regime_stats = {"TREND": 0, "RANGE": 0, "VOLATILITY": 0, "UNKNOWN": 0}

    def _get_stoploss_for_regime(self, regime: int) -> float:
        """取得狀態對應的stoploss"""
        if regime == MarketRegime.TREND:
            return self.TREND_STOP_LOSS
        elif regime == MarketRegime.RANGE:
            return self.RANGE_STOP_LOSS
        elif regime == MarketRegime.VOLATILITY:
            return self.VOLATILITY_STOP_LOSS
        return -0.025  # 預設值

    def _get_roi_for_regime(self, regime: int) -> dict:
        """取得狀態對應的ROI"""
        if regime == MarketRegime.TREND:
            return self.TREND_ROI
        elif regime == MarketRegime.RANGE:
            return self.RANGE_ROI
        elif regime == MarketRegime.VOLATILITY:
            return self.VOLATILITY_ROI
        return self.TREND_ROI  # 預設值

    def _get_trailing_positive_for_regime(self, regime: int) -> float:
        """取得狀態對應的trailing positive"""
        if regime == MarketRegime.TREND:
            return self.TREND_TRAILING_POSITIVE
        elif regime == MarketRegime.RANGE:
            return self.RANGE_TRAILING_POSITIVE
        elif regime == MarketRegime.VOLATILITY:
            return self.VOLATILITY_TRAILING_POSITIVE
        return 0.018

    def _get_trailing_offset_for_regime(self, regime: int) -> float:
        """取得狀態對應的trailing offset"""
        if regime == MarketRegime.TREND:
            return self.TREND_TRAILING_OFFSET
        elif regime == MarketRegime.RANGE:
            return self.RANGE_TRAILING_OFFSET
        elif regime == MarketRegime.VOLATILITY:
            return self.VOLATILITY_TRAILING_OFFSET
        return 0.03

    # ==================== 指標計算 ====================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        計算所有市場狀態檢測所需的指標
        同時計算三種策略類型的指標以避免重複計算
        """

        # ========== 1. TREND指標（動量突破型）==========
        # Parabolic SAR - 趨勢方向確認
        dataframe["sar"] = ta.SAR(dataframe, acceleration=0.02, maximum=0.2)
        dataframe["sar_diff"] = dataframe["sar"] - dataframe["close"]
        dataframe["sar_up"] = dataframe["sar_diff"] < 0  # SAR below price = uptrend

        # Donchian Channel - 突破確認
        dataframe["dc_high"] = dataframe["high"].rolling(window=self.DONCHIAN_PERIOD).max()
        dataframe["dc_low"] = dataframe["low"].rolling(window=self.DONCHIAN_PERIOD).min()
        dataframe["dc_mid"] = (dataframe["dc_high"] + dataframe["dc_low"]) / 2

        # Donchian突破信號
        dataframe["dc_breakout_up"] = dataframe["close"] > dataframe["dc_high"].shift(1)
        dataframe["dc_breakout_down"] = dataframe["close"] < dataframe["dc_low"].shift(1)

        # Momentum - 價格動量
        dataframe["momentum"] = ta.MOM(dataframe, timeperiod=self.TREND_MOMENTUM_PERIOD)
        dataframe["momentum_ma"] = ta.MA(dataframe, timeperiod=5, price="momentum")

        # Rate of Change
        dataframe["roc"] = ta.ROCP(dataframe, timeperiod=10) * 100

        # Bollinger Bands %B - 位置確認
        bb_result = ta.BBANDS(dataframe, timeperiod=self.BB_PERIOD, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb_result["upperband"]
        dataframe["bb_middle"] = bb_result["middleband"]
        dataframe["bb_lower"] = bb_result["lowerband"]
        dataframe["bb_percent"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )

        # ========== 2. RANGE指標（均值回歸型）==========
        # CCI - 商品通道指數
        dataframe["cci"] = ta.CCI(dataframe, timeperiod=self.CCI_PERIOD)
        dataframe["cci_ma"] = ta.MA(dataframe, timeperiod=20, price="cci")

        # Williams %R
        dataframe["williams_r"] = ta.WILLR(dataframe, timeperiod=14)
        dataframe["williams_r_ma"] = dataframe["williams_r"].rolling(window=20).mean()

        # Z-Score - 價格偏離均值
        window = 20
        dataframe["price_ma"] = dataframe["close"].rolling(window=window).mean()
        dataframe["price_std"] = dataframe["close"].rolling(window=window).std()
        dataframe["z_score"] = (dataframe["close"] - dataframe["price_ma"]) / dataframe["price_std"]

        # MFI - 資金流量指標
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)

        # Stochastic
        slowk, slowd = ta.STOCH(dataframe, fastk_period=14, slowk_period=3, slowd_period=3)
        dataframe["stoch_k"] = slowk
        dataframe["stoch_d"] = slowd

        # ========== 3. VOLATILITY指標（波動率擴張型）==========
        # BB Width - 波動率擴張核心指標
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe[
            "bb_middle"
        ]
        dataframe["bb_width_ma"] = dataframe["bb_width"].rolling(window=20).mean()
        dataframe["bb_width_ratio"] = dataframe["bb_width"] / dataframe["bb_width_ma"]

        # Keltner Channel
        keltner_period = 20
        keltner_mult = 2
        dataframe["keltner_mid"] = ta.EMA(dataframe, timeperiod=keltner_period)
        dataframe["keltner_atr"] = ta.ATR(dataframe, timeperiod=keltner_period)
        dataframe["keltner_upper"] = dataframe["keltner_mid"] + (
            keltner_mult * dataframe["keltner_atr"]
        )
        dataframe["keltner_lower"] = dataframe["keltner_mid"] - (
            keltner_mult * dataframe["keltner_atr"]
        )

        # Keltner Channel突破信號
        dataframe["keltner_break_up"] = dataframe["close"] > dataframe["keltner_upper"]
        dataframe["keltner_break_down"] = dataframe["close"] < dataframe["keltner_lower"]

        # CMO - Chande Momentum Oscillator
        dataframe["cmo"] = ta.CMO(dataframe, timeperiod=9)
        dataframe["cmo_ma"] = ta.MA(dataframe, timeperiod=5, price="cmo")

        # OBV - 能量潮
        dataframe["obv"] = ta.OBV(dataframe)
        dataframe["obv_ma"] = dataframe["obv"].rolling(window=10).mean()
        dataframe["obv_slope"] = (dataframe["obv"] - dataframe["obv"].shift(5)) / dataframe[
            "obv"
        ].shift(5)

        # ========== 4. 狀態檢測指標（通用）==========
        # ADX - 趨勢強度（核心狀態檢測指標）
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.ADX_PERIOD)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.ADX_PERIOD)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.ADX_PERIOD)

        # 市場狀態檢測信號（即時計算）
        dataframe["regime_trend_signal"] = self._detect_trend_regime(dataframe)
        dataframe["regime_range_signal"] = self._detect_range_regime(dataframe)
        dataframe["regime_volatility_signal"] = self._detect_volatility_regime(dataframe)

        # 當前即時狀態（未經緩衝確認）
        dataframe["current_regime"] = self._get_current_regime(dataframe)

        # 緩衝確認後的狀態
        dataframe["confirmed_regime"] = self._get_confirmed_regime(dataframe)

        return dataframe

    def _detect_trend_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        檢測是否為TREND市場狀態
        條件：ADX > 20 且價格有明確趨勢方向
        """
        adx_trend = dataframe["adx"] > 20  # 降低門檻
        plus_di_strong = dataframe["plus_di"] > dataframe["minus_di"]
        minus_di_strong = dataframe["minus_di"] > dataframe["plus_di"]

        return adx_trend & (plus_di_strong | minus_di_strong)

    def _detect_range_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        檢測是否為RANGE市場狀態
        條件：ADX < 25 且價格在BB中部附近波動
        """
        adx_calm = dataframe["adx"] < 25  # 放寬門檻
        bb_middle_zone = (dataframe["bb_percent"] > 0.2) & (dataframe["bb_percent"] < 0.8)  # 放寬

        return adx_calm & bb_middle_zone

    def _detect_volatility_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        檢測是否為VOLATILITY市場狀態
        條件：BB Width ratio > 1.2 且Keltner突破
        """
        bb_expansion = dataframe["bb_width_ratio"] > 1.2  # 降低門檻
        keltner_break = dataframe["keltner_break_up"] | dataframe["keltner_break_down"]

        return bb_expansion & keltner_break

    def _get_current_regime(self, dataframe: DataFrame) -> int:
        """
        取得當前即時市場狀態（向量化，不使用iloc）
        優先級：VOLATILITY > TREND > RANGE
        """
        # 使用整列數據的最後一個值
        regime_vol = dataframe["regime_volatility_signal"].iloc[-1]
        regime_trend = dataframe["regime_trend_signal"].iloc[-1]

        # 優先檢測波動率擴張狀態（最明確的信號）
        if regime_vol:
            return MarketRegime.VOLATILITY

        # 檢測動量突破狀態
        if regime_trend:
            return MarketRegime.TREND

        # 預設為均值回歸狀態
        return MarketRegime.RANGE

    def _get_confirmed_regime(self, dataframe: DataFrame) -> int:
        """
        取得經過緩衝確認的市場狀態
        需要連續N根K線滿足同一狀態條件才確認切換
        """
        # 使用最後N根K線計算
        lookback = min(self.REGIME_CONFIRM_CANDLES, len(dataframe))
        recent = dataframe.iloc[-lookback:]

        # 統計各狀態出現次數
        trend_count = recent["regime_trend_signal"].sum()
        range_count = recent["regime_range_signal"].sum()
        volatility_count = recent["regime_volatility_signal"].sum()

        # 取得最新即時狀態
        current_regime = self._get_current_regime(dataframe)

        # 如果狀態連續確認N次，更新確認狀態
        if (
            current_regime == MarketRegime.VOLATILITY
            and volatility_count >= self.REGIME_CONFIRM_CANDLES
        ):
            self._last_regime = self._confirmed_regime
            self._confirmed_regime = MarketRegime.VOLATILITY
            self._regime_candle_count = 0
        elif current_regime == MarketRegime.TREND and trend_count >= self.REGIME_CONFIRM_CANDLES:
            self._last_regime = self._confirmed_regime
            self._confirmed_regime = MarketRegime.TREND
            self._regime_candle_count = 0
        elif current_regime == MarketRegime.RANGE and range_count >= self.REGIME_CONFIRM_CANDLES:
            self._last_regime = self._confirmed_regime
            self._confirmed_regime = MarketRegime.RANGE
            self._regime_candle_count = 0
        else:
            # 狀態不夠確認，計數+1
            self._regime_candle_count += 1

        return self._confirmed_regime

    # ==================== 進場條件路由 ====================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根據當前確認的市場狀態選擇對應的進場條件
        """
        # 確保確認狀態已更新
        self._get_confirmed_regime(dataframe)

        # 根據確認的狀態選擇進場邏輯
        if self._confirmed_regime == MarketRegime.VOLATILITY:
            dataframe = self._entry_volatility_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.TREND:
            dataframe = self._entry_trend_mode(dataframe)
        else:
            dataframe = self._entry_range_mode(dataframe)

        return dataframe

    def _entry_trend_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        TREND模式進場條件（動量突破型）
        來自PSV2_Momentum_Breakout
        """
        long_conditions = (
            dataframe["sar_up"]  # SAR在下方
            & dataframe["dc_breakout_up"]  # Donchian向上突破
            & (dataframe["bb_percent"] > 0.5)
            & (dataframe["bb_percent"] < 0.95)
            & (dataframe["momentum"] > 0)
            & (dataframe["roc"] > 0)
        )

        short_conditions = (
            ~dataframe["sar_up"]  # SAR在上方
            & dataframe["dc_breakout_down"]  # Donchian向下突破
            & (dataframe["bb_percent"] < 0.5)
            & (dataframe["bb_percent"] > 0.05)
            & (dataframe["momentum"] < 0)
            & (dataframe["roc"] < 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def _entry_range_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        RANGE模式進場條件（均值回歸型）
        來自PSV2_Mean_Reversion
        """
        # 多頭進場（超賣反彈）
        long_conditions = (
            (dataframe["cci"] < self.RANGE_CCI_OVERSOLD)
            & (dataframe["williams_r"] < -self.RANGE_WILLIAMS_THRESHOLD)
            & (dataframe["z_score"] < -self.RANGE_ZSCORE_THRESHOLD)
            & (dataframe["mfi"] > 30)
            & (dataframe["stoch_k"] > dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1))
        )

        # 空頭進場（超買回調）
        short_conditions = (
            (dataframe["cci"] > self.RANGE_CCI_OVERBOUGHT)
            & (dataframe["williams_r"] > -self.RANGE_WILLIAMS_THRESHOLD)
            & (dataframe["z_score"] > self.RANGE_ZSCORE_THRESHOLD)
            & (dataframe["mfi"] < 70)
            & (dataframe["stoch_k"] < dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1))
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def _entry_volatility_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        VOLATILITY模式進場條件（波動率擴張型）
        來自PSV2_Volatility_Expansion
        """
        # 多頭進場（波動爆發 + 趨勢確認）
        long_conditions = (
            (dataframe["bb_width_ratio"] > self.VOLATILITY_BB_WIDTH_RATIO)
            & dataframe["keltner_break_up"]
            & (dataframe["cmo"] > self.VOLATILITY_CMO_THRESHOLD)
            & (dataframe["obv_slope"] > 0)
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["roc"] > 0)
        )

        # 空頭進場
        short_conditions = (
            (dataframe["bb_width_ratio"] > self.VOLATILITY_BB_WIDTH_RATIO)
            & dataframe["keltner_break_down"]
            & (dataframe["cmo"] < self.VOLATILITY_CMO_THRESHOLD)
            & (dataframe["obv_slope"] < 0)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["roc"] < 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    # ==================== 出場條件路由 ====================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根據當前確認的市場狀態選擇對應的出場條件
        """
        if self._confirmed_regime == MarketRegime.VOLATILITY:
            dataframe = self._exit_volatility_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.TREND:
            dataframe = self._exit_trend_mode(dataframe)
        else:
            dataframe = self._exit_range_mode(dataframe)

        return dataframe

    def _exit_trend_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        TREND模式出廠條件
        SAR方向反轉時止盈/止損
        """
        dataframe["sar_reversal_long"] = (dataframe["sar_up"] == False) & dataframe["sar_up"].shift(
            1
        ) == True
        dataframe["sar_reversal_short"] = (dataframe["sar_up"] == True) & dataframe["sar_up"].shift(
            1
        ) == False

        dataframe.loc[dataframe["sar_reversal_long"], "exit_long"] = 1
        dataframe.loc[dataframe["sar_reversal_short"], "exit_short"] = 1

        return dataframe

    def _exit_range_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        RANGE模式出廠條件
        價格回歸到均值時止盈
        """
        exit_long_conditions = (dataframe["z_score"] > 0.5) | (dataframe["cci"] > 0)

        exit_short_conditions = (dataframe["z_score"] < -0.5) | (dataframe["cci"] < 0)

        dataframe.loc[exit_long_conditions, "exit_long"] = 1
        dataframe.loc[exit_short_conditions, "exit_short"] = 1

        return dataframe

    def _exit_volatility_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        VOLATILITY模式出廠條件
        BB Width收縮或CMO反向時止盈
        """
        exit_long = dataframe["bb_width_ratio"] < 0.9
        exit_short = dataframe["bb_width_ratio"] < 0.9

        exit_long_cmo = (dataframe["cmo"] < 0) & (dataframe["cmo"].shift(1) > 0)
        exit_short_cmo = (dataframe["cmo"] > 0) & (dataframe["cmo"].shift(1) < 0)

        dataframe.loc[exit_long | exit_long_cmo, "exit_long"] = 1
        dataframe.loc[exit_short | exit_short_cmo, "exit_short"] = 1

        return dataframe

    # ==================== 輔助方法 ====================

    def get_regime_name(self, regime: Optional[int] = None) -> str:
        """取得狀態名稱"""
        if regime is None:
            regime = self._confirmed_regime

        names = {
            MarketRegime.UNKNOWN: "UNKNOWN",
            MarketRegime.TREND: "TREND",
            MarketRegime.RANGE: "RANGE",
            MarketRegime.VOLATILITY: "VOLATILITY",
        }
        return names.get(regime, "UNKNOWN")

    def bot_loop_start(self, **kwargs) -> None:
        """
        每個bot循環開始時調用
        可用於重置或初始化狀態
        """
        # 確保每次循環開始時狀態一致
        # 不要在這裡重置_confirmed_regime，因為我們需要跨循環保持狀態
        pass

    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float, time_in_force: str, **kwargs
    ) -> bool:
        """
        確認進場訂單
        可以在这里添加额外的过滤器或日志
        """
        return True
