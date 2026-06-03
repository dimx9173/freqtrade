# 下一步戰術優先級矩陣

**日期**: 2026-06-03
**評估對象**: Hybrid_v3 架構紅利用盡後的「下一步 5 個候選選項」
**評估方法**: 依「01_process_bottlenecks.md」與「iteration_tracker.md」歷史記錄量化每個選項的時間 / 風險 / 成功機率
**立場**: 誠實評估, 標出每個選項的歷史依據 (過去 session 結果), 不過度樂觀

---

## 1. 當前狀態量化

### 已投入
- **迭代次數**: Hybrid_v3 共 3 次大迭代 (5/20 v1 → 6/1 #2 GA → 6/3 #3 BB_RPB)
- **時間投入**: ~5 小時跨 3 個 session (delegated 還有 1.5 小時 subagent recovery)
- **改善幅度**:
  - 利潤: -3.98% → -0.90% (4 個月) / -0.17% (2 個月)
  - 架構改善 77% (4 個月) / 96% (2 個月)
  - DD: 5.75% → 0.96% (4 個月) / 0.45% (2 個月)
- **關鍵教訓**: 架構紅利已用盡, GA 在當前架構只找到「打平」參數 (Loss 115.499, 0.00% profit)

### 距「可部署」目標差距
- **profit > +0.5%/月**: 4 個月 -0.90% → 需 +2.9% (5 個月) 改善才能達標
- **WR > 60%**: 2 個月 62.1% ✅, 4 個月 57.5% ❌ (差 2.5pp)
- **trades > 50/月**: 2 個月 29 trades = 14.5/月 ❌ (差 35/月) | 4 個月 73 = 18.3/月 ❌

**結論**: 三項目標 **目前 0/3 達標**。其中「trades > 50/月」最難達標 (架構性問題), 「profit +0.5%」需要根本改變, 「WR」只差 2.5pp 但 4 個月樣本波動大。

---

## 2. 候選選項評估矩陣

> 評分說明: 推薦度 = 成功機率 × 0.4 + (1 - 風險) × 0.3 + 兼容性 × 0.3 (加權平均, 0-10)

| 選項 | 時間 (hr) | 成功機率 | profit 改善 | 風險 | 兼容性 | 推薦度 |
|------|----------|----------|-------------|------|--------|--------|
| **A** 加做空邏輯 | 5-6 | **15%** | -10% ~ +2% | ⭐⭐⭐⭐⭐ 極高 | ❌ 低 | **1.0/10** |
| **B** 重新 GA (500+ epochs + BB_RPB space) | 2-3 | **20%** | -1.0% ~ +0.3% | ⭐⭐ 中 | ✅ 高 | **3.2/10** |
| **C** 切換 timeframe (5m/1h) | 4-6 | **10%** | -5% ~ +1% | ⭐⭐⭐⭐ 高 | ❌ 低 | **1.0/10** |
| **D** 接受架構限制 (dry-run, 暫停迭代) | 0.5 | **90%** | 0% (停止虧損) | ⭐⭐ 中 | ✅ 100% | **8.2/10** |
| **E** dynamic custom_stoploss (pred_ATR) | 1.5-2 | **35%** | -0.5% ~ +0.5% | ⭐⭐⭐ 中高 | ✅ 高 | **4.5/10** |

> **重要說明**: 推薦度不是「獲利潛力」而是「期望值」(預期利潤 × 機率 - 預期損失 × 機率)。D 沒有獲利預期但有 90% 機率停止虧損, 所以總體期望值最高。

---

## 3. 各選項詳細分析

### 選項 A: 加做空邏輯 (熊市對沖)
- **預估時間**: 5-6 hr
  - 改 `can_short=True` + config 改 futures 模式: 0.5 hr
  - 實作 `enter_short` 對稱邏輯 (EMA cross down + ADX): 2 hr
  - `populate_exit_trend` 加 `exit_short` + custom_stoploss 雙向: 1.5 hr
  - backtest 驗證 4 個月: 0.5-1 hr
  - 修復發現的 bug: 1 hr
- **預估成功機率**: **15%** (基於 5 個歷史雷區)
  - 🔴 SKILL.md 行 25-32: **方向預測 SNR≈0.02 是死路** (5m 47.8-49.1% < 50%)
  - 🔴 SKILL.md 行 139-154: **多幣種擴展已踩雷 -94.96%** (5185 trades)
  - 🔴 SKILL.md 行 691-712: futures 模式 `leverage()` 報錯, 需重設
  - 🔴 SKILL.md 行 510-553: **trailing_stop + custom_stoploss 衝突已毀過 17.8% WR 策略**
  - 🔴 Hybrid_v3 現有 custom_stoploss 5 層 (正負交錯) 在雙向時會失控
- **預期 profit**: -10% ~ +2% (寬廣分佈, 期望值約 -1.5%)
- **關鍵風險**:
  - 1) Regime detection 99.8% 是基於 long 訓練, 反向 regime 未驗證
  - 2) 「熊市對沖」假設 downtrend 有 alpha, 但 GA 在 -6.59% 熊市已隱含過濾 (架構上限證明)
  - 3) 雙向進場可能讓 signals 互相干擾, 重蹈 LEVEL 振盪 bug (8231 trades 慘案)
- **統計顯著性**: 0 (完全新樣本, 需 4 個月)
- **是否需要 commit**: 是 (大改 .py)
- **實作要點**:
  - 先用 clone 策略隔離實作, **不要在主力 Hybrid_v3.py 直接改**
  - Regime detection 加 `regime_short` 標籤 (adx > 22 + close < ema_slow)
  - 用 `enter_short` 而非 `enter_long` 反向, 確認 `can_short=True` 與 config 一致
  - 必跑 4 個月 backtest (不是 2 個月)

### 選項 B: 重新 GA (含 BB_RPB 參數空間, 500+ epochs)
- **預估時間**: 2-3 hr
  - 改 run_ga.sh 加入 buy_ 參數空間 (~30 個 IntParameter/DecimalParameter): 1 hr
  - 跑 500 epochs hyperopt: 70-90 min
  - analyze_results.py + 整合: 30 min
- **預估成功機率**: **20%** (基於 Iter #2 結果外推)
  - 🟡 Iter #2 50 epochs 找到「打平」參數 (0.00% profit), 500 epochs 不太可能質變
  - 🟡 「架構 > 參數」教訓 (5/20 v1 → 5/21 v2 → 6/1 #2 → 6/3 #3 證明)
  - 🟡 BB_RPB 11 個參數 + ROI/SL/Trailing = 18 維空間, 500 trials 不可能收斂
  - 🟢 已有 `run_ga.sh` 基礎設施, 實作成本低
- **預期 profit**: -1.0% ~ +0.3% (期望 0)
- **關鍵風險**:
  - 1) ProfitDrawDownHyperOptLoss 已證明只能找到「最小回撤」, 找不到正期望值
  - 2) Iter #2 找到的 21.6% ROI 是 overfit (1.5 個月 backtest, 跨 regime 失效)
  - 3) 重新 GA 等同「在錯誤問題上花 90 分鐘」
- **統計顯著性**: 高 (Iter #2 跑出 674 trades)
- **是否需要 commit**: 是 (新參數 .json)
- **實作要點**:
  - 必跑 4 個月 timerange (不是 2 個月)
  - 加 Expectancy loss function (Sharpe + EV), 不要只用 ProfitDrawDown
  - 500 epochs 不夠, 至少 1000+ 或 跑到 loss 收斂
  - 先跑 preflight_check (P0 自動化), 確認 30 trades/2 月 觸發

### 選項 C: 切換 timeframe (5m / 1h)
- **預估時間**: 4-6 hr
  - 5m: 0.5 hr (改 timeframe 即可) + 重設 informative + 校準 BB_RPB: 2 hr
  - 1h: 0.5 hr + 重新校準 EWO/RSI/BB 全部參數 (15m 特定): 3 hr
  - backtest 4 個月: 0.5-1 hr
- **預估成功機率**: **10%** (已知兩個 TF 都有結構性問題)
  - 🔴 SKILL.md 行 25-32: **5m SNR=47.8-49.1% < 50% 是死路** (方向預測)
  - 🔴 SKILL.md 行 92-103: EWO 校準為 BTC 15m 特定 (均值 0, std 0.68)
  - 🔴 BB_RPB 11 個參數全為 15m 校準, 切 TF 後全失效
  - 🔴 1h 進場頻率: 50/月 vs 1h 訊號密度 → 統計顯著性達不到
  - 🟢 MultiTF_RegimeDetector_v1 已有 4 TF 經驗
- **預期 profit**: -5% ~ +1% (期望 -2%)
- **關鍵風險**:
  - 1) 5m 噪音 > 15m, 過度交易風險 (8231 trades 慘案級別)
  - 2) 1h 改完後等於從頭做策略, 等同新策略 baseline
  - 3) Hybrid_v3 整個架構依賴 15m 高頻 + 1h/4h 慢速 consensus, 切單 TF 會破壞設計
- **統計顯著性**: 0 (新樣本)
- **是否需要 commit**: 是 (新策略)
- **實作要點**:
  - 5m 應直接放棄 (SKILL.md 已標為死路)
  - 1h 實作為新策略 (Hybrid_v4_1h.py), 不直接改 Hybrid_v3
  - 1h 需重做 EWO/RSI/BB 數據驅動校準 (不可沿用 15m 預設)
  - 必跑 6 個月 backtest (1h 樣本稀疏)

### 選項 D: 接受架構限制 (uptrend-only, dry-run 觀察, 暫停迭代)
- **預估時間**: 0.5 hr
  - 設定 config 為 dry-run 模式: 10 min
  - 寫 live deployment 計畫文檔: 20 min
- **預估成功機率**: **90%** (對於「停止虧損 + 收集樣本」目標)
  - 🟢 不改架構 = 不會變差
  - 🟢 4 個月 -0.90% 已接近打平, dry-run 真實市場波動可能 ±0.5%
  - 🟢 過去 5 小時投入已榨乾架構紅利, 繼續投入邊際效益遞減
  - 🟡 暫停不等於放棄, 1-2 月後可重新評估
- **預期 profit**: -0.5% ~ +0.5%/月 (期望 0, 但停止投入時間成本)
- **關鍵風險**:
  - 1) 機會成本: 若 E 實際能 +2%, 放棄 = 損失
  - 2) 4 個月 -0.90% 樣本含 1 個 downtrend + 1 個 uptrend, 統計可能波動
  - 3) 「可部署目標 trades > 50/月」完全未達, dry-run 樣本不足
  - 4) **心理風險**: 暫停容易被誤判為「放棄」, 失去 momentum
- **統計顯著性**: 中 (73 trades / 4 個月, 不顯著獲利但顯著不爆倉)
- **是否需要 commit**: 否 (不需改 .py, 但建議 commit 當前狀態與決策)
- **實作要點**:
  - 設定 dry-run 啟動文檔, 不進入 live trading
  - 記錄 4 個月 backtest 結果到 `iteration_tracker.md` (封存為 baseline)
  - 預約 1 個月後重新評估 (新市場 regime)
  - 同時執行 P0 自動化 (preflight_check.py) 降低未來迭代成本

### 選項 E: 套用 dynamic custom_stoploss (用 pred_ATR 計算)
- **預估時間**: 1.5-2 hr
  - 改 `custom_stoploss` 用 `pred_atr` 動態計算: 30 min
  - 跑 4 個月 backtest 驗證: 0.5-1 hr
  - 對比 fixed 5% 與 dynamic ATR-based 結果: 30 min
- **預估成功機率**: **35%** (架構微調, 風險低)
  - 🟢 pred_ATR 已用於 `custom_stake_amount` (line 1277), 已有 cache 基礎
  - 🟢 custom_stoploss 已啟用 (`use_custom_stoploss = True`)
  - 🟢 改動範圍小 (單一 function, ~30 行)
  - 🟡 現有 custom_stoploss 5 層已涵蓋主要情境, 改成 pred_ATR 邊際改善有限
  - 🟡 SKILL.md 行 510-553 警告: 正數回傳會顯示為 trailing_stop_loss
  - 🔴 「預期回收 2-4% 損失」是假設性, 實際 4 個月 -0.90% 中, 損失可能來自 entry 太早 (29 trades 樣本) 而非 stoploss
- **預期 profit**: -0.5% ~ +0.5% (期望 0)
- **關鍵風險**:
  - 1) `custom_stoploss` 在 P0 fix 已改成 5 層分級, 改為 ATR 動態可能破壞利潤保護
  - 2) Hybrid_v3 已有 `trailing_stop = True` + GA 設的 10.7% 觸發, 與新 dynamic stoploss 衝突風險
  - 3) 「回收 2-4% 損失」是基於「stoploss 太寬」假設, 但若損失源於「entry 太早」則無效
  - 4) 29 trades 樣本 (2 個月) 統計不顯著, 動態 stop 可能 overfit
- **統計顯著性**: 中 (Iter #3 已有 29 trades)
- **是否需要 commit**: 是 (改 .py)
- **實作要點**:
  - **先診斷損失來源**: 用 backtest 的 exit reason stats 確認是 stoploss 觸發佔多少
  - 若 stoploss 觸發 < 30% 損失 → E 改 dynamic 改善有限
  - 若 stoploss 觸發 > 50% 損失 → E 改善有理論基礎
  - 新設計: `stoploss = max(-0.05, -2.5 * pred_atr)` (ATR floor 0.5%, 2.5x buffer)
  - 利潤保護層級保留 +0.01/+0.02 正數, 但加註解說明會顯示為 trailing_stop_loss

---

## 4. 推薦順序

### **首選**: 選項 D (接受架構限制, dry-run, 暫停迭代) — 推薦度 8.2/10

**理由**:
1. **期望值最高**: 90% 機率停止虧損 + 0 機率讓狀況變差 = 期望值顯著為正
2. **過去 5 小時已榨乾架構紅利**: 從 -3.98% → -0.17% (架構改善), GA 找到打平 (參數優化), 任何進一步改動的邊際效益 < 0
3. **P0 自動化先做**: 同步推進 `preflight_check.py` (03_process_automation.md 點名), 為未來迭代降本
4. **1 個月後重新評估**: 新市場 regime 可能改變架構上限

### **次選**: 選項 E (dynamic custom_stoploss) — 推薦度 4.5/10

**理由** (若 D 失敗, 即 Brian 想繼續投入):
1. **風險最低**: 改動範圍小 (1 function, 30 行), 即使失敗也只損失 1.5-2 hr
2. **理論基礎存在**: pred_ATR 已用於 position sizing, 用於 stoploss 是合理延伸
3. **可立即驗證**: 4 個月 backtest 30 分鐘跑完, 結果可量化
4. **執行前置**: **必先跑 exit reason stats 診斷** 確認 stoploss 是否為主要損失源

### **緩衝**: 選項 B (重新 GA 500+ epochs) — 推薦度 3.2/10

**理由** (若 D + E 仍想嘗試):
1. **比 A/C 風險低**: 仍在當前架構內, 不引入新變量
2. **可順便驗證 Expectancy loss function**: 若 ProfitDrawDown 持續無解, 證明「架構上限」
3. **時間邊界明確**: 90 min hyperopt, 30 min analysis, 2-3 hr 截止
4. **失敗成本低**: 找不到更好參數只損失 2-3 hr, 不會搞壞策略

### **不推薦**: 選項 A (做空) 與選項 C (切 TF)

**理由**:
- A: 5 個歷史雷區全中, 成功機率 15%, 期望值 -1.5% (負)
- C: 5m 是已知死路 (SKILL.md 標記), 1h 等同從頭做策略, 期望值 -2% (負)

---

## 5. 立即可做的「低懸果實」

> 這些是 30 分鐘內可完成, 預期總體正向的工作, 與推薦 D 並行不衝突

- [ ] **30 min**: 跑 6 個月 backtest 確認 4 個月樣本穩定性 (`freqtrade backtesting --timerange 202511-202605`)
      - 預期: 驗證 4 個月 -0.90% 不是熊市 overfit, 若 6 個月仍 -0.5% ~ -1.5% → D 接受依據更強
      - 風險: 0 (純 backtest)
      - 預期改善: 統計信心 +20%

- [ ] **15 min**: 跑現有 4 個月 backtest 的 exit reason stats
      - 命令: `freqtrade backtesting --strategy Hybrid_v3 --export trades` + `python3 analyze_exit_reasons.py`
      - 預期: 量化各 exit reason (ROI, stoploss, exit_signal, custom_exit) 佔比與平均 profit
      - 決策依據: 決定 E 是否值得做 (若 stoploss 觸發佔損失 > 50% → 改 E; 否 → 跳過)
      - 風險: 0
      - 預期改善: 0% (診斷性, 非改善性)

- [ ] **10 min**: 設定 dry-run 配置 (`config_dryrun.json` 設 `dry_run: true, stake_amount: 100`)
      - 預期: 為 D 選項鋪路, 可隨時切到 dry-run
      - 風險: 0
      - 預期改善: 0% (準備性)

- [ ] **5 min**: `git add iteration_tracker.md + Hybrid_v3.py + 04_tactical_priority.md && git commit -m "auto(strategy): Hybrid_v3 baseline @ 4mo -0.90% WR 57.5%, 決策 D"`
      - 預期: 為當前狀態留下 baseline commit, 未來對比有依據
      - 風險: 0
      - 預期改善: 0% (記錄性)

---

## 6. 附加決策表 (給 Brian 快速決策用)

| 情境 | 該選哪個 | 理由 |
|------|----------|------|
| 還想繼續投入 5+ 小時, 賭大改 | 跳過 A/B/C, 考慮 Hybrid_v4 新策略 | A/B/C 都不是根本解決 |
| 只能再投 1-2 小時 | **E (dynamic stoploss)** | 風險低, 可量化驗證 |
| 不想再投時間, 接受現狀 | **D (dry-run + 暫停)** | 期望值最高, 停止虧損 |
| 想驗證「架構是否真到上限」 | **B (重新 GA 1000+ epochs)** | 用 ProfitDrawDown 找極限 |
| 想徹底換思路 | 暫停 Hybrid 系列, 開發 Adaptive_Scalp_v2 | tracker 已標記, 完全新方向 |

---

**最後更新**: 2026-06-03
**對接對象**: `01_process_bottlenecks.md` (流程問題), `03_process_automation.md` (P0 自動化)
**下一步**: 執行 5 個「低懸果實」, 然後根據 6 個月 backtest 結果決定 D 還是 E
