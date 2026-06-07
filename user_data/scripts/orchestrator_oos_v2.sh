#!/bin/bash
# Orchestrate: OOS 4-way v2 (rerun with fixed baseline) + BC_combo 2nd OOS in parallel
# Both detached, single completion notification point.
# 2026-06-07 — freqtrade Hybrid_v3 family

set -e
cd /home/brian/freqtrade || exit 1

ORCH_LOG=/home/brian/freqtrade/user_data/backtest_results/orchestrator_oos_v2.log
echo "[orchestrator] START  $(date '+%Y-%m-%d %H:%M:%S')" | tee "$ORCH_LOG"

# Launch OOS 4-way v2 (4 parallel backtests, ~20 min total)
bash user_data/scripts/run_oos_4way_v2.sh 2>&1 | tee -a "$ORCH_LOG"
echo "[orchestrator] OOS 4-way v2 dispatched at $(date '+%H:%M:%S')" | tee -a "$ORCH_LOG"

# Launch BC_combo 2nd OOS (1 backtest, ~10 min)
bash user_data/scripts/run_bccombo_oos_v2.sh 2>&1 | tee -a "$ORCH_LOG"
echo "[orchestrator] BC_combo 2nd OOS dispatched at $(date '+%H:%M:%S')" | tee -a "$ORCH_LOG"

# Now wait for all child PIDs to complete
PIDS_DIR=/tmp/orchestrator_oos_v2_pids
mkdir -p "$PIDS_DIR"

# Wait for OOS 4-way PIDs
echo "[orchestrator] Waiting for OOS 4-way v2..." | tee -a "$ORCH_LOG"
for name in A_baseline B_C_sma200 C_BC_combo D_BC_sma200; do
    statusfile=/home/brian/freqtrade/user_data/backtest_results/oos_4way_v2/${name}_status.txt
    if [ -f "$statusfile" ]; then
        pid=$(awk '{for(i=1;i<=NF;i++) if($i ~ /PID=/) print substr($i,5)}' "$statusfile")
        if [ -n "$pid" ]; then
            echo "[orchestrator]   waiting $name PID=$pid" | tee -a "$ORCH_LOG"
            while kill -0 "$pid" 2>/dev/null; do sleep 5; done
            echo "[orchestrator]   $name PID=$pid EXITED" | tee -a "$ORCH_LOG"
        fi
    fi
done

# Wait for BC_combo 2nd OOS PID
statusfile=/home/brian/freqtrade/user_data/backtest_results/bccombo_oos_v2/bccombo_status.txt
if [ -f "$statusfile" ]; then
    pid=$(awk '{for(i=1;i<=NF;i++) if($i ~ /PID=/) print substr($i,5)}' "$statusfile")
    if [ -n "$pid" ]; then
        echo "[orchestrator] Waiting BC_combo 2nd OOS PID=$pid..." | tee -a "$ORCH_LOG"
        while kill -0 "$pid" 2>/dev/null; do sleep 5; done
        echo "[orchestrator]   BC_combo 2nd OOS PID=$pid EXITED" | tee -a "$ORCH_LOG"
    fi
fi

echo "[orchestrator] ALL DONE  $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$ORCH_LOG"

# Summary
echo "" | tee -a "$ORCH_LOG"
echo "=== OOS 4-way v2 summary ===" | tee -a "$ORCH_LOG"
for name in A_baseline B_C_sma200 C_BC_combo D_BC_sma200; do
    log=/home/brian/freqtrade/user_data/backtest_results/oos_4way_v2/${name}.log
    if [ -f "$log" ]; then
        profit=$(grep -E "^\│ Hybrid_v3" "$log" | head -1 | awk -F'│' '{print $5}' | tr -d ' %')
        trades=$(grep -E "^\│ Hybrid_v3" "$log" | head -1 | awk -F'│' '{print $3}' | tr -d ' ')
        echo "  $name: profit=$profit% trades=$trades" | tee -a "$ORCH_LOG"
    fi
done

echo "=== BC_combo 2nd OOS summary ===" | tee -a "$ORCH_LOG"
log=/home/brian/freqtrade/user_data/backtest_results/bccombo_oos_v2/bccombo.log
if [ -f "$log" ]; then
    profit=$(grep -E "^\│ Hybrid_v3" "$log" | head -1 | awk -F'│' '{print $5}' | tr -d ' %')
    trades=$(grep -E "^\│ Hybrid_v3" "$log" | head -1 | awk -F'│' '{print $3}' | tr -d ' ')
    echo "  BC_combo (timerange 20250501-20251115): profit=$profit% trades=$trades" | tee -a "$ORCH_LOG"
fi
echo "[orchestrator] SCRIPT EXIT 0" | tee -a "$ORCH_LOG"
