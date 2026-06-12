#!/bin/bash
# Master Parallel Test Runner
# Runs all non-parameter optimizations in parallel

cd /home/brian/freqtrade

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     PARALLEL NON-PARAMETER OPTIMIZATION TESTING             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Starting all tests in parallel..."
echo ""

# Create results directory
mkdir -p user_data/test_results

# Run tests in background
./user_data/scripts/test_stoploss.sh > user_data/test_results/stoploss_test.log 2>&1 &
STOPLOSS_PID=$!

./user_data/scripts/test_roi.sh > user_data/test_results/roi_test.log 2>&1 &
defROI_PID=$!

./user_data/scripts/test_trailing.sh > user_data/test_results/trailing_test.log 2>&1 &
TRAILING_PID=$!

echo "Started 3 parallel tests:"
echo "  - Stoploss Test (PID: $STOPLOSS_PID)"
echo "  - ROI Test (PID: $defROI_PID)"
echo "  - Trailing Stop Test (PID: $TRAILING_PID)"
echo ""

# Wait for all to complete
wait $STOPLOSS_PID
echo "✅ Stoploss test complete"

wait $defROI_PID
echo "✅ ROI test complete"

wait $TRAILING_PID
echo "✅ Trailing stop test complete"

echo ""
echo "All tests complete!"
echo ""
echo "Results saved to user_data/test_results/"
echo ""

# Generate summary report
echo "Generating summary report..."
python3 << 'PYEOF'
import os
import re

print("\n" + "="*60)
print("OPTIMIZATION TEST RESULTS SUMMARY")
print("="*60 + "\n")

# Parse stoploss results
if os.path.exists('user_data/test_results/stoploss_test.log'):
    print("📊 STOPLOSS TEST RESULTS:")
    print("-" * 40)
    with open('user_data/test_results/stoploss_test.log') as f:
        content = f.read()
        # Extract results for each stoploss value
        for match in re.finditer(r'Testing stoploss: ([-\d.]+).*?(?=Testing stoploss:|$)', content, re.DOTALL):
            section = match.group(0)
            stoploss = match.group(1)
            profit = re.search(r'Total profit %\s+([-\d.]+)', section)
            trades = re.search(r'Trades\s+(\d+)', section)
            winrate = re.search(r'Win %\s+([\d.]+)', section)
            sharpe = re.search(r'Sharpe\s+([-\d.]+)', section)

            print(f"  Stoploss {stoploss}:")
            if profit: print(f"    Profit: {profit.group(1)}%")
            if trades: print(f"    Trades: {trades.group(1)}")
            if winrate: print(f"    Win Rate: {winrate.group(1)}%")
            if sharpe: print(f"    Sharpe: {sharpe.group(1)}")
    print()

# Parse ROI results
if os.path.exists('user_data/test_results/roi_test.log'):
    print("💰 ROI TEST RESULTS:")
    print("-" * 40)
    with open('user_data/test_results/roi_test.log') as f:
        content = f.read()
        for match in re.finditer(r'Testing ROI: (\w+).*?(?=Testing ROI:|$)', content, re.DOTALL):
            section = match.group(0)
            roi_name = match.group(1)
            profit = re.search(r'Total profit %\s+([-\d.]+)', section)
            trades = re.search(r'Trades\s+(\d+)', section)
            winrate = re.search(r'Win %\s+([\d.]+)', section)

            print(f"  ROI {roi_name}:")
            if profit: print(f"    Profit: {profit.group(1)}%")
            if trades: print(f"    Trades: {trades.group(1)}")
            if winrate: print(f"    Win Rate: {winrate.group(1)}%")
    print()

# Parse trailing results
if os.path.exists('user_data/test_results/trailing_test.log'):
    print("📈 TRAILING STOP TEST RESULTS:")
    print("-" * 40)
    with open('user_data/test_results/trailing_test.log') as f:
        content = f.read()
        for match in re.finditer(r'Testing Trailing: (\w+).*?(?=Testing Trailing:|$)', content, re.DOTALL):
            section = match.group(0)
            trail_name = match.group(1)
            profit = re.search(r'Total profit %\s+([-\d.]+)', section)
            trades = re.search(r'Trades\s+(\d+)', section)
            winrate = re.search(r'Win %\s+([\d.]+)', section)

            print(f"  Trailing {trail_name}:")
            if profit: print(f"    Profit: {profit.group(1)}%")
            if trades: print(f"    Trades: {trades.group(1)}")
            if winrate: print(f"    Win Rate: {winrate.group(1)}%")
    print()

print("="*60)
print("\n✅ Summary complete!")
print("Check individual logs in user_data/test_results/ for details")

PYEOF

echo ""
echo "Done!"
