# 📦 Git 版本控制整合

## 概述

系統已整合 Git 自動提交功能，所有通過篩選的策略將自動納入版本控制。

---

## 🔄 自動提交機制

### 階段一：Foundry 自動提交

**觸發時機**：策略通過三週期篩選後

**提交內容**：
- 策略文件：`gen_strategy_*.py`
- 元數據：`metadata.json`

**提交信息格式**：
```
🎯 Foundry: Add candidate strategy {strategy_name} | Win Rate: {win_rate}% | Sharpe: {sharpe}
```

**範例**：
```
🎯 Foundry: Add candidate strategy gen_strategy_20251006_123045_a3f7d9e1 | Win Rate: 52.3% | Sharpe: 1.15
```

### 階段二：Refinery 自動提交

**觸發時機**：策略優化顯著提升後

**提交內容**：
- 優化策略文件：`gen_strategy_*.py`
- 優化報告：`optimization_report.json`

**提交信息格式**：
```
🔧 Refinery: Optimized {strategy_name} | Sharpe: {sharpe_before:.2f} → {sharpe_after:.2f}
```

**範例**：
```
🔧 Refinery: Optimized gen_strategy_20251006_123045 | Sharpe: 1.15 → 1.42
```

---

## ⚙️ 配置說明

### 啟用/禁用自動提交

#### Foundry

編輯 `foundry/foundry_config.py`：

```python
# Git 配置
ENABLE_GIT_INTEGRATION = True  # 啟用
GIT_AUTO_COMMIT = True         # 自動提交
```

#### Refinery

編輯 `refinery/refinery_config.py`：

```python
# Git 配置
ENABLE_GIT_INTEGRATION = True  # 啟用
```

### 自定義提交信息

#### Foundry

```python
GIT_COMMIT_MESSAGE_TEMPLATE = "🎯 Foundry: Add {strategy_name} | WR: {win_rate}% | SR: {sharpe}"
```

#### Refinery

```python
GIT_COMMIT_MESSAGE_TEMPLATE = "🔧 Refinery: {strategy_name} | Sharpe: {sharpe_before} → {sharpe_after}"
```

---

## 📝 手動 Git 操作

### 初始化（首次使用）

```bash
cd ~/pywork/freqtrade/user_data/scripts/strategies_generate

# 如果還未初始化 Git
git init

# 添加 .gitignore
cat > .gitignore << EOF
# 日誌文件
*.log
logs/
*.pid

# 臨時文件
temp_strategies/
__pycache__/
*.pyc
*.pyo

# 舊版本備份
archive_old/

# 回測結果（太大，不納入版本控制）
*.json.zip
backtest_results/
EOF

# 首次提交
git add .
git commit -m "🎉 Init: Three-stage funnel strategy system v2.0"
```

### 查看提交歷史

```bash
# 查看所有提交
git log --oneline

# 只查看 Foundry 提交
git log --oneline --grep="Foundry"

# 只查看 Refinery 提交
git log --oneline --grep="Refinery"

# 查看最近 10 條
git log --oneline -10

# 圖形化查看
git log --graph --oneline --all
```

### 查看特定策略的歷史

```bash
# 查看某個策略的提交記錄
git log --all --grep="gen_strategy_20251006_123045"

# 查看策略文件的變更歷史
git log --follow -- successful_strategies/candidate_pool/candidate_20251006_123045/gen_strategy_*.py
```

### 回滾操作

```bash
# 查看最近的提交
git log -5

# 回滾到某個提交（保留工作區修改）
git reset --soft HEAD~1

# 回滾到某個提交（丟棄所有修改）⚠️  危險操作
git reset --hard <commit-hash>
```

---

## 🔍 Git 查詢技巧

### 按性能指標搜索

```bash
# 查找勝率 > 50% 的策略
git log --grep="Win Rate: 5[0-9]\|Win Rate: [6-9]"

# 查找夏普 > 1.5 的策略
git log --grep="Sharpe: 1\.[5-9]\|Sharpe: [2-9]"

# 查找優化提升 > 30% 的策略
git log --grep="Refinery.*→" --all
```

### 按時間搜索

```bash
# 查看今天的提交
git log --since="today"

# 查看本週的提交
git log --since="1 week ago"

# 查看某個時間範圍
git log --since="2025-10-01" --until="2025-10-07"
```

### 按文件搜索

```bash
# 查看候選池的所有變更
git log -- successful_strategies/candidate_pool/

# 查看優化池的所有變更
git log -- successful_strategies/optimized_candidates/

# 查看畢業策略的所有變更
git log -- successful_strategies/graduated/
```

---

## 📊 統計報告

### 生成統計

```bash
# 總提交數
git rev-list --count HEAD

# Foundry 提交數
git log --oneline --grep="Foundry" | wc -l

# Refinery 提交數
git log --oneline --grep="Refinery" | wc -l

# 今日提交數
git log --since="today" --oneline | wc -l

# 本週提交數
git log --since="1 week ago" --oneline | wc -l
```

### 生成報告

```bash
# 生成本週策略報告
echo "本週生成的策略:" > weekly_report.txt
git log --since="1 week ago" --grep="Foundry" --pretty=format:"%s" >> weekly_report.txt

# 生成本週優化報告
echo "\n本週優化的策略:" >> weekly_report.txt
git log --since="1 week ago" --grep="Refinery" --pretty=format:"%s" >> weekly_report.txt

cat weekly_report.txt
```

---

## 🌐 遠程倉庫整合（可選）

### 設置 GitHub/GitLab

```bash
# 添加遠程倉庫
git remote add origin https://github.com/your-username/freqtrade-strategies.git

# 推送到遠程
git push -u origin main

# 之後每次手動推送
git push
```

### 自動推送（謹慎使用）

如需自動推送，編輯 `foundry/foundry_engine.py`：

```python
def git_commit_strategy(self, strategy_path, metadata):
    """將策略提交到 Git"""
    try:
        # ... 現有提交邏輯 ...
        
        # 添加自動推送（可選）
        subprocess.run(['git', 'push'],
                     cwd=str(Config.STRATEGIES_GENERATE_DIR), check=False)
        
        logger.info(f"📤 已推送到遠程倉庫")
        
    except Exception as e:
        logger.warning(f"⚠️  Git 操作失敗: {e}")
```

**⚠️  注意**：自動推送需要配置 SSH 金鑰或憑證存儲，避免頻繁輸入密碼。

---

## 🛡️  最佳實踐

### 1. 定期備份

```bash
# 每週備份一次
git bundle create ~/backups/strategies_$(date +%Y%m%d).bundle --all

# 恢復備份
git clone ~/backups/strategies_20251006.bundle restored_strategies
```

### 2. 分支管理

```bash
# 創建實驗分支
git checkout -b experiment/new-indicators

# 切換回主分支
git checkout main

# 合併實驗結果
git merge experiment/new-indicators
```

### 3. 標籤管理

```bash
# 標記重要版本
git tag -a v1.0-foundry-milestone -m "首個通過 Foundry 的策略"

# 標記畢業策略
git tag -a graduated-strategy-001 -m "第一個畢業策略"

# 查看所有標籤
git tag -l

# 查看標籤詳情
git show v1.0-foundry-milestone
```

### 4. .gitignore 維護

確保 `.gitignore` 包含：

```gitignore
# 日誌
*.log
logs/
*.pid

# 臨時文件
temp_strategies/
__pycache__/
*.pyc

# 大文件（回測結果）
*.json.zip
backtest_results/

# 舊版本
archive_old/
```

---

## 📈 進階用法

### 生成策略性能趨勢報告

```bash
#!/bin/bash
# generate_performance_trend.sh

echo "策略性能趨勢報告"
echo "=================="
echo ""

echo "近期 Foundry 策略勝率趨勢:"
git log --since="1 month ago" --grep="Foundry" --pretty=format:"%ad | %s" --date=short | \
grep -oP "Win Rate: \K[0-9.]+" | \
awk '{sum+=$1; count++} END {print "平均勝率: " sum/count "%"}'

echo ""
echo "近期 Refinery 夏普提升:"
git log --since="1 month ago" --grep="Refinery" --pretty=format:"%ad | %s" --date=short

echo ""
echo "總計:"
echo "  Foundry 策略數: $(git log --grep='Foundry' --oneline | wc -l)"
echo "  Refinery 優化數: $(git log --grep='Refinery' --oneline | wc -l)"
```

---

## 🆘 故障排除

### 問題 1：提交失敗

```bash
# 檢查 Git 狀態
git status

# 檢查是否有未提交的更改
git diff

# 手動提交
git add successful_strategies/
git commit -m "Manual commit"
```

### 問題 2：合併衝突

```bash
# 查看衝突文件
git status

# 手動解決衝突後
git add <resolved-file>
git commit -m "Resolved conflict"
```

### 問題 3：倉庫過大

```bash
# 清理歷史中的大文件
git filter-branch --tree-filter 'rm -rf backtest_results' HEAD

# 強制垃圾回收
git gc --aggressive --prune=now
```

---

**版本**: v2.0  
**最後更新**: 2025-10-06  
**維護者**: 策略開發團隊
