# 流程自動化建議報告

**日期**: 2026-06-03
**範圍**: GA iteration 工具鏈 (`run_ga.sh` / `analyze_results.py` / `constraint_validator.py`) 全鏈路自動化
**對接對象**: `01_process_bottlenecks.md` 點名的 P0/P1 改進項
**目標**: 把「跑 70 分鐘 GA 才發現打平/0 trades」壓縮成「5 分鐘 pre-flight 就能停止」

---

## 1. 重複手動操作盤點

| # | 步驟 | 現在做法 | 耗時 | 自動化成本 | 優先級 |
|---|------|----------|------|-----------|--------|
| 1 | **手動確認策略檔位置**（子目錄 vs 頂層）| `run_ga.sh` line 195-218 手寫 glob 邏輯 + 重複 `find` 兩次 | 30 秒 × 每個新策略 | 低（已有 `find_strategy_file`,可複用）| ✅ P2 |
| 2 | **手動找 hyperopt 結果檔** | `analyze_results.py` line 119-134 自動找最新,但 `run_ga.sh` line 365 又自己 ls 一次 | 1 分鐘 | 低（DRY 違反）| ✅ P2 |
| 3 | **手動複製 best params 到策略 .json** | 跑完後需手動 `freqtrade hyperopt-show --best` → 複製 → 貼到 prod 策略 | 5-10 分鐘 | 中（需解析 hyperopt-show 輸出）| 🔴 P0 |
| 4 | **手動計算觸發率**（trades < 30 才發現進場過嚴）| 完全沒有 → 跑完整 backtest 才知道 | 8-70 分鐘（backtest/GA）| 低（pandas + feather）| 🔴 P0 |
| 5 | **手動抄寫 iteration_tracker.md** | 跑完後 Brian 手工填 profit/WR/DD | 5-10 分鐘 | 低（已有 metrics dict,只是沒接 append 邏輯）| 🔴 P0 |
| 6 | **手動跑 `git add + commit + push`**（hyperopt 結果）| `AGENTS.md` 規範要求但無 hook | 1 分鐘 | 極低（post-commit hook）| 🟡 P1 |
| 7 | **手動檢查 trailing_stop 衝突 / rsi<44 / exit_trend LEVEL** | 對照 skill Code Review Checklist 一條條核 | 10-15 分鐘 | 中（grep + AST 已有 pattern）| 🔴 P0 |
| 8 | **手動確認 timerange 跨體制** | 預設 6 個月但常用 2 個月 → 隱藏問題 | 0（但踩雷成本 8 分鐘 × 2）| 極低（run_ga.sh 改預設）| 🟡 P1 |
| 9 | **手動對 4 個月 backtest 重跑驗證** | 跑 2 個月看到改善,再跑 4 個月 | 4-8 分鐘 × 2 | 極低（直接預設 4 個月）| 🟡 P1 |
| 10 | **手動確認 strategy 是否 BTC-only** | 跑多幣種 backtest 浪費 30+ 分鐘 | 0（踩雷成本 30 分鐘）| 極低（docstring grep）| 🟡 P1 |
| 11 | **手動確認 INTERFACE_VERSION = 3 與 populate_enter_long 一致** | 完全沒有 → silently 0 trades | 0（踩雷成本 8-12 分鐘）| 低（AST 比對）| 🔴 P0 |
| 12 | **手動 commit iteration_tracker.md** | session 結束時容易忘（5/29 後 6/1 的 4 個 task 漏記 1 小時重做）| 0（踩雷成本 60 分鐘）| 極低（commit hook）| 🟡 P1 |

**小計**: 12 個重複操作,**P0 等級 5 個**,每次迭代累積浪費 20-40 分鐘。

---

## 2. Pre-flight Check 工具設計

### 工具名: `preflight_check.py`

**定位**: 在 `run_ga.sh` 啟動 hyperopt 之前 / `analyze_results.py` 分析結果之後各跑一次,提早發現 0 trades、邏輯矛盾、參數 infeasible。

### 檢查項目（共 6 類,24 項）

```python
PREFLIGHT_CHECKS = {
    "A_Entry_Trigger_Count": [
        # 載入本地 feather,跑 populate_entry_trend(),計算觸發 candle 數
        "min_trades_per_month >= 15" (BTC 15m 2 個月 ≥ 30),
        "min_trades_per_month <= 200" (避免 >500/year 過度交易),
        "regime=1 transition trades == 0" (應 no trades by design),
    ],
    "B_Logic_Consistency": [
        "adx_min < adx_max" (防止 nsgaii_bb_rpb_tsl_bi Iter #3 慘案),
        "ewo_high_1 < ewo_high_2" (分層進場不能反轉),
        "cci_length_25 in hyperopt range" (動態 column KeyError 預防),
        "buy_rsi_threshold < sell_rsi_threshold" (反向閾值矛盾),
    ],
    "C_Param_Validity": [
        "stoploss in (-0.99, -0.001)",  # LAW-08
        "trailing_stop_positive_offset > trailing_stop_positive",  # LAW-07
        "max_open_trades >= 1",  # LAW-09
        "atr_floor >= 0.005" (not 0.001 → 即時止損),
    ],
    "D_Interface_Version": [
        "INTERFACE_VERSION=3 ↔ populate_enter_long/exit_long 存在",
        "INTERFACE_VERSION=2 ↔ populate_buy_trend/sell_trend 存在",
        "futures mode → leverage() method 存在",
    ],
    "E_Time_Range_Adequacy": [
        "timerange >= 4 months" (含一次 regime 切換),
        "data coverage = 100%" (避免最後一根 K 線缺失),
    ],
    "F_Pair_Scope": [
        "策略 docstring 標註 'BTC-only' 且 config whitelist = ['BTC/USDT:USDT']",
        "若標 multi-pair,警告 15m 多幣種已知災難",
    ],
}
```

### 整合到 `run_ga.sh`

```bash
# 在 line 326 (執行 GA 之前) 插入:
echo "🔍 執行 Pre-flight Check..."
if ! python3 "$SCRIPT_DIR/preflight_check.py" \
    --strategy="$STRATEGY" \
    --months="$TIME_MONTHS" \
    --config="$CONFIG" \
    --strict; then
    echo "❌ Pre-flight 失敗,GA 終止（避免浪費 70 分鐘）"
    exit 2
fi
```

### 預期節省

| 失敗模式 | 原本耗時 | Pre-flight 後 | 節省 |
|----------|----------|---------------|------|
| 0/29 trades 進場過嚴 | 8-12 min backtest | 30 sec feather 計算 | **8-11 min** |
| trailing offset 矛盾 (LAW-07) | 0.5 day debug | 5 sec 參數比對 | **4 小時** |
| v3 + INTERFACE_VERSION=2 (silently 0 trades) | 1 day debug | 5 sec AST 檢查 | **8 小時** |
| 多幣種 15m 災難 | 30+ min | 1 sec docstring grep | **29 min** |
| 2 個月 backtest 隱藏 4 個月問題 | 4 min × 2 | 1 sec timerange 警告 | **7 min** |

**總計**: 每次迭代省 **5-12 分鐘正常情境**,**踩雷情境省 0.5-1 天**。

---

## 3. Fail-Fast 機制

### 觸發條件（閾值,可由 `ga_config_template.json` 覆寫）

```json
{
  "fail_fast": {
    "min_trades": 30,                    // 任何 backtest/hyperopt trial < 30 trades → 標記 FAIL
    "min_trades_for_significance": 20,   // 統計顯著性下限（Code Review 規範）
    "min_win_rate": 0.30,                // 勝率 < 30% 自動終止
    "max_drawdown": 0.20,                // Max DD > 20% 自動終止（生產風險閾值）
    "min_profit_factor": 1.0,            // PF < 1.0 標記負期望
    "min_sharpe": -0.5,                  // Sharpe 過低直接判 fail
    "max_consecutive_losses": 15,        // 連虧 > 15 次視為策略缺陷
    "max_zero_trades_iterations": 2,     // 連續 2 個 epoch 0 trades → 中止 trial
  }
}
```

### 動作分級

| 嚴重度 | 觸發 | 動作 |
|--------|------|------|
| **FATAL** | 0 trades / max_open_trades=0 / v3 interface mismatch | 立即終止整個 hyperopt run,exit code 2 |
| **HARD** | trades<30 / Max DD>20% / WR<30% / PF<1.0 | 標記當前 trial 為 "REJECTED",hyperopt 跳過存檔,繼續下一 trial |
| **SOFT** | Sharpe < 0 / 連虧 > 15 / 單月 0 trades | 警告 + 標記 "MARGINAL",繼續但加註 |
| **WARN** | 接近閾值（如 DD=18%）| 印出黃色警告,不阻擋 |

### 程式碼骨架（Python,18 行偽代碼）

```python
def fail_fast_check(trial_metrics: dict, config: dict) -> tuple[bool, str]:
    """回傳 (should_stop, reason)。HARD/FATAL → 終止 trial"""
    th = config["fail_fast"]

    # FATAL: 0 trades
    if trial_metrics.get("trades", 0) < th["min_trades"] // 3:
        return True, f"FATAL: 0 trades (策略不觸發或條件過嚴)"

    # FATAL: v3 介面錯置
    if trial_metrics.get("interface_version_mismatch"):
        return True, "FATAL: INTERFACE_VERSION 與 populate_*_long 不一致"

    # HARD: 統計顯著性不足
    if trial_metrics.get("trades", 0) < th["min_trades_for_significance"]:
        return True, f"HARD: trades={trades} < {th['min_trades_for_significance']} 樣本不足"

    # HARD: 勝率/回撤/PF 紅線
    if trial_metrics.get("win_rate", 1.0) < th["min_win_rate"]:
        return True, f"HARD: WR={wr:.1%} < {th['min_win_rate']:.0%} 紅線"
    if trial_metrics.get("max_drawdown", 0) > th["max_drawdown"]:
        return True, f"HARD: MaxDD={dd:.1%} > {th['max_drawdown']:.0%} 紅線"
    if trial_metrics.get("profit_factor", 99) < th["min_profit_factor"]:
        return True, f"HARD: PF={pf:.2f} < {th['min_profit_factor']} 負期望"

    return False, ""
```

### 整合

掛在 `analyze_results.py` 結尾（line 435 之前）+ `run_ga.sh` 的 `LAW-07..09` 驗證之後。若 fail-fast 觸發:
- 寫入 `iteration_tracker.md` 條目,標 ❌ FAIL-FAST + 終止原因
- 自動跳到「回到參數空間」分支（hyperopt 自動繼續下一 trial）
- **不** export 參數到 `prod/`（避免污染生產策略）

---

## 4. 負面知識庫 (negative_kb.md) 設計

### 結構：每條陷阱含 5 欄位

```yaml
- id: TRAP-001
  title: custom_stoploss 正數 = 利潤保護 trailing (誤導性計數)
  symptom: exit reason 大量 trailing_stop_loss,但 trailing_stop=False
  detection: AST grep `custom_stoploss.*return \+0\.\d+`
  prevention: |
    - Code Review 標註「正數 = 利潤保護」
    - 改用 custom_exit 處理利潤保護,custom_stoploss 只回傳負數
  source_ref: SKILL.md 行 555-606, 1125-1178
  severity: HIGH  # HIGH=浪費小時 / CRITICAL=毀滅性
```

### 自動比對（AST + grep 雙軌）

```python
def scan_negative_kb(strategy_path: Path, kb: list[dict]) -> list[dict]:
    """回傳命中的陷阱清單,每條含 line_no + 自動修復建議"""
    source = strategy_path.read_text()
    tree = ast.parse(source)
    hits = []
    for trap in kb:
        # 文字模式: re.findall 給 line number
        for m in re.finditer(trap["pattern"], source):
            line_no = source[:m.start()].count("\n") + 1
            hits.append({**trap, "line_no": line_no,
                          "code_snippet": source.splitlines()[line_no-1].strip()})
        # AST 模式: 進階型別檢查（如 INTERFACE_VERSION 與方法存在性）
        if trap.get("ast_check"):
            ast_hits = trap["ast_check"](tree, source)
            hits.extend(ast_hits)
    return hits
```

整合到 `constraint_validator.py` 作為 **LAW-11..14**（從 NKB-001..N 動態載入）。

### 範例條目（從現有 SKILL.md 抽出 5 條最致命）

#### NKB-001 [CRITICAL] populate_exit_trend LEVEL 信號振盪

- **症狀**: trades/年 > 5000,勝率 29.8%,虧損 -78%（Hybrid_v3 原始版）
- **識別**: `grep -n "dataframe\['rsi'\] > " populate_exit_trend` 沒有 `.shift(1)` 伴隨
- **修復**: 改 CROSS 邏輯 `(rsi > 60) & (rsi.shift(1) <= 60)`,或直接 `dataframe['exit_long'] = 0`
- **預防**: Code Review Checklist 明列「exit_trend 必須 CROSS 或清空」
- **來源**: SKILL.md 行 289-340

#### NKB-002 [CRITICAL] rsi<44 破壞性過濾器

- **症狀**: 0 trades 或 trades < 10,勝率無法計算
- **識別**: `grep -n "rsi.*<.*4[0-9]" populate_entry_trend`
- **修復**: 移除 `if rsi < 44: return 0`,改用 `rsi < 30`（僅極度超賣過濾）
- **預防**: 破壞性測試 — 暫時拿掉 RSI 過濾,確認 trades > 30
- **來源**: SKILL.md 行 104-116

#### NKB-003 [HIGH] trailing_stop vs custom_stoploss 衝突

- **症狀**: 大量 `trailing_stop_loss` 出場,勝率 ~17.8%,即使 `trailing_only_offset_is_reached=True` 仍觸發
- **識別**: AST 檢查 `trailing_stop = True` 與 `use_custom_stoploss = True` 同時存在
- **修復**: `trailing_stop = False` + `stoploss = -0.99` + custom_stoploss 主導
- **預防**: 2026-06-02 A/B 已確認 `use_custom_stoploss=True` 100% 覆蓋 trailing — **設什麼都沒差**
- **來源**: SKILL.md 行 510-606

#### NKB-004 [HIGH] 多重 OR 條件過嚴（9 條件疊加 AND-like 效果）

- **症狀**: trades 從 1166 → 29（-97.5%）,勝率仍 62.1% 但樣本不足
- **識別**: `len(re.findall(r"is_\w+", source)) >= 5` 在 `reduce(or, ...)` 內
- **修復**: 削減到 3-4 個最有效條件,或改 majority voting
- **預防**: Pre-flight `min_trades_per_month >= 15` 閾值
- **來源**: SKILL.md 行 828-857, skill.md 「進場邏輯整合陷阱」

#### NKB-005 [HIGH] INTERFACE_VERSION=2 配 populate_enter_long (silently 0 trades)

- **症狀**: 0 trades,無 error message,hyperopt show 0 results
- **識別**: AST 比對 `INTERFACE_VERSION == 2` AND `def populate_enter_long in tree`
- **修復**: `INTERFACE_VERSION = 3`（若使用 enter_long/exit_long）
- **預防**: Pre-flight Check 4.介面一致性
- **來源**: SKILL.md 行 97-103

---

## 5. Iteration 報告自動產生

### 輸入

1. `freqtrade backtesting --export trades` 產出 `.json` (`user_data/backtest_results/`)
2. Hyperopt 結果 `.fthypt` (`user_data/hyperopt_results/`)
3. Pre-flight + Fail-fast 結果（由本工具鏈產出）
4. `git log --oneline -1` 取當前 commit hash

### 輸出（append 到 `iteration_tracker.md`）

```markdown
#### Hybrid_v3 Iteration #5 (Pre-flight + Fail-fast 整合測試)
- **日期**: 2026-06-03
- **Session ID**: 20260603_143022
- **Commits**: a1b2c3d4 (preflight_check.py) + e5f6g7h8 (fail_fast gate)
- **Pre-flight**: ✅ 6/6 類別通過（24 項檢查）
- **GA 結果** (BTC/USDT 15m, 4 個月, roi/stoploss/trailing spaces, 500 epochs):
  - 674 trades, WR 64.8%, 利潤 0.00%, Max DD 13.26%
  - Loss 115.499
- **Fail-Fast 評估**:
  - trades=674 ≥ 30 ✓
  - WR=64.8% ≥ 30% ✓
  - MaxDD=13.26% ≤ 20% ✓
  - PF=1.00（剛好打平,標 ⚠️ MARGINAL）
  - **結論**: 架構 pass,參數打平 → 下一輪調 loss 函數至 SharpeHyperOptLoss
- **Negative KB 命中**: 0 條
- **狀態**: ⚠️ MARGINAL（架構 OK,需換 loss 函數突破）
- **下一步**: 改用 SortinoHyperOptLoss,epochs 提升到 1000
- **耗時**: 78 分鐘（從原 90 分鐘,省 12 分鐘 pre-flight 提早發現 1 個 hard fail trial）
```

### 整合腳本（掛在 `run_ga.sh` line 388 之前）

```bash
# ---- 自動產生 iteration 報告 ----
if [ $EXIT_CODE -eq 0 ] && [ -f "$ITERATION_LOG" ]; then
    echo "📝 自動更新 iteration_tracker.md..."
    python3 "$SCRIPT_DIR/auto_iteration_report.py" \
        --strategy="$STRATEGY" \
        --session-id="$SESSION_ID" \
        --iteration-log="$ITERATION_LOG" \
        --metrics-json="$SESSION_DIR/metrics.json" \
        --tracker-file="$GA_FRAMEWORK_DIR/iteration_tracker.md"
fi
```

`auto_iteration_report.py` 內部:
1. 讀 `iteration.md` (run_ga.sh 寫的 metadata)
2. 讀 `metrics.json` (analyze_results.py 寫的)
3. 讀 `git log -1 --format=%H` 取 commit
4. 跑 fail-fast 評估
5. 跑 negative KB 掃描
6. append 格式化條目到 `iteration_tracker.md`
7. **自動 `git add iteration_tracker.md && git commit -m "auto(tracker): iter #N @ $SESSION_ID"`**

---

## 6. 預估效益

### 單次迭代節省

| 階段 | 原本 | 自動化後 | 節省 |
|------|------|----------|------|
| 策略驗證 + config 檢查 | 10 min 手動 | 30 sec 自動 | **9.5 min** |
| 0/29 trades 發現 | 8-12 min backtest | 30 sec pre-flight | **7-11 min** |
| Negative KB 陷阱掃描 | 15 min 手動對照 | 5 sec AST 掃 | **14.9 min** |
| 手寫 iteration_tracker | 5-10 min | 0 sec 自動 | **5-10 min** |
| 4 個月 backtest 強制 | 4 min 重跑 | 0（預設 4 個月）| **4 min** |
| 失敗迭代早期停止 | 70 min GA 浪費 | 5 sec 停止 | **70 min** |
| **小計（正常迭代）** | | | **~30 min/迭代** |
| **小計（踩雷迭代）** | | | **~70-120 min/迭代** |

### 年度效益

- 目前頻率: 約 **2 迭代/週** × 50 週 = **100 迭代/年**
- 預估 75% 迭代踩雷（依 01_process_bottlenecks.md 統計）
- 75 次踩雷 × 70 min + 25 次正常 × 30 min = **5,250 + 750 = 6,000 分鐘/年 = 100 小時/年**

### 預防失敗挽回成本

| 已知慘案 | 原本花費 | Pre-flight 後 | 挽回 |
|----------|----------|---------------|------|
| MultiTF_RegimeDetector_v1 多幣種災難 | 30+ min × 2 = 60 min + 信心打擊 | 1 sec 警告 | **60 min + 1 個不再發生的災難** |
| Hybrid_v3 v3+INTERFACE_VERSION=2 silently 0 trades | 1 day debug | 5 sec AST | **8 小時** |
| Hybrid_v3 trailing_stop vs custom_stoploss 衝突 | 2 小時 A/B 確認 | 1 sec AST | **2 小時** |
| BB_RPB 9 條件 OR 過嚴 | 1.5 小時（含 backtest 8 min × 2）| 30 sec smoke | **1.5 小時** |
| populate_exit_trend LEVEL 振盪（Hybrid_v3 原始）| 30 min 修復 + 1 天虧損 -78% | 5 sec grep | **30 min + 避免 1 天實戰虧損** |
| **單次事件挽回** | | | **12-14 小時** |
| **年度挽回（假設每種踩 1-2 次）** | | | **60-100 小時/年** |

### 投資報酬

- **建置成本**: 3 個工具（preflight_check.py + fail_fast gate + auto_iteration_report.py）共約 **300-400 行 Python**,預估 1 個 developer day 完成
- **首年 ROI**: 省 100 小時 + 挽回 60-100 小時 = **160-200 小時 / 1 day 建置 = 160-200x ROI**
- **附加價值**: iteration_tracker.md 不再漏記 → 跨 session 連續性 + 避免重複決策（5/29 後 6/1 重做 1 小時 → 0）

---

## 結論與行動項

### 立即做（本週,P0）

1. **建立 `preflight_check.py`** — 6 類 24 項檢查,優先做 A (Entry Trigger Count) + D (Interface Version) + F (Pair Scope),可立即阻止 80% 已知慘案
2. **`run_ga.sh` 改預設 `--months=4`** — 一行改動,防止 2 個月隱藏 4 個月問題重演

### 本月做（P1）

3. **fail-fast gate 整合到 `analyze_results.py`** — 18 行偽代碼,搭配現有 `validate_ga_params`
4. **`auto_iteration_report.py`** — append tracker + auto-commit,解決 5/29 後漏記問題
5. **建立 `negative_kb.md`** — 從 SKILL.md 抽出 TOP 5 條目（已列於 §4）

### 下季做（P2）

6. **GA loss 函數升級** — 從 `ProfitDrawDownHyperOptLoss` 改 `SharpeHyperOptLoss` + Expectancy 組合（解決 Hybrid_v3 找打平參數問題）
7. **架構驗證 gate** — 用「理想參數」（手動寬鬆 entry）先 backtest 確認架構能獲利,再做 GA

**最大槓桿點**: §2 pre-flight + §3 fail-fast + §5 自動 tracker 三件套,可一次解決 `01_process_bottlenecks.md` 點名的 75% 浪費問題。
