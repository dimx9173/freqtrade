# 趨勢跟隨策略 (Trend Following) 研究報告

## 1. 為何均值回歸在 2025 年 1-4 月失效？

### 1.1 市場背景

2025 年 1-4 月，加密貨幣市場呈現明顯的趨勢行情：
- BTC 從約 $40,000 一路上漲至約 $70,000，漲幅超過 75%
- 這是典型的強趨勢市場環境

### 1.2 均值回歸失效原因

| 問題 | 說明 |
|------|------|
| 逆勢操作 | 均值回歸策略在趨勢市場中持續反向操作，與趨勢對抗 |
| 連續止損 | 每當價格偏離均值時，策略判斷為「超買/超賣」而逆勢進場，但趨勢持續導致連續止損 |
| 來回被扇 | 價格在均值附近來回震盪時，均值回歸策略會反覆進出场，造成大量交易成本 |
| 利潤有限 | 即使抓住小幅回調，整體趨勢行情中卻错过了大幅移動 |

### 1.3 趨勢跟隨 vs 均值回歸

```
                    趨勢市場          盤整市場
均值回歸            ❌ 虧損           ✅ 獲利
趨勢跟隨            ✅ 獲利           ❌ 虧損
```

**核心洞見**：這兩種策略在不同的市場狀態下表現互補，關鍵在於正確識別市場 regime。

---

## 2. 趨勢跟隨策略核心指標

### 2.1 EMA 交叉 (EMA Crossover)

**原理**：快速 EMA 上穿慢速 EMA 為多頭信號，下穿為空頭信號

| 參數組合 | 用途 | 適用場景 |
|----------|------|----------|
| EMA 12/26 | 標準 MACD 配置 | 中期趨勢 |
| EMA 9/21 | 較敏感 | 短期剝头皮 |
| EMA 5/20 | 最敏感 | 極短線交易 |

```python
# EMA 交叉進場條件
dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)

# 多頭：fast > slow
cond_long = dataframe['ema_fast'] > dataframe['ema_slow']

# 空頭：fast < slow
cond_short = dataframe['ema_fast'] < dataframe['ema_slow']
```

### 2.2 MACD Histogram 方向

**原理**：MACD histogram 斜率代表動能方向

| 條件 | 信號 |
|------|------|
| Histogram > 0 且上升 | 多頭動能增強 |
| Histogram < 0 且下降 | 空頭動能增強 |
| Histogram 穿越零線 | 動能轉折 |

```python
# MACD 計算
macd, signal, hist = ta.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
dataframe['macd_histo'] = hist
dataframe['hist_rising'] = dataframe['macd_histo'] > dataframe['macd_histo'].shift(1)

# 多頭：hist > 0 且上升
cond_macd_long = (dataframe['macd_histo'] >= 0) & dataframe['hist_rising']
```

### 2.3 Supertrend 指標

**原理**：以 ATR 為基礎的趨勢判斷指標，自動追蹤趨勢並提供進出场位

```python
def calculate_supertrend(dataframe, atr_period=14, atr_multiplier=3.0):
    atr = ta.ATR(dataframe, timeperiod=atr_period)
    hl2 = (dataframe['high'] + dataframe['low']) / 2
    upper = hl2 + atr_multiplier * atr
    lower = hl2 - atr_multiplier * atr
    
    supertrend = np.zeros(len(dataframe))
    direction = np.zeros(len(dataframe))
    supertrend[0] = lower.iloc[0]
    direction[0] = 1
    
    for i in range(1, len(dataframe)):
        if dataframe.iloc[i]['close'] <= supertrend[i-1]:
            supertrend[i] = upper.iloc[i]
            direction[i] = -1  # 空頭趨勢
        else:
            supertrend[i] = lower.iloc[i]
            direction[i] = 1   # 多頭趨勢
    
    dataframe['supertrend'] = supertrend
    dataframe['supertrend_direction'] = direction
    return dataframe
```

| 信號 | 條件 |
|------|------|
| 多頭進場 | direction 從 -1 變為 1 (supertrend 反轉向上) |
| 空頭進場 | direction 從 1 變為 -1 (supertrend 反轉向下) |
| 多頭出场 | direction 從 1 變為 -1 |
| 空頭出场 | direction 從 -1 變為 1 |

### 2.4 ADX 確認趨勢強度

**ADX (Average Directional Index)**：測量趨勢強度，不考慮方向

| ADX 值 | 市場狀態 |
|--------|----------|
| ADX < 20 | 盤整/無趨勢 |
| ADX 20-25 | 初步趨勢 |
| ADX 25-50 | 強趨勢 ✅ |
| ADX > 50 | 極強趨勢 (可能即將反轉) |

**DI 方向指標**：
- +DI > -DI：多頭趨勢
- -DI > +DI：空頭趨勢

```python
dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=14)
dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=14)

# 多頭趨勢確認
cond_trend_up = (dataframe['adx'] > 25) & (dataframe['plus_di'] > dataframe['minus_di'])

# 空頭趨勢確認
cond_trend_down = (dataframe['adx'] > 25) & (dataframe['minus_di'] > dataframe['plus_di'])
```

---

## 3. 多空雙向趨勢跟隨策略

### 3.1 完整進場條件

#### 多頭進場 (Long Entry)
```
條件組合：
1. 價格 > EMA (確認在上軌移動)
2. ADX > 25 (趨勢強度足夠)
3. +DI > -DI (方向確認多頭)
4. EMA 多頭排列 (可選：ema_fast > ema_slow)
```

#### 空頭進場 (Short Entry)
```
條件組合：
1. 價格 < EMA (確認在下軌移動)
2. ADX > 25 (趨勢強度足夠)
3. -DI > +DI (方向確認空頭)
4. EMA 空頭排列 (可選：ema_fast < ema_slow)
```

### 3.2 Freqtrade 雙向趨勢策略範例

```python
"""
Scalp_TrendFollow_BiDirectional - 趨勢跟隨雙向策略
==================================================
Timeframe: 5m
Mode: Futures (Long/Short)
Leverage: 5x

核心邏輯：
- 多頭：ADX > 25 + +DI > -DI + EMA多頭排列
- 空頭：ADX > 25 + -DI > +DI + EMA空頭排列
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class Scalp_TrendFollow_BiDirectional(IStrategy):

    # === 基本參數 ===
    timeframe = "5m"
    can_short = True  # 關鍵：開啟空頭功能
    leverage = 5
    futures_leverage = True
    stoploss = -0.02
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.006
    trailing_only_offset_is_reached = True

    # ROI
    minimal_roi = {
        "0": 0.004,
        "3": 0.007,
        "6": 0.010,
        "10": 0.015,
    }

    # === 指標參數 ===
    ema_fast_period = 12
    ema_slow_period = 26
    adx_period = 14
    adx_threshold = 25
    atr_period = 14

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=self.ema_fast_period)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.ema_slow_period)
        
        # ADX + DI
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=self.adx_period)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=self.adx_period)
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)
        
        # EMA 排列
        dataframe['ema_bullish'] = dataframe['ema_fast'] > dataframe['ema_slow']
        dataframe['ema_bearish'] = dataframe['ema_fast'] < dataframe['ema_slow']
        
        # ADX 上升確認
        dataframe['adx_rising'] = dataframe['adx'] > dataframe['adx'].shift(1)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        # === 多頭進場條件 ===
        long_conditions = (
            # 1. EMA 多頭排列
            dataframe['ema_bullish'] &
            # 2. ADX > 25 趨勢強度足夠
            (dataframe['adx'] > self.adx_threshold) &
            # 3. +DI > -DI 多頭方向
            (dataframe['plus_di'] > dataframe['minus_di']) &
            # 4. ADX 正在上升
            dataframe['adx_rising']
        )

        # === 空頭進場條件 ===
        short_conditions = (
            # 1. EMA 空頭排列
            dataframe['ema_bearish'] &
            # 2. ADX > 25 趨勢強度足夠
            (dataframe['adx'] > self.adx_threshold) &
            # 3. -DI > +DI 空頭方向
            (dataframe['minus_di'] > dataframe['plus_di']) &
            # 4. ADX 正在上升
            dataframe['adx_rising']
        )

        dataframe.loc[long_conditions, 'enter_long'] = 1
        dataframe.loc[short_conditions, 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        
        # === 多頭出场條件 ===
        # ADX 下降表示趨勢減弱
        exit_long_cond = dataframe['adx'] < 20
        dataframe.loc[exit_long_cond, 'exit_long'] = 1
        
        # === 空頭出场條件 ===
        # ADX 下降表示趨勢減弱
        exit_short_cond = dataframe['adx'] < 20
        dataframe.loc[exit_short_cond, 'exit_short'] = 1
        
        return dataframe

    def custom_stoploss(self, pair: str, trade, entry: float,
                        current_time, current_rate: float,
                        current_profit: float, **kwargs) -> float:
        # ATR 動態止損
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss
        
        atr = dataframe.iloc[-1]['atr']
        stoploss_pct = (atr * 2) / current_rate
        return -stoploss_pct
```

---

## 4. 市場狀態識別與策略切換

### 4.1 Regime 識別方法

```python
def detect_market_regime(self, dataframe: DataFrame) -> str:
    """
    識別市場狀態：'trend' 或 'range'
    使用 ADX + 波動率複合判斷
    """
    adx = dataframe['adx'].iloc[-1]
    atr_pct = dataframe['atr'].iloc[-1] / dataframe['close'].iloc[-1]
    
    # 趨勢市場：ADX > 25 且波動率適中
    if adx > 25 and atr_pct > 0.005 and atr_pct < 0.05:
        return 'trend'
    
    # 盤整市場：ADX < 20 或波動率過低/過高
    return 'range'
```

### 4.2 組合策略架構

```
                    Market Regime Detector
                           |
           ┌───────────────┴───────────────┐
           │                               │
      ADX > 25                         ADX < 25
           │                               │
        趨勢市場                        盤整市場
           │                               │
    ┌──────┴──────┐                 ┌──────┴──────┐
    │             │                 │             │
  多頭趨勢     空頭趨勢           均值回歸      觀望
  (enter_long) (enter_short)     (BB RSI)    (no trade)
```

### 4.3 動態權重混合策略

```python
class HybridTrendMeanReversionStrategy(IStrategy):
    """
    混合策略：根據市場狀態動態調整權重
    """
    
    def calculate_regime_weights(self, dataframe: DataFrame) -> tuple:
        """
        返回 (trend_weight, mean_reversion_weight)
        """
        adx = dataframe['adx'].iloc[-1]
        
        if adx > 30:
            return (0.8, 0.2)   # 強趨勢：主要用趨勢跟隨
        elif adx > 25:
            return (0.6, 0.4)   # 中等趨勢：傾向趨勢跟隨
        elif adx > 20:
            return (0.4, 0.6)   # 輕微趨勢：傾向均值回歸
        else:
            return (0.2, 0.8)   # 盤整：主要用均值回歸
```

---

## 5. 現有策略中的趨勢邏輯分析

### 5.1 Scalp_ADX_Only (單指標測試)

```python
# 進場條件：ADX > 25 + +DI > -DI + ADX 上升
cond_adx_strong = dataframe["adx"] > self.adx_threshold
cond_adx_fast = dataframe["adx_fast"] > self.adx_threshold_fast
cond_uptrend = dataframe["plus_di"] > dataframe["minus_di"]
cond_adx_rising = dataframe["adx_fast"] > dataframe["adx_fast"].shift(1)

enter_long = cond_adx_strong & cond_adx_fast & cond_uptrend & cond_adx_rising
```

### 5.2 Scalp_EMA_RSI_ADX_Combo (三指標組合)

```python
# 多頭條件
cond_ema_trend = (dataframe["ema_fast"] > dataframe["ema_slow"]) & dataframe["ema_rising"]
cond_rsi = (dataframe["rsi"] >= 35) & (dataframe["rsi"] <= 65)
cond_adx = (dataframe["adx"] > 25) & dataframe["adx_rising"] & (dataframe["plus_di"] > dataframe["minus_di"])

enter_long = cond_ema_trend & cond_rsi & cond_adx
```

### 5.3 ScalpOpt_EMA_ADX_Combo (信號評分系統)

```python
# 信號評分機制
dataframe['signal_quality'] = (
    (dataframe['ema_bullish']).astype(float) * 0.35 +
    (dataframe['adx'] > 25).astype(float) * 0.25 +
    (dataframe['plus_di'] > dataframe['minus_di']).astype(float) * 0.15 +
    ((dataframe['rsi'] > 40) & (dataframe['rsi'] < 70)).astype(float) * 0.10 +
    (dataframe['volume_ratio'] > 1.0).astype(float) * 0.10 +
    (dataframe['above_ema200']).astype(float) * 0.05
)

# 進場：評分 >= 閾值
(dataframe['signal_quality'] >= self.buy_signal_strength.value)
```

---

## 6. 參數建議總結

### 6.1 趨勢跟隨策略推薦參數

| 指標 | 參數 | 建議值 | 說明 |
|------|------|--------|------|
| EMA Fast | period | 12 | 快速均線 |
| EMA Slow | period | 26 | 慢速均線 |
| ADX | period | 14 | 標準 |
| ADX | threshold | 25 | 確認趨勢強度 |
| ATR | period | 14 | 標準 |
| ATR Multiplier | stoploss | 2.0x | 止損距離 |
| Trailing Stop | positive | 0.003 | 3% trailing |
| Trailing Offset | offset | 0.006 | 6% 觸發 |

### 6.2 進場/出場條件速查表

| 條件類型 | 多頭進場 | 空頭進場 | 多頭出场 | 空頭出场 |
|----------|----------|----------|----------|----------|
| EMA | fast > slow | fast < slow | - | - |
| ADX | > 25 | > 25 | < 20 | < 20 |
| +DI vs -DI | +DI > -DI | -DI > +DI | - | - |
| MACD Hist | > 0 且上升 | < 0 且下降 | 轉負 | 轉正 |

### 6.3 Freqtrade 關鍵設定

```python
# 開啟空頭交易
can_short = True

# 期貨槓桿
leverage = 5
futures_leverage = True

# 止損
stoploss = -0.02  # -2%

# Trailing stop
trailing_stop = True
trailing_stop_positive = 0.003
trailing_stop_positive_offset = 0.006
trailing_only_offset_is_reached = True
```

---

## 7. 結論與建議

### 7.1 核心洞見

1. **均值回歸與趨勢跟隨互補**：在不同市場狀態下表現相反
2. **2025 年 1-4 月行情**：明顯的強趨勢市場，均值回歸策略容易受損
3. **ADX 是關鍵指標**：作為市場 regime 的判斷標準

### 7.2 策略選擇建議

| 市場狀態 | ADX 判斷 | 推薦策略 |
|----------|----------|----------|
| 強趨勢 | ADX > 30 | 純趨勢跟隨 |
| 中等趨勢 | ADX 25-30 | 趨勢跟隨為主，均值回歸為輔 |
| 輕微趨勢 | ADX 20-25 | 均衡混合 |
| 盤整 | ADX < 20 | 均值回歸為主或觀望 |

### 7.3 下一步行動

1. **回測驗證**：使用 2025 年 1-4 月數據回測純趨勢跟隨策略
2. **Regime 切換**：實現自動市場狀態識別與策略切換
3. **Short 端優化**：空頭進场條件需要更嚴格（避免被軋空）

---

*研究日期：2026-04-27*
