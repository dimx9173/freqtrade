#!/bin/bash
# Fixed Non-Parameter Optimization Tests

cd /home/brian/freqtrade

echo "=========================================="
echo "Fixed Optimization Tests"
echo "=========================================="

# Test 1: Stoploss -0.03
echo ""
echo "Test 1: Stoploss -0.03"
python3 -c "
import json
with open('user_data/config/test/config_futures_1x.json') as f:
    config = json.load(f)
config['stoploss'] = -0.03
with open('user_data/config/test/temp_sl.json', 'w') as f:
    json.dump(config, f)
"
python3 -m freqtrade backtesting --strategy ElliotV5_SMA_ninja --config user_data/config/test/temp_sl.json --timerange 20250824-20260524 --cache=day 2>&1 | tail -40 > user_data/test_results/sl_03.txt

# Test 2: Stoploss -0.05
echo "Test 2: Stoploss -0.05"
python3 -c "
import json
with open('user_data/config/test/config_futures_1x.json') as f:
    config = json.load(f)
config['stoploss'] = -0.05
with open('user_data/config/test/temp_sl.json', 'w') as f:
    json.dump(config, f)
"
python3 -m freqtrade backtesting --strategy ElliotV5_SMA_ninja --config user_data/config/test/temp_sl.json --timerange 20250824-20260524 --cache=day 2>&1 | tail -40 > user_data/test_results/sl_05.txt

# Test 3: ROI Conservative
echo "Test 3: ROI Conservative"
python3 -c "
import json
with open('user_data/config/test/config_futures_1x.json') as f:
    config = json.load(f)
config['minimal_roi'] = {'0': 0.05, '60': 0.03, '120': 0.02}
with open('user_data/config/test/temp_roi.json', 'w') as f:
    json.dump(config, f)
"
python3 -m freqtrade backtesting --strategy ElliotV5_SMA_ninja --config user_data/config/test/temp_roi.json --timerange 20250824-20260524 --cache=day 2>&1 | tail -40 > user_data/test_results/roi_cons.txt

# Test 4: ROI Balanced
echo "Test 4: ROI Balanced"
python3 -c "
import json
with open('user_data/config/test/config_futures_1x.json') as f:
    config = json.load(f)
config['minimal_roi'] = {'0': 0.08, '60': 0.05, '120': 0.03}
with open('user_data/config/test/temp_roi.json', 'w') as f:
    json.dump(config, f)
"
python3 -m freqtrade backtesting --strategy ElliotV5_SMA_ninja --config user_data/config/test/temp_roi.json --timerange 20250824-20260524 --cache=day 2>&1 | tail -40 > user_data/test_results/roi_bal.txt

echo ""
echo "Tests complete!"
