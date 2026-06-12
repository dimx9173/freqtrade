#!/bin/bash
# Continued Optimization Pipeline
# Run hyperopt on remaining strategies

cd /home/brian/freqtrade

echo "=========================================="
echo "CONTINUED OPTIMIZATION"
echo "=========================================="

# Strategy 1: ElliotV5 - Fine tune parameters
echo ""
echo "Phase 1: ElliotV5 Hyperopt (Buy/Sell spaces)"
python3 -m freqtrade hyperopt \
    --strategy ElliotV5_SMA_ninja \
    --config user_data/config/test/config_futures_1x_hyperopt.json \
    --timerange 20250824-20260524 \
    --spaces buy sell \
    -e 500 \
    --hyperopt-loss SharpeHyperOptLoss \
    --job-workers -1

# Strategy 2: BB_RPB_TSL_BI - Core parameter optimization
echo ""
echo "Phase 2: BB_RPB_TSL_BI Hyperopt (Key parameters)"
python3 -m freqtrade hyperopt \
    --strategy BB_RPB_TSL_BI \
    --config user_data/config/test/config_futures_1x_hyperopt.json \
    --timerange 20250824-20260524 \
    --spaces buy sell \
    -e 300 \
    --hyperopt-loss SharpeHyperOptLoss \
    --job-workers -1

echo ""
echo "Optimization complete!"
echo "Export best parameters with: freqtrade hyperopt-show --best"
