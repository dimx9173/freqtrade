#!/bin/bash
# Quick Hyperopt: ElliotV5_SMA_ninja (Futures 1x)
# For rapid iteration - 200 epochs each

cd /home/brian/freqtrade

echo "=========================================="
echo "Quick Hyperopt: ElliotV5_SMA_ninja"
echo "=========================================="

python3 -m freqtrade hyperopt \
    --strategy ElliotV5_SMA_ninja \
    --config user_data/config/test/config_futures_1x_hyperopt.json \
    --timerange 20250824-20260524 \
    --spaces buy sell \
    -e 200 \
    --hyperopt-loss SharpeHyperOptLoss \
    --job-workers -1

echo ""
echo "Done! Check results above."
