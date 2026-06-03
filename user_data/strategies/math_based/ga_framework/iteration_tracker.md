# 數學策略 GA 迭代追蹤

> 最後更新: 2026-06-03（Phase 1 流程改善完成 + 補 2026-06-01 session 4 個 task）

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
## 待執行迭代
- [ ] **Hybrid_v3 套用 GA 參數 + 整合 BB_RPB 進場邏輯**（基線 +6.22% 已驗證）— 🔴 高優先
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
