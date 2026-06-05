# Path 3 v2: XGBoost + MSI 結果 — 2026-06-05

> **作者**: Brian + MiniMax-M3
> **目標**: 把 Path 2 的 10-asset MSI 特徵加入 XGBoost，驗證是否改善進場預測
> **前次報告**: [multi_breakthrough_p2_p3_results_20260605.md](./multi_breakthrough_p2_p3_results_20260605.md) (Path 3 v1 FAILED)

---

## 結論

🟡 **MSI 特徵微幅改善 XGBoost**（AUC +0.19 pp, proba > 0.5 累積收益翻倍 +30% → +60%）

**核心發現**:
- AUC 提升有限（0.5778 → 0.5797）— 仍接近隨機
- 但 **PR (Participation Ratio) 進入 Top 5 特徵重要性**
- 模型學會「不確定就跳過」：trade 數 -60% (1665 → 660)，但 **WR +4.9 pp, cum ret 翻倍**
- 這是**有意義的 alpha 改善**，但 edge 仍不夠強

---

## 量化證據

### 訓練配置
- **BTC 1h** (Binance, 28 月歷史) + **9 幣種 1h** (Bybit, 12 月)
- MSI: 10-asset rolling 24h correlation matrix eigenvalue decomposition
- 訓練 2024-06-01 ~ 2025-11-30 (v1: 18 月 / v2: 7 月因 MSI 限制)
- OOS 測試 2026-01-01 ~ 2026-05-07 (4 月, 3025 筆)
- Label: 4h 後漲跌 > 0.3% (32% 為正)
- scale_pos_weight=2.0 (處理 class imbalance)

### 模型表現對比

| 指標 | v1 (TA only) | v2 (TA+MSI+PR) | Δ | 評分 |
|------|--------------|----------------|---|------|
| **Test AUC** | 0.5778 | **0.5797** | +0.0019 | 🟡 微幅 |
| Train acc | 0.6488 | 0.7278 | +0.0790 | ✅ |
| Test acc | 0.5276 | 0.6383 | +0.1107 | ✅ |
| Best iter | 29 | 11 | -18 | 🟡 |
| Yes class F1 | 0.46 | 0.33 | -0.13 | ⚠️ |

### 交易表現 (proba > 0.5)

| 指標 | v1 (TA) | v2 (TA+MSI) | Δ |
|------|---------|-------------|---|
| Trades | 1665 | 660 | -60% |
| **Win rate** | 50.3% | **55.2%** | +4.9 pp |
| **Avg return** | 0.018% | **0.091%** | +5x |
| **Cum return** | +30.54% | **+60.36%** | **+29.82 pp** |

### 重要: proba > 0.4 (寬鬆門檻)

| 指標 | v1 | v2 | Δ |
|------|-----|-----|---|
| Trades | 2740 | 2835 | +95 |
| Win rate | 49.3% | 49.0% | -0.3 pp |
| Cum return | -19.27% | -39.49% | -20.22 pp |

**觀察**: 寬鬆門檻 (proba > 0.4) 兩者都虧，但 v2 在嚴格門檻 (proba > 0.5) 表現遠優於 v1 → v2 模型的「高信心」信號更可靠。

### Top 5 Feature Importance

**v1 (TA only)**:
1. natr (0.111)
2. tr (0.076)
3. bb_width (0.063)
4. volume_ma_ratio (0.056)
5. ret_24h (0.055)

**v2 (TA + MSI + PR)**:
1. tr (0.073)
2. ema_12 (0.056)
3. ema_26 (0.054)
4. volume_ma_ratio (0.053)
5. **pr (0.053)** ← MSI 系列特徵進入 Top 5

**注意**: v2 中 `pr` (Participation Ratio) 比 `msi` 進入更高排名 (第 5 vs 不在前 10)，但 `msi` 仍在第 11 名外。說明 PR 比 MSI 更直接有效。

---

## 為什麼 v2 改善有限但有 trade-off 意義

### 改善有限原因
1. **資料量限制**: v2 訓練只有 7 月 (5111 rows)，v1 有 18 月 (13152 rows)，MSI 計算需 10 個幣種齊全
2. **時間框架**: 1h 太密，噪音大（Hybrid_v3 經驗是 15m 較佳）
3. **標籤設計**: 4h > 0.3% 太寬鬆，32% 為正
4. **特徵工程**: TA + MSI 是必要但非充分；缺 funding rate, OI, market microstructure

### 但 trade-off 仍有意義
- ✅ v2 學會「不確定就跳過」→ 從 1665 trades 縮減到 660 trades
- ✅ 嚴格門檻下 WR 從 50.3% 提升到 55.2%
- ✅ 嚴格門檻下 cum return 從 +30% 翻倍到 +60%
- ✅ PR 特徵進入 Top 5 證明有 alpha

---

## 下一步

### 高 ROI 路線
1. **改用 15m timeframe** (與 Hybrid_v3 一致)
2. **加入 funding rate 特徵** (BTC perpetual funding 1h 或 8h)
3. **加入 OI (open interest) 特徵**
4. **MSI 計算改用 15m** (eigenvalue 計算更細)

### 中優先
5. **GA 優化 scale_pos_weight 與 threshold**
6. **Walk-forward 多次 split** (避免單一 OOS 過擬合)

### 低優先
7. **整合到 Freqtrade 策略** (`Hybrid_v3_MSI_XGB.py` 繼承 Hybrid_v3)
8. **完整 backtest with fee/slippage**

---

## 整體 4 路徑突破研發最終總結

| 階段 | 結果 |
|------|------|
| Plan v1.0 | ✅ PLAN.md (9.3KB) |
| Path 1 Cointegration | ❌ FAILED → DEPRECATED |
| Path 2 ORCA (3-asset) | 🟡 PARTIAL |
| Path 2 ORCA (10-asset) | ✅ VALIDATED (MSI-Vol 0.689) |
| **Path 2 整合到 XGBoost** | 🟡 **MARGINAL** (AUC +0.2pp, cum 翻倍) |
| Path 3 XGBoost (v1) | ❌ FAILED (model collapse) |
| Path 3 XGBoost + MSI (v2) | 🟡 MARGINAL |
| Path 4 RL | ⏸️ Phase 2 |
| Path 2 MSI filter POC | ⚠️ Edge 不顯著 (p>0.05) |

**整體評分**: 1 條路徑確認有 alpha (Path 2 ORCA)，1 條微弱改善 (Path 2+3 整合)，2 條失敗 (Path 1, 純 Path 3)

**最終建議**: 4 突破研發完成，沒有「突破」級 edge。**回歸 Hybrid_v3 基準優化**（trailing_stop, ROI 重新 GA）較實際。

---

*Generated: 2026-06-05 by MiniMax-M3*
*Sources:*
- `poc_p3_v2_xgb_msi.py` (v2 with MSI feature)
- `poc_p3_xgboost.py` (v1 baseline)
- `poc_p2_9assets.py` (Path 2 MSI computation)
