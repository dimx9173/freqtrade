# 加密貨幣期貨交易的趨勢識別機制研究
## Freqtrade 框架實作指南

---

## 1. ADX (Average Directional Index) 在趨勢識別中的應用

### 1.1 ADX 核心原理

ADX 是 Welles Wilder 開發的趨勢強度指標，範圍 0-100：

| ADX 值 | 市場狀態 | 交易建議 |
|--------|----------|----------|
| **ADX < 20** | 弱趨勢/盤整 | 均值回歸策略，避免趨勢跟隨 |
| **ADX 20-25** | 過渡區域 | 觀望或輕量測試 |
| **ADX > 25** | 強趨勢 | 趨勢跟隨策略入場 |
| **ADX > 40** | 極強趨勢 | 謹慎反向入場，高反轉風險 |

### 1.2 +DI 與 -DI 交叉判斷趨勢方向

```python
# +DI > -DI 表示多頭趨勢
trend_direction = plus_di > minus_di

#經典交叉進場範例（來自 Scalp_ADX_Only.py）
cond_uptrend = dataframe["plus_di"] > dataframe["minus_di"]

# 快速 ADX 確認趨勢不是即將反轉
cond_adx_rising = dataframe["adx_fast"] > dataframe["adx_fast"].shift(1)
```

### 1.3 ADX 閾值測試參考

從日誌中發現的實際使用閾值：
- `buy_adx = 6` ~ `buy_adx = 30` 
- 常用值：`9`, `19`, `25`, `27`
- 建議初始測試：**ADX > 20** 為趨勢確認，**ADX > 25** 為強趨勢

### 1.4 Freqtrade 動態策略切換實作

```python
class TrendRegimeSwitcher(IStrategy):
    """
    根據 ADX 自動切換策略模式
    """
    # ADX 參數
    adx_period = 14
    adx_threshold_strong = 25
    adx_threshold_weak = 20
    
    # 趨勢方向閾值
    di_cross_threshold = 0
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ADX 主指標
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_period)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.adx_period)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.adx_period)
        
        # ATR for 止損
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        
        # --- Regime 分類 ---
        # 強趨勢：ADX > 25
        dataframe["regime_strong"] = dataframe["adx"] > self.adx_threshold_strong
        
        # 盤整：ADX < 20
        dataframe["regime_choppy"] = dataframe["adx"] < self.adx_threshold_weak
        
        # 趨勢方向
        dataframe["trend_bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["trend_bearish"] = dataframe["minus_di"] > dataframe["plus_di"]
        
        # ADX 上升中（趨勢正在增強）
        dataframe["adx_rising"] = dataframe["adx"] > dataframe["adx"].shift(2)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 模式 1：強趨勢跟隨（ADX > 25 且 +DI > -DI）
        cond_trend_follow = (
            (dataframe["adx"] > self.adx_threshold_strong) &
            dataframe["trend_bullish"] &
            dataframe["adx_rising"]
        )
        
        # 模式 2：均值回歸（ADX < 20 且價格觸及 BB 外軌）
        cond_mean_reversion = (
            dataframe["regime_choppy"] &
            (dataframe["close"] < dataframe["bb_lower"])
        )
        
        # 根據 Regime 動態選擇進場條件
        dataframe["enter_long"] = np.where(
            dataframe["regime_strong"],
            cond_trend_follow.astype(int),
            cond_mean_reversion.astype(int)
        )
        
        return dataframe
```

---

## 2. 價格位置分析

### 2.1 價格相對於 EMA/布林帶的位置

```python
# EMA 多頭排列條件
cond_ema_alignment = (
    (dataframe["ema_fast"] > dataframe["ema_slow"]) &
    (dataframe["ema_slow"] > dataframe["ema_trend"]) &
    dataframe["ema_rising"]
)

# 價格相對 BB 位置 (%B)
# %B < 0: 價格在 BB 下軌下方
# %B = 0.5: 價格在 BB 中軌
# %B > 1: 價格在 BB 上軌上方
dataframe["bb_pct"] = (
    dataframe["close"] - dataframe["bb_lower"]
) / (dataframe["bb_upper"] - dataframe["bb_lower"])

# BB 觸及進場（均值回歸）
cond_bb_touch = dataframe["close"] < dataframe["bb_lower"]
cond_bb_bounce = dataframe["close"] > (dataframe["bb_lower"] * 1.001)  # 已反彈
```

### 2.2 多時間框架價格結構

使用 `@informative` decorator 獲取高時間框架資料：

```python
from freqtrade.strategy import informative

class MultiTimeframeStrategy(IStrategy):
    timeframe = "5m"  # 進場時間框架
    informative_timeframe = "15m"  # 確認時間框架
    
    @informative("15m")
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """15m 時間框架的趨勢指標"""
        dataframe["ema_50_15m"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200_15m"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe
    
    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """1h 時間框架的結構確認"""
        dataframe["ema_200_1h"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["bb_lower_1h"] = ta.BBANDS(
            dataframe["close"], timeperiod=20, nbdevup=2, nbdevdn=2
        )["lower"]
        return dataframe
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 本地時間框架指標
        dataframe["ema_9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 多時間框架確認進場
        # 1m: 價格觸及 BB 下軌
        cond_entry = dataframe["close"] < dataframe["bb_lower"]
        
        # 15m: EMA 多頭排列
        cond_trend_15m = (
            (dataframe["ema_50_15m"] > dataframe["ema_200_15m"]) &
            (dataframe["close"] > dataframe["ema_200_15m"])
        )
        
        # 1h: 價格在 EMA200 上方（長期多頭）
        cond_structure_1h = dataframe["close"] > dataframe["ema_200_1h"]
        
        dataframe["enter_long"] = (
            cond_entry & cond_trend_15m & cond_structure_1h
        ).astype(int)
        
        return dataframe
```

### 2.3 支撐/阻力區域識別

```python
def identify_support_resistance(self, dataframe: DataFrame) -> DataFrame:
    """
    識別最近的支撐/阻力區域
    """
    # 方法 1：近期低點/高點
    dataframe["swing_low"] = dataframe["low"].rolling(20).min()
    dataframe["swing_high"] = dataframe["high"].rolling(20).max()
    
    # 方法 2：成交量加權價格 (VWAP) 附近
    dataframe["vwap"] = (
        dataframe["close"] * dataframe["volume"]
    ).cumsum() / dataframe["volume"].cumsum()
    
    # 方法 3：BB 外軌作為動態支撐/阻力
    bb_upper, bb_middle, bb_lower = ta.BBANDS(
        dataframe["close"], timeperiod=20, nbdevup=2, nbdevdn=2
    )
    dataframe["bb_upper"] = bb_upper
    dataframe["bb_middle"] = bb_middle
    dataframe["bb_lower"] = bb_lower
    
    # 價格接近支撐/阻力
    dataframe["near_support"] = dataframe["close"] < (dataframe["swing_low"] * 1.02)
    dataframe["near_resistance"] = dataframe["close"] > (dataframe["swing_high"] * 0.98)
    
    return dataframe
```

---

## 3. 市場狀態分類 (Market Regime Detection)

### 3.1 三種基本 Regime 類型

| Regime | ADX | BB Width | ATR | 策略類型 |
|--------|-----|----------|-----|----------|
| **強趨勢** | > 25 | 高 | 高 | 趨勢跟隨、動量突破 |
| **盤整/低波動** | < 20 | 低 | 低 | 均值回歸、區間交易 |
| **過渡/反轉跡象** | 20-25 | 變化中 | 變化中 | 觀望或反轉策略 |

### 3.2 使用 BB Width + ATR + ADX 組合判斷

```python
class RegimeDetector:
    """
    市場狀態分類器
    """
    
    # BB Width 閾值（相對值）
    BB_WIDTH_THRESHOLD_LOW = 0.02   # 低波動閾值
    BB_WIDTH_THRESHOLD_HIGH = 0.05  # 高波動閾值
    
    # ATR 閾值（百分比）
    ATR_THRESHOLD_LOW = 0.01   # 1% 
    ATR_THRESHOLD_HIGH = 0.03  # 3%
    
    # ADX 閾值
    ADX_THRESHOLD_STRONG = 25
    ADX_THRESHOLD_WEAK = 20
    
    def detect_regime(self, dataframe: DataFrame) -> DataFrame:
        """
        輸出 regime 信號：
        0 = 盤整/低波動
        1 = 過渡區域
        2 = 強趨勢
        """
        # 計算 BB Width（波動率標準化）
        dataframe["bb_width"] = (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        ) / dataframe["bb_middle"]
        
        # 計算 ATR 百分比
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        
        # --- Regime 邏輯 ---
        # 強趨勢：ADX > 25 且波動率適中/高
        is_strong_trend = (
            (dataframe["adx"] > self.ADX_THRESHOLD_STRONG) &
            (dataframe["bb_width"] > self.BB_WIDTH_THRESHOLD_LOW)
        )
        
        # 盤整：ADX < 20 且低波動
        is_choppy = (
            (dataframe["adx"] < self.ADX_THRESHOLD_WEAK) &
            (dataframe["bb_width"] < self.BB_WIDTH_THRESHOLD_LOW)
        )
        
        # 賦值 regime
        dataframe["regime"] = np.where(
            is_strong_trend, 2,
            np.where(is_choppy, 0, 1)  # 其他情況為過渡區域(1)
        )
        
        # 附加資訊
        dataframe["regime_name"] = np.where(
            dataframe["regime"] == 2, "strong_trend",
            np.where(dataframe["regime"] == 0, "choppy", "transition")
        )
        
        return dataframe
```

### 3.3 不同 Regime 下的策略切換邏輯

```python
class RegimeAwareStrategy(IStrategy):
    """
    根據市場狀態自動切換策略
    """
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 基本指標
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        
        # BB
        bb = ta.BBANDS(dataframe["close"], timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe["bb_upper"] = bb["upper"]
        dataframe["bb_middle"] = bb["mid"]
        dataframe["bb_lower"] = bb["lower"]
        dataframe["bb_width"] = (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        ) / dataframe["bb_middle"]
        
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        
        # --- Regime Detection ---
        # 盤整：ADX < 20 且 BB Width < 0.02
        dataframe["regime_choppy"] = (
            (dataframe["adx"] < 20) &
            (dataframe["bb_width"] < 0.02)
        )
        
        # 強趨勢：ADX > 25
        dataframe["regime_trend"] = dataframe["adx"] > 25
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 進場條件 1：均值回歸（盤整市場）---
        cond_mean_reversion = (
            dataframe["regime_choppy"] &
            (dataframe["close"] < dataframe["bb_lower"]) &
            (dataframe["rsi"] < 35)
        )
        
        # --- 進場條件 2：趨勢跟隨（強趨勢市場）---
        cond_trend_follow = (
            dataframe["regime_trend"] &
            (dataframe["plus_di"] > dataframe["minus_di"]) &
            (dataframe["close"] > dataframe["bb_middle"])
        )
        
        # 根據 Regime 選擇進場條件
        dataframe["enter_long"] = np.where(
            dataframe["regime_trend"],
            cond_trend_follow.astype(int),
            cond_mean_reversion.astype(int)
        )
        
        return dataframe
```

---

## 4. Freqtrade 實作方式

### 4.1 使用 @informative decorator 獲取多時間框架資料

```python
from freqtrade.strategy import informative

class StrategyWithMTF(IStrategy):
    timeframe = "5m"
    
    @informative("15m")
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        15m 時間框架指標 - 自動與 5m 數據對齊
        """
        dataframe["ema_200_15m"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi_15m"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe
    
    @informative("1h", "BTC/USDT:USDT")  # 可指定交易對
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        1h 時間框架指標
        """
        dataframe["ema_50_1h"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 本地指標
        dataframe["ema_9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # 5m/15m 趨勢一致 性檢查
        dataframe["trend_aligned"] = (
            (dataframe["close"] > dataframe["ema_200_15m"]) &
            (dataframe["adx"] > 20)
        )
        
        return dataframe
```

### 4.2 在 populate_indicators 中計算 Regime 指標

```python
def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    """
    計算所有趨勢識別指標
    """
    # === ADX 系列 ===
    dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
    dataframe["adx_fast"] = ta.ADX(dataframe, timeperiod=5)
    dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
    dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
    
    # === ATR ===
    dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
    dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
    
    # === Bollinger Bands ===
    bb = ta.BBANDS(dataframe["close"], timeperiod=20, nbdevup=2, nbdevdn=2)
    dataframe["bb_upper"] = bb["upper"]
    dataframe["bb_middle"] = bb["mid"]
    dataframe["bb_lower"] = bb["lower"]
    
    # BB Width（波動率指標）
    dataframe["bb_width"] = (
        dataframe["bb_upper"] - dataframe["bb_lower"]
    ) / dataframe["bb_middle"]
    
    # BB %B（價格位置）
    dataframe["bb_pct"] = (
        dataframe["close"] - dataframe["bb_lower"]
    ) / (dataframe["bb_upper"] - dataframe["bb_lower"])
    
    # === EMA 系列 ===
    dataframe["ema_9"] = ta.EMA(dataframe, timeperiod=9)
    dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
    dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
    dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
    
    # EMA Slope（趨勢方向）
    dataframe["ema_rising"] = dataframe["ema_9"] > dataframe["ema_9"].shift(2)
    
    # === RSI ===
    dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
    
    # === 趨勢強度標記 ===
    dataframe["strong_trend"] = dataframe["adx"] > 25
    dataframe["weak_trend"] = dataframe["adx"] < 20
    
    # === 進場方向 ===
    dataframe["bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
    dataframe["bearish"] = dataframe["minus_di"] > dataframe["plus_di"]
    
    return dataframe
```

### 4.3 在 populate_entry_trend 中根據 Regime 調整進場條件

```python
def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    """
    根據市場狀態動態調整進場條件
    """
    
    # === 條件 A：均值回歸進場（盤整市場）===
    # 適用於：ADX < 20, BB Width 低
    cond_mr_bb_touch = dataframe["close"] < dataframe["bb_lower"]
    cond_mr_rsi_oversold = dataframe["rsi"] < 35
    cond_mr_volume = dataframe["volume"] > dataframe["volume"].rolling(20).mean() * 0.8
    cond_mr_bullish_candle = dataframe["close"] > dataframe["open"]
    
    entry_mean_reversion = (
        cond_mr_bb_touch &
        cond_mr_rsi_oversold &
        cond_mr_volume &
        cond_mr_bullish_candle
    )
    
    # === 條件 B：趨勢跟隨進場（強趨勢市場）===
    # 適用於：ADX > 25, +DI > -DI
    cond_tf_adx = dataframe["adx"] > 25
    cond_tf_direction = dataframe["plus_di"] > dataframe["minus_di"]
    cond_tf_ema_alignment = (
        (dataframe["ema_9"] > dataframe["ema_21"]) &
        (dataframe["ema_21"] > dataframe["ema_50"])
    )
    cond_tf_above_bb_middle = dataframe["close"] > dataframe["bb_middle"]
    
    entry_trend_follow = (
        cond_tf_adx &
        cond_tf_direction &
        cond_tf_ema_alignment &
        cond_tf_above_bb_middle
    )
    
    # === 條件 C：突破進場（過渡市場，ADX 20-25）===
    # 價格突破 BB 上軌 + 成交量放大
    cond_bo_breakout = dataframe["close"] > dataframe["bb_upper"]
    cond_bo_volume = dataframe["volume"] > dataframe["volume"].rolling(20).mean() * 1.5
    cond_bo_adx_rising = dataframe["adx"] > dataframe["adx"].shift(2)
    
    entry_breakout = (
        cond_bo_breakout &
        cond_bo_volume &
        cond_bo_adx_rising
    )
    
    # === 根據 Regime 選擇進場模式 ===
    dataframe["enter_long"] = np.where(
        dataframe["strong_trend"],
        entry_trend_follow.astype(int),
        np.where(
            dataframe["weak_trend"],
            entry_mean_reversion.astype(int),
            entry_breakout.astype(int)
        )
    )
    
    # 另一種方式：全部開啟，讓 Freqtrade 根據權重選擇
    # dataframe["enter_long"] = (
    #     entry_mean_reversion |
    #     entry_trend_follow |
    #     entry_breakout
    # ).astype(int)
    
    return dataframe
```

---

## 5. 推薦指標組合與閾值

### 5.1 均值回歸策略（盤整市場）

| 指標 | 參數 | 閾值 |
|------|------|------|
| ADX | 14 | < 20 |
| BB Width | 20 | < 0.02 |
| RSI | 14 | < 35 |
| 價格位置 | - | 低於 BB 下軌 |
| 成交量 | 20 MA | > 0.5x MA |

### 5.2 趨勢跟隨策略（強趨勢市場）

| 指標 | 參數 | 閾值 |
|------|------|------|
| ADX | 14 | > 25 |
| +DI vs -DI | 14 | +DI > -DI |
| EMA 排列 | 5/12/21 | 多頭排列 |
| 價格位置 | - | > BB 中軌 |

### 5.3 突破策略（過渡市場）

| 指標 | 參數 | 閾值 |
|------|------|------|
| ADX | 14 | 20-25（上升中） |
| BB Width | 20 | > 0.03（波動放大） |
| 成交量 | 20 MA | > 1.5x MA |
| 價格 | - | 突破 BB 上軌 |

---

## 6. 實際策略範例：動態 Regime 切換

```python
"""
DynamicRegimeStrategy - 動態 Regime 切換策略
==========================================
根據 ADX + BB Width + ATR 自動識別市場狀態並切換策略

Regime 0 (盤整): 均值回歸 - BB 觸及進場
Regime 1 (過渡): 觀望 - 僅突破確認
Regime 2 (趨勢): 趨勢跟隨 - EMA 排列 + ADX 確認
"""

from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class DynamicRegimeStrategy(IStrategy):
    # 基本參數
    timeframe = "5m"
    leverage = 5
    futures_leverage = True
    stoploss = -0.02
    
    minimal_roi = {
        "1": 0.003,
        "3": 0.006,
        "5": 0.010,
        "10": 0.015,
    }
    
    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.004
    trailing_only_offset_is_reached = True
    
    # Regime 參數
    adx_strong_threshold = 25
    adx_weak_threshold = 20
    bb_width_low_threshold = 0.02
    atr_low_threshold = 0.01
    
    @informative("15m")
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_200_15m"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === ADX 系列 ===
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        
        # === ATR ===
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        
        # === Bollinger Bands ===
        bb = ta.BBANDS(dataframe["close"], timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe["bb_upper"] = bb["upper"]
        dataframe["bb_middle"] = bb["mid"]
        dataframe["bb_lower"] = bb["lower"]
        dataframe["bb_width"] = (bb["upper"] - bb["lower"]) / bb["mid"]
        
        # === EMA ===
        dataframe["ema_9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        
        # === RSI ===
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        
        # === Regime 分類 ===
        dataframe["regime_strong"] = (
            (dataframe["adx"] > self.adx_strong_threshold) &
            (dataframe["bb_width"] > self.bb_width_low_threshold)
        )
        dataframe["regime_choppy"] = (
            (dataframe["adx"] < self.adx_weak_threshold) &
            (dataframe["bb_width"] < self.bb_width_low_threshold)
        )
        
        # === 方向 ===
        dataframe["bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Regime 2: 強趨勢 - 趨勢跟隨
        entry_trend = (
            dataframe["regime_strong"] &
            dataframe["bullish"] &
            (dataframe["ema_9"] > dataframe["ema_21"]) &
            (dataframe["close"] > dataframe["bb_middle"])
        )
        
        # Regime 0: 盤整 - 均值回歸
        entry_meanrev = (
            dataframe["regime_choppy"] &
            (dataframe["close"] < dataframe["bb_lower"]) &
            (dataframe["rsi"] < 35) &
            (dataframe["close"] > dataframe["open"])
        )
        
        # 根據 Regime 選擇
        dataframe["enter_long"] = np.where(
            dataframe["regime_strong"],
            entry_trend.astype(int),
            entry_meanrev.astype(int)
        )
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe
```

---

## 7. 結論與建議

### 7.1 關鍵發現

1. **ADX 是核心趨勢強度指標**：ADX > 25 確認趨勢存在，ADX < 20 確認盤整
2. **+DI/-DI 交叉提供方向**：比 ADX 本身更適合判斷進場方向
3. **BB Width 補充波動率資訊**：ADX 高的同時需確認波動率不是極低
4. **多時間框架確認至關重要**：15m/1h 的 EMA200 位置是關鍵結構過濾

### 7.2 實務建議

- **不要依賴單一指紋**：組合 ADX + BB Width + ATR + EMA 排列
- **Regime 切換需緩衝區**：避免在 ADX 20-25 臨界區頻繁切換
- **回測各 regime 獨立表現**：確認策略在每個市場狀態下的期望值
- **考慮暫停機制**：連續虧損時自動降低交易頻率

---

*研究完成時間：2026-04-27*
*資料來源：Freqtrade 策略庫、實測日誌、Talib 指標文件*
