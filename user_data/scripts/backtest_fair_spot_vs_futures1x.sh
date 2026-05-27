#!/bin/bash
# Fair comparison: Spot vs Futures 1x
# Same 23 pairs, same stake_amount=50, same timeframe=5m

cd /home/brian/freqtrade

STRATEGIES="ElliotV5_SMA_ninja BB_RPB_TSL_BI PSV5_Hybrid NASOSv4 NASOSv5_mod3 SMAOffsetProtectOptV1"
TIMEFRAME="5m"
TIMERANGE="20250101-20250525"

echo "=========================================="
echo "FAIR BACKTEST: Spot vs Futures 1x"
echo "=========================================="
echo "Pairs: 23 (identical set)"
echo "Stake: 50 USDT"
echo "Timeframe: 5m"
echo "Leverage: 1x (futures)"
echo ""

# SPOT backtests
for strat in $STRATEGIES; do
    echo "--- Spot: $strat ---"
    python3 -m freqtrade backtesting \
        --config user_data/config/test/config_6.json \
        --strategy $strat \
        --timeframe $TIMEFRAME \
        --timerange $TIMERANGE \
        --export trades \
        --export-filename user_data/backtest_results/spot_${strat}_$(date +%Y%m%d_%H%M%S)
done

# FUTURES 1x backtests
for strat in $STRATEGIES; do
    echo "--- Futures 1x: $strat ---"
    python3 -m freqtrade backtesting \
        --config user_data/config/test/config_futures_1x.json \
        --strategy $strat \
        --timeframe $TIMEFRAME \
        --timerange $TIMERANGE \
        --export trades \
        --export-filename user_data/backtest_results/futures1x_${strat}_$(date +%Y%m%d_%H%M%S)
done

echo ""
echo "=========================================="
echo "Backtests complete!"
echo "=========================================="
