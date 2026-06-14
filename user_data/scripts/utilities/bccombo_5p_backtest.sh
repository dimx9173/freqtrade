#!/bin/bash
# ==============================================
# BC_combo 5 pair 完整 Backtest (W5)
# ==============================================
# Usage: bash user_data/scripts/utilities/bccombo_5p_backtest.sh
# 前置: W4 download_futures_history.sh 已完成 (5/5 pair 5m-futures)
# 區間: 20250116-20260524 (對齊 cross-asset 1h 數據可用範圍)
# 目的: cross-section 驗證 trailing_stop=False 修復 + MSI gate 統計
#       (W1 BTC only = 14 trades, 不夠統計顯著; 5 pair 預期 60-100 trades)

set -e

cd /home/brian/freqtrade
source .venv/bin/activate

CONFIG="user_data/config/test/config_bccombo_5p.json"
STRATEGY="Hybrid_v3_expBC_combo"
TIMERANGE="20250116-20260524"
RESULT_DIR="user_data/reports/bccombo_5p_backtest"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="$RESULT_DIR/${STRATEGY}_W5_${TIMESTAMP}.log"

mkdir -p "$RESULT_DIR"

echo "========================================"
echo "BC_combo 5 pair Backtest (W5: cross-section 驗證)"
echo "Strategy: $STRATEGY"
echo "Pairs: BTC ETH SOL XRP BNB"
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
  --breakdown month day \
  2>&1 | tee "$LOG"

# W3: 統計 MSI gate 觸發次數
echo ""
echo "========================================"
echo "MSI gate 觸發統計 (5 pair 合計):"
MSI_GATE_COUNT=$(grep -c "MSI chaos gate" "$LOG" 2>/dev/null || echo 0)
echo "  MSI chaos gate 觸發次數: $MSI_GATE_COUNT"

# Pair-by-pair MSI gate 統計
echo ""
echo "Pair-by-pair trades (從 log 提取):"
grep -A 5 "Pair" "$LOG" | grep "USDT:USDT" | head -10
echo "========================================"

# 關鍵指標
echo ""
echo "========================================"
echo "W5 關鍵指標 (trailing_stop=False, 5 pair):"
grep -E "Total/Daily Avg Trades|Trades.*Avg Profit|Avg Duration|Win.*Draw.*Loss" "$LOG" | head -10
echo "========================================"
