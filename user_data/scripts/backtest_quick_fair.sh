#!/bin/bash
# Quick fair comparison for a single strategy

cd /home/brian/freqtrade

STRATEGY=${1:-ElliotV5_SMA_ninja}
TIMEFRAME="5m"
TIMERANGE="20250101-20250525"

echo "=========================================="
echo "Quick Fair Backtest: $STRATEGY"
echo "=========================================="

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
