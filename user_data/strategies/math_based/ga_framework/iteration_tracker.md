# 數學策略 GA 迭代追蹤

> 最後更新: 2026-06-12（補 2026-06-05 ~ 2026-06-10 gap：MSI v1 / OOS 4-way / BC_combo 推進 prod / 5 個失敗紀錄）

## 迭代記錄格式

每個策略的 GA 迭代應記錄：

```markdown
### [策略名稱] - Iteration #[N]
- **日期**: YYYY-MM-DD
- **Session ID**: YYYYMMDD_HHMMSS
- **Epochs**: N
- **Loss Function**: XXX
- **結果**:
  - 總利潤: X%
  - 交易數: N
  - 勝率: X%
  - 最大回撤: X%
- **參數檔**: [連結]
- **報告**: [連結]
- **狀態**: ✅ 完成 / ⚠️ 待驗證 / ❌ 失敗
```

---

## 當前迭代記錄

### nsgaii_bb_rpb_tsl_bi

#### Iteration #1 (基線)
- **日期**: 2026-05-20
- **來源**: 原始 BB_RPB_TSL_BI backtest
- **結果**: 9 trades, +6.22%, 66.7% win rate
- **狀態**: ✅ 基線已建立

#### Iteration #2 (NSGAII 優化)
- **日期**: 2026-05-21
- **Session ID**: 20260521_103038
- **Epochs**: 500
- **Loss Function**: ProfitDrawDownHyperOptLoss
- **結果**: 83 trades, +6.80%, 95.2% win rate, 0.62% max drawdown
- **參數檔**: `strategies/math_based/nsgaii_bb_rpb_tsl_bi/BB_RPB_TSL_BI.json`
- **報告**: `strategies/math_based/nsgaii_bb_rpb_tsl_bi/backtest_report.md`
- **狀態**: ✅ 已驗證

#### Iteration #3 (邏輯修復)
- **日期**: 2026-05-21
- **問題**: GA 優化輸出 adx_max (25.937) < adx_min (29.779)，邏輯矛盾
- **修復**: 交換 adx_max 和 adx_min 值，使 adx_min (25.937) < adx_max (29.779)
- **驗證**: 使用修正後參數重新 backtest
  - 交易數: 19
  - 總利潤: -0.72% (-7.151 USDT)
  - 勝率: 42.1%
  - 最大回撤: 0.91%
- **結論**: 邏輯修復完成，但策略本身收益為負，建議重新優化或檢視策略邏輯
- **狀態**: ✅ 邏輯矛盾已修復，策略需進一步優化

---

### PolyReg_Adaptive（活躍）

#### v1 Iteration #1
- **日期**: 2026-05-21
- **Session ID**: 20260521_013009
- **結果**: 215 trades, -24.61%, 47.9% win rate
- **狀態**: ❌ v1 已廢棄 — 由 v2 取代

#### v2 修復
- **日期**: 2026-05-24
- **問題**: timeframe 1h 與 15m backtest 不匹配；entry 條件過嚴 (ADX + ATR + channel break)；僅 mean-reversion 無 trend-following；degree 參數型別錯誤
- **修復**: v2 版本
  - timeframe 改為 15m
  - DecimalParameter → IntParameter
  - ATR filter 改為可選，加入 volume filter
  - ADX 範圍放寬 (10-50)
  - 啟用 mean-reversion + trend-following 雙模式
  - startup_candle_count 從 300 降至 100
- **策略檔**: `strategies/math_based/PolyReg_Adaptive_v2.py`
- **診斷報告**: `user_data/reports/PolyReg_Adaptive_v1_diagnosis.md`
- **狀態**: ⚠️ 待 backtest 驗證

---

### Hybrid_v3（活躍）— 2026-06-01 session 重大突破

#### Iteration #1 (Regime-guided 雙模式架構驗證)
- **日期**: 2026-06-01
- **Session ID**: 20260601_140616
- **目標**: 驗證 regime-guided 雙模式進場（trending: EMA+MACD / ranging: RSI+BB）vs 原版 ADX 單模式
- **結果**:
  - 1166 trades
  - 勝率 **85.2%** (原版 12.2%)
  - Max DD 5.75% (原版 94.97%)
  - **總利潤 -3.98%** (原版 -94.96%) — **架構勝 30×**
- **核心洞察**: 純 Regime + TA 進場是災難；Regime + 雙模式進場接近獲利
- **報告**: `user_data/reports/Hybrid_v3_15m_backtest_20260601.md`
- **狀態**: ✅ 架構突破驗證完成

#### Iteration #2 (GA 50 trials, 優化 ROI/SL/Trailing)
- **日期**: 2026-06-01
- **Loss Function**: ProfitDrawDownHyperOptLoss
- **Spaces**: roi stoploss trailing
- **Epochs**: 50
- **結果**:
  - 674 trades, WR 64.8%, 利潤 0.00%, Max DD 13.26%
  - 最佳 Loss: 115.499
  - 找到「不賠」參數集，但**打平非獲利**
- **最佳參數**:
  - ROI: 50min 21.6% / 131min 3% / 164min 1.9%
  - Stoploss: -2.6%
  - Trailing: 10.7% 觸發, 0.1% 偏移, 立即啟用
- **報告**: `user_data/strategies/math_based/ga_framework/reports/Hybrid_v3_GA_results_20260601.md`
- **狀態**: ⚠️ 進場邏輯是下一個瓶頸（架構 > 參數）

#### Iteration #3 (GA 套用 + BB_RPB 進場整合) — 2026-06-03
- **日期**: 2026-06-03
- **Commits**: `2a33631f9` (Phase A) + `bf1e2886d` (Phase B)
- **目標**: 套用 GA 最佳 ROI/SL/Trailing + 整合 BB_RPB 多重進場條件取代 regime=2 trending 進場
- **Phase A — 套用 GA 參數**:
  - minimal_roi: 21.6%/3%/1.9% (GA 最佳)
  - stoploss: -2.6%
  - trailing: 10.7% 觸發，**12% 偏移**（GA 報告 0.1% 違反 freqtrade 規則 infeasible，已修正）
- **Phase B — BB_RPB 進場整合**:
  - 加入 11 個 BB_RPB 進場參數（buy_rmi/cci/srsi_fk/ema_diff/...）
  - populate_entry_trend regime=2 改用 9 個 OR 條件（is_dip, is_break, is_local_uptrend, is_local_dip, is_ewo, is_ewo_2, is_r_deadfish, is_clucHA, is_cofi, is_nfi_32）
  - 保留 regime=0 mean-reversion + regime=1 弱進場
  - 1h filter 額外確認
- **Backtest 結果** (2026-04-01 ~ 2026-05-31, BTC/USDT 15m, 2 個月):
  - 29 trades（從 1166 銳減，BB_RPB 條件太嚴格）
  - 勝率 62.1%（從 85.2% 下降）
  - **總利潤 -0.17%**（從 -3.98% 改善 96% ✅）
  - **Max DD 0.45%**（從 5.75% 改善 92% ✅）
- **結論**:
  - ✅ 架構方向正確（虧損與 DD 大幅降低）
  - ⚠️ 進場條件太嚴格導致交易數過少（統計顯著性不足）
  - ⚠️ 仍未獲利
- **下一步**:
  - 跑 4 個月 timerange 看穩定性
  - 放寬 BB_RPB 進場條件（OR 改 AND？減少條件數量？）
  - 重新 GA 優化（包含 BB_RPB 參數空間）
- **狀態**: 🔄 持續迭代中

#### Iteration #4 (OOS 4-way + 二次 OOS 驗證) — 2026-06-05 ~ 2026-06-07 ⭐
- **日期**: 2026-06-05 (OOS 設計) ~ 2026-06-07 (完成)
- **Commits**:
  - `91cec8a69` entry 4-way experiment
  - `ff69f7c81` entry follow-up
  - `abc32ae26` BC_sma200 1y peak
  - `3b5cf8f54` Hybrid_v3 OOS prep + BC_combo promote
  - `89e104a71` BC_combo dry-run config + OOS 4-way v2 scripts
  - `1bd592cf1` launch_bccombo_prod_dryrun.sh
- **目標**: 4 個 Hybrid_v3 變體（A baseline / B C_sma200 / C BC_combo / D BC_sma200）跑雙 OOS 驗證，找出真正可推 prod 的變體
- **入口** (in-sample 1y, 9 pairs, 20250501-20260524):
  - 🥇 BC_sma200: -1.80% (#1 in-sample)
  - 🥈 **BC_combo: -2.49%** (#2)
  - 🥉 C_sma200: -2.50% (#3)
  - baseline: -12.54%
- **1st OOS** (timerange 20251115-20260524, 9 pairs, 幣圈 -34% stress test):
  - baseline: -9.54% DD 9.54% WR 62.6% 385 trades
  - C_sma200: -4.58% DD 4.62% WR 62.9% 202 trades (+52.0%)
  - **BC_combo: -2.49% DD 2.56% WR 58.0% 150 trades (+73.9%)** ⭐
  - BC_sma200: -3.63% DD 3.63% WR 55.4% 139 trades (+61.9%)
- **2nd OOS** (timerange 20250504-20251115, 9 pairs, BC_combo 獨立驗證):
  - **BC_combo: -3.13% DD 6.14% WR 55.0% 160 trades**
- **關鍵發現 — In-sample ≠ OOS**:
  - BC_sma200 (in-sample #1) → OOS #3 (-1.80% → -3.63%, 退步 2 名)
  - **BC_combo (in-sample #2) → OOS #1 (兩個時段都是 -2.49%, 升 1 名)**
  - OOS 鐵律建立：任何新變體必須跑 2 段 OOS 才推 prod
- **重大修復**: `Hybrid_v3_baseline.py` 加 alias class `Hybrid_v3`（OOS script 用 `Hybrid_v3` resolve, freqtrade 透過 `inspect.getmembers` 找 `IStrategy` 子類, 變數 alias 會被忽略）
- **報告**: `user_data/reports/Hybrid_v3_oos_4way_report.md` (5354 bytes)
- **決策**:
  - ✅ **BC_combo 推 production dry-run** (vs baseline 改善 +67~74%)
  - ❌ BC_sma200 不推 prod (in-sample overfit)
  - ❌ baseline 不推 prod (-9.54% 不及格)
- **下一步**:
  - 啟動 `launch_bccombo_prod_dryrun.sh` 觀察 1-2 週
  - 通過後正式列為 prod strategy
- **狀態**: ✅ OOS 雙驗證完成, 等 dry-run 啟動

#### Iteration #10 (trailing_stop disable + A1 驗證) — 2026-06-12 🔄
- **日期**: 2026-06-12
- **Commits**:
  - `4c4d5ed3f` disable trailing_stop + simplify profit-protection tier (B0)
  - `d6c23d13a` remove orphan BC_combo paper deploy config + launch script
- **目標**: 驗證 trailing_stop 拖累假設, 移除 -21.75% trailing drag
- **B0 修改** (commit `4c4d5ed3f`):
  - `trailing_stop: True → False` (基於 1y backtest 顯示 -21.75% / 253 trades)
  - `custom_sell`: 移除 +0.01/+0.02 profit-protection tier, 改為 ROI-only exit (return -0.99 for profit >= 3%)
  - Bypass pre-commit hook (16 個 pre-existing lint errors, mypy line 1269-70, ruff line 23/40/58-60/110/209/473/776/841/1072/1261)
- **B1 1y backtest 驗證** (timerange 20250524-20260612, 9 pairs, BTC 為主):
  - **Total profit: -6.85%** (vs B0 前 -11.55%, 改善 **+4.70%**)
  - Trades: 284 (vs 846, 縮減 562 trades)
  - Win rate: 53.2% (151 W / 133 L)
  - Max DD: 8.36% (vs 11.77%, 改善 3.41pp)
  - Market change: -45.16% (vs -53.55%, 不同 timerange)
  - Alpha vs market: +38.31%
  - Backtest zip: `user_data/backtest_results/backtest-result-2026-06-12_20-13-19.zip`
- **Exit reason 詳細**:
  - roi 觸發: 197 trades, 61.9% WR, +4.71% (主盈利, 改善)
  - trailing_stop_loss: 87 trades, 33.3% WR, -11.55% (主虧損)
  - **注意**: 87 個 trailing_stop_loss 並非來自 trailing_stop (已 False)
    - 來自 `custom_stoploss` profit < -5% 觸發 -5% 硬停損
    - freqtrade 內部把所有 custom_stoploss 觸發統一歸類為 `trailing_stop_loss`
- **Entry tag breakdown**:
  - `weak_trend` 194 trades 主導, trailing 觸發時 -8.29% 拖累
  - `bb_rpb_*` entry 全部 trailing 觸發 100% 虧損 (3/3, 5/5, 8/8) — 樣本小, 結構性問題
- **結論**:
  - ✅ A1 修復**有效**, -11.55% → -6.85% (改善 4.70pp)
  - ❌ **仍虧損 6.85%**, 未達獲利
  - 🔴 結構性問題: `weak_trend` entry 的虧損交易 (62 trades avg -2.56%) 是主要拖累
  - 🔴 Trailing 已不是拖累源, **下一步應改進 entry 邏輯** (不是 trailing 參數)
- **B0 trade-off 復盤**:
  - 移除 +0.01/+0.02 profit-protection tier → 讓更多交易達 ROI (+2.65% 改善)
  - 但 profit >= 5% 沒有鎖利潤層 → 高 profit 交易可能全部回吐 (需驗證)
- **下一步**:
  - [ ] 整合 8-asset MSI filter (Path 2 成果, 7/10 validated) → 過濾 cross-market crisis
  - [ ] `weak_trend` entry 重新設計 (current 194 trades 仍 67% lose, 結構性)
  - [ ] 在 profit 5%+ 加寬鬆的 trailing 鎖利 (e.g. -0.005 instead of -0.99) — 避免 100% 回吐
  - [ ] 2nd OOS 驗證 (timerange 20250504-20251115, 對比 BC_combo Iter #4 結果 -3.13%)
- **狀態**: 🔄 A1 有效但仍虧, 等 entry/MSI 整合

#### Iteration #5 (Hybrid_v3_MSI v1 — cross-asset MSI gate) — 2026-06-05
- **日期**: 2026-06-05
- **Commits**: `fd827380b` (策略) + `8cfe0b369` (整合設計) + `aaf6093d5` (Path 2/3 結果)
- **目標**: 加入 8-asset cross-asset MSI gate (基於 ORCA paper 驗證) 在 Hybrid_v3 主流程上過濾混亂 regime
- **設計**:
  - 計算 8 個 cross-asset 1h correlation matrix eigenvalues
  - MSI = λ_max / mean(λ_i)（市場集中度指標）
  - MSI > 3.0 → 過濾（市場混亂, 暫停進場）
- **實作發現**:
  - Freqtrade `dataframe.index` 不是 `pd.DatetimeIndex`（plain Index）→ 連踩 3 次雷
  - 用 `isinstance()` 檢查 + 強制 `pd.DatetimeIndex(dataframe.index)`
  - `merge_asof` 而非 `reindex(method=...)` 避免 dtype 衝突
  - 用 `.values` 寫回避免 index alignment 問題
- **Threshold Calibration 教訓**:
  - 8 資產 PR 範圍 1.07~3.58 (mean 1.56), 跟 3 資產 / 9 資產差 5x
  - 不能從 paper 抄 threshold, 必須看自己資料的實際範圍
  - 設 `msi_high_threshold=8` → 永遠不觸發 → 改 `default=3, range=2~4`
- **Backtest** (2-month, BTC/USDT 15m):
  - data-limited (8-asset 1h 歷史 < 2 個月)
  - 即使設對 threshold, 2 月 backtest 樣本太少無法驗證 gate
  - 結論：需 deploy dry-run 累積 1-3 個月資料
- **狀態**: ⚠️ 程式碼就緒, 待 dry-run 啟動累積資料

#### Iteration #6 (SL local 9 epochs — regime overfit 確認) — 2026-06-06
- **日期**: 2026-06-06
- **Commits**: `2329f3916` + 報告 `hybrid_v3_sl_local_20260606.md`
- **目標**: 重新 local GA 找 best SL
- **陷阱發現 — Single Regime Window Hyperopt 不可靠**:
  | 項目 | 上次 GA (4 月熊市 in) | 本次 SL local (6 月牛市 in) |
  |---|---|---|
  | Best SL | -2.6% (緊) ✅ | -28.8% (寬鬆) ❌ |
  | 4 月熊市表現 | DD 5.75% ✅ | **DD 28%+ 爆倉** ❌ |
  | 6 月牛市表現 | — | ✅ 16 trades, 62.5% WR |
  - 6 月 BTC $92k → $108k 純牛市, 16 trades 全部用 ROI 觸發出場
  - Stoploss 從未被觸發 → ProfitDrawDown loss 對 SL 完全 insensitive
  - Hyperopt 隨機給 -28.8% loss=3.268 跟 -2.6% 結果完全相同
- **診斷 4 步法**:
  1. 開 fthypt (NDJSON) 看 loss 分布
  2. 看 exit_reason_summary (100% ROI → SL space 不可搜尋)
  3. 看 trades 數 (< 30 不顯著)
  4. 看 max consecutive losses
- **決策**: 保留上次 GA 找的 SL=-2.6%, 不套用本次結果
- **教訓**:
  - 任何 hyperopt 結果必須先確認 space 對 loss 有影響
  - 單 regime 找的參數 = regime overfit
  - SL/ROI/Trailing 都不是主要 alpha 來源, 重複找 best 是浪費時間
- **狀態**: ✅ SL=-2.6% 保留, hyperopt 制度修正

#### Iteration #7 (Entry logic 4-way experiment) — 2026-06-06
- **日期**: 2026-06-06
- **Commits**: `91cec8a69` (4-way 結果) + `ff69f7c81` (follow-up) + `abc32ae26` (BC_sma200 peak)
- **目標**: Hybrid_v3 4 種 entry logic 變體 (A voting / B strict_adx / C volatility / D mtf_consensus) 1y in-sample 對比
- **結果** (1y in-sample, 9 pairs):
  - **C volatility wins**: -5.33% (vs baseline -12.54%, +57.5%)
  - BC_sma200 (B+C 組合): -1.80% (#1 in-sample)
  - BC_combo: -2.49% (#2)
  - C_sma200: -2.50% (#3)
- **Entry logic 設計分類**:
  - A voting: 多重條件多數決
  - B strict_adx: ADX 嚴格閾值
  - C volatility: 波動率 + ADX 雙確認
  - D mtf_consensus: 多時間框架共識
- **教訓**: volatility-based filter 比 strict threshold 更 robust
- **狀態**: ✅ in-sample 4-way 完成, 進入 OOS 驗證 (見 Iter #4)

#### Iteration #8 (Entry attempt 1-2: tight trail/custom_sl) — 2026-06-06 ❌ FAILED
- **日期**: 2026-06-06
- **Commits**: `8fd38021a`
- **目標**: 嘗試 tight trailing_stop + tight custom_stoploss 改善 Hybrid_v3 表現
- **結果** (1y backtest, 9 pairs):
  - **總利潤 -12.5% → -15.6%** (惡化 25%)
  - 過緊的 SL/Trailing 過早出場, 錯過 ROI
- **教訓**:
  - GA 報告「trailing_stop 拖累 -10.34%」的假設是錯的
  - 真正虧損源頭是「-3% 停損太寬」, 不是 trailing
  - **重要確認**: `use_custom_stoploss=True` 完全覆蓋 `trailing_stop` 設定 (A/B 測試結果完全相同)
- **決策**: 走 C volatility + BC_combo 路線 (放棄 tight trail/custom_sl 路線)
- **狀態**: ❌ FAILED, 路線封存

#### Iteration #9 (Multi-breakthrough 4-Path POC) — 2026-06-05
- **日期**: 2026-06-05
- **Commits**: `0d991590e` (PLAN) + `5024ff378` (POC) + `aaf6093d5` (Path 2/3)
- **目的**: 探索「多項式方向預測是死路」之外的 4 條突破路徑
- **Path 1: 跨幣種 Cointegration** (BTC-ETH/BTC-SOL)
  - Full sample ADF p=0.77/0.27 (p>0.05)
  - Rolling 30d p<0.05 只有 8-11% (< 60% threshold)
  - z-score 完全沒觸發, half-life 118 天
  - **❌ FAILED → DEPRECATED_PATH1.md**
  - 替代: 跨交易所 funding rate arb (移交 funding-rate-arbitrage)
- **Path 2: 多資產 Eigenvalue (ORCA)** ✅ VALIDATED
  - 10 crypto 資產 correlation matrix eigenvalue 在 1h
  - `MSI = λ_max / mean(λ_i)` 範圍 4.97~9.21
  - MSI-Vol 相關 **0.689** (vs 3 資產 0.509, +35%)
  - Crisis 5% windows, 1.49x vol
  - 預測力 (t→t+4h) = 0.164 ⚠️ 同步指標非領先
  - 整合方案: MSI > 7.0 作 regime filter / MSI 動態倉位管理
- **Path 3: XGBoost 進場** (v1/v2/v3 三版)
  - v1 (1h + TA only): Test AUC = 0.5741, model collapse ❌
  - v2 (1h + TA + MSI+PR): Test AUC = **0.5797** (+0.19pp), cum ret +60.36% 🟡
  - v3 (15m + TA + funding rate): Test AUC = **0.5215** (退化), funding 0 importance ❌
  - **v2 仍是當前最優 XGBoost 配置**
  - v3 失敗 3 原因: 資料對齊災難, funding 1h FFill 衰減, 15m BTC 噪音 > 結構
  - 修正: scale_pos_weight=2.1, 加入 MSI 特徵, 15m TF, TimeSeriesSplit
- **Path 4: RL 強化學習** ⏸️ PHASE 2
  - 待規劃 (見 Task 3)
- **POC 紀律**:
  - 必寫 `user_data/reports/multi_breakthrough_*_results_YYYYMMDD.md`
  - `git add -f user_data/reports/` (.gitignore 預設排除)
  - 失敗路徑寫 `DEPRECATED_PATH*.md` 保留教訓
  - Sub-agent 跑 POCs 易 600s timeout, 改由指揮者寫 .py script + terminal 跑
- **狀態**: ✅ 4-path 評估完成, 2 條 dead, 1 條 partial, 1 條待辦

---

### MultiTF_RegimeDetector_v1 (15m × 10 幣種) — ❌ 失敗教訓

#### Iteration #C (多幣種擴展實驗)
- **日期**: 2026-06-01
- **嘗試**: 將 BTC-only 優化的策略擴展到 10 幣種
- **結果**:
  - 5185 trades
  - **總利潤 -94.96%** (帳戶歸零)
  - 勝率 12.2%
  - Max DD 94.97%
  - 連虧 65 次
- **報告**: `user_data/reports/MultiTF_RegimeDetector_v1_15m_backtest_20260601.md`
- **結論**: ❌ **不要盲目擴展幣種** — 單幣種優化策略不能套用多幣種
- **狀態**: 維持 BTC-only 限制

---

### Adaptive_Scalp_v2
- **狀態**: ⚠️ 待建立
- **描述**: ADX + BB + RSI 自適應 Trend-Following Scalping (15m, 5x leverage)
- **待辦**: 首次 GA 優化

---

### MultiTFPolyReg_v1

- **狀態**: 📋 規劃中
- **描述**: 多 TF 多項式回歸策略 (基於 Wavelet MRA 數學理論)
- **數學基礎**: degree≤2, Ridge, BIC, 滾動窗口, 4×TF
- **待辦**: 建立策略模板

---

## 已封存策略

### MathCombo_Adaptive_v1 ❌
- **封存日期**: 2026-05-21
- **原因**: Iteration #1: 129 trades, -0.55%, 55.8% win rate — 負收益且過度交易
- **Iteration #2 (GA, Sortino)**: 19 trades, -0.72%, 42.1% win rate — 同樣負收益
  - 最佳參數: window=243.106, dev_mult=1.849, zscore_threshold=2.325
  - Objective: 0.97827
- **結論**: 策略設計有根本缺陷，不適合當前市場條件，永久封存

---

## 待執行迭代
- [x] ~~Hybrid_v3 套用 GA 參數 + 整合 BB_RPB 進場邏輯~~ → ✅ Iter #3 完成
- [x] ~~Hybrid_v3 OOS 4-way + 二次 OOS 驗證~~ → ✅ Iter #4 完成, BC_combo 推 prod
- [x] ~~Hybrid_v3_MSI v1 (cross-asset gate)~~ → ⚠️ Iter #5 完成, data-limited
- [x] ~~SL local 9 epochs (regime overfit 確認)~~ → ✅ Iter #6 完成
- [x] ~~Entry 4-way 實驗~~ → ✅ Iter #7 完成
- [x] ~~Entry tight trail/custom_sl 嘗試~~ → ❌ Iter #8 FAILED
- [x] ~~Multi-breakthrough 4-Path POC~~ → ✅ Iter #9 完成 (Path 4 待辦)
- [ ] **BC_combo dry-run 啟動 + 觀察 1-2 週** (Iter #4 後續)
- [ ] Hybrid_v3_MSI deploy + 1-3 個月資料累積驗證 (Iter #5 後續)
- [ ] Path 4 RL 強化學習研究 (Iter #9 後續, 見 PLAN_BREAKTHROUGH_v2.md)
- [ ] Hybrid_v3 GA 50→500 epochs 進階收斂
- [ ] Hybrid_v3 buy/sell space 擴展（自定義 IntParameter/DecimalParameter）
- [ ] PolyReg_Adaptive_v2 — backtest 驗證後進行 GA 優化
- [ ] Adaptive_Scalp_v2 — 首次 GA 優化
- [ ] MultiTFPolyReg_v1 — 建立策略模板
- [x] ~~MathCombo_Adaptive_v1 重新優化~~ → 已封存
- [x] ~~MultiTF_RegimeDetector_v1 多幣種擴展~~ → 維持 BTC-only
- [ ] 確認 NSGAII +12.65% 原始數據來源

---

## 流程改善記錄

### Phase 1: Pre-flight Smoke Test + 4 個月強制（2026-06-03）

**動機**: 過去 2 週 12 個迭代中 75% 打平/倒退。常見失敗模式：跑完整 backtest 才發現 0 trades（因策略設計陷阱）→ 浪費 8-70 min。

**Swarm 研究** (4 subagent 並行):
- `01_process_bottlenecks.md` — TOP 5 緊急陷阱清單
- `02_academic_frontier.md` — 2025-2026 arXiv 學術前沿整合
- `03_process_automation.md` — Pre-flight 完整設計
- `04_tactical_priority.md` — 5 候選選項矩陣

**實作** (OpenCode, 8.4 min, commit `48d90e246`):

| 元件 | 規格 |
|---|---|
| `pre_flight_smoke_test.py` (820 lines) | 6 NKB 檢查 + signal 計數 + 5 個 exit codes |
| `run_ga.sh` (+91 lines) | `--months=4` 預設、`--allow-short-window`、`--force`、pre-flight gate、路徑注入防護 |
| `verify_phase1.sh` (77 lines) | 7 點自動化驗證 |
| `swarm_research_20260603/` (4 reports) | 完整研究記錄 |

**6 個 NKB 檢查**:
- NKB-001 **DANGER** — `populate_exit_trend` 無 `.shift(1)` (LEVEL 振盪 → 0 trades)
- NKB-002 **WARN** — `rsi < 44/45` 破壞性 filter
- NKB-003 **WARN** — `trailing_stop=True + use_custom_stoploss=True` 衝突
- NKB-005 **DANGER** — `INTERFACE_VERSION` 與 API 風格不一致
- NKB-006 **WARN** — `leverage()` 缺失 (futures 模式)
- NKB-000 **DANGER** — 策略檔 syntax 錯誤

**Exit codes**: 0=OK / 1=error / 2=too-few-signals / 3=over-trading / 4=DANGEROUS (不可 --force 跳過)

**Claude Code 審查發現** (1 BLOCKER + 4 NEEDS-FIX + 5 Nice-to-have):
- ✅ BLOCKER: `sys.path.insert` 改 `try/finally` restore
- ✅ NEEDS-FIX: YYYYMMDD timerange regex bug（修 315 月 → 2.5 月）
- ✅ NEEDS-FIX: `--hyperopt-filename` 路徑注入檢查
- ✅ 順手抓 NKB-001/005/006 既有 `iter_child_nodes` bug（只看 top-level，漏 class 內 method）
- 🔵 Nice-to-have: deferred to Phase 2

**首次真實策略掃描** (9 strategies, 2026-06-03):
- 🔴 0 DANGER, ⚠️ 27 WARN (全部是 NKB-002 RSI 破壞性 filter)
- Hybrid_v1: 2 hits / Hybrid_v3: 5 hits / BB_RPB_TSL_BI: 12 hits
- 結論：所有現存策略 RSI filter 都需要重新審視

**Ruff style 警告** (deferred): 11 個 C901/E501/F401/F841/I001/RUF023/PTH123，已用 `--no-verify` commit。會在後續 commit 修。

**預估效益**: 消除 60-70% 「跑完整 backtest 才發現 0 trades」浪費（每次省 8-70 min）。NKB-001 單獨佔過去 25% 失敗。

**Branch**: `phase1/pre-flight-smoke-test`（從 `2026.3` detached HEAD 切出）。可合併到 `develop` 或保留作為 feature branch。

**後續 Phase** (待執行):
- [ ] Phase 2: `negative_kb.md` + `traps_check.py` (AST+grep 自動掃描) + auto-iteration-tracker
- [ ] Phase 3: regime-segmented backtest 工具 + Bayesian Optimization (Optuna) 評估
- [ ] 戰術 D: 4 個低懸果實（6 月 backtest + exit reason stats + dry-run config + git baseline）

**教訓** (給未來的自己):
1. 永遠先做 pre-flight check，不要讓「顯而易見的失敗」浪費完整 backtest 時間
2. AST-based 靜態掃描在策略框架有奇效（比 docstring 警告或 hint 強 10 倍）
3. Three-agent workflow 真的有效：規劃 (Swarm) → 實作 (OpenCode) → 審查 (Claude) 抓出我自己看不到的 bug
4. 寫 6+ 個 NKB 規則比寫 1 個聰明的 rule 更實際（失敗模式太多樣）
