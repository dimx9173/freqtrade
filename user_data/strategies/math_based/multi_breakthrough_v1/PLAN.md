# Multi-Breakthrough 數學策略研發計畫 v1.0

> **作者**: Brian (Speculari) + MiniMax-M3
> **日期**: 2026-06-05
> **目標**: 擺脫 Hybrid_v3 結構性限制（uptrend-only、單幣種 BTC），探索 4 條新架構突破
> **方法論**: 每條路徑先做 POC (proof of concept) 驗證可行性，再決定是否進入完整 backtest
> **POC 結果**: [multi_breakthrough_poc_results_20260605.md](../../reports/multi_breakthrough_poc_results_20260605.md) — Path 1 ❌ FAILED, Path 2 🟡 PARTIAL

---

## 0. 戰略定位

### Hybrid_v3 結構性限制（Iter #4 證實）
- **Uptrend-only**：downtrend 期間結構性虧損（4 個月熊市虧 -0.9%）
- **BTC-only**：其他 9 個幣種全部 < 40% WR（無 edge）
- **架構 vs 參數**：GA 50 epoch 找到「不賠」參數，但找不到「賺錢」參數（架構是瓶頸）

### 突破的四條路徑
1. **跨幣種 cointegration 配對** — 利用 BTC-ETH / BTC-SOL 等高相關性對的 spread mean-reversion
2. **隨機矩陣 / 光譜圖論 (ORCA)** — 觀察 correlation matrix eigenvalue 分佈偵測 regime
3. **Hybrid AI regime + XGBoost (Generating Alpha)** — regime filter + 多指標特徵 ML 進場
4. **Reinforcement Learning 進場決策** — DQN/PPO 學會何時進場（Phase 2）

---

## 路徑 1：跨幣種 Cointegration 配對交易 ⭐ (優先)

### 1.1 學術基礎
- **Engle-Granger (1987)**：兩階段 cointegration 檢定
- **Johansen (1988)**：多元 cointegration
- **Gatev, Goetzmann, Rouwenhorst (2006)**：Pairs trading 經典文獻

### 1.2 POC 範圍
- **標的對**：BTC-USDT / ETH-USDT, BTC-USDT / SOL-USDT（高相關性 pair）
- **時間框架**：15m（與 Hybrid_v3 一致）
- **資料範圍**：2025-06-01 ~ 2026-06-01（12 個月，包含 bull + bear + range）
- **指標**：
  - Rolling cointegration (Engle-Granger) over 30-day window
  - Hedge ratio via OLS
  - Spread = log(BTC) - β × log(ETH)
  - z-score = (spread - mean) / std
- **進場規則**：
  - 進場：z < -2.0 (long spread: long BTC, short ETH)
  - 進場：z > +2.0 (short spread: short BTC, long ETH)
  - 出場：z 回到 [-0.5, +0.5]
  - 止損：z > 3.5 或 z < -3.5

### 1.3 驗證標準
- [ ] Cointegration 持續存在（p-value < 0.05 in > 60% of rolling windows）
- [ ] z-score 進場觸發次數 > 30（12 個月）
- [ ] Spread 顯著 mean-revert (half-life < 24h)
- [ ] 損益 > Hybrid_v3 BTC-only 基準

### 1.4 Freqtrade 適配性
- 需自訂 IStrategy 子類
- 同時持兩個倉位（delta-neutral if hedge ratio 正確）
- 需整合 `populate_entry_trend` 為配對信號

### 1.5 風險
- ⚠️ Cointegration 在 regime 變化時崩潰（特別是 crypto）
- ⚠️ 跨交易所 funding rate 差異會侵蝕 carry
- ⚠️ 履約保證金需求 2x 現貨策略

---

## 路徑 2：隨機矩陣 / 光譜圖論 (ORCA) ⭐⭐ (中期)

### 2.1 學術基礎
- **arXiv:2604.17251 (ORCA)**：Online Regime Correlation Analyzer
- **Bouchaud & Potters (2009)**：隨機矩陣理論在金融的應用
- **Laloux et al. (1999)**：correlation matrix eigenvalue cleaning

### 2.2 POC 範圍
- **特徵維度**：10 個幣種 × 5 個指標 = 50 維 + 光譜特徵 127 維 = 177 維
- **核心指標**：
  - 最大 eigenvalue λ_max 變化（市場模式轉換）
  - 參與率 (Participation Ratio) PR = (Σ λᵢ)² / Σ λᵢ²
  - 市場狀態指標 (Market State Index, MSI) = λ_max / mean(λ)
  - eigenvalue 偏度 (skewness)
- **時間框架**：5m (ORCA 論文用 5m 級別)
- **資料範圍**：BTC 5m 2025-01-01 ~ 2026-06-01

### 2.3 驗證標準
- [ ] λ_max 在 crisis (LUNA, FTX, CFX) 期間顯著上升
- [ ] MSI > threshold 能預測波動率急升
- [ ] 基於 MSI 的 regime classifier 準確度 > 70%
- [ ] 整合到 Hybrid_v3 regime detection 後改善 AUC > 5%

### 2.4 實作工具
- Python: numpy.linalg.eigvals, scipy.linalg.eigh
- rolling correlation matrix on 50 assets
- eigenvalue decomposition every 100 candles

### 2.5 風險
- ⚠️ 計算成本高（rolling 50×50 eigendecomp）
- ⚠️ 過擬合（ORCA 論文 206 維特徵，相對 12 月資料可能 overfit）
- ⚠️ 與現有 regime detection (rolling ridge) 可能冗餘

---

## 路徑 3：Hybrid AI Regime + XGBoost (Generating Alpha) ⭐⭐⭐ (推薦)

### 3.1 學術基礎
- **arXiv:2601.19504 (Generating Alpha)**：Hybrid AI regime-adaptive system
  - 架構：EMA+MACD (trend) + RSI+BB (mean-rev) + XGBoost (ML) + 波動率 filter + dynamic exposure
  - **24 個月報酬 135.49%**，打敗 S&P 500 和 NASDAQ-100
- **Chen & Guestrin (2016)**：XGBoost 原始論文
- **Brian 的 Hybrid_v3** 已經是類似架構（regime + TA），只缺 XGBoost 層

### 3.2 POC 範圍
- **標的**：BTC/USDT:USDT（Hybrid_v3 已知有效）
- **時間框架**：15m
- **訓練目標**：預測「未來 4 小時 (16 根 15m K 線) 收盤價漲跌 > 0.3%」
  - label: 1 if future_return > 0.003, 0 otherwise
- **特徵 (約 25 維)**：
  - Regime: regime, regime_1h, regime_4h
  - Trend: ema_12, ema_26, ema_50, adx, plus_di, minus_di
  - Mean-Rev: rsi, bb_position, bb_width
  - Volatility: atr, atr_z, vol_ma_ratio
  - Volume: volume_ma_ratio, obv_slope
  - Cross-TF: h1_ema_slope, h4_ema_slope
  - Funding: funding_rate, funding_rate_diff
- **訓練資料**：2024-06-01 ~ 2025-12-01（18 個月訓練）
- **測試資料**：2026-01-01 ~ 2026-06-01（6 個月 OOS 測試）
- **模型**：XGBoost binary classifier, max_depth=4, n_estimators=200

### 3.3 驗證標準
- [ ] OOS 準確度 > 55%（顯著優於 50% 隨機）
- [ ] 整合到 Hybrid_v3 進場後，總利潤改善 > 1%
- [ ] 特徵重要性 top 5 包含 regime, adx, funding_rate（驗證 alpha 真實性）
- [ ] 沒有 look-ahead bias（嚴格 walk-forward split）

### 3.4 Freqtrade 適配性
- 在 `populate_indicators` 加 XGBoost predict 結果為新欄位
- 模型用 joblib pickle 序列化存到 `user_data/models/`
- Live inference 在 `populate_entry_trend` 讀 model 預測

### 3.5 風險
- ⚠️ 過擬合（XGBoost 對 15m 高頻資料特別敏感）
- ⚠️ Look-ahead bias（必須嚴格 walk-forward）
- ⚠️ Regime 變化時 model 失效（需定期 retrain）

---

## 路徑 4：Reinforcement Learning 進場決策（Phase 2）

### 4.1 學術基礎
- **Mnih et al. (2015)**：DQN 論文
- **Schulman et al. (2017)**：PPO 論文
- **FinRL / ElegantRL**：金融 RL 開源框架

### 4.2 POC 範圍（待 Phase 2 展開）
- 環境設計：基於 15m BTC 資料的 gymnasium 環境
- 狀態空間：regime + TA 特徵 + 持倉狀態
- 動作空間：0 (flat), 1 (long), 2 (short)
- Reward：PnL - λ × |position| × volatility

### 4.3 Phase 2 觸發條件
- 路徑 1-3 至少一個成功 → RL 有 benchmark 可對比
- 計算資源允許（GPU）
- 願意花 1 週以上訓練調參

---

## 5. 執行計畫

### 5.1 階段 1：研究 + 設計（Week 1）
| 動作 | 負責 | 工具 |
|------|------|------|
| 路徑 1：cointegration 文獻 + 公式 | sub-agent A | web research + arxiv |
| 路徑 2：ORCA 論文精讀 + eigenvalue 公式 | sub-agent B | web research + arxiv |
| 路徑 3：Generating Alpha 論文精讀 + XGBoost 架構 | sub-agent C | web research + arxiv |

### 5.2 階段 2：小型 POC（Week 2）
| 動作 | 工具 | 預估時間 |
|------|------|---------|
| 路徑 1：BTC-ETH cointegration notebook POC | execute_code + pandas + statsmodels | 2-3 小時 |
| 路徑 2：BTC eigenvalue distribution notebook POC | execute_code + numpy | 2-3 小時 |
| 路徑 3：XGBoost 訓練 + 4 月 backtest | execute_code + xgboost + sklearn | 4-6 小時 |

### 5.3 階段 3：策略整合（Week 3-4）
- 對成功的 POC 寫成 Freqtrade IStrategy
- 對齊 Hybrid_v3 風格（populate_indicators, populate_entry_trend, custom_stoploss）
- 加入策略審查清單（trailing_stop=False, use_exit_signal=False 等）

### 5.4 階段 4：Backtest 驗證（Week 4）
- 4 個月 OOS backtest
- 多幣種擴展驗證（每條路徑獨立測）
- 與 Hybrid_v3 BTC-only 基準對比

---

## 6. 預期成果

### 成功標準（任一達成即可）
- ✅ 找到新架構勝過 Hybrid_v3 BTC-only 基準（年化 > 0%）
- ✅ 多幣種策略（> 2 個幣種）勝率 > 50%
- ✅ 熊市期間（下個 4 個月回測）虧損 < 1%

### 失敗處理
- ❌ 全部 POC 失敗 → 回到 Hybrid_v3 優化（trailing_stop 修復、ROI 重新 GA）
- ❌ 部分成功 → 保留成功的，歸檔失敗的（依 skill 棄用流程）

---

## 7. 風險總表

| 風險 | 機率 | 影響 | 緩解 |
|------|------|------|------|
| sub-agent timeout | 中 | 中 | 只做研究設計，不跑 backtest |
| 過擬合 | 高 | 高 | 嚴格 walk-forward，OOS 6 個月 |
| 計算資源不足 | 中 | 中 | 先跑小規模 POC，scale up |
| 學術路線與現實差距 | 高 | 中 | 用 Hybrid_v3 基準對比，不迷信論文 |
| Regime 變化失效 | 中 | 高 | 持續監控，每月 retrain model |

---

## 8. 參考文獻

1. Engle & Granger (1987). "Co-integration and Error Correction"
2. Gatev, Goetzmann, Rouwenhorst (2006). "Pairs Trading: Performance of a Relative-Value Arbitrage Rule"
3. arXiv:2604.17251 (ORCA). "Online Regime Correlation Analyzer"
4. arXiv:2601.19504 (Generating Alpha). "Hybrid AI regime-adaptive system"
5. Chen & Guestrin (2016). "XGBoost: A Scalable Tree Boosting System"
6. Schulman et al. (2017). "Proximal Policy Optimization Algorithms"
7. Freqtrade 文檔：https://www.freqtrade.io/en/stable/

---

*Document Version: 1.0.0*
*Last Updated: 2026-06-05*
*Plan Owner: Brian (Speculari)*
