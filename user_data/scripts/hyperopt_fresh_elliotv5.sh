#!/bin/bash
# Fresh Hyperopt for ElliotV5 with optimized base settings

cd /home/brian/freqtrade

echo "=========================================="
echo "Fresh Hyperopt: ElliotV5 (Futures 1x)"
echo "=========================================="

# Run hyperopt with optimized stoploss and ROI
python3 -m freqtrade hyperopt \
    --strategy ElliotV5_SMA_ninja \
    --config user_data/config/test/config_futures_1x_hyperopt.json \
    --timerange 20250824-20260524 \
    --spaces buy sell \
    -e 1000 \
    --hyperopt-loss SharpeHyperOptLossDaily \
    --hyperopt-loss-onlyprofit false \
    --job-workers -1 \
    --min-trades 50

echo ""
echo "Hyperopt complete!"
echo "Export with: freqtrade hyperopt-show --best"
