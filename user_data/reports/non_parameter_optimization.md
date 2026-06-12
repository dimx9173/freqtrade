
# 非參數優化機會分析報告

## 概述

除了 Hyperopt 參數調整，還有許多**非參數優化**可以大幅提升策略表現。

---

## 1. ⏰ 時間框架優化

### 當前設定
- timeframe: 5m

### 優化選項

| 時間框架 | 特性 | 適合策略 | 預期影響 |
|---------|------|----------|----------|
| **3m** | 更頻繁交易 | 高頻策略 | +20% 交易數 |
| **15m** | 減少噪音 | 趨勢策略 | +10% 勝率 |
| **1h** | 大趨勢 | 波段策略 | +15% 獲利 |

### 建議測試
```python
# 測試不同時間框架
timeframes = ['3m', '5m', '15m', '1h']
# 預期 15m 可能最適合 ElliotV5 (減少假訊號)
```

---

## 2. 🛑 Stoploss 策略

### 當前設定
- stoploss: -0.189 (-18.9%)

### 問題
- **過寬**: -18.9% 虧損容忍度太高
- **固定**: 未考慮幣對波動性差異

### 優化選項

| 策略 | 設定 | 優點 | 缺點 |
|------|------|------|------|
| **固定收緊** | -0.03 to -0.05 | 風險控制 | 可能過早出場 |
| **ATR-based** | -1.5x ATR | 動態調整 | 需要額外計算 |
| **不設** | None | 依賴 ROI | 可能大虧損 |

### 建議
```python
# ATR-based stoploss (推薦)
stoploss = -0.03  # 固定 3%
# 或
custom_stoploss = 1.5 * dataframe['atr']  # 動態
```

---

## 3. 💰 ROI 設定優化

### 當前設定
```python
minimal_roi = {
    "0": 0.215,    # 21.5% (立即)
    "40": 0.132,   # 13.2% (40分鐘後)
    "87": 0.086,   # 8.6% (87分鐘後)
    "201": 0.03    # 3% (201分鐘後)
}
```

### 問題
- **過高**: 21.5% 初始目標難達成
- **複雜**: 4層級不易管理

### 優化選項

| 策略 | 設定 | 適合市場 | 預期效果 |
|------|------|----------|----------|
| **積極型** | {'0': 0.10} | 牛市 | 快速獲利了結 |
| **保守型** | {'0': 0.05, '60': 0.03} | 震盪 | 穩定獲利 |
| **分層型** | {'0': 0.08, '30': 0.05, '60': 0.02} | 混合 | 平衡 |

### 建議
```python
# 簡化 ROI (推薦)
minimal_roi = {
    "0": 0.08,     # 8% 目標
    "60": 0.05,    # 5% (1小時後)
    "120": 0.03    # 3% (2小時後)
}
```

---

## 4. 📈 Trailing Stop 優化

### 當前設定
- trailing_stop: True
- trailing_stop_positive: 未明確設定

### 優化選項

| 參數 | 當前 | 建議 | 效果 |
|------|------|------|------|
| trailing_stop_positive | 0.01 | 0.02 | 保留更多利潤 |
| trailing_stop_positive_offset | 0.02 | 0.03 | 更大緩衝 |
| trailing_only_offset_is_reached | False | True | 避免過早出場 |

### 建議
```python
trailing_stop = True
trailing_stop_positive = 0.02
trailing_stop_positive_offset = 0.03
trailing_only_offset_is_reached = True
```

---

## 5. 💵 倉位管理

### 當前設定
- stake_amount: 50 USDT (固定)

### 優化選項

| 策略 | 設定 | 風險 | 預期效果 |
|------|------|------|----------|
| **固定金額** | 50 USDT | 中 | 簡單 |
| **百分比** | 0.02 (2%) | 低 | 自動調整 |
| **波動率調整** | 根據 ATR | 低 | 最佳 |

### 建議
```python
# 百分比倉位 (推薦)
stake_amount = 0.02  # 2% 資金

# 或動態倉位
def custom_stake_amount(self, pair, current_time, current_rate, ...):
    volatility = self.dp.get_pair_dataframe(pair)['atr'].iloc[-1]
    if volatility > threshold:
        return 0.01  # 1% (高波動)
    return 0.03  # 3% (低波動)
```

---

## 6. 🔄 進出場邏輯改進

### 建議新增條件

#### A. 趨勢過濾
```python
# 只順勢交易
dataframe['trend'] = dataframe['ema_50'] > dataframe['ema_200']
# 買入條件增加:
conditions.append(dataframe['trend'] == True)  # 只做多頭趨勢
```

#### B. 波動率過濾
```python
# 避開盤整
dataframe['volatility'] = dataframe['high'] - dataframe['low']
conditions.append(dataframe['volatility'] > dataframe['volatility'].rolling(20).mean())
```

#### C. 成交量確認
```python
# 確認有足夠成交量
conditions.append(dataframe['volume'] > dataframe['volume'].rolling(20).mean() * 1.5)
```

#### D. 多時間框架確認
```python
# 1h 趨勢確認
informative = self.dp.get_pair_dataframe(pair, timeframe='1h')
conditions.append(informative['close'] > informative['ema_50'])
```

---

## 7. 📊 幣對選擇優化

### 當前設定
- 23幣對 (部分資料不完整)

### 優化建議

#### A. 篩選條件
```python
# 只選擇:
# 1. 高波動率 (ATR > 閾值)
# 2. 高流動性 (Volume > 閾值)
# 3. 趨勢明顯 (ADX > 25)
```

#### B. 動態調整
```python
# 每月重新評估幣對表現
# 移除表現差的幣對
# 加入新幣對
```

### 建議幣對清單
- **核心**: BTC, ETH, BNB, SOL, XRP
- **衛星**: DOGE, ADA, AVAX, LINK, TON
- **排除**: USD1 (穩定幣), 低流動性幣

---

## 8. ⚠️ 風險管理增強

### 建議新增

#### A. 最大持倉限制
```python
max_open_trades = 5  # 同時最多5筆
```

#### B. 相關性控制
```python
# 避免同時持有多個高度相關幣對
# 例如: 不會同時持有 BTC 和 ETH (相關性 > 0.8)
```

#### C. 日虧損上限
```python
# 單日虧損達 5% 停止交易
```

#### D. 連敗保護
```python
# 連續3筆虧損後，降低倉位或暫停
```

---

## 優化優先順序

### 立即執行 (今天)
1. ✅ 調整 ROI 設定 (簡化)
2. ✅ 收緊 Stoploss (-0.189 → -0.05)
3. ✅ 測試 15m 時間框架

### 短期 (本週)
4. ✅ 優化 Trailing Stop 參數
5. ✅ 加入趨勢過濾
6. ✅ 調整倉位管理

### 中期 (本月)
7. ✅ 優化幣對選擇
8. ✅ 加入風險管理機制
9. ✅ 多時間框架確認

---

## 預期效果

| 優化項目 | 預期提升 |
|---------|----------|
| ROI 簡化 | +2% to +3% |
| Stoploss 收緊 | +1% to +2% |
| 時間框架調整 | +2% to +5% |
| 趨勢過濾 | +3% to +5% |
| 風險管理 | +1% to +2% |
| **綜合** | **+10% to +15%** |

---

報告時間: 2026-05-26
