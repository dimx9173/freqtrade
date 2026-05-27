# 🏭 全自動化剝頭皮策略探勘與驗證工廠

**三階段漏斗式策略篩選系統**

利用 AI 進行大規模指標探索，持續發掘、驗證並部署可在實盤中獲利的剝頭皮交易策略。

---

## 📊 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    輸入：技術指標庫 (40+ 指標)                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  階段一：策略鑄造廠 (The Foundry) - 全自動化生成與海選            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  🤖 AI 生成策略 → 三週期回測 (3m/9m/18m) → 嚴格篩選             │
│                                                                  │
│  篩選標準：                                                       │
│  • 最大回撤 < 7%                                                 │
│  • 月均交易 > 60 筆                                              │
│  • 勝率 > 50%                                                    │
│  • 利潤因子 > 1.2                                                │
│  • 夏普比率 > 1.0                                                │
│                                                                  │
│  產出：候選策略池 (Candidate Pool)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  階段二：精煉工坊 (The Refinery) - 半自動化潛力優化               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  🔧 Hyperopt 參數優化 → 停損機制優化 → 績效評估                  │
│                                                                  │
│  優化目標：                                                       │
│  • 最大化夏普比率                                                 │
│  • 夏普提升 > 20%                                                │
│  • 優化後夏普 > 1.2                                              │
│                                                                  │
│  產出：優化候選池 (Optimized Candidates)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  階段三：決策室 (The War Room) - 人工審核與前向測試               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  👨‍💼 策略邏輯審核 → 樣本外測試 → 壓力測試 → 最終決策              │
│                                                                  │
│  決策選項：                                                       │
│  • 畢業 (Graduate): 投入實盤測試                                 │
│  • 退回 (Revert): 返回優化                                       │
│  • 淘汰 (Discard): 永久存檔                                      │
│                                                                  │
│  產出：畢業策略 (Graduated Strategies)                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                  🚀 部署至實盤交易系統
```

---

## 🚀 快速開始

### 環境要求

- Python 3.8+
- Freqtrade (已安裝並配置)
- Google Gemini CLI (已安裝)
- Git (版本控制)

### 階段一：啟動策略鑄造廠

```bash
cd ~/pywork/freqtrade/user_data/scripts/strategies_generate

# 驗證配置
cd foundry
python3 foundry_config.py

# 啟動鑄造廠 (7x24 持續運行)
cd ..
./run_foundry.sh start

# 查看實時日誌
tail -f foundry/logs/foundry_$(date +%Y%m%d).log

# 查看統計
./run_foundry.sh stats

# 停止運行
./run_foundry.sh stop
```

### 階段二：運行精煉工坊

```bash
# 優化候選池中的策略（默認最多 5 個）
./run_refinery.sh run

# 優化更多策略
./run_refinery.sh run 10

# 查看優化統計
./run_refinery.sh stats
```

### 階段三：決策室審核

```bash
# 啟動交互式儀表板
cd war_room
python3 war_room_dashboard.py

# 或使用命令行模式
python3 war_room_dashboard.py list               # 列出所有優化策略
python3 war_room_dashboard.py detail STRATEGY    # 查看詳情
python3 war_room_dashboard.py graduated          # 查看畢業策略
```

---

## 📁 目錄結構

```
strategies_generate/
│
├── foundry/                              # 🏭 階段一：策略鑄造廠
│   ├── foundry_config.py                 # 配置文件
│   ├── foundry_engine.py                 # 核心引擎
│   ├── temp_strategies/                  # 臨時策略（自動清理）
│   └── logs/                             # 運行日誌
│
├── refinery/                             # 🔧 階段二：精煉工坊
│   ├── refinery_config.py                # 配置文件
│   ├── refinery_engine.py                # 優化引擎
│   └── logs/                             # 運行日誌
│
├── war_room/                             # 🏛️  階段三：決策室
│   └── war_room_dashboard.py             # 交互式儀表板
│
├── successful_strategies/                # 💎 成功策略存儲
│   ├── candidate_pool/                   # 候選池（通過 Foundry）
│   │   └── candidate_YYYYMMDD_HHMMSS/
│   │       ├── gen_strategy_*.py
│   │       └── metadata.json
│   │
│   ├── optimized_candidates/             # 優化池（通過 Refinery）
│   │   └── optimized_YYYYMMDD_*/
│   │       ├── gen_strategy_*.py
│   │       └── optimization_report.json
│   │
│   └── graduated/                        # 畢業策略（準備實盤）
│       └── *_graduated_*/
│           ├── gen_strategy_*.py
│           ├── optimization_report.json
│           └── graduation_record.json
│
├── run_foundry.sh                        # 🏭 鑄造廠啟動腳本
├── run_refinery.sh                       # 🔧 精煉工坊啟動腳本
└── README.md                             # 📖 本文件
```

---

## 🎯 階段一：策略鑄造廠 (The Foundry)

### 功能說明

- **7x24 持續運行**：全自動化生成與測試
- **AI 驅動**：Gemini CLI 生成策略代碼
- **三週期驗證**：3個月、9個月、18個月回測
- **快速失敗**：短期不達標立即終止
- **自動修復**：修復常見代碼錯誤
- **Git 整合**：自動提交通過的策略

### 篩選標準

| 指標 | 標準 | 說明 |
|------|------|------|
| 最大回撤 | < 7% | 風險控制 |
| 月均交易 | > 60 筆 | 流動性要求 |
| 勝率 | > 50% | 獲利穩定性 |
| 利潤因子 | > 1.2 | 風險回報比 |
| 夏普比率 | > 1.0 | 風險調整後收益 |

### 命令說明

```bash
./run_foundry.sh start    # 啟動鑄造廠
./run_foundry.sh stop     # 停止運行
./run_foundry.sh restart  # 重啟
./run_foundry.sh status   # 查看狀態
./run_foundry.sh stats    # 統計報告
./run_foundry.sh watch    # 實時監控
./run_foundry.sh cleanup  # 清理日誌
```

### 配置修改

編輯 `foundry/foundry_config.py`：

```python
# 修改篩選標準
FOUNDRY_CRITERIA = {
    'max_drawdown': 0.07,        # 最大回撤
    'min_trades_per_month': 60,  # 月均交易
    'min_win_rate': 0.50,        # 勝率
    'min_profit_factor': 1.2,    # 利潤因子
    'min_sharpe_ratio': 1.0,     # 夏普比率
}

# 修改運行間隔
CYCLE_INTERVAL = 60  # 秒
```

---

## 🔧 階段二：精煉工坊 (The Refinery)

### 功能說明

- **Hyperopt 優化**：自動尋找最佳參數
- **多空間優化**：ROI、止損、買入/賣出信號
- **性能比較**：優化前後對比
- **智能晉升**：顯著提升才晉升

### 優化目標

- **主要目標**：最大化夏普比率
- **晉升標準**：夏普提升 > 20% 或 優化後夏普 > 1.2

### 命令說明

```bash
./run_refinery.sh run        # 優化 5 個策略
./run_refinery.sh run 10     # 優化 10 個策略
./run_refinery.sh stats      # 查看統計
```

### 配置修改

編輯 `refinery/refinery_config.py`：

```python
# Hyperopt 配置
HYPEROPT_EPOCHS = 100  # 優化輪數
HYPEROPT_LOSS = "SharpeHyperOptLoss"  # 優化目標
HYPEROPT_SPACES = ["buy", "sell", "roi", "stoploss"]

# 優化標準
REFINEMENT_CRITERIA = {
    'sharpe_improvement': 0.20,      # 夏普提升 > 20%
    'profit_improvement': 0.15,      # 利潤提升 > 15%
    'min_sharpe_after_opt': 1.2,     # 優化後夏普 > 1.2
}
```

---

## 🏛️  階段三：決策室 (The War Room)

### 功能說明

- **交互式儀表板**：查看優化策略詳情
- **性能對比**：優化前後完整對比
- **畢業管理**：標記策略為可部署
- **審核追蹤**：記錄審核決策

### 審核流程

1. **查看優化策略列表**
   ```bash
   python3 war_room_dashboard.py list
   ```

2. **查看策略詳情**
   ```bash
   python3 war_room_dashboard.py detail optimized_YYYYMMDD_*
   ```

3. **人工審核要點**
   - 策略邏輯是否清晰合理？
   - 是否存在過度擬合？
   - 是否有未來函數？
   - 交易邏輯是否穩健？

4. **標記為畢業**
   ```bash
   # 交互式模式
   python3 war_room_dashboard.py
   # 選擇選項 3，輸入策略名稱和審核備註
   ```

### 決策選項

| 決策 | 操作 | 說明 |
|------|------|------|
| **畢業 (Graduate)** | 標記為畢業 | 投入模擬交易或小資金實盤 |
| **退回 (Revert)** | 移回候選池 | 返回階段二進行調整 |
| **淘汰 (Discard)** | 永久存檔 | 不予採用，保留供研究 |

---

## 📊 性能指標說明

### KPI 定義

- **夏普比率 (Sharpe Ratio)**：風險調整後收益，> 1.0 為佳
- **最大回撤 (Max Drawdown)**：最大虧損幅度，< 7% 為佳
- **勝率 (Win Rate)**：獲利交易比例，> 50% 為佳
- **利潤因子 (Profit Factor)**：總獲利/總虧損，> 1.2 為佳
- **月均交易 (Trades/Month)**：流動性指標，> 60 筆為佳

---

## 🔄 完整工作流程

### 自動化部分（階段一）

```bash
# 1. 啟動鑄造廠（持續運行）
./run_foundry.sh start

# 系統將自動：
# - 生成指標組合
# - 調用 AI 生成策略
# - 執行三週期回測
# - 嚴格篩選
# - 通過的策略自動進入候選池
# - Git 自動提交
```

### 定期執行（階段二）

```bash
# 2. 每週執行一次優化（建議週末）
./run_refinery.sh run 10

# 系統將：
# - 對候選池中的策略進行 Hyperopt 優化
# - 比較優化前後性能
# - 顯著提升的策略進入優化池
# - Git 自動提交
```

### 人工審核（階段三）

```bash
# 3. 定期審核優化策略（每週或每月）
cd war_room
python3 war_room_dashboard.py

# 您需要：
# - 查看優化策略列表
# - 分析策略邏輯和性能
# - 決定畢業、退回或淘汰
# - 記錄審核決策
```

---

## 🛠️ 故障排除

### Foundry 相關

**問題：策略生成失敗**
```bash
# 檢查 Gemini CLI
gemini --version

# 查看詳細日誌
tail -100 foundry/logs/foundry_*.log | grep ERROR
```

**問題：回測失敗**
```bash
# 驗證配置
cd foundry
python3 foundry_config.py

# 檢查數據
ls -la ~/pywork/freqtrade/user_data/data/bybit/
```

### Refinery 相關

**問題：Hyperopt 超時**
```python
# 編輯 refinery/refinery_config.py
HYPEROPT_EPOCHS = 50  # 減少輪數
```

**問題：無候選策略可優化**
```bash
# 檢查候選池
ls -la successful_strategies/candidate_pool/

# 先運行 Foundry 生成候選策略
./run_foundry.sh start
```

---

## 📈 系統監控

### 查看運行狀態

```bash
# Foundry 狀態
./run_foundry.sh status

# 統計報告
./run_foundry.sh stats
./run_refinery.sh stats

# 實時監控
./run_foundry.sh watch
```

### Git 歷史追蹤

```bash
# 查看提交歷史
git log --oneline | grep "Foundry\|Refinery"

# 查看特定策略的提交
git log --all --grep="strategy_name"
```

---

## 🎓 最佳實踐

### 運行建議

1. **Foundry**：長期持續運行（7x24），建議使用 nohup 或 tmux
2. **Refinery**：每週定期執行（週末），避免高峰時段
3. **War Room**：每週或每月審核一次，確保質量控制

### 資源管理

1. **定期清理**：刪除失敗的臨時策略
2. **日誌管理**：定期清理 7 天前的日誌
3. **磁碟監控**：監控策略文件數量，避免爆滿

### 安全建議

1. **小資金測試**：畢業策略先用小資金實盤測試
2. **持續監控**：實盤運行時持續監控性能
3. **止損保護**：確保所有策略都有合理止損

---

## 📞 技術支援

如遇問題，請檢查：

1. **日誌文件**：`foundry/logs/`, `refinery/logs/`
2. **配置文件**：確保路徑和參數正確
3. **依賴環境**：Python、Freqtrade、Gemini CLI

---

## 📄 授權聲明

本系統為內部交易工具，僅供授權人員使用。
策略代碼與回測結果僅供參考，實盤交易需自負風險。

---

**版本**: v2.0 (三階段漏斗系統)  
**最後更新**: 2025-10-06  
**系統狀態**: ✅ 生產就緒

**開始探索獲利策略！** 🚀💰
