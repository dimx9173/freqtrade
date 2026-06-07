#!/bin/bash
# BC_combo 2nd OOS validation (20250501-20251115, prior 6 months)
# Purpose: confirm BC_combo OOS win is not just luck on 20251115-20260524
# Config:  user_data/config/backtest_1y_9pairs.json (modified timerange)
# Output:   user_data/backtest_results/bccombo_oos_v2/

set -e
cd /home/brian/freqtrade || exit 1
PY=/home/brian/freqtrade/.venv/bin/python3
CONFIG=user_data/config/backtest_1y_9pairs.json
TIMERANGE=20250501-20251115
RESULTS_DIR=user_data/backtest_results/bccombo_oos_v2
mkdir -p "$RESULTS_DIR"

# Reuse the in-sample config but override timerange to 20250501-20251115 (6m prior slice)
nohup setsid $PY -m freqtrade backtesting \
    --strategy "Hybrid_v3_expBC_combo" \
    --config "$CONFIG" \
    --timerange "$TIMERANGE" \
    --export trades \
    --user-data-dir user_data \
    > "$RESULTS_DIR/bccombo.log" 2>&1 < /dev/null &
PID=$!
disown 2>/dev/null
echo "[bccombo_2nd_OOS] PID=$PID  $(date '+%H:%M:%S')  timerange=$TIMERANGE" > "$RESULTS_DIR/bccombo_status.txt"
echo "Launched BC_combo 2nd OOS  PID=$PID  timerange=$TIMERANGE"
