#!/bin/bash
set -e
CONFIG_DIR="user_data/config/test"
STRATEGY="NASOSv5_mod3"
TIMERANGE="20250501-20260525"
RESULT_LOG="user_data/reports/futures_sl_sweep_results.txt"

mkdir -p user_data/reports
rm -f user_data/backtest_results/*.pickle

echo "NASOSv5_mod3 Futures 1x Stoploss Sweep Report" > "$RESULT_LOG"
echo "Timerange: $TIMERANGE | Strategy: $STRATEGY | Pairlist: 23 pairs" >> "$RESULT_LOG"
echo "============================================================" >> "$RESULT_LOG"

for sl in -0.05 -0.10 -0.15 -0.20; do
    config="$CONFIG_DIR/config_futures_1x_sl$(echo $sl | tr -d '.').json"
    label="SL $(echo $sl | sed 's/-0./-/')%"
    echo ""
    echo "Running $label ..."
    rm -f user_data/backtest_results/*.pickle
    python -m freqtrade backtesting --config "$config" --strategy "$STRATEGY" --timerange "$TIMERANGE" --dry-run-wallet 1000 --stake-amount 50 --max-open-trades 20 > /tmp/bt_${sl}.log 2>&1
    
    trades=$(grep -oP "NASOSv5_mod3 │\s+\K\d+" /tmp/bt_${sl}.log || echo "N/A")
    profit=$(grep "Total profit %" /tmp/bt_${sl}.log | awk '{print $NF}')
    dd=$(grep "Absolute drawdown" /tmp/bt_${sl}.log | awk '{print $3}')
    dd_pct=$(grep "Absolute drawdown" /tmp/bt_${sl}.log | awk '{print $4}' | tr -d '()')
    win=$(grep -oP "NASOSv5_mod3 │\s+\d+\s+[\-\d.]+\s+[\-\d.]+\s+[\-\d.]+%\s+[\d:]+\s+\d+\s+\d+\s+\d+\s+\K[\d.]+" /tmp/bt_${sl}.log || echo "N/A")
    
    echo "$label | Trades: $trades | Profit: $profit | Drawdown: $dd $dd_pct | Win%: $win" >> "$RESULT_LOG"
    echo "  $label done: Trades=$trades Profit=$profit DD=$dd_pct Win%=$win"
done

echo ""
echo "All done. Results saved to $RESULT_LOG"
cat "$RESULT_LOG"
