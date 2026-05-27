#!/bin/bash
# CORRECTED Fair comparison: Same timerange as original spot test

cd /home/brian/freqtrade

STRATEGY=${1:-ElliotV5_SMA_ninja}
# Use same timerange as original spot test that showed +10.16%
TIMERANGE="20250824-20260524"
TIMEFRAME="5m"

echo "=========================================="
echo "CORRECTED Fair Backtest: $STRATEGY"
echo "=========================================="
echo "Timerange: $TIMERANGE (same as original spot)"
echo ""

# SPOT
echo ""
echo "--- SPOT ---"
python3 -m freqtrade backtesting \
    --config user_data/config/test/config_6.json \
    --strategy $STRATEGY \
    --timeframe $TIMEFRAME \
    --timerange $TIMERANGE \
    --export trades

# FUTURES 1x
echo ""
echo "--- FUTURES 1x ---"
python3 -m freqtrade backtesting \
    --config user_data/config/test/config_futures_1x.json \
    --strategy $STRATEGY \
    --timeframe $TIMEFRAME \
    --timerange $TIMERANGE \
    --export trades
