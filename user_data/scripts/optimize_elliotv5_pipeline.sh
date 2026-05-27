#!/bin/bash
# ElliotV5 Futures 1x Optimization Pipeline
# Includes automatic git commit

cd /home/brian/freqtrade

echo "=========================================="
echo "Futures 1x Optimization: ElliotV5_SMA_ninja"
echo "=========================================="

# Run quick hyperopt
echo ""
echo "Running quick hyperopt (200 epochs)..."
./user_data/scripts/hyperopt_quick_elliotv5.sh

# Check if hyperopt succeeded
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Hyperopt completed successfully"
    
    # Export best parameters
    echo ""
    echo "Exporting best parameters..."
    python3 -m freqtrade hyperopt-show --best --export-json user_data/strategies/prod/ElliotV5_SMA_ninja_futures1x.json
    
    # Git commit
    echo ""
    echo "Committing to git..."
    git add user_data/strategies/prod/ElliotV5_SMA_ninja_futures1x.json
    git add user_data/config/test/config_futures_1x_hyperopt.json
    git commit -m "auto(hyperopt): ElliotV5_SMA_ninja futures1x params @ $(date +%Y%m%d_%H%M%S)"
    git push
    
    echo ""
    echo "✅ Optimization complete and committed!"
else
    echo ""
    echo "❌ Hyperopt failed"
    exit 1
fi
