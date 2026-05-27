# Freqtrade 趨勢跟隨策略分析報告

**研究日期**: 2026-04-27  
**目標**: 分析 15m/1h 時間框架的趨勢跟隨策略，特別針對 futures 模式

---

## 1. 執行摘要

### 1.1 市場背景
2025 年 1-4 月加密貨幣市場呈現明顯強趨勢行情：
- BTC 从约 $40,000 上涨至约 $70,000，涨幅超过 75%
- 典型的趋势市场环境

### 1.2 核心發現
| 問題 | 說明 |
|------|------|
| 均值回歸失效 | 逆勢操作导致连续止损 |
| 高勝率不等於盈利 | EMA+ADX 組合 72% 勝率仍虧損 84% |
| 風險報酬失衡 | 平均虧損遠大於平均獲利 |

---

## 2. 主要趨勢跟隨策略分析

### 2.1 Scalp_ADX_Only（單指標測試）

**時間框架**: 5m  
**模式**: Futures (Long only)

**進場條件**:
```
1. ADX > 25 (主指標閾值)
2. ADX_fast > 30 (快速確認)
3. +DI > -DI (多頭方向)
4. ADX 正在上升
```

**出場條件**: Trailing stop + ATR stop

**優點**:
- 隔離測試 ADX 指標有效性
- 邏輯簡潔，易於優化

**缺點**:
- 缺少趨勢方向確認
- 單一指標準確度有限

---

### 2.2 Scalp_EMA_RSI_ADX_Combo（三指標組合）

**時間框架**: 5m  
**模式**: Futures

**進場條件**:
```
1. EMA 多頭排列: EMA5 > EMA12 > EMA20
2. RSI 在 35-65 範圍
3. ADX > 25 + ADX 上升 + +DI > -DI
```

**出場條件**:
- RSI > 70 (過熱)
- ADX < 20 (趨勢減弱)

**風險設定**:
```python
stoploss = -0.02
trailing_stop_positive = 0.002
trailing_stop_positive_offset = 0.004
```

**問題診斷**:
- 三個指標必須同時滿足條件，信號數量過少
- 5m 框架噪音過多，不適合趨勢策略

---

### 2.3 ScalpOpt_EMA_ADX_Combo（信號評分系統）

**時間框架**: 5m  
**模式**: Futures (Long only)

**進場條件**:
```python
# 信號評分機制
signal_quality = (
    (ema_bullish) * 0.35 +           # EMA 多頭排列
    (adx > 25) * 0.25 +              # ADX 強度
    (+DI > -DI) * 0.15 +             # 方向
    (RSI 40-70) * 0.10 +             # RSI 健康範圍
    (volume_ratio > 1.0) * 0.10 +    # 量能異常
    (above_ema200) * 0.05             # 長期趨勢
)

# 進場: 評分 >= 0.35
```

**回測結果 (2025-01-01 ~ 2026-04-26)**:
| 指標 | 數值 |
|------|------|
| 總交易次數 | 5,653 |
| 勝率 | 72.1% |
| 總盈虧 | **-84.64%** |
| 起始資金 | 10,000 USDT |
| 最終資金 | 1,536.15 USDT |

**關鍵問題**:
1. **止損過大**: 139 筆止損交易平均虧損 10.11%
2. **進場信號過多**: 5,653 筆，需更嚴格過濾
3. **Trailing Stop 唯一獲利**: +13,002 USDT

---

### 2.4 Scalp_Breakout（突破策略）

**時間框架**: 5m  
**模式**: Futures (Long/Short)

**進場條件**:
```
多頭進場:
- 價格突破前 20 根 K 線最高點
- 成交量 > SMA(20) 量能

空頭進場:
- 價格跌破前 20 根 K 線最低點
- 成交量放大確認
```

**出场條件**:
- 價格跌破前 10 根 K 線最低點
- +1% 止盈

**風險設定**:
```python
stoploss = -0.005  # -0.5%
minimal_roi = {"0": 0.01}  # 1% 止盈
```

**優點**:
- 固定止損止盈，風險可控
- 雙向交易捕捉趨勢

**缺點**:
- 假突破過多
- 5m 框架頻繁被掃

---

### 2.5 ML_Supertrend_Aslan（Supertrend 策略）

**時間框架**: 1h ⭐  
**模式**: Futures (Long/Short)

**核心邏輯**:

#### Reversal Mode（反轉模式）:
```
進場: Supertrend 方向從 -1 變為 1
出場: Supertrend 方向從 1 變為 -1
```

#### Breakout Mode（突破模式）:
```
進場: 價格突破趨勢高點（在上升趨勢中）
出场: 價格跌破趨勢低點（在下降趨勢中）
```

**可選過濾器**:
- RSI 動量過濾
- 成交量確認

**關鍵參數**:
```python
st_atr_multiplier = 1.4  # ATR 倍數
st_atr_period = 30       # ATR 期間
stoploss = -0.10         # -10%
take_profit_pct = 0.15   # 15% 止盈
tp_sl_ratio = 1.5        # TP/SL 比
```

**優點**:
- 1h 時間框架更適合趨勢捕捉
- ATR 自適應止損
- 支援 Reversal 和 Breakout 兩種模式

**缺點**:
- -10% 止損過大
- 參數優化空間大

---

### 2.6 ArcVWAPSupertrend（VWAP + Supertrend）

**時間框架**: 15m ⭐  
**模式**: Futures (Long only)

**來源**: TradingView Pine Script 轉換

**核心邏輯**:
```
1. Arc Engine: 基於 ATR 的動態趨勢追蹤線
2. VWAP 確認: 價格在 VWAP 同側確認趨勢
3. 突破進場: 價格穿越 Arc + VWAP 確認
```

**優點**:
- 15m 框架平衡了敏感度和可靠性
- VWAP 多時間框架確認
- Arc 速度自適應

**缺點**:
- 僅做多，無法做空
- 邏輯複雜，最佳化難度高

---

## 3. 關鍵指標分析

### 3.1 ADX 閾值參考

| ADX 值 | 市場狀態 | 交易建議 |
|--------|----------|----------|
| ADX < 20 | 盤整/無趨勢 | 均值回歸，避免趨勢跟隨 |
| ADX 20-25 | 過渡區域 | 觀望或輕量測試 |
| **ADX > 25** | **強趨勢** | **趨勢跟隨入場** ✅ |
| ADX > 40 | 極強趨勢 | 謹慎反向入場，高反轉風險 |

### 3.2 EMA 組合推薦

| 組合 | 用途 | 適用場景 |
|------|------|----------|
| EMA 5/12/20 | 短期趨勢 | 15m/1h 剝头皮 |
| EMA 12/26 | 標準 MACD | 中期趨勢 |
| EMA 9/21 | 較敏感 | 短期交易 |
| EMA 50/200 | 長期結構 | 方向確認 |

### 3.3 進場/出廠條件速查表

| 條件類型 | 多頭進場 | 空頭進場 | 多頭出廠 | 空頭出廠 |
|----------|----------|----------|----------|----------|
| EMA | fast > slow | fast < slow | - | - |
| ADX | > 25 | > 25 | < 20 | < 20 |
| +DI vs -DI | +DI > -DI | -DI > +DI | - | - |
| RSI | 35-65 | 35-65 | > 70 | < 30 |
| Supertrend | direction=1 | direction=-1 | direction=-1 | direction=1 |

---

## 4. 15m/1h 時間框架策略推薦

### 4.1 推薦策略 #1: ML_Supertrend_Aslan（修改版）

**時間框架**: 1h  
**模式**: Futures Long/Short

**修改建議**:
```python
# 調整後的參數
timeframe = '1h'
st_atr_multiplier = 2.0  # 從 1.4 提高到 2.0，減少假信號
st_atr_period = 20       # 從 30 降低到 20，更敏感
stoploss = -0.05         # 從 -0.10 降低到 -5%
take_profit_pct = 0.10   # 從 0.15 降低到 10%
signal_mode = 'reversal' # 使用反轉模式

# 加入 ADX 過濾
use_adx_filter = True
adx_threshold = 25
```

**進場條件**:
```
1. Supertrend 反轉向上 (direction: -1 → 1)
2. ADX > 25 (趨勢強度確認)
3. +DI > -DI (方向確認)
4. RSI < 70 (非過熱)
```

**出场條件**:
```
1. Supertrend 反轉向下 (direction: 1 → -1)
2. 或 RSI > 75 (過熱止盈)
3. 或 ADX < 20 (趨勢結束)
```

---

### 4.2 推薦策略 #2: ArcVWAPSupertrend（修改版）

**時間框架**: 15m  
**模式**: Futures Long/Short（修改後）

**修改建議**:
```python
# 開啟空頭交易
can_short = True

# 調整止損
stoploss = -0.05  # 從 -0.10 降低

# 加入 ADX 確認
use_adx_confirm = True
adx_threshold = 25
```

**進場條件**:
```
1. 確認的 Bullish Flip (flip_confirmed == True)
2. Trend == 1 (上升趨勢)
3. ADX > 25 (可選)
```

---

### 4.3 推薦策略 #3: 純 ADX + EMA 組合（簡化版）

**時間框架**: 15m  
**模式**: Futures Long/Short

**進場條件**:
```python
# 多頭進場
cond_long = (
    (dataframe['ema_fast'] > dataframe['ema_slow']) &  # EMA 多頭排列
    (dataframe['adx'] > 25) &                          # 趨勢強度
    (dataframe['plus_di'] > dataframe['minus_di']) &   # 方向
    (dataframe['adx'] > dataframe['adx'].shift(1))     # ADX 上升
)

# 空頭進場
cond_short = (
    (dataframe['ema_fast'] < dataframe['ema_slow']) &  # EMA 空頭排列
    (dataframe['adx'] > 25) &                          # 趨勢強度
    (dataframe['minus_di'] > dataframe['plus_di']) &   # 方向
    (dataframe['adx'] > dataframe['adx'].shift(1))     # ADX 上升
)
```

**风险設定**:
```python
stoploss = -0.03
trailing_stop = True
trailing_stop_positive = 0.005
trailing_stop_positive_offset = 0.015
trailing_only_offset_is_reached = True
leverage = 5
```

---

## 5. 2025 年趨勢市場適用性評估

### 5.1 為何 2025 年需要趨勢跟隨策略

| 時間段 | 市場狀態 | ADX | 適合策略 |
|--------|----------|-----|----------|
| 2025 Q1 | BTC 強趨勢上漲 | > 30 | 趨勢跟隨 |
| 2025 Q2 | 可能的回調 | 25-30 | 混合策略 |
| 當前 | 等待確認 | ? | 觀望 |

### 5.2 策略選擇框架

```
                    ADX 判斷
                        │
            ┌───────────┴───────────┐
            │                       │
        ADX > 25                ADX < 25
            │                       │
        趨勢市場                  盤整市場
            │                       │
    ┌───────┴───────┐       ┌───────┴───────┐
    │               │       │               │
 多頭趨勢      空頭趨勢    均值回歸      觀望
(enter_long) (enter_short) (BB RSI)   (no trade)
```

### 5.3 風險管理要點

1. **止損設置**: 不超過 -5%（建議 -3%）
2. **Trailing Stop**: 必要功能，鎖住利潤
3. **槓桿控制**: 5x 適合趨勢行情
4. **ADX 過濾**: 只在 ADX > 25 時進場

---

## 6. 最佳策略推薦總結

### 6.1 針對 15m 時間框架

| 排名 | 策略名稱 | 評分 | 理由 |
|------|----------|------|------|
| 1 | ArcVWAPSupertrend | ⭐⭐⭐⭐⭐ | VWAP 確認減少假信號，15m 完美適配 |
| 2 | Scalp_15m_EMA_RSI | ⭐⭐⭐⭐ | 簡潔有效，EMA 多頭排列確認 |
| 3 | ML_Supertrend_Aslan (Breakout) | ⭐⭐⭐ | Supertrend 自動追蹤 |

### 6.2 針對 1h 時間框架

| 排名 | 策略名稱 | 評分 | 理由 |
|------|----------|------|------|
| 1 | ML_Supertrend_Aslan (Reversal) | ⭐⭐⭐⭐⭐ | 1h 框架最佳，趨勢自動追蹤 |
| 2 | EMA + ADX 組合 | ⭐⭐⭐⭐ |經典組合，1h 更穩定 |

### 6.3 關鍵參數優化建議

```python
# 趨勢跟隨策略標準參數
stoploss = -0.03              # -3% 止損
trailing_stop = True
trailing_stop_positive = 0.005  # 0.5% trailing
trailing_stop_positive_offset = 0.015  # 1.5% 觸發
leverage = 5                  # 5x 槓桿
adx_threshold = 25            # ADX 閾值
minimal_roi = {
    "0": 0.005,    # 0.5%
    "3": 0.010,    # 1%
    "6": 0.015,    # 1.5%
}
```

---

## 7. 下一步行動建議

1. **回測驗證**: 使用 2025 年 1-4 月數據回測修改後的 ML_Supertrend_Aslan
2. **參數優化**: 針對 15m/1h 框架優化 ADX 閾值和 EMA 參數
3. **Short 端測試**: 實現空頭交易，捕捉下跌趨勢
4. **市場 Regime 檢測**: 根據 ADX 動態切換趨勢/均值回歸策略

---

*報告完成*
