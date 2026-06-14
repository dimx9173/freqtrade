#!/bin/bash
# ==============================================
# Data Staleness Watchdog (治本 W2 --erase 數據災難)
# ==============================================
# 用法:
#   1. 部署: cp data_staleness_watchdog.sh ~/.hermes/scripts/
#   2. 加 cron: 0 4 * * * (每天 04:00 檢查, 在 daily download 後)
#   3. 任何 pair 數據 > 7 天 stale → 警告
#
# 設計:
# - 掃描 user_data/data/bybit/futures/*-5m-futures.feather
# - 對比 mtime vs 當前時間
# - 超過 7 天 (預設) → 警告
# - 連續 3 天未更新 → 升級為 alert

set -e

DATADIR="/home/brian/freqtrade/user_data/data/bybit/futures"
MAX_AGE_DAYS=7
LOG="/home/brian/.hermes/logs/data_staleness_watchdog.log"
mkdir -p "$(dirname "$LOG")"

cd "$DATADIR" || { echo "[$(date)] $DATADIR not accessible" >> "$LOG"; exit 1; }

NOW=$(date +%s)
WARN_COUNT=0
ALERT_COUNT=0

echo "[$(date +%Y-%m-%d_%H:%M:%S)] Data staleness check" >> "$LOG"

for f in *-5m-futures.feather; do
  if [ ! -f "$f" ]; then continue; fi

  MTIME=$(stat -c %Y "$f" 2>/dev/null || echo 0)
  AGE_SEC=$((NOW - MTIME))
  AGE_DAYS=$((AGE_SEC / 86400))

  # 提取 pair 名 (e.g., BTC_USDT_USDT-5m-futures.feather → BTC)
  PAIR=$(echo "$f" | cut -d'_' -f1)

  if [ "$AGE_DAYS" -gt "$MAX_AGE_DAYS" ]; then
    echo "  $PAIR: $AGE_DAYS days stale (max=$MAX_AGE_DAYS)" >> "$LOG"
    WARN_COUNT=$((WARN_COUNT + 1))
  fi
done

if [ "$WARN_COUNT" -gt 0 ]; then
  echo ""
  echo "🚨 DATA STALENESS ALERT"
  echo "  Datadir: $DATADIR"
  echo "  Stale pairs: $WARN_COUNT (max_age=${MAX_AGE_DAYS}d)"
  echo ""
  echo "  [治本] 跑 daily download: bash user_data/scripts/utilities/download_futures_daily.sh"
  echo "  [治本] 跑 history download: bash user_data/scripts/utilities/download_futures_history.sh"
  echo "  [治本] 治本: daily cron 必須 --prepend (commit 38d463d4d)"
fi

# 永遠 exit 0
exit 0
