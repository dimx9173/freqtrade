#!/bin/bash
# Test 2: ROI Optimization

cd /home/brian/freqtrade

echo "=========================================="
echo "Test 2: ROI Optimization"
echo "=========================================="

# Test different ROI configurations
python3 << 'PYEOF'
import json
import subprocess

roi_configs = [
    ("conservative", {"0": 0.05, "60": 0.03, "120": 0.02}),
    ("balanced", {"0": 0.08, "60": 0.05, "120": 0.03}),
    ("aggressive", {"0": 0.10, "30": 0.07, "60": 0.05}),
]

for name, roi in roi_configs:
    print(f"\nTesting ROI: {name} - {roi}")

    # Create temp config
    with open('user_data/config/test/config_futures_1x.json') as f:
        config = json.load(f)
    config['minimal_roi'] = roi
    with open(f'user_data/config/test/config_futures_1x_roi_{name}.json', 'w') as f:
        json.dump(config, f, indent=2)

    # Run backtest
    result = subprocess.run([
        'python3', '-m', 'freqtrade', 'backtest',
        '--strategy', 'ElliotV5_SMA_ninja',
        '--config', f'user_data/config/test/config_futures_1x_roi_{name}.json',
        '--timerange', '20250824-20260524',
        '--export', 'trades',
        '--cache=day'
    ], capture_output=True, text=True)

    # Extract key metrics
    for line in result.stdout.split('\n'):
        if any(x in line for x in ['Total profit %', 'Win %', 'Sharpe', 'Trades']):
            print(line.strip())

PYEOF

echo ""
echo "ROI test complete!"
