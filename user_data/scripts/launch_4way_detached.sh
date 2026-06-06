#!/bin/bash
# 4-way parallel backtest — fully detached (nohup + setsid)
# Each backtest: 1y 9 pairs, 20250501-20260524
# Output: user_data/backtest_results/exp_4way/{A,B,C,D}.log

cd /home/brian/freqtrade || exit 1
PY=/home/brian/freqtrade/.venv/bin/python3
CONFIG=user_data/config/backtest_1y_9pairs.json
TIMERANGE=20250501-20260524
RESULTS_DIR=user_data/backtest_results/exp_4way
mkdir -p "$RESULTS_DIR"

run_bt() {
    local name=$1
    local strategy=$2
    nohup setsid $PY -m freqtrade backtesting \
        --strategy "$strategy" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --export trades \
        --user-data-dir user_data \
        > "$RESULTS_DIR/${name}.log" 2>&1 < /dev/null &
    local pid=$!
    disown 2>/dev/null
    echo "[$name] PID=$pid  $(date '+%H:%M:%S')" > "$RESULTS_DIR/${name}_status.txt"
    echo "Launched $name PID=$pid"
}

run_bt "A_voting"        "Hybrid_v3_expA_voting"
run_bt "B_strict_adx"    "Hybrid_v3_expB_strict_adx"
run_bt "C_volatility"    "Hybrid_v3_expC_volatility"
run_bt "D_mtf_consensus" "Hybrid_v3_expD_mtf_consensus"

echo "All 4 launched. Will run independently."
