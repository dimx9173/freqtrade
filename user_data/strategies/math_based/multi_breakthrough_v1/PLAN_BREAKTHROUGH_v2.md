# Multi-Breakthrough 數學策略研發計畫 v2.0 — Post Path 1-3 Retrospective

> **作者**: Brian (Speculari) + MiniMax-M3 (SDD Orchestrator)
> **日期**: 2026-06-12
> **目標**: Path 1-3 結果 retrospective + Path 4 RL 深度設計 + 新增 Path 5-6
> **前置**: [PLAN.md](./PLAN.md) v1.0 (2026-06-05) + [POC results](../../reports/multi_breakthrough_poc_results_20260605.md)

---

## 0. v1.0 Retrospective (Path 1-3 結果總結)

### 0.1 結果矩陣

| Path | 名稱 | 評分 | 結果 | 教訓 |
|------|------|:----:|------|------|
| 1 | 跨幣種 Cointegration | 0/10 | ❌ FAILED | Crypto 不適用統計套利 (ADF p>0.05) |
| 2 | 多資產 Eigenvalue (ORCA) | 7/10 | ✅ VALIDATED | MSI-Vol 相關 0.689, 已用於 Hybrid_v3_MSI v1 |
| 3 | XGBoost 進場 | 2/10 | ❌ FAILED | v2 最佳 AUC=0.5797, 不足以獨立驅動交易 |
| 4 | RL 強化學習 | — | ⏸️ PHASE 2 | 待 v2 規劃 |

### 0.2 三大跨路徑教訓（指導 v2 設計）

#### 教訓 A：**15m 噪音 > 結構**（從 Path 1+3 共同驗證）
- 15m BTC 上: cointegration rolling p<0.05 僅 8-11%
- 15m BTC 上: XGBoost v3 (15m+funding) AUC 退化到 0.52
- **結論**: 15m 不是統計模型/ML 的好目標, 須重新考慮 TF 選擇

#### 教訓 B：**同步指標 ≠ 領先指標**（Path 2 ORCA）
- MSI-Vol 相關 0.689 (強), 但預測力 (t→t+4h) = 0.164
- ORCA paper 自己是 Sharpe 1.13, 我們無法複現 = 不同資料/不同 regime
- **結論**: 同步指標可作為 filter, 不能作為 signal

#### 教訓 C：**Crypto 結構套利死路**（Path 1）
- BTC-ETH / BTC-SOL 在 crypto 沒有 cointegration
- funding rate 是唯一有結構的 alpha (已移交 FRA)
- **結論**: 不要浪費時間在 crypto spread/pairs

### 0.3 Hybrid_v3 體系當前位置
- 架構正確（regime + 雙模式）✅
- BC_combo OOS 雙驗證通過 ✅
- vs baseline 改善 +67~74% ✅
- **仍未獲利**（-2.49% OOS profit, -3.13% 2nd OOS）
- **核心問題**: 進場 alpha 不足, 架構無法彌補

### 0.4 v2.0 戰略調整

| 維度 | v1.0 (失敗路線) | v2.0 (調整後) |
|------|----------------|---------------|
| TF | 15m | 1h / 4h (15m 噪音) |
| 模型 | XGBoost / cointegration | RL 序列決策 |
| 目標 | 預測方向 (死路) | 學習進場時機 + 持倉時間 |
| Validation | OOS 2 段 | OOS 3 段 + walk-forward |
| 評估 | 單純 profit | Sharpe + Calmar + Max DD |

---

## 路徑 4: Reinforcement Learning 進場決策 ⭐⭐⭐⭐⭐ (主推)

### 4.1 為何 RL 適合此問題（v2 重新論證）

**問題本質**: 「何時進場、持倉多久、何時出場」是一個**序列決策問題**，
不是監督學習的「預測下一刻方向」問題。

| 屬性 | Hybrid_v3 當前 | RL 可解 |
|------|---------------|---------|
| 進場觸發 | 規則 (9 OR 條件) | 學出最優策略 |
| 持倉時間 | 固定 (ROI/SL/Trailing) | 動態最佳化 |
| Reward | — | Sharpe/Profit/Max DD |
| State | 當前 K 線 | 歷史 K 線 + 持倉 P&L |

**學術背書**:
- **FinRL (2020, arXiv:2011.09607)**: 金融 RL benchmark, PPO/A2C/DQN
- **Moody & Saffell (2001)**: 「Recurrent Reinforcement Learning for Trading」
- **Jiang et al. (2017)**: 「Efficient Portfolio Trading with Policy Iteration」
- **FinRL-DeepSeek (2025)**: LLM-augmented RL for trading, 驗證 reward shaping 重要性

**為何 v1.0 沒做 RL**:
- v1.0 規劃時沒 GPU 資源 → 2026-06 已有 Modal serverless GPU ✅
- 計算時間預估 1 週 → 現在 sub-agent 600s timeout 問題已用 plan-then-execute 模式解

### 4.2 RL 環境設計 (gymnasium 標準)

#### 4.2.1 狀態空間 (Observation Space)
```python
# 維度設計 (~32 維)
observation = {
    # 1. 持倉狀態 (3 dim)
    "position": 0 / 1 / -1,  # flat / long / short
    "holding_period_bars": int,
    "unrealized_pnl_pct": float,

    # 2. 價格特徵 (10 dim, normalized)
    "close_norm": float,  # (close - sma_50) / sma_50
    "high_low_range_pct": float,
    "return_1h": float, "return_4h": float, "return_24h": float,
    "volatility_4h": float, "volatility_24h": float,
    "ema_cross": float,  # (ema_12 - ema_26) / close
    "adx_norm": float,  # adx / 50
    "rsi_norm": float,  # (rsi - 50) / 50

    # 3. Regime 特徵 (5 dim, 從 Hybrid_v3 移植)
    "regime": int (0/1/2),
    "regime_1h": int, "regime_4h": int,
    "adx_consensus": float,
    "di_spread": float,  # plus_di - minus_di

    # 4. 波動率/結構 (8 dim)
    "atr_norm": float,
    "bb_position": float,  # (close - bb_lower) / (bb_upper - bb_lower)
    "bb_width": float,
    "volume_norm": float,  # volume / volume_ma_20
    "msi": float,  # ORCA cross-asset (從 Path 2 整合)
    "msi_change_4h": float,
    "funding_rate": float,
    "oi_change_4h": float,

    # 5. 持倉 P&L 特徵 (6 dim, 從 trade metadata)
    "entry_price_norm": float,
    "highest_pnl_pct": float,
    "lowest_pnl_pct": float,
    "time_to_roi_1": float,
    "time_to_sl": float,
    "drawdown_from_peak_pct": float,
}
# Total: 32 維
```

#### 4.2.2 動作空間 (Action Space)
```python
# 3 動作 (簡化版, 先驗證概念)
action = 0: FLAT (close position if any)
action = 1: LONG (open long or hold long)
action = 2: SHORT (open short or hold short, if can_short)

# 進階版 (Phase 2): 5 動作
# action = 0: FLAT
# action = 1: LONG (1x)
# action = 2: LONG (2x)  # 加倉
# action = 3: CLOSE_PARTIAL (close 50%)
# action = 4: SHORT
```

#### 4.2.3 Reward 設計（核心）
```python
# 多目標 reward (需仔細調權重)
reward = (
    delta_pnl_pct * w_pnl                # 短期 P&L
    + sharpe_increment * w_sharpe         # Sharpe 改善
    - max_drawdown_increment * w_dd       # 懲罰 DD 擴大
    - holding_time_penalty * w_time       # 懲罰過度持倉
    + roi_bonus * w_roi                   # 觸發 ROI 加分
    - overtrading_penalty * w_freq        # 懲罰過度交易
)
# 預設權重: w_pnl=1.0, w_sharpe=0.5, w_dd=2.0, w_time=0.001, w_roi=0.1, w_freq=0.01
```

**Reward shaping 陷阱** (v1.0 三大教訓):
- ❌ 純 P&L → RL 學會「all-in long」過度槓桿
- ❌ 純 Sharpe → 學會「完全 flat」無交易
- ✅ 必須 multi-objective, 用 w_dd 懲罰回撤

#### 4.2.4 Episode 設計
```python
# 一個 episode = 90 天 (約 6 個月 1h 數據)
episode_length_bars = 90 * 24  # 2160 bars @ 1h
data_start = 2025-06-01
data_end = 2026-06-01 (train)
data_oos_1 = 2026-01-01 ~ 2026-04-01 (OOS-1)
data_oos_2 = 2026-04-01 ~ 2026-07-01 (OOS-2)
data_oos_3 = 2026-07-01 ~ 2026-10-01 (forward, future)
```

### 4.3 RL 算法選擇

| 算法 | 適用 | 優點 | 缺點 | 推薦 |
|------|------|------|------|:----:|
| **DQN** | 離散動作 | 簡單, 樣本高效 | 不穩定, 高估 | ⭐⭐ |
| **PPO** | 連續/離散 | 穩定, 易調 | 樣本效率低 | ⭐⭐⭐⭐ |
| **A2C** | 連續/離散 | 快速 | 不穩定 | ⭐⭐ |
| **SAC** | 連續 | 樣本高效 | 不適用離散動作 | ❌ |
| **TD3** | 連續 | 穩定 | 不適用離散動作 | ❌ |

**首選 PPO** (Schulman 2017):
- 離散動作友善
- Clipped objective 避免 policy 劇變
- FinRL 預設算法, 文獻支援完整

### 4.4 POC 階段劃分（v2.0）

#### POC-1: 環境骨架 (Day 1-2, 1 GPU hour)
```bash
# 目標: 環境能跑通 random policy, 確認 observation/action/reward 維度
poc_p4_rl_environment.py
```
- 30-50 行
- 用 `freqtrade` 本地 feather 載入 BTC 1h 資料
- 環境封裝為 `gymnasium.Env` 子類
- 驗證 1000 step 跑完不爆
- **驗證標準**: random policy 跑 10 個 episode, return 在合理範圍 (-5% ~ +5%)

#### POC-2: PPO 訓練 baseline (Day 3-4, 2 GPU hour on Modal)
```bash
# 目標: PPO 在 BTC 1h 上能學到比 random 好的策略
poc_p4_rl_train.py
```
- 用 stable-baselines3 (PPO)
- 訓練 100K timesteps (~100 episodes)
- 對比: random policy vs PPO vs Hybrid_v3 規則
- **驗證標準**:
  - PPO 累積 reward > random policy
  - PPO trade count 介於 50-200 (避免不交易/過度交易)
  - PPO max drawdown < 10%

#### POC-3: 多幣種 generalization (Day 5-6, 3 GPU hour)
```bash
# 目標: PPO 在 ETH/SOL/BNB 也能 work (而非 BTC-only)
poc_p4_rl_multicoin.py
```
- 環境改為「幣種參數化」, 共用 policy
- 訓練: BTC + ETH + SOL 同時訓練
- 測試: 在 XRP/BNB 上 OOS
- **驗證標準**:
  - 訓練集平均 reward > 0
  - 測試集 reward > random policy
  - 沒有崩潰到全 flat

#### POC-4: Regime + MSI 整合 (Day 7-8, 2 GPU hour)
```bash
# 目標: 把 Path 2 驗證的 MSI 整合進 RL observation
poc_p4_rl_with_msi.py
```
- 從 8-asset 1h 算 MSI, 加到 observation
- 對比: 無 MSI vs 有 MSI
- **驗證標準**:
  - 有 MSI 的 PPO Sharpe > 無 MSI PPO
  - 有 MSI 的 PPO max DD < 無 MSI

#### POC-5: Live paper-trade 模擬 (Day 9-10, 1 GPU hour)
```bash
# 目標: 模擬 30 天 live paper-trade, 驗證 out-of-sample 表現
poc_p4_rl_paper_trade.py
```
- 用 2026-06-12 ~ 2026-07-12 (未來 30 天, 等時間到才跑)
- 載入 trained PPO model
- 每 1h 跑 inference, 模擬下單
- **驗證標準**:
  - Sharpe > 0.5
  - Max DD < 5%
  - 勝率 > 50%

### 4.5 計算資源需求

| POC | Local CPU | Modal GPU | 預估時間 |
|-----|-----------|-----------|---------|
| POC-1 | 1h | — | 1 hour |
| POC-2 | — | A10G 1h | 2 hours (cost: $0.50) |
| POC-3 | — | A10G 2h | 3 hours (cost: $1.00) |
| POC-4 | — | A10G 1h | 2 hours (cost: $0.50) |
| POC-5 | 30h live sim | — | realtime (next 30 days) |
| **Total** | 31h | 4 GPU hours | 1 week wall-clock | **$2.00 Modal cost** |

### 4.6 風險與緩解

| 風險 | 機率 | 影響 | 緩解 |
|------|------|------|------|
| **過擬合 (RL 最大風險)** | 高 | 高 | Walk-forward + 3 段 OOS + 限制網路容量 |
| **Reward hacking** | 高 | 高 | 多 objective + 行為檢查 (持倉時間分佈) |
| **Stationarity 假設失效** | 中 | 高 | Regime 變化時 retrain, 用 ensemble of PPOs |
| **計算時間** | 中 | 中 | 先 small-scale POC, scale up |
| **可解釋性差** | 高 | 中 | 訓練完跑 SHAP/feature importance, 跟 Hybrid_v3 比對 |

### 4.7 成功標準（v2.0 修正）

**MVP 標準 (任一達成即算 Path 4 突破)**:
- [ ] PPO 在 BTC 1h 2025-06-01 ~ 2026-06-01 訓練, OOS-1 (2026-01-01 ~ 2026-04-01) 累積 P&L > 0
- [ ] PPO 勝率 > 50%, 最大回撤 < 5%, Sharpe > 0.5
- [ ] PPO trade count 介於 50-200 (不是學會不交易)
- [ ] PPO 在 ETH/SOL OOS 也 work (不只 BTC)

**Production 標準 (額外)**:
- [ ] 3 段 OOS 都通過
- [ ] Paper-trade 30 天也通過
- [ ] 比 Hybrid_v3 BC_combo 改善 ≥ 20% (Sharpe-based)
- [ ] 模型檔 < 50MB (Freqtrade 可載入)

---

## 路徑 5: Transformer-based Sequence Model (新) ⭐⭐⭐

### 5.1 為何 v2 新增

Hybrid_v3 + RL 仍受限於「當前 observation → 動作」的 Markov 假設。
真實金融序列有**長期依賴** (e.g. 30 天前 funding rate 影響當前 regime)。

**Transformer 擅長**:
- 多 TF attention (15m + 1h + 4h 一起學)
- Long context (30 天序列)
- 跟 RL 互補 (RL 學 policy, Transformer 學 representation)

### 5.2 設計草圖
```python
# 輸入: 過去 30 天 * 96 bars/day (15m) = 2880 bars
# 架構: 
#   - Input: (batch, 2880, 32 features)  
#   - Patch embedding: split into 96 patches of 30 bars
#   - 4-layer Transformer encoder
#   - CLS token → 32-dim embedding
#   - 線性層 → action logits (3 classes)
# 模型大小: ~5M params (可塞進 50MB)
```

### 5.3 Phase 3 觸發條件
- Path 4 RL POC-2 (PPO baseline) 通過
- 計算資源允許 (transformer 訓練比 PPO 慢 5-10x)
- 預估 2 週後啟動

---

## 路徑 6: Hybrid_v3 + RL Policy Distillation (整合) ⭐⭐⭐⭐

### 6.1 概念

**Teacher**: Hybrid_v3 BC_combo 規則 (穩定但保守)
**Student**: PPO policy (學 BC_combo 行為 + 自己探索)
**Distillation**: 用 BC_combo 軌跡預訓練 PPO, 加速收斂

### 6.2 為何推薦
- v2 教訓: random init 從零學 PPO 在 1 週很難收斂
- BC_combo 已有 OOS 驗證的 trade 路徑
- Distillation 給 PPO 一個「暖啟動」, 探索空間縮小
- **預期**: 訓練時間從 100K steps 降到 20K steps

### 6.3 實作 (sketch)
```python
# 1. 跑 BC_combo 2025-06-01 ~ 2026-06-01, 收集所有 trades
bc_trades = run_bc_combo_backtest()
observations, actions, rewards = extract_trajectories(bc_trades)

# 2. 用 BC_combo 軌跡預訓練 PPO (行為克隆)
ppo.policy.pretrain(observations, actions)  # 30K steps

# 3. 在環境中 fine-tune PPO
ppo.learn(total_timesteps=20_000)  # 比 baseline 100K 少 5x
```

### 6.4 Phase 2 觸發
- POC-1, POC-2 都通過
- 預估 1 週後啟動

---

## 5. v2.0 執行計畫

### 5.1 Week 1 (6/12-6/18): Path 4 POC-1 + POC-2
| 日 | 任務 | 工具 | 預期產出 |
|----|------|------|---------|
| 6/12 (今天) | 寫 PLAN_BREAKTHROUGH_v2.md (本檔) | sub-agent A (研究) | 本檔 ✅ |
| 6/12 | 寫 poc_p4_rl_environment.py (skeleton) | execute_code (本機) | skeleton + 10 episode smoke test |
| 6/13 | 完整 env + reward shaping | sub-agent B (實作) | poc_p4_rl_env.py (200 lines) |
| 6/14 | Modal GPU 跑 PPO baseline | Modal A10G | poc_p4_rl_train.py + model.pth |
| 6/15 | 分析 PPO vs random vs BC_combo | sub-agent C (分析) | POC-2 報告 |
| 6/16-17 | 修復 + 調參 | sub-agent B | POC-2 通過 MVP |
| 6/18 | Week 1 retrospective | this file | v2.0 weekly status |

### 5.2 Week 2 (6/19-6/25): Path 4 POC-3 + POC-4
| 日 | 任務 |
|----|------|
| 6/19-20 | POC-3: 多幣種 generalization |
| 6/21-22 | POC-4: MSI 整合 |
| 6/23-24 | 跑 3 段 OOS 驗證 |
| 6/25 | Week 2 retrospective |

### 5.3 Week 3 (6/26-7/2): Path 6 (Distillation) + Path 5 評估
| 日 | 任務 |
|----|------|
| 6/26-27 | Path 6 POC: 行為克隆 + PPO 暖啟動 |
| 6/28-30 | 跑 paper-trade simulation (與 live 同時) |
| 7/1-2 | Path 5 Transformer 評估 (Go/No-Go decision) |

### 5.4 Week 4 (7/3-7/9): Production 化
| 日 | 任務 |
|----|------|
| 7/3-4 | 包裝成 Freqtrade IStrategy (RL model → onnx 推論) |
| 7/5-7 | OOS 3 段 + paper-trade 30 天驗證 |
| 7/8-9 | Go/No-Go production 決策 |

### 5.5 預期產出
- `poc_p4_rl_*.py` 系列 (5 個 POC, 共 ~1000 lines)
- `user_data/reports/multi_breakthrough_v2_p4_pocN_results_YYYYMMDD.md` (5 份報告)
- 若成功: Freqtrade `Hybrid_v3_RL_v1.py` (production candidate)
- 若失敗: `DEPRECATED_PATH4.md` (保留教訓)

---

## 6. 風險總表 (v2.0)

| 風險 | 機率 | 影響 | 緩解 |
|------|------|------|------|
| **過擬合 (RL/Transformer 共同)** | 高 | 高 | 3 段 OOS + walk-forward + 限制模型容量 |
| **Reward hacking** | 高 | 高 | 多 objective + 行為檢查 (持倉時間分佈) |
| **Stationarity 假設失效** | 中 | 高 | Regime 變化時 retrain, ensemble of PPOs |
| **計算時間** | 中 | 中 | 先 small-scale POC, scale up |
| **Modal GPU 排隊** | 中 | 中 | 預約 GPU, 離峰跑 |
| **Stable-baselines3 套件過時** | 低 | 低 | 用 v2.x stable release, 鎖版本 |
| **Pip install 環境衝突** | 中 | 中 | 用 venv, 跟 freqtrade 隔離 |
| **過早 hype → 期望管理** | 高 | 中 | 設定 MVP 標準, 過了才對外說 |

---

## 7. 為何 v2.0 機率比 v1.0 高

| 維度 | v1.0 (失敗率估 80%) | v2.0 (預估失敗率 50%) |
|------|---------------------|----------------------|
| 問題定義 | 預測方向 (死路) | 序列決策 (合理) |
| TF 選擇 | 15m (噪音) | 1h (結構) |
| 演算法 | XGBoost (監督) | PPO (強化) |
| 數據需求 | 大量標註 | 環境互動 |
| 可解釋性 | 中 | 中 (比 XGBoost 差) |
| 與現有體系整合 | 平行 (無關) | 互補 (Path 6 distillation) |
| 學術支援 | 強 (XGBoost) | 強 (FinRL) |
| 實作複雜度 | 中 | 高 |
| 計算成本 | 中 ($0) | 中 ($2) |
| 過去 session 經驗 | 12 次失敗 (XGBoost v1/v2/v3) | 全新 (RL) |

**主要差異**: v1.0 選擇 15m 監督學習 → 結構性死路。v2.0 選 1h 強化學習 → 全新問題定義。

---

## 8. 參考文獻 (v2.0 新增)

1. **Mnih et al. (2015)**. "Human-level control through deep reinforcement learning" (DQN)
2. **Schulman et al. (2017)**. "Proximal Policy Optimization Algorithms" (PPO)
3. **Moody & Saffell (2001)**. "Learning to Trade via Direct Reinforcement"
4. **FinRL (2020, arXiv:2011.09607)**. "Deep Reinforcement Learning for Automated Stock Trading"
5. **Jiang et al. (2017)**. "Efficient Portfolio Trading with Policy Iteration"
6. **FinRL-DeepSeek (2025, arXiv:2502.07389)**. "LLM-Augmented RL for Trading"
7. **Hessel et al. (2018)**. "Rainbow: Combining Improvements in Deep Reinforcement Learning"
8. **Vaswani et al. (2017)**. "Attention Is All You Need" (Transformer)
9. **Path 1-3 references**: 見 [PLAN.md v1.0](./PLAN.md) § 8

---

*Document Version: 2.0.0*
*Last Updated: 2026-06-12*
*Plan Owner: Brian (Speculari)*
*Co-Author: MiniMax-M3 (SDD Orchestrator)*
