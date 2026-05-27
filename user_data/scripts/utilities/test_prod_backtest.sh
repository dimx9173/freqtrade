#!/bin/bash
# ==============================================
# Test/Prod 一鍵回測腳本
# ==============================================

cd /home/brian/freqtrade

STRATEGY=${1:-"all"}
TIMERANGE=${2:-"20250824-20260524"}
CONFIG_PATH="user_data/config/test"
STRATEGY_PATH="user_data/strategies/test/prod"
RESULT_DIR="user_data/reports/test_prod_backtest"

mkdir -p "$RESULT_DIR"

echo "========================================"
echo "Test/Prod Backtest"
echo "Strategy: $STRATEGY"
echo "Timerange: $TIMERANGE"
echo "========================================"

# 定義策略列表
strategies=(
  "SMAOffsetProtectOptV1|5"
  "BB_RPB_TSL_BI|3"
  "PSV5_Hybrid|2"
  "NASOSv4|1"
  "NASOSv5_mod3|4"
  "ElliotV5_SMA_ninja|6"
)

run_backtest() {
  local strategy=$1
  local config_id=$2
  local config_file="$CONFIG_PATH/config_${config_id}.json"
  local output_file="$RESULT_DIR/${strategy}_backtest.log"
  
  echo ""
  echo "----------------------------------------"
  echo "Backtesting: $strategy"
  echo "Config: $config_file"
  echo "----------------------------------------"
  
  if [[ ! -f "$config_file" ]]; then
    echo "WARNING: Config not found: $config_file"
    return 1
  fi
  
  python3 -m freqtrade backtesting \
    --config "$config_file" \
    --strategy "$strategy" \
    --strategy-path "$STRATEGY_PATH" \
    --timerange "$TIMERANGE" \
    2>&1 | tee "$output_file"
  
  # 提取關鍵結果
  echo ""
  echo "📊 $strategy 結果摘要:"
  grep -E "Tot Profit %|Win  Draw  Loss|Trades|Drawdown" "$output_file" | tail -5
  echo ""
  echo "詳細結果: $output_file"
}

# 執行回測
if [[ "$STRATEGY" == "all" ]]; then
  for s in "${strategies[@]}"; do
    IFS='|' read -r name config_id <<< "$s"
    run_backtest "$name" "$config_id"
  done
else
  # 找到對應的 config_id
  config_id=""
  for s in "${strategies[@]}"; do
    IFS='|' read -r name cid <<< "$s"
    if [[ "$name" == "$STRATEGY" ]]; then
      config_id="$cid"
      break
    fi
  done
  
  if [[ -z "$config_id" ]]; then
    echo "ERROR: Unknown strategy: $STRATEGY"
    echo "可用策略:"
    for s in "${strategies[@]}"; do
      IFS='|' read -r name cid <<< "$s"
      echo "  - $name"
    done
    exit 1
  fi
  
  run_backtest "$STRATEGY" "$config_id"
fi

echo "========================================"
echo "Backtest completed"
echo "結果目錄: $RESULT_DIR"
echo "========================================"
