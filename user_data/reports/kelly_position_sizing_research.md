# 機率論與凱利公式 — 交易策略研究報告
*Brian Tseng — 2026-05-05*

---

## 一、核心公式

### 1. 凱利公式（Kelly Criterion）

$$f^* = \frac{W \cdot R - (1 - W)}{R}$$

其中：
- $f^*$ = 帳戶應投入的最大比例
- $W$ = 勝率（Win Rate）
- $R$ = 盈虧比（AvgWin / AvgLoss）

**簡化版**（當 R=1 時）：
$$f^* = 2W - 1$$

### 2. 期望值公式（Expectancy）

$$E = P_{win} \times AvgWin - P_{loss} \times AvgLoss$$

或用 R 表示：
$$E = W \times R \times |AvgLoss| - (1-W) \times |AvgLoss|$$

### 3. 期望值 > 0 的條件

$$E > 0 \iff W > \frac{1}{1+R}$$

| 盈虧比 R | 所需最低勝率 |
|---------|-------------|
| 1:1 | > 50% |
| 2:1 | > 33.3% |
| 3:1 | > 25% |
| 0.5:1 | > 66.7% |

### 4. V90 的期望值計算

V90 實測數據：
- 勝率：68.8%（W = 0.688）
- 平均交易：-0.24%
- 平均贏：未知（從報告推估）
- 平均虧：未知

假設：AvgWin = 0.3%, AvgLoss = 0.6%（1:2 盈虧比）
- $E = 0.688 \times 0.3\% - 0.312 \times 0.6\% = 0.2064\% - 0.1872\% = +0.0192\%$

**正期望，但平均贏幅太小** → 問題在於交易成本 + 市場環境

---

## 二、凱利公式的實際應用

### 完整凱利（Full Kelly）
- **缺點**：波動性極大，帳戶可能剧烈起伏
- **公式**：$f = \frac{W}{L} - \frac{1-W}{R}$，其中 L = 1（假設止損比例）

### 半凱利（Half Kelly）
$$f_{half} = \frac{f^*}{2}$$
- 降低波動性，保留約 75% 的成長率
- **實際交易推薦**

### 四分之一凱利（Quarter Kelly）
$$f_{quarter} = \frac{f^*}{4}$$
- 常用於機構投資
- 最大程度控制下行風險

---

## 三、R-Multiples（Van Tharp）系統

### 定義
- **1R** = 初始風險（等於止損距離）
- 所有交易以 R 為單位衡量

### 系統期望值
$$E[R] = (P_{win} \times AvgR_{win}) - (P_{loss} \times 1R)$$

### V90 的 R 表達
假設止損 = -0.3%：
- 若 AvgWin = 0.3%, AvgLoss = 0.3% → R 比率 = 1:1
- 若 AvgWin = 0.3%, AvgLoss = 0.6% → R 比率 = 0.5:1
- 若 AvgWin = 0.6%, AvgLoss = 0.3% → R 比率 = 2:1

---

## 四、關鍵策略概念

### 1. Hoddak Bounce Strategy
- **核心**：價格服從常態分佈，在均值附近反彈
- **進場**：價格偏離均值 > 2 個標準差時反向交易
- **適用**：高波動性市場（crypto 適合）
- **風險**：趨勢市場中均值的偏離可能持續擴大

### 2. Delta Neutral + 槓桿套利
- **做法**：同時持有現貨 + 期貨空頭，鎖定基差
- **目標**：賺取資金費率（funding rate）
- **例子**：持有 1 BTC 現貨 + 做空等價值期貨合約
- **Freqtrade 應用**：在期貨 bot 上實現

### 3. 定額 vs 動態倉位

| 方法 | 公式 | 優點 | 缺點 |
|------|------|------|------|
| **定額（Fixed Stake）** | 每次投入固定金額 | 簡單穩定 | 不適應帳戶成長 |
| **定比（Fixed Fractional）** | 每次投入帳戶的固定比例 f% | 複利成長 | 可能超出凱利 |
| **凱利（Kelly）** | $f^* \times$ 帳戶餘額 | 數學最優 | 波動大 |
| **反凱利（Anti-Kelly）** | $f^* \times k$（k < 1） | 穩健 | 成長慢 |

### 4. 定比倉位計算

$$Position = \frac{Account \times f\%}{EntryPrice \times (StopLoss\% + Fee\%)}$$

---

## 五、對 V90 Scalp 策略的啟示

### V90 現狀診斷
- **勝率**：68.8%（足夠高）
- **盈虧比**：需要實測數據
- **期望值**：根據現有數據計算接近零或微正

### 可改進方向

#### 方案 A：凱利優化倉位
```
目標：根據期望值動態調整倉位
公式：f* = (W × R - (1-W)) / R
若 W=0.688, R=1.0（目標盈虧比）:
f* = (0.688 × 1 - 0.312) / 1 = 0.376 = 37.6% 帳戶
→ 半凱利 = 18.8%
→ 四分之一凱利 = 9.4%

Freqtrade 無法動態改倉位（每次 stake_amount 固定）
→ 需要 custom_stake_amount 或手動干預
```

#### 方案 B：R-Multiples 系統改造
```
1. 測量真實 AvgWin 和 AvgLoss
2. 計算期望值 E = W×R - (1-W)
3. 根據 E 決定是否交易
4. 設定目標 R = 2:1（每筆風險不超過 0.3%）
```

#### 方案 C：槓桿 + 凱利
```
在期貨模式使用：
- 2x 槓桿
- 止損 -0.3%（對槓桿倉位 = -0.6%）
- 目標 +0.3%（對槓桿倉位 = +0.6%）
- 月目標 10% → 需要 33.3% 月報酬 / 2x 槓桿 = 16.7% 月報酬

若 AvgWin = 0.3%, AvgLoss = 0.3%, 2x 槓桿:
實質 AvgWin = 0.6%, 實質 AvgLoss = 0.6%
E = 0.688 × 0.6% - 0.312 × 0.6% = 0.2256%
每月 480 筆交易（666/6m × 30d）
月期望 = 480 × 0.2256% = +10.8% ✅ 接近目標
```

---

## 六、實測 V90 數據補充

建議收集以下數據以計算完整期望值：
```bash
# 從 backtest result 提取
# 總交易：666
# 總損益：-80.325 USDT
# 平均交易：-0.24%
# 勝交易：458
# 虧交易：208

# 計算：
AvgWin = TotalProfit / WinTrades = (-80.325 + |LossSum|) / 458
AvgLoss = |LossSum| / 208
```

---

## 七、關鍵論文/文獻

1. **Kelly, J.L. (1956)** — "A New Interpretation of Information Rate"（原始凱利公式）
2. **Tharp, Van K.** — "The New Trading for a Living"（R-Multiples 系統）
3. **Ed Thorp** — 凱利公式在21點和對沖基金中的應用
4. **Benter, W.** — "Beat the Dealer"（概率優勢在實際賭博/交易中的應用）
5. **Li et al. (2020)** — "LSTM-Based Quantitative Trading Using Dynamic K-Top and Kelly Criterion" (IEEE IJCNN 2020) — DOI: 10.1109/ijcnn48605.2020.9207264
6. **Kim (2024)** — "Kelly Criterion Extension: Advanced Gambling Strategy" (Mathematics) — DOI: 10.3390/math12111725
7. **Jacot & Mochkovitch (2023)** — "Kelly criterion and fractional Kelly strategy for non-mutually exclusive bets" (J. Quant. Anal. Sports) — DOI: 10.1515/jqas-2020-0122
8. **Wu & Hung (2018)** — "Option Buy-Side Strategy with Simple Index Futures + Kelly Criterion" (IEEE BESC 2018) — DOI: 10.1109/besc.2018.8697308
9. **Blotnick** — "The Power of Position Sizing in Portfolio Management" (SSRN) — DOI: 10.2139/ssrn.5363482

---

## 八、核心發現（2026-05-05 更新）

### 8.1 實測數據修正

| 指標 | V90 (Binance) | V91 (Binance) | **V91 (Bybit)** |
|------|:---:|:---:|:---:|
| 總虧損 | -8.03% | -32.04% | **-9.14%** |
| 勝率 | 68.8% | 36.8% | **39.6%** |
| Avg Win | 0.50% | 0.27% | **0.20%** |
| Avg Loss | 1.88% | 0.49% | **0.29%** |
| 盈虧比 R | 0.27:1 | 0.55:1 | **0.69:1** |
| Profit Factor | 0.59 | 0.32 | **0.45** |
| 所需勝率(BEP) | 78.7% | 64.5% | **59.3%** |
| 落後差距 | -9.9% | -27.7% | **-19.7%** |

### 8.2 凱利公式的關鍵限制

> **⚠️ 最重要發現：凱利公式不能在負期望策略上創造奇蹟**

凱利公式的本質：優化已經是正期望的策略的成長率。

$$f^* = \frac{W \times R - (1-W)}{R}$$

前提條件：$W \times R > (1-W)$，即策略本身必須正期望。

**V91 Bybit 驗證**：
- W = 39.6%, R = 0.69
- W × R = 0.273 < (1-W) = 0.604
- **f* = (0.396 × 0.69 - 0.604) / 0.69 = -0.299**
- 負數 → 凱利公式說「不該下注」

### 8.3 學術研究啟示

**Kim (2024) — Kelly Criterion Extension (KCE)**
- 核心：傳統凱利只考慮靜態市場，KCE 針對動態市場條件調整
- 啟示：隨市場狀況動態調整倉位，而非固定比例

**Li et al. (2020) — LSTM + Kelly**
- 核心：用 LSTM 預測未來價格方向 + Kelly 計算倉位
- 與 Brian 策略的差異：他們用 ML 預測方向再應用凱利，而非用 ML 直接預測進場

**Jacot & Mochkovitch (2023) — Fractional Kelly**
- 核心：當投注非互斥時（多個倉位同時存在），完整凱利會高估風險
- Freqtrade 實際就是這種情況（max_open_trades > 1）
- 建議：使用 1/4 或 1/2 凱利

### 8.4 唯一可行方向

既然凱利無法補救負期望，**必須先改善策略本身**：

| 方向 | 做法 | 所需條件 |
|------|------|---------|
| **提高 R** | 寬止損 + 寬目標（1:3） | 勝率 35% 即可正期望 |
| **提高勝率** | 拉長 timeframe（15m/1h）| ML 噪音減少 |
| **加入方向過濾** | 只在趨勢方向交易 | 避免逆勢交易 |
| **Delta Neutral** | 現貨+期貨對沖 | 收取 funding rate |

---

## 九、總結行動項（修訂版）

| 優先順序 | 行動 | 預期效果 |
|---------|------|---------|
| ⭐⭐⭐ | **放棄 1:1 R:R scalp**（已驗證失敗） | — |
| ⭐⭐⭐ | **改用 1:3 R:R 寬止損** | 35% 勝率即可正期望 |
| ⭐⭐ | **拉長 timeframe 到 15m/1h** | ML 預測更準 |
| ⭐⭐ | **測試只在順趨勢方向進場** | 過濾逆勢交易 |
| ⭐ | **實作 Delta Neutral + Kelly** | 期貨+現貨對沖 |
