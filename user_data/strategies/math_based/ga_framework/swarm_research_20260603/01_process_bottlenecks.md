# 流程瓶頸診斷報告

**日期**: 2026-06-03
**分析對象**: 數學策略 GA 迭代流程（過去 2 週,2026-05-20 ~ 2026-06-03）
**分析範圍**: 整個迭代工作流（非單一策略）

---

## 1. 反覆失敗的迭代方向

| 方向 | 出現次數 | 失敗模式 | 教訓 |
|------|----------|----------|------|
| **多幣種擴展（1→10）** | 2 次（5/29 多幣種測試 + 6/1 MultiTF_RegimeDetector_v1）| 交易數 234→5185,虧損 -3.11%→**-94.96%**,勝率 39.7%→12.2% | BTC 優化策略不適用其他幣種,15m 噪音太大 |
| **Polynomial direction prediction** | 持續出現（5/21 v1 215 trades -24.61%,5/24 v2 修復中,MathCombo 封存） | SNR≈0.02 等於噪音,5m 準確度 47.8-49.1% | 多項式迴歸只能做 regime + ATR,**不能預測方向** |
| **完整複雜 entry 條件直接整合** | 2 次（Hybrid_v3 Iter #2 9 條件 OR,Iter #3 BB_RPB 9 OR） | 1166→29 trades（-97.5%）,利潤雖改善但樣本不足 | 應先單條件 smoke test 確認觸發率,再組合 |
| **2 個月 backtest 驗證** | 4+ 次（幾乎所有 GA iteration 都跑 2 個月）| 顯示 -0.17%「進步」,跑 4 個月變 -0.90%（熊市）| 4 個月為最低標準,需含至少一次體制切換 |
| **GA 找「打平」參數** | 1 次明確（Hybrid_v3 Iter #2 Loss 115.499, 0.00% profit）| Loss 函數能找到零虧損但無法獲利 | ProfitDrawDownHyperOptLoss 不夠,需 Sharpe + Expectancy |
| **close > EMA filter** | 1 次嘗試（6/3 Iter #4） | 加 close > ema_50/100/20 全部無效（73/-0.90% 數值不變）| regime=2 已隱含過濾 downtrend,filter 重複 |

---

## 2. 浪費時間的環節

| 環節 | 平均耗時 | 浪費原因 |
|------|----------|----------|
| **完整 backtest 跑完才發現 0/29 trades** | ~8-12 min/次 | 沒有 pre-flight smoke test。Hybrid_v3 Iter #3 跑 2 個月才發現 OR 9 條件過嚴。**應在 backtest 前先計算 condition_trigger_count** |
| **NSGAII 500 epochs 找打平參數** | 70 min/次 | 架構問題不可能靠參數解決。應先驗證「架構本身能否在理想參數下獲利」,再做 GA |
| **邏輯矛盾（adx_max < adx_min）修好後仍負收益** | ~15 min/次 | 修復了格式錯誤但沒發現策略本身設計錯誤。應在交換值之前先檢查策略邏輯邊界 |
| **多幣種 backtest 浪費 7+ 分鐘 × 10 幣種** | 30+ min | BTC-only 是已知結論,還是要跑才確認。應在跑 backtest 前檢查策略文檔的幣種限制 |
| **2 個月 vs 4 個月 backtest 結果矛盾** | 4-8 min × 2 | 跑完 2 個月看到改善,跑 4 個月又退步。**應強制 4+ 個月** |
| **iteration_tracker.md 未更新導致重複決策** | 重做 1 小時 | 5/29 後 6/1 session 4 個 task 沒記,造成重複分析。應強制每次 session 結束前 commit tracker |
| **CPU 密集任務委派 subagent 600s timeout** | 600s/次 | backtest/hyperopt 委派 leaf subagent 必 timeout。應只用 background + notify_on_complete |

**總計估算**: 過去 2 週浪費約 6-8 小時在「跑完才知道方向錯」,而非「用 5 分鐘診斷就停止」。

---

## 3. 緊急陷阱統計（從 skill 抽出 TOP 5）

### 陷阱 #1: rsi<44 破壞性過濾器（出現 2+ 次）
- **症狀識別**: 0 trades 或 trades < 10,勝率無法計算
- **修復成本**: 5 分鐘（移除一行）
- **預防機制**: Code review checklist 明列「RSI 過濾器需破壞性測試」
- **來源**: skill 行 104-116

### 陷阱 #2: populate_exit_trend LEVEL 信號振盪（出現 1 次,毀滅性）
- **症狀識別**: trades/年 > 5000,勝率 29.8%,虧損 -78%
- **修復成本**: 30 分鐘（加 `shift(1)` 改 CROSS,或清空函式）
- **預防機制**: Code review checklist 明列「exit_trend 必須 CROSS 邏輯或清空」
- **來源**: skill 行 289-340

### 陷阱 #3: custom_stoploss 正數 = 利潤保護 trailing（出現 3+ 次,誤導性）
- **症狀識別**: exit reason 大量為 `trailing_stop_loss`（即使 `trailing_stop=False`）
- **修復成本**: 1-2 小時（含 A/B 確認實驗）
- **預防機制**: 2026-06-02 A/B 測試已確認 `use_custom_stoploss=True` 100% 覆蓋 `trailing_stop` 設定 — 設什麼都沒差
- **來源**: skill 行 1125-1178,行 555-606

### 陷阱 #4: 多幣種擴展 1→10 在 15m 的災難（出現 2 次,帳戶歸零）
- **症狀識別**: 交易數暴增 22x,勝率從 39.7%→12.2%
- **修復成本**: 永久封存該實驗
- **預防機制**: ARCHITECTURE.md + skill 明確標註「BTC-only」,跑前 grep 策略 docstring
- **來源**: skill 行 988-1011

### 陷阱 #5: BB_RPB 多重 OR 條件整合過嚴（出現 1 次,Iter #3）
- **症狀識別**: trades 從 1166 → 29（-97.5%）,統計顯著性不足
- **修復成本**: 1-2 小時（削減 OR 條件數量或改 majority voting）
- **預防機制**: 整合前先跑 smoke test `condition_trigger_count`,目標 30-80 trades/月
- **來源**: skill 行 828-857

**次要陷阱**（出現 1 次但嚴重）:
- profit_drawdown 未檢查 `current_profit > 0` → 虧損時立即出場
- ATR floor 0.001 → 即時止損（應 0.005）
- Freqtrade v3 `buy`/`sell` space 命名不一致 → hyperopt 失敗
- Bybit 無歷史 trades → OF 路線 dead end
- futures 缺 `leverage()` 方法

---

## 4. 過去 2 週迭代 ROI

| 策略 | 迭代次數 | 真正改善 | 打平/倒退 |
|------|----------|----------|----------|
| nsgaii_bb_rpb_tsl_bi | 3 | 1（Iter #2 +0.58pp）| 2（Iter #1 基線,Iter #3 -7.52pp）|
| PolyReg_Adaptive | 2 | 0 | 2（v1 -24.61%,v2 未驗證）|
| Hybrid_v3 | 4 | 2（架構突破 -91pp,Iter #3 -3.81pp）| 2（Iter #2 打平,Iter #4 4 個月 -0.90%）|
| MultiTF_RegimeDetector_v1 | 1 | 0 | 1（多幣種 -94.96% 災難）|
| MathCombo_Adaptive_v1 | 2 | 0 | 2（封存）|

**總計**:
- 總迭代次數: **12 個 iteration**
- 真正改善的: **3 次 (25%)**
- 打平/倒退的: **9 次 (75%)**
- **從未達到 GA framework 定義的 "Expectancy > 0" 標準**

**唯一正向累計**: Hybrid_v3 從 -94.96% → -0.90%（架構突破 +94pp）,但仍未獲利。

---

## 5. 改進優先級

### P0（立即修,本週內）
1. **建立 `pre_flight_smoke_test.py`**: 在每次完整 backtest 前,先跑 1 個月的策略 `.populate_entry_trend()` 計算 trigger_count。若 < 30 trades/2 個月 → 立即停止並警告「進場過嚴,需放寬」。
2. **強制 4 個月 backtest 為 GA 驗證最低標準**: 修改 `run_ga.sh` 預設 `--months=4`,2 個月 backtest 需明確加 `--allow-short-window` flag。

### P1（本月內）
1. **迭代前檢查 `iteration_tracker.md`**: 任何新 session 第一步是讀取 tracker 確認上次狀態,避免重複決策（如 close > EMA filter 的 redundant 嘗試）。
2. **Loss 函數升級**: `ProfitDrawDownHyperOptLoss` 只能找「打平」,改用 `SharpeHyperOptLoss` 或自定義 Expectancy-based loss。
3. **新增架構驗證 gate**: 在跑 GA 之前,先用「理想參數」（手動調到極寬鬆的 entry）跑一次 backtest,確認架構本身在寬鬆條件下能否獲利。若不能 → 跳過 GA,直接修改架構。

### P2（下次 session）
1. **用 subagent 做「結果分析」而非「執行 backtest」**: backtest/hyperopt 必用 background + notify_on_complete,subagent 只用於解讀 fthypt 結果。
2. **建立 traps_check.py 自動掃描**: 對新策略自動檢查 trailing_stop/custom_stoploss 衝突、exit_trend LEVEL、RSI 破壞性等 14 個已知陷阱。
3. **MultiTFPolyReg_v1 重新評估**: 由於 direction prediction 是死路,MultiTFPolyReg 應只做 regime + ATR,不要碰方向預測。

---

## 結論

整個迭代流程的核心瓶頸**不是策略設計**,而是**缺乏「早期停止」與「架構驗證」**機制:

1. **75% 迭代是打平/倒退** — 但每次都要跑完整 backtest/GA 才知道（4 個月 BTC 15m backtest ≈ 8 分鐘,500 epoch GA ≈ 70 分鐘）
2. **最常見的失敗模式**是「參數已優化到極限,架構本身有缺陷」 — GA 找到的「打平」參數其實是 Loss 函數的天花板
3. **過去 2 週唯一真正進步**的是 Hybrid_v3 從 -94.96% → -0.90%（架構突破 +94pp）,但仍未獲利

**最大槓桿點**: 實作 P0 的 `pre_flight_smoke_test.py`,預估可節省未來 60-70% 的 backtest/GA 時間浪費。
