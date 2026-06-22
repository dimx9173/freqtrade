#!/bin/bash
# =============================================================================
# sweep_nasosv4.sh — NASOSv4 參數 sweep
# 測試 stake × max_open 對 3 regime 的影響
#
# 當前 v2: stake=50, max_open=3 (1.5% 資金利用率)
# Brian 目標: stake=200, max_open=5 (10% 資金利用率)
# =============================================================================
set -e

cd /home/brian/freqtrade || exit 1

PYTHON=".venv/bin/python"
BASE_CONFIG="user_data/config/backtest_futures_standard.json"
TIMERANGE_REGIMES=(
  "20250701-20250930:BULL"
  "20250301-20250630:SIDEWAYS"
  "20251101-20260430:BEAR"
)

# Config matrix: stake × max_open
# 6 組合,涵蓋 baseline + Brian 目標 + 中間值
STAKES=(50 100 200)
MAX_OPENS=(3 5)
STRATEGY="NASOSv4"
STRATEGY_DIR="user_data/strategies/prod"

OUT_BASE="user_data/reports/nasosv4_optimization"
mkdir -p "$OUT_BASE"

# 確保 HTTP server 在跑 (RemotePairList workaround)
if ! curl -s -o /dev/null http://127.0.0.1:8765/user_data/config/coinmarketcap-futures-pairlist.json; then
  echo "▶ Starting local HTTP server on port 8765..."
  nohup python3 -m http.server 8765 --bind 127.0.0.1 >/tmp/http_server.log 2>&1 &
  echo $! > /tmp/http_server.pid
  sleep 2
fi

# 確保 SIDEWAYS pairlist 可用
cp -n user_data/config/coinmarketcap-futures-pairlist_SIDEWAYS.json /tmp/ 2>/dev/null || true

TOTAL=$((${#STAKES[@]} * ${#MAX_OPENS[@]} * ${#TIMERANGE_REGIMES[@]}))
COUNT=0
START_TIME=$(date +%s)

for combo in "${STAKES[@]}" ; do : ; done  # just for syntax check

for stake in "${STAKES[@]}"; do
  for maxopen in "${MAX_OPENS[@]}"; do
    for entry in "${TIMERANGE_REGIMES[@]}"; do
      timerange="${entry%%:*}"
      regime="${entry##*:}"
      COUNT=$((COUNT+1))

      CONFIG="/tmp/bt_nasosv4_${stake}_${maxopen}.json"

      # 用 SIDEWAS 專用 pairlist for SIDEWAS regime, 否則用標準 pairlist
      if [ "$regime" = "SIDEWAYS" ]; then
        pairlist_url="http://127.0.0.1:8765/user_data/config/coinmarketcap-futures-pairlist_SIDEWAYS.json"
      else
        pairlist_url="http://127.0.0.1:8765/user_data/config/coinmarketcap-futures-pairlist.json"
      fi

      # 複製 base config 並修改 stake + max_open + pairlist
      cp "$BASE_CONFIG" "$CONFIG"
      python3 -c "
import json
with open('$CONFIG') as f: d = json.load(f)
d['stake_amount'] = $stake
d['max_open_trades'] = $maxopen
d['pairlists'][0]['pairlist_url'] = '$pairlist_url'
with open('$CONFIG', 'w') as f: json.dump(d, f, indent=4)
"

      OUT_DIR="$OUT_BASE/${regime}/stake${stake}_maxopen${maxopen}"
      mkdir -p "$OUT_DIR"

      ELAPSED=$(( $(date +%s) - START_TIME ))
      echo ""
      echo "=========================================="
      echo "▶ [$COUNT/$TOTAL] NASOSv4 | stake=$stake max_open=$maxopen | $regime ($timerange) [elapsed: ${ELAPSED}s]"
      echo "=========================================="

      rm -rf user_data/backtest_results/*
      $PYTHON -m freqtrade backtesting \
        --config "$CONFIG" \
        --strategy "$STRATEGY" \
        --strategy-path "$STRATEGY_DIR" \
        --timerange "$timerange" \
        --dry-run-wallet 10000 \
        2>&1 | tee "$OUT_DIR/backtest.log"

      if ls user_data/backtest_results/*.zip >/dev/null 2>&1; then
        cp user_data/backtest_results/*.zip "$OUT_DIR/" 2>/dev/null || true
        cp user_data/backtest_results/*.meta.json "$OUT_DIR/" 2>/dev/null || true
        echo "  ✓ saved"
      else
        echo "  ⚠ no .zip result"
      fi
    done
  done
done

TOTAL_ELAPSED=$(( $(date +%s) - START_TIME ))
echo ""
echo "=========================================="
echo "✓ NASOSv4 sweep completed: $TOTAL runs in ${TOTAL_ELAPSED}s"
echo "Results: $OUT_BASE"
echo "=========================================="
