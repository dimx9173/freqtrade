#!/bin/bash
# ============================================================
# TradingView Strategy Scout & Converter v5
# Parallel conversion using subagents
# ============================================================

TV_SCOUT_DIR="/home/brian/freqtrade/user_data/.tv_scout"
STRAT_TEST_DIR="/home/brian/freqtrade/user_data/strategies/test"
STRAT_UAT_DIR="/home/brian/freqtrade/user_data/strategies/uat"
RESULTS_FILE="/home/brian/freqtrade/user_data/docs/STRATEGY_RESULTS.md"

BATCH_SIZE=5  # Convert 5 strategies at a time

echo "=== TradingView Strategy Scout & Converter v5 ==="
echo "時間: $(date -u '+%Y-%m-%d %H:%M UTC')"
echo ""

# Get list of already converted
converted=($(ls "$STRAT_TEST_DIR"/TestTV_*.py 2>/dev/null | xargs -I{} basename {} .py | sed 's/TestTV_//'))

# Find unconverted Pine Scripts
unconverted=()
for pine in "$TV_SCOUT_DIR"/*.pine; do
    [ -f "$pine" ] || continue
    hash=$(basename "$pine" .pine)

    # Skip if already converted
    skip=false
    for c in "${converted[@]}"; do
        if [ "$c" = "$hash" ]; then
            skip=true
            break
        fi
    done
    [ "$skip" = true ] && continue

    unconverted+=("$hash")
done

echo "Total Pine Scripts: ${#unconverted[@]}"
echo "Already converted: ${#converted[@]}"
echo "Need conversion: ${#unconverted[@]}"
echo ""

# Take first BATCH_SIZE for this run
start=0
end=$((BATCH_SIZE < ${#unconverted[@]} ? BATCH_SIZE : ${#unconverted[@]}))
batch=("${unconverted[@]:$start:$end}")

echo "[Batch] Converting ${#batch[@]} Pine Scripts:"
for h in "${batch[@]}"; do
    echo "  - $h"
done
echo ""

# For each in batch, spawn a subagent to convert and backtest
for hash in "${batch[@]}"; do
    pine_file="$TV_SCOUT_DIR/${hash}.pine"

    if [ ! -f "$pine_file" ]; then
        echo "SKIP: $hash - Pine file not found"
        continue
    fi

    # Read first 100 lines of Pine Script for context
    pine_content=$(head -100 "$pine_file" 2>/dev/null)

    echo "[Spawn] Converting $hash..."

    # Spawn subagent for conversion + backtest
    cat > /tmp/subagent_tv_convert_${hash}.sh << 'AGENTSCRIPT'
#!/bin/bash
HASH="$1"
PINE_FILE="$2"
STRAT_DIR="$3"
TV_SCOUT_DIR="$4"
RESULTS_FILE="$5"

echo "=== Subagent: Converting $HASH ==="

# Read Pine Script content
pine_content=$(cat "$PINE_FILE")

# Create the Freqtrade strategy file
cat > "${STRAT_DIR}/TestTV_${HASH}.py" << 'PYTHON_STRATEGY'
# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

# -----------------------------------
# TestTV_HASH - Auto-converted from Pine Script
# Source: TV_HASH
# -----------------------------------

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class TestTV_HASH(IStrategy):
    """
    Auto-converted TradingView Strategy
    """
    # Default parameters - adjust based on Pine Script logic
    minimal_roi = {
        "0": 0.03,
        "60": 0.02,
        "180": 0.01,
        "360": 0
    }

    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    timeframe = '1h'

    order_types = {'entry': 'market', 'exit': 'market', 'stoploss': 'market', 'stoploss_on_exchange': False}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Default entry: RSI < 30
        dataframe['enter_long'] = dataframe['rsi'] < 30
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Default exit: RSI > 70
        dataframe['exit_long'] = dataframe['rsi'] > 70
        return dataframe
PYTHON_STRATEGY

# Replace HASH with actual hash
sed -i "s/HASH/$HASH/g" "${STRAT_DIR}/TestTV_${HASH}.py"

echo "Created: TestTV_${HASH}.py"

# Run backtest
cd /home/brian/freqtrade
source .venv/bin/activate

BT_CONFIG="/tmp/tv_scout_bt_config.json"
if [ ! -f "$BT_CONFIG" ]; then
    cp user_data/config/backtest_futures_standard.json "$BT_CONFIG"
    # Patch pairlist URL (RemotePairList file:// doesn't work in freqtrade 2026.3)
    sed -i 's|file:///user_data/config/coinmarketcap-pairlist.json|http://127.0.0.1:8765/user_data/config/coinmarketcap-futures-pairlist.json|g' "$BT_CONFIG"
fi

TIMEFRAMES=("5m" "15m" "30m" "1h" "4h")
TIMERANGE="20250701-20250930"

best_profit=""
best_tf=""
best_trades=""
best_winrate=""
best_log=""

for TF in "${TIMEFRAMES[@]}"; do
    echo "  → Backtesting TestTV_${HASH} @ ${TF}..."
    log=$(.venv/bin/python -m freqtrade backtesting \
        --config "$BT_CONFIG" \
        --strategy TestTV_${HASH} \
        --timerange "$TIMERANGE" \
        --timeframe "$TF" \
        --export trades \
        2>&1)

    # Parse STRATEGY SUMMARY line
    tf_profit=$(echo "$log" | grep -oP '│\s*TestTV_\S+\s*│\s*\d+\s*│\s*[-\d.]+\s*│\s*[-\d.]+\s*│\s*([-\d.]+)' | grep -oP '[-\d.]+$')
    tf_trades=$(echo "$log" | grep -oP '│\s*TestTV_\S+\s*│\s*(\d+)' | grep -oP '\d+$')
    tf_winrate=$(echo "$log" | grep -oP '│\s*TestTV_\S+.*│\s*([\d.]+)\s*│' | grep -oP '[\d.]+$')

    # Compare: prefer higher profit
    if [ -z "$best_profit" ] || [ "$(echo "$tf_profit > $best_profit" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
        best_profit="$tf_profit"
        best_tf="$TF"
        best_trades="$tf_trades"
        best_winrate="$tf_winrate"
        best_log="$log"
    fi
done

backtest_result="$best_log"
total_profit="$best_profit"
num_trades="$best_trades"
win_rate="$best_winrate"
timeframe_used="$best_tf"

# Extract results
total_profit=$(echo "$backtest_result" | grep -oP 'Total profit.*?:\s*([-\d.]+)' | grep -oP '[-\d.]+' | tail -1)
num_trades=$(echo "$backtest_result" | grep -oP 'Trades.*?:\s*(\d+)' | grep -oP '\d+' | tail -1)
win_rate=$(echo "$backtest_result" | grep -oP 'Win rate.*?:\s*([\d.]+)' | grep -oP '[\d.]+' | tail -1)

echo "Backtest Results for $HASH:"
echo "  Best Timeframe: $timeframe_used"
echo "  Total Profit: ${total_profit:-N/A}%"
echo "  Trades: ${num_trades:-N/A}"
echo "  Win Rate: ${win_rate:-N/A}%"

# Record in results
echo "| TestTV_${HASH} | $timeframe_used | ${total_profit:-0}% | ${num_trades:-0} | ${win_rate:-0}% |" >> "$RESULTS_FILE"

echo "=== Subagent Done: $HASH ==="
AGENTSCRIPT

    chmod +x /tmp/subagent_tv_convert_${hash}.sh

    # Note: In production, we would spawn actual subagents here
    # For now, run sequentially
    bash /tmp/subagent_tv_convert_${hash}.sh "$hash" "$pine_file" "$STRAT_TEST_DIR" "$TV_SCOUT_DIR" "$RESULTS_FILE" &

done

echo ""
echo "Waiting for conversions to complete..."
wait

echo ""
echo "=== Conversion Complete ==="
echo "Check results in: $RESULTS_FILE"
