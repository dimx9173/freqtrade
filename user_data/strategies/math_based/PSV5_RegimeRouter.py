"""
PSV5_RegimeRouter - 市場狀態路由策略
======================================
整合3個狀態專用策略的統一入口

基於 C1/C3 分析結果：
- TRENDING: 73.8% 持續性，avg 3.8 candles
- RANGING: 73.4% 持續性，avg 3.8 candles
- BREAKOUT: 70.9% 持續性，avg 3.4 candles
- STRONG_TREND/VOLATILE_TREND: 持續性低(~45%)，avg 1.7-1.8 candles

路由邏輯：
1. 計算市場狀態（ADX + 波動率）
2. 根據狀態選擇對應的進場邏輯：
   - TRENDING/STRONG_TREND → 趨勢跟隨邏輯（EMA突破 + ADX確認）
   - RANGING → 均值回歸邏輯（BB觸及 + RSI極值）
   - BREAKOUT/VOLATILE_TREND → 突破邏輯（ATR擴張 + 價格突破）
3. 出場條件根據狀態動態調整：
   - 趨勢市場：ROI {0:0.12, 1440:0.08, 2880:0.05}, trailing 0.03
   - 震盪市場：ROI {0:0.04, 360:0.02, 720:0.01}
   - 突破市場：ROI {0:0.06, 180:0.04, 360:0.02}, trailing 0.02

作者: Brian's PSV5 Regime Router
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
    TRENDING = 1  # 趨勢市場（來自PSV5_TrendFollowing）
    STRONG_TREND = 2  # 強趨勢市場
    RANGING = 3  # 震盪市場（來自PSV5_RangeTrading）
    BREAKOUT = 4  # 突破市場（來自PSV5_Breakout）
    VOLATILE_TREND = 5  # 高波動趨勢市場


class PSV5_RegimeRouter(IStrategy):
    """
    PSV5 市場狀態路由策略

    整合 PSV5_TrendFollowing、PSV5_RangeTrading、PSV5_Breakout 三個策略
    根據即時市場狀態動態選擇最適合的交易邏輯

    市場狀態檢測：
    - TRENDING/STRONG_TREND: ADX > 7 + 低波動率 (volatility <= 3.69%)
    - RANGING: ADX < 6 + 低波動率 (volatility <= 2.54%)
    - BREAKOUT/VOLATILE_TREND: 波動率 > 3.69% (ATR expansion)

    Entry Logic:
    - TREND: EMA突破 + ADX確認 + RSI 40-60 + 價格通道突破
    - RANGE: BB觸軌 + RSI超買超賣 + EMA200附近
    - BREAKOUT: ATR擴張 + 價格突破 + 成交量確認 + ADX方向

    Exit Logic (Dynamic ROI + Trailing):
    - TREND: ROI {0:0.12, 1440:0.08, 2880:0.05}, trailing 0.03
    - RANGE: ROI {0:0.04, 360:0.02, 720:0.01}, no trailing
    - BREAKOUT: ROI {0:0.06, 180:0.04, 360:0.02}, trailing 0.02
    """

    # ==================== 基本設定 ====================
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # 強制使用exit_signal
    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 200  # 需要足夠計算 EMA200, BB, ATR

    # ==================== 狀態檢測參數 ====================
    # ADX 閾值
    ADX_TREND_THRESHOLD = 7.0  # 趨勢市場門檻 (ADX > 7)
    ADX_RANGE_MAX = 6.0  # 震盪市場上限 (ADX < 6)

    # 波動率閾值
    VOLATILITY_LOW_MAX = 3.69  # 低波動率上限 (%)
    VOLATILITY_VERY_LOW_MAX = 2.54  # 非常低波動率 (震盪市場)
    ATR_EXPANSION_RATIO = 1.5  # ATR 擴張倍數

    # 狀態確認緩衝
    REGIME_CONFIRM_CANDLES = 3  # 需要連續N根K線確認才切換

    # ==================== TREND 狀態參數 ====================
    TREND_STOP_LOSS = -0.04
    TREND_ROI = {
        "0": 0.12,  # 12% 立即目標
        "1440": 0.08,  # 8% 1天後
        "2880": 0.05,  # 5% 2天後
    }
    TREND_TRAILING_POSITIVE = 0.03
    TREND_TRAILING_OFFSET = 0.05
    TREND_TRAILING_ONLY_OFFSET = True

    # ==================== RANGE 狀態參數 ====================
    RANGE_STOP_LOSS = -0.02
    RANGE_ROI = {
        "0": 0.04,  # 4% 立即目標
        "360": 0.02,  # 2% 6小時後
        "720": 0.01,  # 1% 12小時後
    }
    RANGE_TRAILING = False  # 均值回歸不使用 trailing

    # ==================== BREAKOUT 狀態參數 ====================
    BREAKOUT_STOP_LOSS = -0.03
    BREAKOUT_ROI = {
        "0": 0.06,  # 6% 立即目標
        "180": 0.04,  # 4% 3小時後
        "360": 0.02,  # 2% 6小時後
    }
    BREAKOUT_TRAILING_POSITIVE = 0.02
    BREAKOUT_TRAILING_OFFSET = 0.04
    BREAKOUT_TRAILING_ONLY_OFFSET = True

    # ==================== Freqtrade 固定參數 ====================
    # 預設值（會根據狀態動態調整）
    stoploss = -0.03
    minimal_roi = {"0": 0.06, "180": 0.04, "360": 0.02}
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # ==================== 內部狀態追蹤 ====================
    _confirmed_regime = MarketRegime.UNKNOWN
    _regime_candle_count = 0
    _last_regime = MarketRegime.UNKNOWN
    _current_regime = MarketRegime.UNKNOWN

    # ==================== 指標計算 ====================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        計算所有市場狀態檢測所需的指標
        同時計算三種策略類型的指標
        """

        # ========== 1. ADX (趨勢強度) ==========
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ========== 2. EMA (指數移動平均線) ==========
        dataframe["ema_9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # EMA 排列（趨勢方向）
        dataframe["ema_bullish"] = (dataframe["ema_9"] > dataframe["ema_21"]) & (
            dataframe["ema_21"] > dataframe["ema_200"]
        )
        dataframe["ema_bearish"] = (dataframe["ema_9"] < dataframe["ema_21"]) & (
            dataframe["ema_21"] < dataframe["ema_200"]
        )

        # ========== 3. RSI (相對強弱指數) ==========
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ========== 4. ATR (平均真實波動) ==========
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_ma"] = dataframe["atr"].rolling(window=20).mean()
        dataframe["atr_ratio"] = dataframe["atr"] / dataframe["atr_ma"]

        # ========== 5. 波動率計算 ==========
        # 歷史波動率 (收盤價變化率的標準差)
        dataframe["volatility"] = dataframe["close"].pct_change().rolling(window=20).std() * 100

        # ========== 6. Bollinger Bands (布林帶 - 均值回歸用) ==========
        bb_result = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb_result["upperband"]
        dataframe["bb_middle"] = bb_result["middleband"]
        dataframe["bb_lower"] = bb_result["lowerband"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe[
            "bb_middle"
        ]

        # BB 位置
        dataframe["bb_position"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )

        # BB 觸軌條件
        dataframe["bb_touch_lower"] = dataframe["close"] <= dataframe["bb_lower"] * 1.01
        dataframe["bb_touch_upper"] = dataframe["close"] >= dataframe["bb_upper"] * 0.99

        # ========== 7. 價格通道 (Donchian - 趨勢突破用) ==========
        channel_period = 20
        dataframe["channel_high"] = dataframe["high"].rolling(window=channel_period).max()
        dataframe["channel_low"] = dataframe["low"].rolling(window=channel_period).min()

        # 價格突破信號
        dataframe["price_breakout_up"] = dataframe["close"] > dataframe["channel_high"].shift(1)
        dataframe["price_breakout_down"] = dataframe["close"] < dataframe["channel_low"].shift(1)

        # ========== 8. 近期高低點 (突破策略用) ==========
        dataframe["recent_high"] = dataframe["high"].rolling(window=10).max()
        dataframe["recent_low"] = dataframe["low"].rolling(window=10).min()
        dataframe["breakout_up"] = dataframe["close"] > dataframe["recent_high"].shift(1)
        dataframe["breakout_down"] = dataframe["close"] < dataframe["recent_low"].shift(1)

        # ========== 9. 成交量 ==========
        dataframe["volume_ma"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma"]

        # ========== 10. 動量指標 ==========
        dataframe["roc"] = ta.ROCP(dataframe, timeperiod=10) * 100

        # ========== 11. DI 交叉信號 ==========
        dataframe["di_bullish_cross"] = (dataframe["plus_di"] > dataframe["minus_di"]) & (
            dataframe["plus_di"].shift(1) <= dataframe["minus_di"].shift(1)
        )
        dataframe["di_bearish_cross"] = (dataframe["minus_di"] > dataframe["plus_di"]) & (
            dataframe["minus_di"].shift(1) <= dataframe["plus_di"].shift(1)
        )

        # ========== 12. 價格與 EMA200 關係 ==========
        dataframe["near_ema200"] = (dataframe["close"] >= dataframe["ema_200"] * 0.97) & (
            dataframe["close"] <= dataframe["ema_200"] * 1.03
        )
        dataframe["above_ema200"] = dataframe["close"] > dataframe["ema_200"]
        dataframe["below_ema200"] = dataframe["close"] < dataframe["ema_200"]

        # ========== 13. 市場狀態檢測信號 ==========
        dataframe["regime_trending"] = self._detect_trending_regime(dataframe)
        dataframe["regime_ranging"] = self._detect_ranging_regime(dataframe)
        dataframe["regime_breakout"] = self._detect_breakout_regime(dataframe)

        # 即時市場狀態
        dataframe["current_regime"] = self._get_current_regime(dataframe)

        # 緩衝確認後的狀態
        dataframe["confirmed_regime"] = self._get_confirmed_regime(dataframe)

        return dataframe

    def _detect_trending_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        檢測 TRENDING 市場狀態
        條件：ADX > 7 且波動率 <= 3.69%
        """
        adx_strong = dataframe["adx"] > self.ADX_TREND_THRESHOLD
        low_volatility = dataframe["volatility"] <= self.VOLATILITY_LOW_MAX

        return adx_strong & low_volatility

    def _detect_ranging_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        檢測 RANGING 市場狀態
        條件：ADX < 6 且波動率 <= 2.54%
        """
        adx_weak = dataframe["adx"] < self.ADX_RANGE_MAX
        very_low_vol = dataframe["volatility"] <= self.VOLATILITY_VERY_LOW_MAX

        return adx_weak & very_low_vol

    def _detect_breakout_regime(self, dataframe: DataFrame) -> pd.Series:
        """
        檢測 BREAKOUT/VOLATILE_TREND 市場狀態
        條件：ATR 擴張 > 1.5x 或 波動率 > 3.69%
        """
        atr_expansion = dataframe["atr_ratio"] > self.ATR_EXPANSION_RATIO
        high_volatility = dataframe["volatility"] > self.VOLATILITY_LOW_MAX

        return atr_expansion | high_volatility

    def _get_current_regime(self, dataframe: DataFrame) -> int:
        """
        取得當前即時市場狀態（向量化）
        優先級：BREAKOUT > TRENDING > RANGING
        """
        regime_breakout = dataframe["regime_breakout"].iloc[-1]
        regime_trending = dataframe["regime_trending"].iloc[-1]
        regime_ranging = dataframe["regime_ranging"].iloc[-1]

        # 優先檢測突破狀態（最明確的信號）
        if regime_breakout:
            # 進一步區分 BREAKOUT 和 VOLATILE_TREND
            adx_strong = dataframe["adx"].iloc[-1] > self.ADX_TREND_THRESHOLD
            if adx_strong:
                return MarketRegime.VOLATILE_TREND
            return MarketRegime.BREAKOUT

        # 檢測趨勢狀態
        if regime_trending:
            # 進一步區分 TRENDING 和 STRONG_TREND
            adx_very_strong = dataframe["adx"].iloc[-1] > 10
            if adx_very_strong:
                return MarketRegime.STRONG_TREND
            return MarketRegime.TRENDING

        # 預設為震盪狀態
        return MarketRegime.RANGING

    def _get_confirmed_regime(self, dataframe: DataFrame) -> int:
        """
        取得經過緩衝確認的市場狀態
        需要連續N根K線滿足同一狀態條件才確認切換
        """
        lookback = min(self.REGIME_CONFIRM_CANDLES, len(dataframe))
        recent = dataframe.iloc[-lookback:]

        # 統計各狀態出現次數
        breakout_count = recent["regime_breakout"].sum()
        trending_count = recent["regime_trending"].sum()
        ranging_count = recent["regime_ranging"].sum()

        # 取得最新即時狀態
        current_regime = self._get_current_regime(dataframe)
        self._current_regime = current_regime

        # 如果狀態連續確認N次，更新確認狀態
        if current_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            if breakout_count >= self.REGIME_CONFIRM_CANDLES:
                self._last_regime = self._confirmed_regime
                self._confirmed_regime = current_regime
                self._regime_candle_count = 0
            else:
                self._regime_candle_count += 1

        elif current_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            if trending_count >= self.REGIME_CONFIRM_CANDLES:
                self._last_regime = self._confirmed_regime
                self._confirmed_regime = current_regime
                self._regime_candle_count = 0
            else:
                self._regime_candle_count += 1

        elif current_regime == MarketRegime.RANGING:
            if ranging_count >= self.REGIME_CONFIRM_CANDLES:
                self._last_regime = self._confirmed_regime
                self._confirmed_regime = current_regime
                self._regime_candle_count = 0
            else:
                self._regime_candle_count += 1
        else:
            self._regime_candle_count += 1

        return self._confirmed_regime

    # ==================== 進場條件路由 ====================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根據當前確認的市場狀態選擇對應的進場條件
        """
        # 確保確認狀態已更新
        self._get_confirmed_regime(dataframe)

        # 清空之前的進場信號
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # 根據確認的狀態選擇進場邏輯
        if self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            dataframe = self._entry_breakout_mode(dataframe)
        elif self._confirmed_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            dataframe = self._entry_trend_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.RANGING:
            dataframe = self._entry_range_mode(dataframe)

        return dataframe

    def _entry_trend_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        TREND 模式進場條件（來自 PSV5_TrendFollowing）
        條件：ADX > 7 + EMA排列 + 價格突破通道 + RSI 40-60
        """
        # 多頭進場：ADX > 7 + EMA多頭排列 + RSI 40-60 + 價格突破上升
        long_conditions = (
            (dataframe["adx"] > self.ADX_TREND_THRESHOLD)
            & (dataframe["ema_bullish"])
            & (dataframe["rsi"] > 40)
            & (dataframe["rsi"] < 60)
            & (dataframe["price_breakout_up"])
            & (dataframe["volume"] > 0)
        )

        # 空頭進場：ADX > 7 + EMA空頭排列 + RSI 40-60 + 價格跌破通道
        short_conditions = (
            (dataframe["adx"] > self.ADX_TREND_THRESHOLD)
            & (dataframe["ema_bearish"])
            & (dataframe["rsi"] > 40)
            & (dataframe["rsi"] < 60)
            & (dataframe["price_breakout_down"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def _entry_range_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        RANGE 模式進場條件（來自 PSV5_RangeTrading）
        條件：ADX < 6 + BB觸軌 + RSI超買超賣 + 價格在EMA200附近
        """
        # 多頭進場：ADX < 6 + BB下軌觸及 + RSI超賣 + EMA200附近
        long_conditions = (
            (dataframe["adx"] < self.ADX_RANGE_MAX)
            & (dataframe["bb_touch_lower"])
            & (dataframe["rsi"] < 30)
            & (dataframe["near_ema200"])
            & (dataframe["volume"] > 0)
        )

        # 空頭進場：ADX < 6 + BB上軌觸及 + RSI超買 + EMA200附近
        short_conditions = (
            (dataframe["adx"] < self.ADX_RANGE_MAX)
            & (dataframe["bb_touch_upper"])
            & (dataframe["rsi"] > 70)
            & (dataframe["near_ema200"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    def _entry_breakout_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        BREAKOUT 模式進場條件（來自 PSV5_Breakout）
        條件：ATR擴張 > 1.5x + 價格突破 + 成交量確認 + ADX方向
        """
        # 多頭進場：ATR擴張 + 價格突破 + 成交量放大 + ADX方向確認
        long_conditions = (
            (dataframe["atr_ratio"] > self.ATR_EXPANSION_RATIO)
            & (dataframe["breakout_up"])
            & (dataframe["volume_ratio"] > 1.5)
            & (dataframe["adx"] > 5)
            & (dataframe["plus_di"] > dataframe["minus_di"])
            & (dataframe["roc"] > 0)
            & (dataframe["volume"] > 0)
        )

        # 空頭進場
        short_conditions = (
            (dataframe["atr_ratio"] > self.ATR_EXPANSION_RATIO)
            & (dataframe["breakout_down"])
            & (dataframe["volume_ratio"] > 1.5)
            & (dataframe["adx"] > 5)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["roc"] < 0)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[long_conditions, "enter_long"] = 1
        dataframe.loc[short_conditions, "enter_short"] = 1

        return dataframe

    # ==================== 出場條件路由 ====================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根據當前確認的市場狀態選擇對應的出场條件
        """
        if self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            dataframe = self._exit_breakout_mode(dataframe)
        elif self._confirmed_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            dataframe = self._exit_trend_mode(dataframe)
        elif self._confirmed_regime == MarketRegime.RANGING:
            dataframe = self._exit_range_mode(dataframe)

        return dataframe

    def _exit_trend_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        TREND 模式出廠條件
        EMA排列反轉 或 ADX下降 或 DI交叉
        """
        # 多頭出廠：EMA空頭排列 或 ADX下降 或 DI空頭交叉
        long_exit = (
            (dataframe["ema_bearish"]) | (dataframe["adx"] < 6) | (dataframe["di_bearish_cross"])
        )

        # 空頭出廠
        short_exit = (
            (dataframe["ema_bullish"]) | (dataframe["adx"] < 6) | (dataframe["di_bullish_cross"])
        )

        dataframe.loc[long_exit, "exit_long"] = 1
        dataframe.loc[short_exit, "exit_short"] = 1

        return dataframe

    def _exit_range_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        RANGE 模式出廠條件
        RSI 回歸中性區域 (40-60)
        """
        # 均值回歸主要依賴 ROI 出廠，這裡用 RSI 中性確認
        rsi_neutral = (dataframe["rsi"] >= 40) & (dataframe["rsi"] <= 60)

        # 多頭出廠：RSI 回歸中性
        dataframe.loc[rsi_neutral, "exit_long"] = 1
        dataframe.loc[rsi_neutral, "exit_short"] = 1

        return dataframe

    def _exit_breakout_mode(self, dataframe: DataFrame) -> DataFrame:
        """
        BREAKOUT 模式出廠條件
        動量反轉 或 ATR 收縮
        """
        # 多頭出廠：ROC 負向 或 ATR 收縮
        long_exit = (dataframe["roc"] < 0) | (dataframe["atr_ratio"] < 1.0)

        # 空頭出廠
        short_exit = (dataframe["roc"] > 0) | (dataframe["atr_ratio"] < 1.0)

        dataframe.loc[long_exit, "exit_long"] = 1
        dataframe.loc[short_exit, "exit_short"] = 1

        return dataframe

    # ==================== 動態參數調整 ====================

    def get_stoploss(
        self, trade, entry, current_time, lookback_1h, current_rate, current_time_1h, **kwargs
    ) -> float:
        """
        根據市場狀態返回對應的stoploss
        """
        if self._confirmed_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            return self.TREND_STOP_LOSS
        elif self._confirmed_regime == MarketRegime.RANGING:
            return self.RANGE_STOP_LOSS
        elif self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            return self.BREAKOUT_STOP_LOSS
        return -0.03  # 預設值

    def get_roi_table(self, trade) -> Optional[dict]:
        """
        根據市場狀態返回對應的ROI字典
        """
        if self._confirmed_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            return self.TREND_ROI
        elif self._confirmed_regime == MarketRegime.RANGING:
            return self.RANGE_ROI
        elif self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            return self.BREAKOUT_ROI
        return {"0": 0.06, "180": 0.04, "360": 0.02}  # 預設值

    @property
    def trailing_stop(self) -> bool:
        """
        根據市場狀態返回是否使用 trailing stop
        """
        if self._confirmed_regime == MarketRegime.RANGING:
            return False  # 均值回歸不使用 trailing
        return True  # 趨勢和突破使用 trailing

    @property
    def trailing_stop_positive(self) -> float:
        """
        根據市場狀態返回 trailing stop positive 值
        """
        if self._confirmed_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            return self.TREND_TRAILING_POSITIVE
        elif self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            return self.BREAKOUT_TRAILING_POSITIVE
        return 0.02  # 預設值

    @property
    def trailing_stop_positive_offset(self) -> float:
        """
        根據市場狀態返回 trailing stop offset 值
        """
        if self._confirmed_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            return self.TREND_TRAILING_OFFSET
        elif self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            return self.BREAKOUT_TRAILING_OFFSET
        return 0.04  # 預設值

    @property
    def trailing_only_offset_is_reached(self) -> bool:
        """
        根據市場狀態返回 trailing_only_offset_is_reached
        """
        if self._confirmed_regime in [MarketRegime.TRENDING, MarketRegime.STRONG_TREND]:
            return self.TREND_TRAILING_ONLY_OFFSET
        elif self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            return self.BREAKOUT_TRAILING_ONLY_OFFSET
        return True  # 預設值

    # ==================== 倉位管理 ====================

    def adjust_position_size(self, dataframe: DataFrame, metadata: dict) -> float:
        """
        根據市場狀態和波動率調整倉位
        BREAKOUT 模式下使用 ATR 波動率倉位調整
        """
        if self._confirmed_regime in [MarketRegime.BREAKOUT, MarketRegime.VOLATILE_TREND]:
            if len(dataframe) < 20:
                return None

            atr_ratio = dataframe["atr_ratio"].iloc[-1]

            # ATR 越高，倉位越小
            if atr_ratio > 2.0:
                return 0.5  # 50% 倉位
            elif atr_ratio > 1.0:
                reduction = 1 - (atr_ratio - 1.0) / 1.0 * 0.5
                return max(0.5, reduction)

        # 其他狀態使用默認倉位
        return None

    def get_ticker_indicator_list(self) -> list:
        """
        返回需要的 indicators 列表
        """
        return [
            "adx",
            "plus_di",
            "minus_di",
            "ema_9",
            "ema_21",
            "ema_200",
            "rsi",
            "atr",
            "atr_ratio",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "channel_high",
            "channel_low",
            "recent_high",
            "recent_low",
            "volume",
            "roc",
        ]
