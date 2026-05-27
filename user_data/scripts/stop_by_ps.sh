#!/bin/zsh
# stop_by_ps.sh
# 功能：根據 config 檔案和策略名稱，找到對應的 monitor_run.sh 行程並優雅停止
# 用法：zsh stop_by_ps.sh "user_data/config/config_3.json" "BB_RPB_TSL_BI"

CONFIG_FILE="$1"
STRATEGY_NAME="$2"

if [[ -z "$CONFIG_FILE" ]] || [[ -z "$STRATEGY_NAME" ]]; then
  echo "用法: zsh stop_by_ps.sh <config_file> <strategy_name>"
  echo "範例: zsh stop_by_ps.sh user_data/config/config_3.json BB_RPB_TSL_BI"
  exit 1
fi

echo "正在查找 Bot: config=$CONFIG_FILE strategy=$STRATEGY_NAME"

# 找到 freqtrade trade subprocess 的 PID
# --strategy 在 Python subprocess cmdline 中可直接匹配
# grep -v grep 排除 grep 自己
# awk 取得 PID（第一欄）
PID=$(ps aux | grep "freqtrade trade.*--strategy $STRATEGY_NAME" | grep "$CONFIG_FILE" | grep -v grep | awk '{print $2}' | head -1)

if [[ -z "$PID" ]]; then
  echo "找不到運行中的 Bot (config: $CONFIG_FILE, strategy: $STRATEGY_NAME)"
  exit 1
fi

echo "找到 monitor_run.sh PID: $PID"

# 取得該 PID 的進程組 ID（Process Group ID），這樣可以一次殺掉 monitor_run.sh 和它的子 freqtrade 進程
PGID=$(ps -o pgid= -p $PID 2>/dev/null | tr -d ' ')

if [[ -z "$PGID" ]]; then
  echo "無法取得進程組 ID，嘗試直接殺掉 PID: $PID"
  kill -TERM $PID 2>/dev/null
else
  echo "進程組 PGID: $PGID"
  # 殺掉整個進程組（負號表示 PGID）
  kill -TERM -$PGID 2>/dev/null
fi

# 等待進程結束（最多 90 秒）
echo "正在等待進程優雅結束..."
COUNT=0
while true; do
  if ! kill -0 $PID 2>/dev/null; then
    echo "Bot 已停止 (PID: $PID)"
    exit 0
  fi
  sleep 3
  COUNT=$((COUNT + 3))
  if [[ $COUNT -ge 90 ]]; then
    echo "等待逾時，強制結束..."
    kill -KILL -$PGID 2>/dev/null
    kill -KILL $PID 2>/dev/null
    sleep 2
    if kill -0 $PID 2>/dev/null; then
      echo "WARNING: Process still alive after SIGKILL"
    fi
    exit 1
  fi
  echo "  等待中... ${COUNT}s"
done
