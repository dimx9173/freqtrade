#!/bin/bash
# ==============================================
# Working Tree Dirty Watchdog (治本 MEMORY pitfall 18)
# ==============================================
# 用法:
#   1. 部署: cp dirty_watchdog.sh ~/.hermes/scripts/
#   2. 加 cron: 0 */6 * * * (每 6 小時檢查一次)
#   3. 發現 > 5 dirty 時, 發 Telegram 警告
#
# 設計:
# - 進入 ~/freqtrade (or 多個 repo)
# - git status --porcelain 計數
# - 超過閾值 (預設 5) → 警告
# - 同時列出 dirty 檔名, 方便定位
#
# 治本邏輯:
# - dirty > 5 → 觸發 0→not_clean cron job
# - not_clean > 24h → 觸發 daily_digest
# - daily_digest 連 3 天 → 觸發 Brian Telegram 強提醒

set -e

REPO="/home/brian/freqtrade"
THRESHOLD=5
LOG="/home/brian/.hermes/logs/dirty_watchdog.log"
mkdir -p "$(dirname "$LOG")"

cd "$REPO" || { echo "[$(date)] $REPO not accessible" >> "$LOG"; exit 1; }

# git status --porcelain 計數 (M/A/D/?/!!)
DIRTY_COUNT=$(git status --porcelain 2>/dev/null | wc -l)
UNTRACKED_COUNT=$(git status --porcelain 2>/dev/null | grep "^??" | wc -l)
MODIFIED_COUNT=$(git status --porcelain 2>/dev/null | grep "^ M" | wc -l)

echo "[$(date +%H:%M:%S)] dirty=$DIRTY_COUNT modified=$MODIFIED_COUNT untracked=$UNTRACKED_COUNT" >> "$LOG"

# 閾值警告
if [ "$DIRTY_COUNT" -gt "$THRESHOLD" ]; then
  echo ""
  echo "🚨 DIRTY WATCHDOG ALERT"
  echo "  Repo: $REPO"
  echo "  Dirty: $DIRTY_COUNT (modified=$MODIFIED_COUNT untracked=$UNTRACKED_COUNT)"
  echo "  Threshold: $THRESHOLD"
  echo "  Files:"
  git status --short | head -20
  echo ""
  echo "  [治本] git add -u && git commit (按類型分 commit)"
  echo "  [治本] 嚴重 dirty: git checkout -- <file> (還原)"
  echo "  [治本] 治本: 每次改完即 commit (MEMORY 鐵律 #4)"
fi

# 永遠 exit 0 (watchdog 不應 fail cron chain)
exit 0
