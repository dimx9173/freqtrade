#!/bin/bash
# Test 1: Stoploss Optimization

cd /home/brian/freqtrade

echo "=========================================="
echo "Test 1: Stoploss Optimization"
echo "=========================================="

# Create test configs with different stoploss values
for stoploss in -0.03 -0.05 -0.10; do
    echo ""
    echo "Testing stoploss: $stoploss"
    
    # Create temp config
    python3 -c "
import json
with open('user_data/config/test/config_futures_1x.json') as f:
    config = json.load(f)
config['stoploss'] = $stoploss
with open(f'user_data/config/test/config_futures_1x_sl${stoploss}.json', 'w') as f:
    json.dump(config, f, indent=2)
"
    
    # Run backtest
    python3 -m freqtrade backtest \
        --strategy ElliotV5_SMA_ninja \
        --config user_data/config/test/config_futures_1x_sl${stoploss}.json \
        --timerange 20250824-20260524 \
        --export trades \
        --cache=day \
        2>&1 | grep -E "Total profit %|Win %|Sharpe|Trades"
        
done

echo ""
echo "Stoploss test complete!"
