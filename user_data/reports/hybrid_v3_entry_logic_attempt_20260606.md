# Hybrid_v3 進場邏輯修法探索 — Stop-loss 方向錯誤

**日期**: 2026-06-06
**目標**: 修進場邏輯，讓 Hybrid_v3 1 年回測從 -12.54% 改善
**結論**: 🟡 stoploss 方向錯誤，需從 regime 偵測著手

---

## 🔬 實驗記錄

### 1. 1 年 9 幣種 Baseline
- **Hybrid_v3 (現行 prod)**: -125.41 USDT (-12.54%), 823 trades, WR 63.4%
- 9 幣種 1 年 spot 市場: -35.37%
- Alpha outperform: +22.83%

### 2. 1 年進場分布 (Hybrid_v3 baseline)
| Enter Tag | Trades | WR | Profit |
|---|---|---|---|
| weak_trend (regime=1) | 769 (93%) | 64.5% | -110.76 |
| mean_rev (regime=0) | 35 (4%) | 65.7% | -6.81 |
| bb_rpb_local_uptrend (regime=2) | 10 (1%) | 30% | **+16.41** |
| 其他 BB_RPB (regime=2) | 9 | 0% | -24.25 |

**核心發現**: 93% trades 是 weak_trend (regime=1 transition)，而 regime=1 是「弱趨勢」的本質定義 → **進場有 edge (64.5% WR) 但弱趨勢環境中 trailing 觸發頻繁, avg_win 0.35% << avg_loss 2.76%**

### 3. Exit Reason 分析
- **ROI 觸發**: 645 trades (78%), avg +0.354%, total **+108.44 USDT** ✅
- **trailing_stop_loss 觸發**: 178 trades (22%), avg -2.764%, total **-233.85 USDT** ❌

**trailing 是虧損源頭**！但實查 trade 細節發現：
- 5 個 trailing trades 的 max_gain 全 < 5%
- 意味著 trailing 從未真正啟用 (trailing trigger 10.7%)
- 真正觸發的是 **custom_stoploss 的 1.5%~3% profit protection tier**
- freqtrade 把 custom_stoploss 觸發記為 "trailing_stop_loss" exit_reason

### 4. 實驗 A: Hybrid_v3_tight_trail (trailing 10.7% → 5%)
- 結果: **完全相同** -125.41 USDT
- 原因: trailing 從未啟用，trailing 參數無影響

### 5. 實驗 B: Hybrid_v3_tight_custom_sl (收緊 profit protection)
| 指標 | Baseline | Tight custom_sl | Δ |
|---|---|---|---|
| Trades | 823 | 987 | +164 |
| WR | 63.4% | 62.1% | -1.3pp |
| Profit | -12.54% | **-15.63%** | **-3.09pp** ❌ |
| Max DD | 13.00% | 15.75% | +2.75pp ❌ |
| Avg duration | 8h53m | 7h02m | -1h51m |

**收緊 custom_stoploss 反而惡化**！原因：
- 寬鬆 stoploss 給弱趨勢 trades 空間發展到 ROI 21.6% (前 50min)
- 收緊後，原本 1.5%~3% 浮盈的 trades 過早被切，錯失 ROI
- avg duration 縮短 1h51m = **流失 1.5% 浮盈 → 21.6% ROI 的機會**

---

## 🎯 真正的問題根源

### 進場邏輯問題
- **93% trades 是 weak_trend (regime=1)**: 表示 regime 偵測過度寬鬆
- ADX 20-22 threshold 讓多數時間分類為 regime=2 trending → 但進場後又很快變 regime=1
- **regime 2 (BB_RPB) 只有 19 trades 進場** → 進場條件太嚴格 (9 個 AND-combined)

### 修法方向（推薦順序）

#### 1. 放寬 regime=2 進場條件（推薦）
- 9 個 BB_RPB 條件改 OR-combined（任一滿足即可）
- 預期: regime=2 trades 從 19 增到 50-100
- bb_rpb_local_uptrend avg +3.45% 是唯一正報酬, 應放大

#### 2. 提高 ADX regime threshold
- 從 ADX 22 trending → 25 trending
- 讓 regime=1 範圍縮窄，regime=2 更純
- 預期: weak_trend 769 trades 降到 400-500

#### 3. 為 regime=1 設計專屬出場
- weak_trend 進場後用更寬鬆 ROI (前 30min 15%, 30-90min 5%)
- 短持倉 weak_trend (平均 < 4h) 配合短 ROI

#### 4. 改進 regime 偵測算法
- 不只用 ADX，加入趨勢斜率 (EMA200 1h 斜率)
- 或用 HMM (Hidden Markov Model) 自動偵測 regime 轉換

---

## 📊 為何不繼續修 stoploss

| 修法 | 預期 | 實際 | 結論 |
|---|---|---|---|
| 收緊 trailing (10.7%→5%) | 減少 trailing 觸發 | 無影響（從未觸發） | ❌ |
| 收緊 custom_sl (1.5%→0.5%) | 減少 avg_loss | -3.09pp 惡化 | ❌ |
| 放寬 custom_sl (0%→-2%) | 增加 avg_win | 未測 | 可能但非根本 |

**真正的 alpha 必須從進場邏輯來**:
- 讓 regime=2 (BB_RPB) 進場更多 → avg +3.45% 高品質
- 減少 regime=1 過度進場 → 避免弱趨勢 trailing 觸發
- 提升 regime=0 (mean_rev) 進場品質 → 35 trades 是樣本太少

---

## 📁 產出

- `user_data/strategies/math_based/multi_tf_regime_v1/Hybrid_v3_tight_trail.py` (實驗 A, 失敗)
- `user_data/strategies/math_based/multi_tf_regime_v1/Hybrid_v3_tight_custom_sl.py` (實驗 B, 失敗)
- `user_data/strategies/math_based/multi_breakthrough_v1/analyze_bt.py` (通用 backtest 分析工具)
- `user_data/config/backtest_1y_tight_trail.json`, `backtest_1y_tight_custom_sl.json`
- 本報告

## 🎬 下一步

| 選項 | 動作 | 預期 | 時間 |
|---|---|---|---|
| **1A** | Hybrid_v3_or_bb_rpb.py (regime=2 條件改 OR) | regime=2 trades 5x, 改善 2-5% | 30-60 分 |
| **1B** | Hybrid_v3_tight_regime.py (ADX 22→25) | weak_trend -50%, 改善 1-3% | 30-60 分 |
| **1C** | Hybrid_v3_combo.py (1A + 1B) | 改善 3-8% | 60-90 分 |
| **2** | 部署 Hybrid_v3_MSI v1 dry-run | live 累積 | 0 |
| **3** | 完全新設計 regime 偵測 (HMM) | 根本突破 | 數小時 |

**我的推薦**: **1A**（regime=2 OR 條件），理由：
- 進場邏輯的核心 9 個 NFI 條件太嚴
- bb_rpb_local_uptrend avg +3.45% 是當前最賺
- OR-combined 改動小 (1 行程式碼)
- 預期 1 年回測從 -12.54% 改善到 -8%~-10%

請選？
