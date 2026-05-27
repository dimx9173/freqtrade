#!/bin/bash
# Test all optimized strategies

cd /home/brian/freqtrade

echo "=========================================="
echo "Testing Optimized Strategies"
echo "=========================================="

strategies=("ElliotV5_SMA_ninja_opt" "BB_RPB_TSL_BI_opt" "PSV5_Hybrid_opt")

for strategy in "${strategies[@]}"; do
    echo ""
    echo "Testing: $strategy"
    echo "----------------------------------------"
    
    python3 -m freqtrade backtesting \
        --strategy $strategy \
        --config user_data/config/test/config_futures_1x.json \
        --timerange 20250824-20260524 \
        --cache=day \
        2>&1 | tail -40 > user_data/test_results/${strategy}.txt
    
    # Extract key metrics
    echo "Results:"
    grep -E "ElliotV5|BB_RPB|PSV5" user_data/test_results/${strategy}.txt | head -1
    
done

echo ""
echo "All tests complete!"
