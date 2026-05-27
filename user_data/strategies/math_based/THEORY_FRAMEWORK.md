# 數學理論交易策略框架

**版本**: v2.0  
**更新日期**: 2026-05-21  
**作者**: Brian Tseng (Speculari)  

---

## 一、核心理論基礎

### 1.1 凱利公式 (Kelly Criterion)

**公式**:
```
f* = (W × R - (1-W)) / R
```

**變數**:
- `f*` = 帳戶應投入的最大比例
- `W` = 勝率 (Win Rate)
- `R` = 盈虧比 (AvgWin / AvgLoss)

**簡化版** (當 R=1 時):
```
f* = 2W - 1
```

**應用**:
- **半凱利 (Half Kelly)**: f_half = f* / 2 — 降低波動，保留 75% 成長率
- **四分之一凱利 (Quarter Kelly)**: f_quarter = f* / 4 — 機構投資常用

### 1.2 期望值公式 (Expectancy)

**公式**:
```
E = P_win × AvgWin - P_loss × AvgLoss
```

**或表示為**:
```
E = W × R × |AvgLoss| - (1-W) × |AvgLoss|
```

**正期望值條件**:
```
E > 0 ⟺ W > 1/(1+R)
```

| 盈虧比 R | 所需最低勝率 |
|---------|-------------|
| 1:1 | > 50% |
| 2:1 | > 33.3% |
| 3:1 | > 25% |
| 0.5:1 | > 66.7% |

### 1.3 R-Multiples (Van Tharp 系統)

**定義**:
- **1R** = 初始風險 (等於止損距離)
- 所有交易以 R 為單位衡量

**系統期望值**:
```
E[R] = (P_win × AvgR_win) - (P_loss × 1R)
```

---

## 二、風險報酬比 (Risk/Reward Ratio) 設計

### 2.1 基礎原則

**剝頭皮策略推薦 R/R >= 1:2**

| 止損 | 止盈 | R/R | 盈虧平衡勝率 |
|------|------|-----|-------------|
| 3% | 3% | 1:1 | 50% |
| 3% | 4.5% | 1:1.5 | 40% |
| 2% | 4% | 1:2 | 33% |
| 1.5% | 4.5% | 1:3 | 25% |
| 1% | 4% | 1:4 | 20% |

### 2.2 針對不同市場狀態的動態 R/R

#### 趨勢市場 (ADX > 25)
```
止盈: 3-4× 止損
止損: 1.5%
止盈: 4.5-6%
```

#### 盤整市場 (ADX < 20)
```
止盈: 2× 止損
止損: 1%
止盈: 2%
```

#### 高波動市場 (ATR > 1.5× 平均)
```
止損: 擴大到 2%
止盈: 至少 4%
R/R 保持 1:2
```

### 2.3 ATR 動態止盈/止損計算

```python
def calculate_atr_based_levels(current_price, atr, market_state):
    """
    ATR 動態計算止盈止損
    
    Parameters:
    - current_price: 當前價格
    - atr: ATR(14) 值
    - market_state: 'trend', 'ranging', 'volatile'
    
    Returns:
    - stop_loss_pct: 止損百分比
    - take_profit_pct: 止盈百分比
    """
    if market_state == 'trend':
        stop_multiplier = 2.0
        profit_multiplier = 5.0
    elif market_state == 'ranging':
        stop_multiplier = 1.5
        profit_multiplier = 3.0
    else:  # volatile
        stop_multiplier = 2.5
        profit_multiplier = 5.0
    
    stop_pct = (atr * stop_multiplier) / current_price
    profit_pct = (atr * profit_multiplier) / current_price
    
    # 確保最小 R/R = 1:2
    if profit_pct < stop_pct * 2:
        profit_pct = stop_pct * 2
    
    return stop_pct, profit_pct
```

---

## 三、市場狀態識別

### 3.1 ADX (Average Directional Index) 趨勢強度

| ADX 值 | 市場狀態 | 交易建議 |
|--------|----------|----------|
| **ADX < 20** | 弱趨勢/盤整 | 均值回歸策略，避免趨勢跟隨 |
| **ADX 20-25** | 過渡區域 | 觀望或輕量測試 |
| **ADX > 25** | 強趨勢 | 趨勢跟隨策略入場 |
| **ADX > 40** | 極強趨勢 | 謹慎反向入場，高反轉風險 |

### 3.2 +DI 與 -DI 交叉判斷趨勢方向

```python
# +DI > -DI 表示多頭趨勢
trend_direction = plus_di > minus_di

# 快速 ADX 確認趨勢不是即將反轉
cond_adx_rising = dataframe["adx_fast"] > dataframe["adx_fast"].shift(1)
```

### 3.3 市場狀態分類 (Regime)

| Regime | ADX 範圍 | 市場狀態 | 交易策略 | 風險報酬比 |
|--------|----------|----------|----------|------------|
| **0** | < 20 | 盤整/低波動 | 均值回歸 (BB + RSI) | 1:1.5 |
| **1** | 20-25 | 過渡/觀望 | 輕倉觀望或不做單 | N/A |
| **2** | > 25 | 強趨勢 | 趨勢跟隨 (EMA + ADX) | 1:3 |

---

## 四、止損策略類型

### 4.1 三種止損策略對比

| 類型 | 優點 | 缺點 | 適用場景 |
|------|------|------|----------|
| **固定百分比** | 簡單穩定 | 不適應波動 | 高頻剝頭皮 |
| **ATR 動態** | 適應市場 | 計算複雜 | 所有場景 |
| **技術位止損** | 精準 | 需要識別 | 有明顯支撐阻力 |

### 4.2 追蹤止損 (Trailing Stop)

```python
# Freqtrade trailing stop 配置示例
trailing_stop = True
trailing_stop_positive = 0.005  # 從利潤 0.5% 開始追蹤
trailing_stop_positive_offset = 0.015  # 利潤達到 1.5% 後激活
trailing_only_offset_is_reached = True  # 只有達到偏移才激活
```

**剝頭皮推薦配置**:
```
趨勢強時: trailing_stop_positive = 0.3%, offset = 1%
盤整時:   禁用 trailing，使用固定止盈
```

### 4.3 時間止損 (Time-based Exit)

```python
def time_based_exit(trade, current_time, max_hold_minutes=60):
    """
    時間止損：防止持倉過夜捕捉突發事件
    """
    hold_minutes = (current_time - trade.open_date).seconds / 60
    return hold_minutes >= max_hold_minutes
```

**建議**:
- 5m timeframe: 最大持倉 30-45 分鐘
- 15m timeframe: 最大持倉 60-90 分鐘

---

## 五、不同槓桿倍數的推薦設置

| 槓桿 | 止損 | 止盈 | R/R | 盈虧平衡勝率 |
|------|------|------|------|-------------|
| 3x | 2.0% | 4.0% | 1:2 | 33% |
| 5x | 1.5% | 4.5% | 1:3 | 25% |
| 10x | 1.0% | 4.0% | 1:4 | 20% |
| 20x | 0.5% | 3.0% | 1:6 | 14% |

---

## 六、策略實作架構

### 6.1 自適應策略架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    Adaptive Strategy 架構                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────┐                     │
│   │   5m Timeframe  │    │   15m Timeframe │ (informative)     │
│   │   進場信號       │    │   趨勢確認       │                     │
│   └────────┬────────┘    └────────┬────────┘                   │
│            │                       │                             │
│            └───────────┬───────────┘                             │
│                        ▼                                         │
│            ┌─────────────────────┐                               │
│            │   Market Regime      │                               │
│            │   Detector (ADX)      │                               │
│            └──────────┬────────────┘                               │
│                       │                                            │
│          ┌────────────┼────────────┐                              │
│          │            │            │                              │
│          ▼            ▼            ▼                              │
│   ┌───────────┐ ┌───────────┐ ┌───────────┐                     │
│   │ Regime 0   │ │ Regime 1  │ │ Regime 2  │                     │
│   │ 均值回歸   │ │  過渡觀望  │ │ 趨勢跟隨   │                     │
│   │ BB + RSI  │ │ 輕倉/不做 │ │ EMA + ADX │                     │
│   └───────────┘ └───────────┘ └───────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 進場條件設計

#### Regime 0 - 均值回歸進場 (ADX < 20)

**多頭進場**:
1. `close < bb_lower` (觸及下軌)
2. `rsi < 35` (RSI 超賣)
3. `volume > volume_ma * 0.8` (成交量確認)
4. `close > open` (陽燭確認)

**空頭進場**:
1. `close > bb_upper` (觸及上軌)
2. `rsi > 65` (RSI 超買)
3. `volume > volume_ma * 0.8` (成交量確認)
4. `close < open` (陰燭確認)

#### Regime 2 - 趨勢跟隨進場 (ADX > 25)

**多頭進場**:
1. `adx > 25` (趨勢強度確認)
2. `plus_di > minus_di` (多頭方向)
3. `ema_fast > ema_slow` (均線多頭排列)
4. `adx_rising` (趨勢增強中)

**空頭進場**:
1. `adx > 25`
2. `minus_di > plus_di`
3. `ema_fast < ema_slow`
4. `adx_rising`

---

## 七、風險監控指標

### 7.1 實際 R/R 計算

```python
def calculate_actual_rr(trades):
    """計算實際風險報酬比"""
    wins = [t for t in trades if t.profit > 0]
    losses = [t for t in trades if t.profit < 0]
    
    avg_win = sum(t.profit for t in wins) / len(wins)
    avg_loss = abs(sum(t.profit for t in losses) / len(losses))
    
    return avg_win / avg_loss
```

### 7.2 期望值監控

```python
def calculate_expectancy(win_rate, avg_win, avg_loss):
    """計算期望值"""
    return win_rate * avg_win - (1 - win_rate) * avg_loss
```

### 7.3 關鍵監控指標

| 指標 | 健康範圍 | 警告範圍 | 危險範圍 |
|------|----------|----------|----------|
| 實際 R/R | > 1:2 | 1:1.5 - 1:2 | < 1:1.5 |
| 期望值 | > 0 | -0.1% - 0 | < -0.1% |
| 勝率 | > 35% | 25% - 35% | < 25% |
| 最大回撤 | < 10% | 10% - 20% | > 20% |

---

## 八、迭代記錄

### v2.0 (2026-05-21)
- **更新**: 重新整理理論框架，建立統一文件
- **新增**: 完整數學公式、市場狀態分類、止損策略對比
- **策略數**: 15 個數學理論策略
- **狀態**: 待測試與優化

### v1.0 (2026-05-21)
- **建立**: 整理所有數學理論策略到統一目錄
- **來源**: test/, research/

---

## 九、參考文件

- `risk_reward_ratio_design.md` — 風險報酬比詳細設計
- `trend_detection_mechanisms.md` — 趨勢識別機制詳細實作
- `adaptive_scalp_v2_spec.md` — 自適應策略規格
- `pullback_strategy_research.md` — 回調策略研究
- `strategy_failure_analysis.md` — 策略失敗分析

---

## 十、待研究項目

- [ ] 凱利公式在組合策略中的應用
- [ ] 多時間框架 R/R 優化
- [ ] 機器學習預測市場狀態轉換
- [ ] 動態倉位管理 (基於 R/R 和勝率)
