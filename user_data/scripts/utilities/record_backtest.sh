#!/bin/bash
# record_backtest.sh — 自動記錄回測結果到 strategy_evolution_log.md
# 用法: ./record_backtest.sh <version> <timerange>
# 範例: ./record_backtest.sh v70.2 20251101-20260501

VERSION=$1
TIMERANGE=$2
LOG_FILE=${3:-"/tmp/latest_backtest.log"}
RESULT_FILE="/home/brian/freqtrade/user_data/reports/strategy_evolution_log.md"

if [ -z "$VERSION" ] || [ -z "$TIMERANGE" ]; then
    echo "用法: $0 <version> <timerange> [log_file]"
    echo "範例: $0 v70.2 20251101-20260501"
    exit 1
fi

if [ ! -f "$LOG_FILE" ]; then
    echo "錯誤: 找不到 log 檔案 $LOG_FILE"
    exit 1
fi

# 提取關鍵數據
PROFIT=$(grep "Total profit %" "$LOG_FILE" | head -1 | awk '{print $NF}')
TRADES=$(grep "Total/Daily Avg Trades" "$LOG_FILE" | head -1 | awk '{print $NF}')
WINRATE=$(grep -E "Win  Draw  Loss  Win%" "$LOG_FILE" | tail -1 | awk -F'│' '{print $8}' | awk '{print $NF}')
DRAWDOWN=$(grep "Absolute drawdown" "$LOG_FILE" | head -1 | awk -F'│' '{print $3}' | xargs)
LONG_SHORT=$(grep "Long / Short trades" "$LOG_FILE" | head -1 | awk -F'│' '{print $3}' | xargs)
MARKET=$(grep "Market change" "$LOG_FILE" | head -1 | awk '{print $NF}')

# 追加到記錄檔
cat >> "$RESULT_FILE" << EOF

---

## $VERSION — $(date +%Y-%m-%d) — 自動記錄
- **Timerange**: $TIMERANGE
- **Market**: $MARKET
- **Result**: $PROFIT, $TRADES trades, $WINRATE win, $DRAWDOWN drawdown
- **Long/Short**: $LONG_SHORT
- **Status**: 待分析

EOF

echo "✅ 已記錄 $VERSION 到 $RESULT_FILE"
