#!/bin/bash
# Test 4: Trailing Stop Optimization

cd /home/brian/freqtrade

echo "=========================================="
echo "Test 4: Trailing Stop Optimization"
echo "=========================================="

# Test different trailing configurations
python3 << 'PYEOF'
import json
import subprocess

trailing_configs = [
    ("tight", {"trailing_stop_positive": 0.01, "trailing_stop_positive_offset": 0.02}),
    ("medium", {"trailing_stop_positive": 0.02, "trailing_stop_positive_offset": 0.03}),
    ("loose", {"trailing_stop_positive": 0.03, "trailing_stop_positive_offset": 0.05}),
]

for name, config in trailing_configs:
    print(f"\nTesting Trailing: {name} - {config}")

    # Create temp config
    with open('user_data/config/test/config_futures_1x.json') as f:
        base_config = json.load(f)
    base_config.update(config)
    with open(f'user_data/config/test/config_futures_1x_trail_{name}.json', 'w') as f:
        json.dump(base_config, f, indent=2)

    # Run backtest
    result = subprocess.run([
        'python3', '-m', 'freqtrade', 'backtest',
        '--strategy', 'ElliotV5_SMA_ninja',
        '--config', f'user_data/config/test/config_futures_1x_trail_{name}.json',
        '--timerange', '20250824-20260524',
        '--export', 'trades',
        '--cache=day'
    ], capture_output=True, text=True)

    for line in result.stdout.split('\n'):
        if any(x in line for x in ['Total profit %', 'Win %', 'Sharpe', 'Trades']):
            print(line.strip())

PYEOF

echo ""
echo "Trailing stop test complete!"
