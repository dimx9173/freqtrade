#!/bin/bash
# OOS 4-way backtest (fixed baseline) — fully detached
# 2026-06-07: rerun full 4-way with Hybrid_v3 alias fixed
# Config: user_data/config/backtest_oos_1y_9pairs.json (timerange 20251115-20260524)
# Output:  user_data/backtest_results/oos_4way_v2/

set -e
cd /home/brian/freqtrade || exit 1
PY=/home/brian/freqtrade/.venv/bin/python3
CONFIG=user_data/config/backtest_oos_1y_9pairs.json
TIMERANGE=20251115-20260524
RESULTS_DIR=user_data/backtest_results/oos_4way_v2
mkdir -p "$RESULTS_DIR"

run_bt() {
    local name=$1
    local strategy=$2
    local logfile="$RESULTS_DIR/${name}.log"
    local statusfile="$RESULTS_DIR/${name}_status.txt"
    nohup setsid $PY -m freqtrade backtesting \
        --strategy "$strategy" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --export trades \
        --user-data-dir user_data \
        > "$logfile" 2>&1 < /dev/null &
    local pid=$!
    disown 2>/dev/null
    echo "[$name] PID=$pid  $(date '+%H:%M:%S')  strategy=$strategy" > "$statusfile"
    echo "Launched $name PID=$pid  strategy=$strategy"
}

run_bt "A_baseline"  "Hybrid_v3"
run_bt "B_C_sma200"  "Hybrid_v3_expC_sma200"
run_bt "C_BC_combo"  "Hybrid_v3_expBC_combo"
run_bt "D_BC_sma200" "Hybrid_v3_expBC_sma200"

echo "All 4 launched. Logs in $RESULTS_DIR"
