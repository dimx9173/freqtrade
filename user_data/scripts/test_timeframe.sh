#!/bin/bash
# Test 3: Timeframe Optimization

cd /home/brian/freqtrade

echo "=========================================="
echo "Test 3: Timeframe Optimization"
echo "=========================================="

# Note: Requires data download for each timeframe
for tf in 3m 15m 1h; do
    echo ""
    echo "Testing timeframe: $tf"
    echo "(Note: Need to download data for $tf first)"
    
    # Create temp config
    python3 -c "
import json
with open('user_data/config/test/config_futures_1x.json') as f:
    config = json.load(f)
config['timeframe'] = '$tf'
with open(f'user_data/config/test/config_futures_1x_tf_${tf}.json', 'w') as f:
    json.dump(config, f, indent=2)
"
done

echo ""
echo "Timeframe configs created. Download data before testing:"
echo "freqtrade download-data --timeframes 3m 15m 1h --timerange 20250824-20260524"
