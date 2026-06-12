#!/bin/bash
# Scalp GA - Pure Exec Runner v2
# Runs GA as detached subprocess, writes PID for tracking
# No OpenClaw session involvement = no lock conflicts

WORKDIR="/home/brian/freqtrade"
VENV="$WORKDIR/.venv"
LOG_DIR="$WORKDIR/test/scalp/logs"
STOP_MARKER="$WORKDIR/test/scalp/GA_STOP_MARKER.txt"
REPORT_DIR="$WORKDIR/test/scalp/reports"
PID_FILE="/tmp/scalp_ga.pid"
LOCK_FILE="/tmp/scalp_ga.lock"

mkdir -p "$LOG_DIR" "$REPORT_DIR"

TODAY=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/iterate_${TODAY}.log"

log() {
    echo "[$(date -u +%H:%M:%S)] $1" >> "$LOG_FILE"
}

log "=== GA START ==="

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        log "GA already running (PID $OLD_PID), skipping."
        exit 0
    fi
    log "Stale PID $OLD_PID, clearing."
fi

# Check lock
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)))
    if [ "$LOCK_AGE" -lt 300 ]; then
        log "Lock file exists (<5min old), skipping."
        exit 0
    fi
    log "Stale lock file, removing."
    rm -f "$LOCK_FILE"
fi

# Check STOP_MARKER
if [ -f "$STOP_MARKER" ]; then
    STOP_AGE=$(($(date +%s) - $(stat -c %Y "$STOP_MARKER" 2>/dev/null || echo 0)))
    if [ "$STOP_AGE" -gt 86400 ]; then
        log "STOP_MARKER stale (>24h), auto-clearing."
        rm -f "$STOP_MARKER"
    else
        log "STOP active, skipping."
        exit 0
    fi
fi

# Create lock
touch "$LOCK_FILE"
echo $$ > "$PID_FILE"

# Get baseline report
LAST_REPORT=$(ls -t "$REPORT_DIR"/report_*.json 2>/dev/null | head -1)
log "Baseline report: $LAST_REPORT"

# Launch GA detached
cd "$WORKDIR"
source "$VENV/bin/activate"

nohup python3 -u test/scalp/iterate_strategies.py \
    --constraints "$WORKDIR/test/scalp/ga_constraints.json" \
    >> "$LOG_FILE" 2>&1 &

GA_PID=$!
echo "$GA_PID" > "$PID_FILE"
log "GA launched, PID=$GA_PID"

# Cleanup on exit
trap 'rm -f "$LOCK_FILE"; rm -f "$PID_FILE"; log "=== GA CLEANUP ==="' EXIT

# Wait for GA to finish (check every 2min)
for i in $(seq 1 30); do
    sleep 120
    if ! ps -p "$GA_PID" > /dev/null 2>&1; then
        log "GA finished (PID $GA_PID done)"
        break
    fi
    log "GA still running... (${i}/30 = $((i*2))min)"
done

# If still running after 60min, let it be (will be picked up next run)
if ps -p "$GA_PID" > /dev/null 2>&1; then
    log "GA still running after 60min, releasing (will continue in background)."
fi

# Check for new report
NEW_REPORT=$(ls -t "$REPORT_DIR"/report_*.json 2>/dev/null | head -1)
if [ "$NEW_REPORT" != "$LAST_REPORT" ] && [ -n "$NEW_REPORT" ]; then
    log "NEW REPORT: $NEW_REPORT"
    # Touch a trigger file for the analyzer
    touch "/tmp/scalp_ga_report_ready"
fi

log "=== GA END ==="
