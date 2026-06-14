#!/bin/bash
# ==============================================
# BC_combo 1y Backtest (W1: trailing_stop=False 驗證 + W3: MSI gate 統計)
# ==============================================
# Usage: bash user_data/scripts/utilities/bccombo_1y_backtest.sh
# 前置: W4 download_futures_history.sh 已完成 (5/5 pair 5m-futures)
# 區間: 20250116-20260524 (對齊 cross-asset 1h 數據可用範圍)
# 合併: 一次 backtest 同時驗證 trailing_stop=False 修復 + 統計 MSI gate 觸發次數

set -e

cd /home/brian/freqtrade
source .venv/bin/activate

CONFIG="user_data/config/test/config_bccombo_btc.json"
STRATEGY="Hybrid_v3_expBC_combo"
TIMERANGE="20250116-20260524"
RESULT_DIR="user_data/reports/bccombo_1y_backtest"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="$RESULT_DIR/${STRATEGY}_W1W3_${TIMESTAMP}.log"

mkdir -p "$RESULT_DIR"

echo "========================================"
echo "BC_combo 1y Backtest (W1: trailing_stop=False + W3: MSI gate)"
echo "Strategy: $STRATEGY"
echo "Timerange: $TIMERANGE"
echo "Config: $CONFIG"
echo "Log: $LOG"
echo "========================================"

freqtrade backtesting \
  --config "$CONFIG" \
  --strategy-path user_data/strategies/prod \
  --strategy "$STRATEGY" \
  --timerange "$TIMERANGE" \
  --timeframe 15m \
  --data-format-ohlcv feather \
  --export trades \
  --breakdown month \
  2>&1 | tee "$LOG"

# W3: 統計 MSI gate 觸發次數
echo ""
echo "========================================"
echo "W3 MSI gate 統計:"
MSI_GATE_COUNT=$(grep -c "MSI chaos gate" "$LOG" 2>/dev/null || echo 0)
echo "  MSI chaos gate 觸發次數: $MSI_GATE_COUNT"
echo "========================================"

# W1: 提取關鍵指標
echo ""
echo "========================================"
echo "W1 關鍵指標 (trailing_stop=False):"
grep -E "Total Profit|Profit %|Trades|Win%|Drawdown|Max" "$LOG" | head -15
echo "========================================"
