# 🤖 AI Agent 研發 Freqtrade 策略工作流

> 使用 AI Agent 開發並迭代優化 Freqtrade 策略的標準化流程
> 排除參數優化（交給 hyperopt），專注於策略邏輯設計與迭代改進

---

## 📊 基準參考

| 策略 | 時間框架 | 期間 | 報酬率 | 市場表現 | 勝率 |
|------|---------|------|--------|---------|------|
| **TestRSI** | 1h | 2025-01-16 ~ 2025-06-01 | **+4.92%** | -11.36% | 高 |
| SMCStrategy (原始) | 5m | 同上 | -6.57% | -13.16% | 44.4% |
| SMC_v2_cfo | 5m | 同上 | -3.56% | -13.16% | 31.6% |

**目標**：打敗 TestRSI 基準（+4.92%），最大回撤 < 10%

---

## 🔄 核心工作流

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Research — 市場分析 & 策略方向確認                    │
├─────────────────────────────────────────────────────────────┤
│  1.1 分析市場特性（下跌/震盪/上漲）                              │
│  1.2 確認目標指標組合                                          │
│  1.3 定義進場/出場邏輯框架                                      │
│  1.4 產出：策略規格文件（SPEC.md）                              │
└──────────────────────────┬────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: Build — AI Agent 生成策略代碼                       │
├─────────────────────────────────────────────────────────────┤
│  2.1 Coding Agent 根據規格生成策略                             │
│  2.2 代碼審查（語法錯誤、邏輯漏洞）                              │
│  2.3 產出：strategy.py + config.json                          │
└──────────────────────────┬────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: Validate — Backtest 驗證                          │
├─────────────────────────────────────────────────────────────┤
│  3.1 freqtrade backtesting                                   │
│  3.2 檢查：錯誤、崩潰、邏輯問題                                │
│  3.3 產出：backtest report                                   │
└──────────────────────────┬────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: Diagnose — AI Agent 分析結果                        │
├─────────────────────────────────────────────────────────────┤
│  4.1 Review Agent 解讀 backtest 輸出                         │
│  4.2 診斷問題（勝率、持倉時間、force_exit）                    │
│  4.3 提出 3 個具體改進方向                                     │
│  4.4 產出：診斷報告 + 改進建議                                  │
└──────────────────────────┬────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 5: Iterate — 迭代優化                                 │
├─────────────────────────────────────────────────────────────┤
│  5.1 Coding Agent 根據建議修改策略                            │
│  5.2 回到 Phase 3 重新驗證                                    │
│  5.3 直到：報酬 > 基準 且 回撤 < 10%                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 AI 擅長 vs 不擅長的任務

| 任務 | AI 效率 | 建議 |
|------|---------|------|
| 指標組合設計 | ⭐⭐⭐⭐⭐ | AI 擅長測試不同 TA-Lib 指標排列 |
| 進場邏輯編碼 | ⭐⭐⭐⭐ | 將主觀想法轉為 Python 程式碼 |
| 風險規則設計 | ⭐⭐⭐⭐ | 止損/止盈/最大持倉邏輯 |
| 多時間框架整合 | ⭐⭐⭐⭐ | 確認信號 + 進場信號疊加 |
| 訊號權重優化 | ⭐⭐⭐ | 多指標評分系統 |
| **⚠️ 參數調優** | ⭐ | **交給 hyperopt** |

---

## 🔧 實作指令

### 環境確認

```bash
# Freqtrade 虛擬環境
cd /home/brian/freqtrade
FREQ=/home/brian/freqtrade/.venv/bin/freqtrade

# 策略存放位置
STRAT_DIR=/home/brian/freqtrade/user_data/strategies/test
CONFIG=/home/brian/freqtrade/user_data/config/config_AtrPinStrategy.json

# 標準回測參數
TIMERANGE=20250116-20250601
FEE=0.0004
```

### Phase 1: Research

```bash
# 使用 web search 分析市場特性
# 確認哪些指標組合在 BTC 1h 表現好
# 查閱 freqtrade 文件
```

### Phase 2: Build（使用 Coding Agent）

```bash
# 啟動 Claude Code 生成策略
cd /home/brian/freqtrade && \
claude --permission-mode bypassPermissions --print \
  '在 user_data/strategies/test/ 目錄下，
   生成一個名為 TestAI_v1.py 的 freqtrade 策略：

   【市場環境】
   - 交易對：BTC/USDT（幣本位永續合約）
   - 時間框架：1h
   - 資料範圍：2025-01-16 至 2025-06-01

   【進場邏輯】
   - RSI < 45（超賣區邊緣）
   - MACD 快線 > 慢線（金叉）
   - 價格低於 20日均線（逢低買入）

   【出場邏輯】
   - RSI > 55 獲利了結
   - 或 MACD 死叉止損

   【風險規則】
   - 止損：2%
   - 最大持倉：24小時
   - 最大同持倉：3個

   【成功標準】
   - 報酬 > +4.92%（打敗 TestRSI 基準）
   - 最大回撤 < 10%

   生成完整策略後，立即執行 backtest 驗證。'
```

### Phase 3: Validate

```bash
# 本地 backtest 驗證
$FREQ backtesting \
  --strategy TestAI_v1 \
  --config $CONFIG \
  --strategy-path $STRAT_DIR \
  --timerange $TIMERANGE \
  --fee $FEE
```

### Phase 4: Diagnose

```bash
# AI 分析 backtest 結果
claude --permission-mode bypassPermissions --print \
  '分析以下 backtest 結果，診斷問題：
   - 為何勝率低/高？
   - 為何有超長持倉（force_exit）？
   - 為何 Sharpe 為負？
   - 為何整體報酬為負？

   提出 3 個具體改進方向，並說明原理。'
```

### Phase 5: Iterate

```bash
# 基於診斷讓 AI 修改策略
claude --permission-mode bypassPermissions --print \
  '修改 TestAI_v1.py：
   根據診斷結果，做以下三項改動：
   1. [具體改動1]
   2. [具體改動2]
   3. [具體改動3]

   改動完成後，重新執行 backtest 並對比結果。'
```

---

## 📋 策略研究 Prompt 模板

```markdown
## 策略規格（SPEC.md）

### 基本資訊
- 策略名稱：TestAI_v1
- 交易對：BTC/USDT, ETH/USDT
- 時間框架：1h
- 目標市場：2025-01-16 ~ 2025-06-01（下跌市場）

### 進場條件
1. [指標A] [條件] [數值]
2. [指標B] [條件] [數值]
3. [指標C] [條件] [數值]
（所有條件為 AND 關係）

### 出場條件
1. [指標X] [條件] [數值] → 止盈
2. [指標Y] [條件] [數值] → 止損
3. 持倉 > [N] 小時 → 強制退出

### 風險規則
- 最大同持倉：3
- 單筆風險：2%
- 最大持倉時間：24小時

### 成功標準
- 絕對報酬 > +4.92%
- 最大回撤 < 10%
- Sharpe > 0.5
- 勝率 > 40%
```

---

## ⚡ 並行策略研究

同時讓多個 Coding Agent 研究不同方向：

```bash
# Agent 1: 趨勢追蹤方向
claude --print --project /home/brian/freqtrade \
  '研究並生成 EMA 交叉 + ADX 趨勢策略到 strategies/test/TestTrend.py' &

# Agent 2: 均值回歸方向
claude --print --project /home/brian/freqtrade \
  '研究並生成 RSI 極值 + 布林帶策略到 strategies/test/TestMeanRev.py' &

# Agent 3: 成交量突破方向
claude --print --project /home/brian/freqtrade \
  '研究並生成成交量突破 + MACD 策略到 strategies/test/TestVolBreak.py' &

# 等待所有 agent 完成
wait
```

---

## 🚫 避免的錯誤

1. **不要一次給太多任務** — AI 擅長迭代，每次專注一個改進
2. **不要跳過 backtest** — 每次改動都要驗證
3. **不要只追求高勝率** — 盈虧比和 Sharpe 同等重要
4. **不要忽視 force_exit** — 超長持倉通常是策略漏洞
5. **不要跳過參數優化** — 生成策略後用 hyperopt 找最優參數

---

## 📁 文件結構

```
user_data/
├── docs/
│   ├── AI_AGENT_STRATEGY_WORKFLOW.md   # 本文件
│   └── STRATEGY_RESULTS.md              # 策略研究成果
├── strategies/
│   ├── prod/                            # 正式策略
│   ├── test/                             # 測試策略
│   │   ├── TestRSI.py                   # 基準策略
│   │   ├── TestAI_v1.py                 # AI 生成策略
│   │   └── ...
│   ├── scalp/                            # 短線策略
│   └── smc/                              # SMC 策略
└── config/
    ├── config_AtrPinStrategy.json       # 標準回測設定
    └── config_test.json                  # 測試用設定
```

---

## 🔗 相關資源

- [Freqtrade 官方文檔](https://www.freqtrade.io/en/stable/)
- [Freqtrade Strategy 101](https://www.freqtrade.io/en/stable/strategy-101/)
- [Freqtrade Backtesting](https://www.freqtrade.io/en/stable/backtesting/)
- [Freqtrade Hyperopt](https://www.freqtrade.io/en/stable/hyperopt/)
- [TA-Lib 指標文檔](https://ta-lib.org/)

---

*最後更新：2026-04-12*
