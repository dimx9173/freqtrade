#!/bin/bash
# Launch Hybrid_v3_expBC_combo as prod dry-run (slot 7)
# 2026-06-07 — after OOS 4-way + 2nd OOS validation passed
#
# Usage:
#   bash user_data/scripts/launch_bccombo_prod_dryrun.sh
#
# Pre-reqs:
#   - config_7_bccombo.json exists and validated
#   - prod/Hybrid_v3_expBC_combo.py is in place
#   - Bybit data downloaded (ETH/SOL/BNB/XRP/DOGE/ADA/AVAX/TON/SUI 15m)
#
# Monitors via monitor_run.sh (auto-restart on crash)
# DB: tradesv3_97.sqlite (separate from prod 91-96 slots)
# Log: user_data/logs/freqtrade_BC_combo.log

set -e
cd /home/brian/freqtrade || exit 1

CONFIG=user_data/config/config_7_bccombo.json
DB_URL="sqlite:///user_data/sqlite/tradesv3_97.sqlite"
LOGFILE=user_data/logs/freqtrade_BC_combo.log
STRATEGY_PATH=user_data/strategies/prod
STRATEGY=Hybrid_v3_expBC_combo

# Sanity checks
echo "[launch] Sanity checks..."
if [ ! -f "$CONFIG" ]; then echo "FAIL: $CONFIG missing"; exit 1; fi
if [ ! -f "$STRATEGY_PATH/${STRATEGY}.py" ]; then echo "FAIL: $STRATEGY_PATH/${STRATEGY}.py missing"; exit 1; fi
echo "[launch] config: $CONFIG"
echo "[launch] strategy: $STRATEGY"
echo "[launch] db: $DB_URL"
echo "[launch] log: $LOGFILE"

# Touch logfile so monitor can start
mkdir -p user_data/logs
touch "$LOGFILE"

# Build the freqtrade command
CMD="freqtrade trade --config $CONFIG --db-url $DB_URL --logfile $LOGFILE --strategy-path $STRATEGY_PATH --strategy $STRATEGY"

echo ""
echo "[launch] Command to run via monitor_run.sh:"
echo "  $CMD"
echo ""
echo "[launch] To actually start the bot, run:"
echo "  cd /home/brian/freqtrade"
echo "  zsh user_data/scripts/utilities/monitor_run.sh '$CMD' &"
echo ""
echo "[launch] Status files:"
echo "  user_data/logs/freqtrade_BC_combo.log"
echo "  user_data/sqlite/tradesv3_97.sqlite (will be created on first run)"
echo ""
echo "[launch] API server will be on port 13997 (http://0.0.0.0:13997)"
echo ""
echo "[launch] DRY-RUN ONLY — no real trades. Observe 1-2 weeks before live."
echo "[launch] Not started. Run the monitor command above to launch."
