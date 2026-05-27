# 策略失敗深度分析報告

## 執行摘要

| 策略 | 時間軸 | 勝率 | 總 ROI | 核心問題 |
|------|--------|------|--------|----------|
| BinHV45_Contract | 1m | N/A (0 交易) | N/A | 進場條件過於嚴格，BB 週期過長 |
| Modified_EMA_Scalp | 5m | 68.9% | -26.63% | 止損過寬 + ROI 分配失當，風險報酬比劣 |
| BiDirectional_BB_Scalp | 5m | 27.1% | -31.18% | 進場條件矛盾 + ATR 動態止損過寬 |

---

## 1. BinHV45_Contract — 零交易根本原因分析

### 1.1 進場邏輯解構

**原始碼第 104-118 行（進場條件）：**

```python
# Long entry (第 104-109 行)
long_conditions = (
    qtpylib.crossed_below(dataframe["close"], dataframe["bb_lowerband"])  # 條件 A
    & (dataframe["bb_delta"] > self.buy_bbdelta / 10000)                   # 條件 B: 0.0007
    & (dataframe["closedelta"] > self.buy_closedelta / 10000)              # 條件 C: 0.0017
    & (dataframe["tail"] < self.buy_tail / 100)                            # 條件 D: 0.25
)
```

**四個 AND 條件的邏輯衝突：**

| 條件 | 含義 | 隱含含義 |
|------|------|----------|
| A: `crossed_below(close, bb_lower)` | 價格由上往下穿越下軌 | 價格正在**下跌** |
| B: `bb_delta > 0.0007` | BB 通道寬度足夠 | 波動率門檻（合理） |
| C: `closedelta > 0.0017` | 收盤價相較前根上漲 >0.17% | 價格正在**上漲** ❌ |
| D: `tail < 0.25` | 收盤價位於 BB 通道下象限 | 價格**低** ❌ |

**核心矛盾：條件 A + C + D 同時滿足不可能發生**

- `crossed_below(close, bb_lower)` = 價格正在向下突破下軌
- `closedelta > 0.0017` = 價格相較前一根 K 線上涨
- `tail < 0.25` = 收盤價接近下軌

這三者在物理意義上互相排斥。要同時滿足「價格向下穿越下軌」且「收盤價相對前一根上漲」，在正常市場行情下幾乎不可能。

### 1.2 BB 週期過長問題

- **BB 參數：window=40, stds=2**（第 70 行）
- 在 **1m 時間軸**上，相當於使用**過去 40 分鐘的數據**計算布林帶
- 40 期 BB 在 1m 框架下極度落後，價格很少戲劇性地「接觸」下軌後再滿足其他delta 條件
- **Short 側條件同樣存在類似矛盾**：`closedelta < -0.0017`（下跌）但價格向上穿越上軌

### 1.3 修復建議

**修改 `populate_entry_trend` 方法（第 97-124 行）：**

```python
# === 方案 A：移除矛盾條件，收緊進場時機 ===
def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    # Long entry: 價格接觸下軌 + 足夠波動率 + RS
```

對於 Long 端，移除 `closedelta > 0` 這個衝突的條件。當價格接觸布林帶下軌時，delta 應該是負值，這與上漲的 closedelta 要求相矛盾。保留 BB 寬度和 RSI 過濾就足夠了。

Short 端也面臨類似的問題——當價格接觸上軌時，closedelta 的正負要求與實際價格運動方向不符。

我需要移除這個衝突的條件，並且將布林帶週期從 40 縮短到 15-20，這樣在 1m 圖表上能更快地反映價格變化。同時應該用 `crossed` 來判斷真正的突破，而不是簡單的接觸。

另外，tail 參數的閾值設為 25% 太寬鬆了，這會導致進場時機過早。

---

## 2. Modified_EMA_Scalp — 高勝率卻虧損的根本原因

### 2.1 數據驗證

| 指標 | 數值 |
|------|------|
| 勝率 | 68.9% |
| 總 ROI | -26.63% |
| 期望值 | 0.689 × avg_win + 0.311 × avg_loss < 0 |

**推算平均獲利與虧損：**
假設每筆交易風險金額相同（`R`）：
- 68.9% 勝率的交易平均獲利：`W`
- 31.1% 勝率的交易平均虧損：`L`

總 ROI = 68.9% × (W/R) - 31.1% × (L/R) = -0.2663

假設平均止損觸發 = -3%（stoploss），則：
- 68.9% × avg_win - 31.1% × 0.03 = -0.2663
- 68.9% × avg_win = -0.2663 + 0.00933 = -0.257
- **avg_win ≈ -0.373 ≈ -37.3%**（不可能）

結論：**勝率報告有誤，或平均獲利遠低於 ROI 設定（2%），多數贏的交易在觸發 2% ROI 前就回撤了**。

### 2.2 ROI 與止損的根本衝突

**原始碼設定：**
```python
# 第 40-43 行
minimal_roi = {
    "0": 0.02,     # 進場後立即 2% 就離場
    "30": 0.01,    # 30 分鐘後 1% 就離場
}
stoploss = -0.03   # 3% 止損
```

**5x 槓桿下的損益放大：**

| 事件 | 帳戶層面影響 |
|------|-------------|
| 觸發 2% ROI（5x） | +10% 帳戶獲利 |
| 觸發 3% 止損（5x） | -15% 帳戶虧損 |
| **比例** | 止損殺傷力是 ROI 的 **1.5 倍** |

**問題關鍵：**
- 高勝率掩蓋了「贏時賺不夠，輸時亏太多」的結構性缺陷
- `minimal_roi` 設計不良：0 分鐘就 2% ROI 太激進，大部分贏單根本吃不到
- 30 分鐘後 1% ROI = 5% 帳戶收益，仍可觀，但行情往往在抵達前就反轉

### 2.3 進場邏輯分析

```python
# 第 86-90 行
dataframe["enter_long"] = (
    (dataframe["close"] < dataframe["bb_lowerband"])  # 價格低於下軌
    & (dataframe["rsi"] < 30)                           # RSI 超賣
    & (dataframe["adx"] > 20)                           # ADX > 20（趨勢強度）
)
```

**矛盾點：**
- ADX > 20 表示**有趨勢**，但布林帶均值回歸策略**假設價格會回歸均線**
- 強趨勢市場中（ADX > 20），價格沿 BB 下軌持續走低而不反彈
- RSI < 30 與 ADX > 20 的組合：在下跌趨勢中常同時出現，意昧著**順勢做空**而非逆勢抄底

### 2.4 修復建議

**方案 A：調整 ROI 表格（推薦）**

修改 `minimal_roi`（第 40-43 行）：

```python
minimal_roi = {
    "0": 0.005,    # 0.5% - 快速入場，鎖住部分利潤
    "20": 0.015,   # 1.5% - 第二目標
    "60": 0.025,   # 2.5% - 主要目標
}
```

**方案 B：加入追蹤止損（Trailing Stop）**

在 `custom_stoploss` 中加入：

```python
def custom_stoploss(self, pair, trade, current_time, current_rate,
                    current_profit, after_fill, **kwargs) -> float:
    # 浮動止損：利潤 > 1% 後，止損線提高到成本價
    if current_profit > 0.01:
        return -0.005  # 鎖住至少 0.5% 利潤
    return self.stoploss  # 否則用預設 3% 止損
```

**方案 C：移除或降低 ADX 條件（改為參數）**

ADX > 20 在強趨勢市場中與均值回歸假設衝突。考慮：
- 降低 ADX 閾值至 15，或
- 完全移除 ADX 條件，改用其他震盪指標

---

## 3. BiDirectional_BB_Scalp — 低勝率與虧損的根本原因

### 3.1 進場邏輯的致命缺陷

**原始碼第 119-136 行：**

```python
# Long entry conditions (第 119-126 行)
long_conditions = qtpylib.crossed_below(
    dataframe["close"],
    dataframe["bb_lowerband"] * self.bb_long_threshold.value,  # 0.99
) | (
    (dataframe["close"] < dataframe["bb_lowerband"] * self.bb_long_threshold.value)
    & (dataframe["rsi"] < self.rsi_long_threshold.value)       # 35
    & (dataframe["volume"] > dataframe["volume_ma"])
)
```

**OR 邏輯導致第一個條件形同虛設：**

- 分支 A：`crossed_below(close, 0.99 × bb_lower)`
- 分支 B：`close < 0.99 × bb_lower` AND `rsi < 35` AND `volume > ma`

當分支 A 觸發（價格向下穿越下軌的 99% 位置），**同時也滿足分支 B 的第一個子條件**（因為 `crossed_below` 本身就蘊含價格已低於閾值）。這使得分支 B 的其餘條件（RSI + Volume）成為實質上的唯一進場標準，分支 A 完全被稀釋。

實質 Long 進場條件簡化為：
```
close < 0.99 × bb_lower AND rsi < 35 AND volume > ma
```

### 3.2 RSI 閾值矛盾

| 方向 | 參數設定 | 常見超買/超賣區 | 問題 |
|------|----------|----------------|------|
| Long RSI 閾值 | 預設 35（範圍 25-40）| 超賣通常 < 30 | 35 過於接近，進場太早 |
| Short RSI 閾值 | 預設 65（範圍 60-75）| 超買通常 > 70 | 65 過於接近，進場太早 |

**Long 進場需要 RSI < 35，但超賣標準是 < 30**，這意味策略在 RSI = 34 就進場，而真正的超賣反彈往往在 RSI < 30 才發生。

### 3.3 ATR 動態止損過寬

**原始碼第 175-176 行：**

```python
stoploss_distance = (atr * self.atr_multiplier.value) / current_rate
return -stoploss_distance
```

- ATR 預設週期 14，倍數 2.0
- 在 5m 圖表上，ATR(14) 代表過去 70 分鐘的平均真範圍
- 計算：假設比特幣價格 $50,000，ATR = $200（4%）
  - 止損距離 = $200 × 2 / $50,000 = 0.008 = **0.8%**

問題：
1. **市場波動大時 ATR 止損被動拉寬**，失去保護作用
2. 5% 是**最大止損（stoploss = -0.05）**，但 ATR 動態止損override了它
3. 止損設在 -0.8% 但 ROI 目標 3%，**報酬風險比僅 3.75:1 看起來不錯，但 ATR 過寬導致平均虧損擴大**

### 3.4 修復建議

**修改進場邏輯（`populate_entry_trend`，第 107-141 行）：**

```python
# 移除 OR 邏輯，用 crossed 確保真正的穿越事件
long_conditions = (
    qtpylib.crossed_below(
        dataframe["close"],
        dataframe["bb_lowerband"] * self.bb_long_threshold.value,
    )
    & (dataframe["rsi"] < self.rsi_long_threshold.value)
    & (dataframe["volume"] > dataframe["volume_ma"])
)

short_conditions = (
    qtpylib.crossed_above(
        dataframe["close"],
        dataframe["bb_upperband"] * self.bb_short_threshold.value,
    )
    & (dataframe["rsi"] > self.rsi_short_threshold.value)
    & (dataframe["volume"] > dataframe["volume_ma"])
)
```

**修改 ATR 止損倍數（`custom_stoploss`，第 153-176 行）：**

```python
# 將 ATR 倍數從 2.0 降低至 1.0-1.5
stoploss_distance = (atr * 1.0) / current_rate  # 從 2.0 改為 1.0
return -stoploss_distance
```

**或完全移除 ATR 動態止損，改用固定止損：**

```python
# 在 custom_stoploss 中
return self.stoploss  # 回覆使用 -0.05 固定止損
```

**調整 RSI 閾值參數（預設值）：**

```python
# 第 48-49 行
rsi_long_threshold = IntParameter(25, 35, default=30, space="buy")    # 從 35 改為 30
rsi_short_threshold = IntParameter(65, 75, default=70, space="sell")  # 從 65 改為 70
```

**加入趨勢濾網：**

```python
# 在 populate_indicators 中加入 MA 趨勢判斷
dataframe["sma_50"] = ta.SMA(dataframe["close"], timeperiod=50)

# 在進場條件中加入
# Long: 額外要求 close > SMA_50（多頭市場）
# Short: 額外要求 close < SMA_50（空頭市場）
```

---

## 4. 綜合風險報酬比分析

| 策略 | 勝率 | Avg Win / R | Avg Loss / R | R:R 比率 | 期望值（/R）|
|------|------|-------------|--------------|----------|------------|
| BinHV45_Contract | N/A | N/A | N/A | N/A | 0 (無交易) |
| Modified_EMA_Scalp | 68.9% | ~0.4% | 3% | ~0.13:1 | **負** |
| BiDirectional_BB_Scalp | 27.1% | 3% | ~0.8% | ~3.75:1 | **仍為負** |

> **Modified_EMA_Scalp 問題最嚴重**：即使 3.75:1 的 R:R（平均贏是平均虧的 3.75 倍），27.1% 勝率仍不足以覆蓋交易成本和市場微結構摩擦。

---

## 5. 行動優先順序

| 優先級 | 策略 | 修復動作 | 預期效果 |
|--------|------|----------|----------|
| 🔴 P0 | BinHV45_Contract | 移除矛盾條件 + 縮短 BB 週期至 15 | 恢復交易信號 |
| 🔴 P0 | Modified_EMA_Scalp | 加入追蹤止損 + 降低 ROI 期望 | 止損殺傷力減半 |
| 🟡 P1 | BiDirectional_BB_Scalp | 修復 OR 邏輯 + 收緊 ATR 倍數 | 提升勝率至 35%+ |
| 🟡 P1 | BiDirectional_BB_Scalp | 調整 RSI 閾值至經典超買/超賣區 | 進場時機更精確 |
