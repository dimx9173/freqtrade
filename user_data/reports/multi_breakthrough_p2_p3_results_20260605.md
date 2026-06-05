# Path 2 + 3 整合結果 — 2026-06-05

> **作者**: Brian + MiniMax-M3
> **範圍**: 4 突破路徑中的 Path 2 (extended) + Path 3
> **前次報告**: [multi_breakthrough_poc_results_20260605.md](./multi_breakthrough_poc_results_20260605.md) (Path 1 FAILED + Path 2 3-asset)

---

## 摘要

| 路徑 | 結果 | 評分 | 決策 |
|------|------|------|------|
| Path 1 (Cointegration) | ❌ FAILED | 0/10 | DEPRECATED |
| **Path 2 3-asset (initial)** | 🟡 PARTIAL | 5/10 | Need more assets |
| **Path 2 10-asset (extended)** | ✅ **VALIDATED** | **7/10** | **可作 regime 特徵** |
| **Path 3 XGBoost (initial)** | ❌ **FAILED** | 2/10 | **模型 collapse** |
| Path 4 RL | ⏸️ PHASE 2 | — | Deferred |

**整體**: 1 條路線 (Path 2) 獲得有意義的 alpha 來源，可供 Phase 3 策略整合。

---

## Path 2 Extended: 10-asset Eigenvalue Distribution ✅ VALIDATED

### 結論
**10 資產 eigenvalue decomposition 在 1h timeframe 確實捕捉 regime 變化**，MSI-Vol 相關 0.689 (vs 3 資產 0.509)，可作為 Freqtrade 策略的 regime 偵測特徵。

### 量化證據

| 指標 | 3 資產 (POC 1) | 10 資產 (POC 2) | 改善 |
|------|----------------|----------------|------|
| Mean MSI | 2.621 (飽和) | **7.693** | 範圍擴大 |
| MSI 範圍 | 1.61~2.96 (窄) | **4.97~9.21** | spread 充足 |
| MSI std | 0.210 | **0.791** | 變化豐富 |
| MSI-Vol 相關 | 0.509 | **0.689** | +35% |
| Crisis 偵測 | 1.79x vol | 1.49x vol | — |
| Crisis 日期 | 2025-06-13, 09-06 | 2026-03-22 | 與事件對應 |
| 預測力 (t→t+4h) | — | 0.164 (⚠️ 弱) | 同步指標 |

### 理論
- **λ_1 = 7.69 ± 0.79**: 絕對主導 eigenvalue，符合 crypto 高耦合特性
- **λ_2 = 0.87 ± 0.25**: 次要模式（可能是 BTC vs alt 分離）
- **λ_3~λ_5**: 弱模式
- **MSI > 8.9 (p95)** 視為「regime 集中」 (市場單一方向)
- **MSI < 6.7 (p10)** 視為「regime 分散」 (個幣獨立運動)

### 應用場景
- **進場過濾器**: MSI > 8.0 (高耦合) → 趨勢策略; MSI < 6.5 (分散) → 暫停交易
- **風控**: MSI 急升 → 加強止損 (高波動)
- **倉位管理**: MSI 分散時降低倉位

### 限制
- **預測力弱**: MSI(t)→Vol(t+4h) = 0.164，僅同步指標非領先指標
- **BTC bybit 1h 資料短**: 僅 2026-03-20 ~ 2026-05-24 (2 個月)，限制了 eigenvalue 計算的時間跨度
- **需 10 幣種資料齊全**: 任一幣種缺失會降低效果

---

## Path 3: XGBoost Entry Signal ❌ FAILED (Model Collapse)

### 結論
**XGBoost 在純 TA 特徵下沒有學到有用的進場信號**，模型 collapse 到「永遠預測 No」。

### 量化證據

| 指標 | 數值 | 判定 |
|------|------|------|
| Train accuracy | 68.07% | 看似好 |
| Test accuracy | 67.93% | 看似好 |
| **Test AUC** | **0.5741** | ❌ 接近隨機 |
| Yes class precision | 0.00 | ❌ 完全沒預測到 |
| Yes class recall | 0.00 | ❌ 完全沒預測到 |
| Trades (proba > 0.5) | 0 | ❌ |
| Trades (proba > 0.4) | 182 | cum -6.64% ❌ |
| Buy & Hold BTC OOS | -7.84% | 略勝 B&H 但仍虧 |

### 為什麼失敗

1. **Class imbalance**: Label 32% Yes / 68% No，模型學到 trivial classifier
2. **特徵不足**: 只有 20 個 TA 特徵，缺少 funding rate, OI, 多時間框架共識, market microstructure
3. **時間框架不適配**: 1h 太密，噪音大（Hybrid_v3 結論是 15m 最佳）
4. **Look-ahead 風險**: 嚴格 walk-forward split 還不夠，需排除 info leakage
5. **目標設計太寬鬆**: 4h > 0.3% 觸發 32% 樣本，太多正例稀釋信號

### Feature Importance (Top 5)
1. `natr` (Normalized ATR) — 波動率最重要
2. `tr` (True Range)
3. `ret_24h` (24h return) — 動能
4. `volume_ma_ratio` — 量能
5. `bb_width` — 波動率結構

**注意**: Top 5 都是「波動率相關」特徵，沒有 trend/regime 特徵。

### 教訓
- 純 TA 特徵不足以 beat Buy & Hold
- XGBoost 對 class imbalance 敏感，需 scale_pos_weight 或 SMOTE
- 需引入 Path 2 MSI 作為 regime 特徵（市場模式信息）
- 應用 15m timeframe 與 Hybrid_v3 一致

### 下一步
**Path 3 v2**: 結合 Path 2 MSI 作為特徵 + 用 15m timeframe + 處理 class imbalance

---

## 整合建議

### 短期 (1-2 週)
1. **Path 2 → Freqtrade populate_indicators 整合**
   - 在 `Hybrid_v3.py` 加 MSI 計算
   - 用 MSI > 8.0 作為 regime filter
   - 跑 4 月 OOS backtest 對比基準
2. **Path 3 → 加入 MSI 特徵重訓**
   - 用 15m timeframe
   - 處理 class imbalance (SMOTE 或 scale_pos_weight)
   - 加入 funding rate, OI 特徵

### 中期 (1 月)
3. **驗證 Path 2 改善 Hybrid_v3 基準**:
   - 目標: 利潤從 -3.98% → -2.0% (50% 改善)
   - WR 從 85.2% → 87% (微幅)
4. **寫新的 Freqtrade 策略 `Hybrid_v4_MSI.py`**

### 長期 (Phase 2)
5. **Path 4 RL**: 等 Path 2+3 整合到生產環境後再啟動

---

## 4 路徑最終評分

| 路徑 | 評分 | 進度 | 下次動作 |
|------|------|------|---------|
| Path 1 Cointegration | 0/10 | ❌ DEPRECATED | — |
| **Path 2 ORCA** | **7/10** | ✅ VALIDATED | 整合到 Hybrid_v3 |
| Path 3 XGBoost | 2/10 | ❌ FAILED | 加 MSI 特徵重跑 |
| Path 4 RL | — | ⏸️ PHASE 2 | 等 Phase 3 完成 |

---

*Generated: 2026-06-05 by MiniMax-M3*
*Sources:*
- `user_data/strategies/math_based/multi_breakthrough_v1/poc_p2_9assets.py`
- `user_data/strategies/math_based/multi_breakthrough_v1/poc_p3_xgboost.py`
