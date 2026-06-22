#!/bin/bash
# =============================================================================
# backtest_regime.sh — 通用 regime backtest runner
# Usage: ./backtest_regime.sh <TIMERANGE> <REGIME_NAME> <OUT_DIR>
# =============================================================================
set -e
cd ~/freqtrade || exit 1

PYTHON=".venv/bin/python"
CONFIG_SRC="user_data/config/backtest_futures_standard.json"
CONFIG="/tmp/bt_std_working.json"
TIMERANGE="$1"
REGIME_NAME="$2"
OUT_BASE="$3"
STRATEGY_DIR="user_data/strategies/prod"
mkdir -p "$OUT_BASE"

# 確認 HTTP server 在跑
if ! curl -s -o /dev/null http://127.0.0.1:8765/user_data/config/coinmarketcap-futures-pairlist.json; then
  echo "▶ Starting local HTTP server on port 8765..."
  python3 -m http.server 8765 --bind 127.0.0.1 >/tmp/http_server.log 2>&1 &
  echo $! > /tmp/http_server.pid
  sleep 2
fi

# 創建 working config: 用合約格式 pairlist URL
cp "$CONFIG_SRC" "$CONFIG"
sed -i 's|file:///user_data/config/coinmarketcap-pairlist.json|http://127.0.0.1:8765/user_data/config/coinmarketcap-futures-pairlist.json|g' "$CONFIG"

STRATEGIES=(
  "BB_RPB_TSL_BI"
  "ElliotV5_SMA_ninja"
  "NASOSv4"
  "NASOSv5_mod3"
  "SMAOffsetProtectOptV1"
)

for STRAT in "${STRATEGIES[@]}"; do
  echo ""
  echo "=========================================="
  echo "▶ [$REGIME_NAME] Backtesting: $STRAT  ($TIMERANGE)"
  echo "=========================================="

  OUT_DIR="$OUT_BASE/$STRAT"
  mkdir -p "$OUT_DIR"

  rm -rf user_data/backtest_results/*
  rm -f "/tmp/backtest_${STRAT}.log"

  $PYTHON -m freqtrade backtesting \
    --config "$CONFIG" \
    --strategy "$STRAT" \
    --strategy-path "$STRATEGY_DIR" \
    --timerange "$TIMERANGE" \
    --dry-run-wallet 10000 \
    2>&1 | tee "/tmp/backtest_${STRAT}.log"

  cp "/tmp/backtest_${STRAT}.log" "$OUT_DIR/backtest.log"
  if ls user_data/backtest_results/*.zip >/dev/null 2>&1; then
    cp user_data/backtest_results/*.zip "$OUT_DIR/" 2>/dev/null || true
    cp user_data/backtest_results/*.meta.json "$OUT_DIR/" 2>/dev/null || true
    echo "✓ $STRAT results saved"
  else
    echo "⚠ $STRAT produced no .zip result"
  fi
done

echo ""
echo "=========================================="
echo "✓ All 5 strategies completed for $REGIME_NAME ($TIMERANGE)"
echo "Results: $OUT_BASE"
echo "=========================================="
