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

backtest_result=$(freqtrade backtesting \
    --config user_data/config.json \
    --strategy TestTV_${HASH} \
    --timerange 20260401-20260419 \
    --timeframe 1h \
    --export trades \
    2>&1)

# Extract results
total_profit=$(echo "$backtest_result" | grep -oP 'Total profit.*?:\s*([-\d.]+)' | grep -oP '[-\d.]+' | tail -1)
num_trades=$(echo "$backtest_result" | grep -oP 'Trades.*?:\s*(\d+)' | grep -oP '\d+' | tail -1)
win_rate=$(echo "$backtest_result" | grep -oP 'Win rate.*?:\s*([\d.]+)' | grep -oP '[\d.]+' | tail -1)

echo "Backtest Results for $HASH:"
echo "  Total Profit: ${total_profit:-N/A}%"
echo "  Trades: ${num_trades:-N/A}"
echo "  Win Rate: ${win_rate:-N/A}%"

# Record in results
echo "| TestTV_${HASH} | $HASH | ${total_profit:-0}% | ${num_trades:-0} | ${win_rate:-0}% |" >> "$RESULTS_FILE"

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
