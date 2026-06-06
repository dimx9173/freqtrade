#!/bin/bash
# 4-way parallel backtest runner for Hybrid_v3 entry logic experiments
# Each backtest: 1y 9 pairs, 20250501-20260524

cd /home/brian/freqtrade || exit 1
PY=/home/brian/freqtrade/.venv/bin/python3
CONFIG=user_data/config/backtest_1y_9pairs.json
TIMERANGE=20250501-20260524
RESULTS_DIR=user_data/backtest_results/exp_4way
mkdir -p "$RESULTS_DIR"

echo "Starting 4 parallel backtests at $(date '+%H:%M:%S')"
echo "============================================================"

run_bt() {
    local name=$1
    local strategy=$2
    local logfile="$RESULTS_DIR/${name}.log"
    local start=$(date +%s)
    echo "[$name] START $(date '+%H:%M:%S')"
    $PY -m freqtrade backtesting \
        --strategy "$strategy" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --export trades \
        --user-data-dir user_data \
        > "$logfile" 2>&1
    local exit_code=$?
    local end=$(date +%s)
    local elapsed=$((end - start))
    if [ $exit_code -eq 0 ]; then
        echo "[$name] DONE  ${elapsed}s  $(date '+%H:%M:%S')"
    else
        echo "[$name] FAIL  exit=$exit_code  ${elapsed}s"
    fi
}

# Launch all 4 in background
run_bt "A_voting"        "Hybrid_v3_expA_voting"        > "$RESULTS_DIR/A_status.txt" 2>&1 &
PID_A=$!
run_bt "B_strict_adx"    "Hybrid_v3_expB_strict_adx"    > "$RESULTS_DIR/B_status.txt" 2>&1 &
PID_B=$!
run_bt "C_volatility"    "Hybrid_v3_expC_volatility"    > "$RESULTS_DIR/C_status.txt" 2>&1 &
PID_C=$!
run_bt "D_mtf_consensus" "Hybrid_v3_expD_mtf_consensus" > "$RESULTS_DIR/D_status.txt" 2>&1 &
PID_D=$!

echo "PIDs: A=$PID_A  B=$PID_B  C=$PID_C  D=$PID_D"
echo "============================================================"

# Wait for all
wait $PID_A; echo "A exit=$?"
wait $PID_B; echo "B exit=$?"
wait $PID_C; echo "C exit=$?"
wait $PID_D; echo "D exit=$?"

echo "============================================================"
echo "All 4 backtests finished at $(date '+%H:%M:%S')"
echo "Logs in $RESULTS_DIR"
