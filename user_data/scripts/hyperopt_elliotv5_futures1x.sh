#!/bin/bash
# ElliotV5_SMA_ninja Hyperopt for Futures 1x

cd /home/brian/freqtrade

echo "=========================================="
echo "Hyperopt: ElliotV5_SMA_ninja (Futures 1x)"
echo "=========================================="
echo ""

# Buy space optimization
echo "Phase 1: Optimizing BUY parameters..."
python3 -m freqtrade hyperopt \
    --strategy ElliotV5_SMA_ninja \
    --config user_data/config/test/config_futures_1x_hyperopt.json \
    --timerange 20250824-20260524 \
    --spaces buy \
    -e 500 \
    --hyperopt-loss SharpeHyperOptLoss \
    --job-workers -1 \
    --disable-param-export

# Sell space optimization  
echo ""
echo "Phase 2: Optimizing SELL parameters..."
python3 -m freqtrade hyperopt \
    --strategy ElliotV5_SMA_ninja \
    --config user_data/config/test/config_futures_1x_hyperopt.json \
    --timerange 20250824-20260524 \
    --spaces sell \
    -e 500 \
    --hyperopt-loss SharpeHyperOptLoss \
    --job-workers -1 \
    --disable-param-export

# Full optimization
echo ""
echo "Phase 3: Full optimization..."
python3 -m freqtrade hyperopt \
    --strategy ElliotV5_SMA_ninja \
    --config user_data/config/test/config_futures_1x_hyperopt.json \
    --timerange 20250824-20260524 \
    --spaces buy sell \
    -e 1000 \
    --hyperopt-loss SharpeHyperOptLoss \
    --job-workers -1

echo ""
echo "=========================================="
echo "Hyperopt Complete!"
echo "=========================================="
