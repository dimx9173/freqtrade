#!/bin/bash
# =============================================================================
# backtest_3regime.sh - 三市場統一回測腳本
# =============================================================================
# 使用方式: ./backtest_3regime.sh <strategy_file> <strategy_name> <timerange> [config]
#
# 三市場 timerange:
#   BULL:      20250701-20250930  (Jul-Sep 2025, +8%/+5.4%)
#   BEAR:      20251101-20260430  (Nov 2025 - Apr 2026, 持續下跌)
#   SIDEWAYS:  20250301-20250630  (Mar-Jun 2026, 橫盤)
# =============================================================================

STRATEGY_FILE="$1"
STRATEGY_NAME="$2"
TIMERANGE="${3:-20251101-20260430}"
CONFIG="${4:-user_data/config/config_6_futures_1x.json}"
STRATEGY_PATH="$(dirname "$STRATEGY_FILE")"

cd ~/freqtrade || exit 1

echo "=========================================="
echo "回測策略: $STRATEGY_NAME"
echo "Timerange: $TIMERANGE"
echo "=========================================="

rm -rf user_data/backtest_results/*

$HOME/.linuxbrew/bin/python3 -m freqtrade backtesting \
  --config "$CONFIG" \
  --strategy "$STRATEGY_NAME" \
  --strategy-path "$STRATEGY_PATH" \
  --timerange "$TIMERANGE" \
  --dry-run-wallet 10000 \
  --fee 0.0005 \
  --timerange "$TIMERANGE" \
  2>&1 | tee "/tmp/backtest_${STRATEGY_NAME}.log"

echo ""
echo "=========================================="
echo "回測完成，結果保存在: /tmp/backtest_${STRATEGY_NAME}.log"
echo "=========================================="
