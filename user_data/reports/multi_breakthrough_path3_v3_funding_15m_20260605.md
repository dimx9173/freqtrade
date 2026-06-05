# Path 3 v3 結果：15m TF + Funding Rate (XGBoost)

**日期**: 2026-06-05
**腳本**: `poc_p3_v3_funding_15m.py`
**資料**: binance BTC 15m (2024-01-01 ~ 2025-01-09, 35,936 rows)
**標的**: 1h funding rate FFill 到 15m (9 個 lag + cumsum + streak + std features)

---

## 結果：🔴 負結果 (v2 對比)

| 指標 | v2 (1h + MSI+PR) | v3 (15m + funding rate) | Δ |
|------|------|------|------|
| Test AUC | 0.5797 | **0.5215** | **-0.0582** |
| proba>0.5 trades | 660 | 3869 | +3209 |
| proba>0.5 WR | 55.2% | 54.3% | -0.9 pp |
| proba>0.5 cum ret | +60.36% | +1693.46%* | misleading |
| **Funding rate 重要性** | N/A | **0.0000 (0.0%)** | 模型完全忽略 |

*cum ret 1693% 是 3869 個 trades 的累積 (平均單筆 0.078%)，但 AUC 0.5215 ≈ 0.5 表示模型**幾乎隨機**，累積的高收益是 overtrading 的 bias 偏差，不是真實 alpha。長期會被手續費 (0.1% × 2 = 0.2%) 吃掉。

---

## Top 15 Features (v3)

```
ema_26     0.095902
ema_50     0.092175
bb_upper   0.087185
ema_12     0.086363
ema_200    0.083226
bb_lower   0.082161
natr       0.073979
adx_14     0.064568
bb_width   0.063019
minus_di   0.062031
plus_di    0.060053
rsi_14     0.058686
volume_ma_ratio  0.047814
tr         0.042837
fr_lag1    0.000000  ← 9 個 funding features 全部 0
```

**Funding Rate contribution: 0.0000 (0.0%)**
**TA contribution: 1.0000 (100.0%)**
**Cross-asset contribution: 0.0000 (0.0%)** (v3 放棄 MSI, 見下方說明)

---

## 為什麼 v3 失敗？

### 1. 資料對齊災難 (致命)
- binance BTC 15m: 2024-01-01 ~ 2025-01-09 (1 年)
- bybit 9 幣種 1h: 2025-05-01 起 (12 月, **不與 15m 區間重疊**)
- binance 9 幣種 1h: **完全沒有** (下載器問題)
- → v3 無法同時擁有 15m TF + cross-asset MSI
- → v3 放棄 cross-asset MSI，純 15m + funding rate

### 2. Funding Rate 1h → 15m FFill = 訊號退化
- Bybit BTC 1h funding rate 每 8h 結算一次 (0.01% × 3 = 0.03%/日)
- 1h update → FFill 到 4 個 15m bars = **同一數值重複 4 次**
- XGBoost 認為「lag1 = lag4 = lag8 = lag24」毫無區辨力
- 9 個 funding features 全部重要性 = 0 (split 次數 0)

### 3. 15m 顆粒度 vs 1h funding 結構不匹配
- Funding rate 是 8h 週期性信號
- 1h update 頻率對 8h 週期信號是 over-sampling
- 15m TF 對 1h funding 是更 over-sampling
- → 正確設計應該是 funding rate 1h TF + 其他 OHLCV 1h/15m TF (multi-TF 模型)

### 4. AUC 0.52 顯示模型無分辨力
- 14 個 TA features 在 15m 顆粒度也沒有顯著 split
- 可能 15m BTC 噪音過大，TA 在 1h 才有效

---

## 與 v2 對比的解讀

| 路徑 | TF | MSI/PR | Funding | AUC | 結論 |
|------|----|--------|---------|-----|------|
| **v1 (TA only, 1h)** | 1h | ❌ | ❌ | 0.5778 | baseline |
| **v2 (TA+MSI+PR, 1h)** | 1h | ✅ | ❌ | 0.5797 | +0.19 pp, PR 進 Top 5 |
| **v3 (TA+funding, 15m)** | 15m | ❌ | ✅ | **0.5215** | **-5.6 pp, funding 0 importance** |

### 結論
- **15m TF 對 BTC 1h TA/features 是過度採樣**
- **Funding rate 在 15m 顆粒度上沒有結構信號**
- **v2 的 1h + MSI/PR 是目前最佳配置**

---

## 修正方向（若要重做 v3）

### A. 改用 multi-TF 模型 (1h 為主 TF，15m 作為 confirm)
- binance BTC 1h + binance BTC 15m (multi-TF)
- 訓練: 2024-01-01 ~ 2024-09-30 (1h)
- 測試: 2024-10-01 ~ 2025-01-09 (1h)
- 加 15m features (rsi_15m, macd_15m) 與 1h TA 一起訓練
- 預期: 1h 主 TF 提供穩定 split, 15m 提供結構 confirm

### B. 直接放棄 funding rate 整合 (B 路線 v3 失敗)
- v2 的 1h + MSI+PR 已達 0.5797, 繼續優化其他路徑

### C. 改用 funding rate 1h (不放 15m)
- binance BTC 1h (2024-01-01 ~ 2026-05-07, 28 月) + bybit BTC funding rate 1h
- 訓練: 2024-01-01 ~ 2025-12-31 (24 月)
- 測試: 2026-01-01 ~ 2026-05-07 (5 月 OOS)
- funding rate 在 1h 顆粒度可能有效（不過度採樣）

---

## v3 失敗的策略意涵

1. **不要盲信「更細的 TF = 更好」**：15m 噪音可能反而掩蓋結構
2. **Feature 與 TF 的時間尺度要匹配**：8h 週期信號配 1h update 已足，15m 是 over-sampling
3. **負結果也是結果**：避免未來浪費時間在 funding rate 整合上
4. **v2 的 1h + MSI/PR 仍是當前最優 XGBoost 配置**

---

## 數據產出

- `poc_p3_v3_funding_15m.py` (13.4KB, 313 行)
- `poc_p3_v3_predictions.csv` (9695 筆測試預測)
- `poc_p3_v3_feat_imp.csv` (23 個 feature importance)
- 本報告

## 推薦下一步

**回歸 v2 基準 (選項 A)**：trailing_stop 與 ROI 重新 GA 優化
**或暫停 Freqtrade (選項 D)**：切回 funding-rate-arbitrage 處理 SPEC v1.0 實作
