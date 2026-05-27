# 🚀 快速啟動指南 v2.0

## 三階段漏斗系統快速上手

---

## ⚡ 3 分鐘快速啟動

### 1️⃣ 驗證環境（30秒）

```bash
# 確認依賴
python3 --version   # 需要 3.8+
gemini --version    # 需要已安裝
git --version       # 需要已安裝

# 進入工作目錄
cd ~/pywork/freqtrade/user_data/scripts/strategies_generate
```

### 2️⃣ 啟動鑄造廠（1分鐘）

```bash
# 驗證配置
cd foundry
python3 foundry_config.py

# 啟動系統
cd ..
./run_foundry.sh start

# 應該看到：
# ✓ 配置驗證通過
# ✓ 鑄造廠啟動成功
# ℹ PID: XXXXX
```

### 3️⃣ 監控運行（持續）

```bash
# 查看實時日誌
tail -f foundry/logs/foundry_$(date +%Y%m%d).log

# 或查看統計
./run_foundry.sh stats

# 按 Ctrl+C 退出日誌查看（系統繼續運行）
```

**✅ 完成！** 系統現在正在 7x24 自動生成與篩選策略。

---

## 📊 三階段操作流程

### 🏭 階段一：策略鑄造廠（全自動）

**目標**：從 AI 生成的策略中，自動篩選出穩健的候選策略

```bash
# 啟動（一次性操作，之後持續運行）
./run_foundry.sh start

# 日常監控
./run_foundry.sh stats      # 查看統計
./run_foundry.sh watch      # 實時監控（10秒刷新）
./run_foundry.sh status     # 查看運行狀態

# 停止（如需維護）
./run_foundry.sh stop
```

**產出目錄**：`successful_strategies/candidate_pool/`

**篩選標準**：
- ✅ 回撤 < 7%
- ✅ 月交易 > 60 筆
- ✅ 勝率 > 50%
- ✅ 利潤因子 > 1.2
- ✅ 夏普 > 1.0

---

### 🔧 階段二：精煉工坊（定期執行）

**目標**：優化候選策略，找到最佳參數

**建議頻率**：每週執行一次（例如週日）

```bash
# 優化候選池中的策略（默認最多 5 個）
./run_refinery.sh run

# 優化更多策略
./run_refinery.sh run 10

# 查看優化結果
./run_refinery.sh stats
```

**產出目錄**：`successful_strategies/optimized_candidates/`

**晉升標準**：
- ✅ 夏普提升 > 20%
- ✅ 或優化後夏普 > 1.2

---

### 🏛️  階段三：決策室（定期審核）

**目標**：人工審核優化策略，決定是否部署

**建議頻率**：每週或每月一次

```bash
cd war_room

# 啟動交互式儀表板
python3 war_room_dashboard.py

# 或使用命令行模式
python3 war_room_dashboard.py list               # 列表
python3 war_room_dashboard.py detail STRATEGY    # 詳情
python3 war_room_dashboard.py graduated          # 畢業策略
```

**交互式菜單**：
```
1. 查看優化策略列表
2. 查看策略詳情
3. 標記策略為畢業
4. 查看畢業策略
0. 退出
```

**產出目錄**：`successful_strategies/graduated/`

---

## 🎯 典型使用場景

### 場景 1：首次運行

```bash
# Day 1：啟動鑄造廠
./run_foundry.sh start

# 系統開始 7x24 運行，自動生成和篩選策略
# 等待 1-2 週累積候選策略
```

### 場景 2：週末優化

```bash
# 週日：檢查候選池
./run_foundry.sh stats

# 如果有 5+ 個候選策略，執行優化
./run_refinery.sh run 5

# 查看優化結果
./run_refinery.sh stats
```

### 場景 3：月度審核

```bash
# 每月第一個週末：審核優化策略
cd war_room
python3 war_room_dashboard.py

# 在交互式界面中：
# 1. 查看所有優化策略
# 2. 逐個查看詳情
# 3. 決定是否畢業
# 4. 對畢業策略進行實盤測試準備
```

---

## 📁 目錄速查

```
strategies_generate/
├── foundry/                    # 階段一：自動生成與篩選
│   ├── logs/                   # 運行日誌
│   └── temp_strategies/        # 臨時策略
│
├── refinery/                   # 階段二：參數優化
│   └── logs/                   # 優化日誌
│
├── war_room/                   # 階段三：人工審核
│   └── war_room_dashboard.py   # 儀表板
│
└── successful_strategies/      # 成功策略存儲
    ├── candidate_pool/         # 候選池 ← Foundry 產出
    ├── optimized_candidates/   # 優化池 ← Refinery 產出
    └── graduated/              # 畢業策略 ← War Room 產出
```

---

## 🔧 常用命令速查表

### Foundry（階段一）

| 命令 | 說明 |
|------|------|
| `./run_foundry.sh start` | 啟動鑄造廠 |
| `./run_foundry.sh stop` | 停止運行 |
| `./run_foundry.sh restart` | 重啟 |
| `./run_foundry.sh status` | 查看狀態 |
| `./run_foundry.sh stats` | 統計報告 |
| `./run_foundry.sh watch` | 實時監控 |
| `./run_foundry.sh cleanup` | 清理舊日誌 |

### Refinery（階段二）

| 命令 | 說明 |
|------|------|
| `./run_refinery.sh run` | 優化 5 個策略 |
| `./run_refinery.sh run N` | 優化 N 個策略 |
| `./run_refinery.sh stats` | 統計報告 |

### War Room（階段三）

| 命令 | 說明 |
|------|------|
| `python3 war_room_dashboard.py` | 交互式模式 |
| `python3 war_room_dashboard.py list` | 列出所有策略 |
| `python3 war_room_dashboard.py detail NAME` | 查看詳情 |
| `python3 war_room_dashboard.py graduated` | 畢業策略 |

---

## ⚠️  常見問題

### Q1: 如何停止 Foundry？

```bash
./run_foundry.sh stop
```

### Q2: 如何查看生成了多少策略？

```bash
./run_foundry.sh stats
```

### Q3: Foundry 生成太慢怎麼辦？

檢查 Gemini CLI 是否正常：
```bash
gemini --version

# 查看日誌中的錯誤
tail -50 foundry/logs/foundry_*.log | grep ERROR
```

### Q4: 候選池中沒有策略可優化？

先運行 Foundry 一段時間（至少幾天），累積候選策略：
```bash
# 檢查候選池
ls -la successful_strategies/candidate_pool/

# 如果為空，確保 Foundry 在運行
./run_foundry.sh status
```

### Q5: 如何修改篩選標準？

編輯配置文件：
```bash
# Foundry 標準
vim foundry/foundry_config.py
# 找到 FOUNDRY_CRITERIA

# Refinery 標準
vim refinery/refinery_config.py
# 找到 REFINEMENT_CRITERIA
```

### Q6: 回測失敗怎麼辦？

驗證配置：
```bash
cd foundry
python3 foundry_config.py

# 檢查數據目錄
ls -la ~/pywork/freqtrade/user_data/data/bybit/
```

---

## 📊 預期時間線

### 第 1 週

- **Day 1**：啟動 Foundry
- **Day 2-7**：系統持續運行，生成 5-20 個候選策略（取決於 AI 速度和篩選通過率）

### 第 2 週

- **週末**：執行第一次 Refinery 優化（5-10 個候選策略）
- **結果**：2-5 個優化策略進入優化池

### 第 3-4 週

- **持續**：Foundry 繼續生成新候選
- **週末**：定期執行 Refinery
- **累積**：優化池達到 10+ 個策略

### 第 1 個月底

- **月度審核**：在 War Room 中審核所有優化策略
- **決策**：選出 2-3 個策略標記為畢業
- **準備**：為畢業策略準備實盤測試環境

---

## 🎓 下一步行動

### 立即行動

1. ✅ 啟動 Foundry：`./run_foundry.sh start`
2. ✅ 設置定期提醒：每週日執行 Refinery
3. ✅ 標記日曆：每月第一個週末進行 War Room 審核

### 學習資源

- 完整文檔：`README.md`
- Foundry 配置：`foundry/foundry_config.py`
- Refinery 配置：`refinery/refinery_config.py`
- 日誌查看：`foundry/logs/`, `refinery/logs/`

---

**版本**: v2.0  
**更新日期**: 2025-10-06  
**開始探索獲利策略！** 🚀💰
