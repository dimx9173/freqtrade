#!/bin/zsh

# 腳本配置
# ---
# monitor_run.sh 監控 freqtrade 程序，如果程序意外終止，則重啟程序
# monitor_run.sh "zsh hyperopt.sh 12 > user_data/logs/auto_crontab.log"
COMMAND="$1"
# 可選：第二個參數指定週期性重啟秒數（預設 0 = 關閉）。
# 若交由外部每 7 天觸發 auto_optimize.sh，建議維持 0。
RESTART_INTERVAL=${2:-0}

# 腳本所在目錄（用於引用 scripts/*）
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# 嘗試自 COMMAND 字串解析 config 與 strategy（若無則留空）
CONFIG_PATH=$(echo "$COMMAND" | sed -nE 's/.*--config[[:space:]]+([^[:space:]]+).*/\1/p')
STRATEGY_NAME=$(echo "$COMMAND" | sed -nE 's/.*--strategy[[:space:]]+([^[:space:]]+).*/\1/p')

# 停止旗標與子進程 PID 追蹤
STOP_REQUESTED=0
PID_TRACKER=""
CHILD_PGID=""
OWN_PGID=$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')

# 清理：在腳本結束前先關閉策略程序
cleanup() {
  STOP_REQUESTED=1
  echo "接收到結束訊號，正在停止策略進程..."

  # 先嘗試優雅結束目前追蹤的進程組（若存在），否則針對單一 PID
  if [[ -n "$CHILD_PGID" ]] && [[ "$CHILD_PGID" != "$OWN_PGID" ]]; then
    kill -TERM -$CHILD_PGID 2>/dev/null || true
  elif [[ -n "$PID_TRACKER" ]] && kill -0 $PID_TRACKER 2>/dev/null; then
    kill -TERM $PID_TRACKER 2>/dev/null || true
  fi

  # 若能解析出 config 與 strategy，使用 scripts/stop_by_ps.sh 輔助關閉
  if [[ -n "$CONFIG_PATH" ]] && [[ -n "$STRATEGY_NAME" ]] && [[ -x "$SCRIPT_DIR/scripts/stop_by_ps.sh" ]]; then
    zsh "$SCRIPT_DIR/scripts/stop_by_ps.sh" "$CONFIG_PATH" "$STRATEGY_NAME" || true
  fi

  # 最多等待 60 秒讓子進程（或其進程組）優雅退出
  END_TIME=$(( $(date +%s) + 60 ))
  while true; do
    if [[ -n "$CHILD_PGID" ]]; then
      if ! kill -0 -$CHILD_PGID 2>/dev/null; then
        break
      fi
    elif [[ -n "$PID_TRACKER" ]]; then
      if ! kill -0 $PID_TRACKER 2>/dev/null; then
        break
      fi
    else
      break
    fi
    if [[ $(date +%s) -ge ${END_TIME} ]]; then
      echo "等待優雅退出逾時，強制結束"
      if [[ -n "$CHILD_PGID" ]] && [[ "$CHILD_PGID" != "$OWN_PGID" ]]; then
        kill -KILL -$CHILD_PGID 2>/dev/null || true
      elif [[ -n "$PID_TRACKER" ]]; then
        kill -KILL $PID_TRACKER 2>/dev/null || true
      fi
      break
    fi
    sleep 2
  done

  echo "策略進程已停止，退出監控腳本。"
}

# 監聽常見結束訊號以及 EXIT
trap 'cleanup' INT TERM HUP QUIT EXIT

# 設定重啟週期（單位：秒）。
# 預設關閉（交由外部排程觸發最佳化與重啟）。

# 腳本主邏輯
# ---
echo "腳本啟動中... 開始監控 freqtrade 程序。"

# 追蹤上次重啟的時間
LAST_RESTART=$(date +%s)

while true; do

  # 檢查是否需要定期重啟
  CURRENT_TIME=$(date +%s)
  if [[ $RESTART_INTERVAL -gt 0 ]] && [[ $((CURRENT_TIME - LAST_RESTART)) -ge $RESTART_INTERVAL ]]; then
    echo "已達到週期重啟秒數（$RESTART_INTERVAL），正在重啟程序..."
    kill $PID_TRACKER &>/dev/null
    wait $PID_TRACKER &>/dev/null
    LAST_RESTART=$CURRENT_TIME
    echo "程序已重啟。"
  fi

  # 啟動 freqtrade 程序（以新進程組啟動，便於整組終止）
  echo "正在啟動 freqtrade..."
  if command -v setsid >/dev/null 2>&1; then
    setsid zsh -c "exec $COMMAND" &
  else
    # 回退：不使用 setsid，仍嘗試以單一 PID 追蹤
    zsh -c "exec $COMMAND" &
  fi
  PID_TRACKER=$!
  # 取得進程組 ID（去除空白）
  CHILD_PGID=$(ps -o pgid= -p $PID_TRACKER 2>/dev/null | tr -d ' ')

  # 等待程序結束
  wait $PID_TRACKER

  # 若為外部要求停止，則不再重啟
  if [[ $STOP_REQUESTED -eq 1 ]]; then
    echo "已完成停止要求，結束監控。"
    break
  fi

  # 當程序結束時，發出通知並重啟
  echo "freqtrade 程序意外終止，正在重新啟動..."
  sleep 10 # 短暫延遲，避免啟動過於頻繁
  PID_TRACKER=""
  CHILD_PGID=""
done
