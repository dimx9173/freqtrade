#!/bin/bash
# ==============================================
# Test/Prod 合約一鍵回測腳本
# ==============================================

cd /home/brian/freqtrade

STRATEGY=${1:-"all"}
TIMERANGE=${2:-"20250824-20260524"}
CONFIG_PATH="user_data/config/test"
STRATEGY_PATH="user_data/strategies/test/prod"
RESULT_DIR="user_data/reports/test_prod_backtest_futures"

mkdir -p "$RESULT_DIR"

echo "========================================"
echo "Test/Prod Futures Backtest"
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
  local base_config="$CONFIG_PATH/config_${config_id}.json"
  local futures_config="/tmp/futures_config_${config_id}.json"
  local output_file="$RESULT_DIR/${strategy}_backtest.log"
  
  echo ""
  echo "----------------------------------------"
  echo "Futures Backtesting: $strategy"
  echo "Base Config: $base_config"
  echo "----------------------------------------"
  
  if [[ ! -f "$base_config" ]]; then
    echo "WARNING: Config not found: $base_config"
    return 1
  fi
  
  # 創建合約 config
  python3 << PYEOF
import json
with open('$base_config') as f:
    c = json.load(f)

# 修改為合約模式
c['trading_mode'] = 'futures'
c['margin_mode'] = 'isolated'
c['stoploss'] = -0.05  # 合約用較緊 stoploss

# 加入槓桿設定（如果沒有）
if ' leverage' not in c:
    c['leverage'] = 3  # 預設 3x

# 確保 pair whitelist 是合約格式
pairs = c.get('exchange', {}).get('pair_whitelist', [])
new_pairs = []
for p in pairs:
    if '/USDT' in p and ':USDT' not in p:
        new_pairs.append(p.replace('/USDT', '/USDT:USDT'))
    else:
        new_pairs.append(p)
c['exchange']['pair_whitelist'] = new_pairs

with open('$futures_config', 'w') as f:
    json.dump(c, f, indent=2)
print('Futures config created')
PYEOF
  
  python3 -m freqtrade backtesting \
    --config "$futures_config" \
    --strategy "$strategy" \
    --strategy-path "$STRATEGY_PATH" \
    --timerange "$TIMERANGE" \
    2>&1 | tee "$output_file"
  
  # 提取關鍵結果
  echo ""
  echo "📊 $strategy 合約結果摘要:"
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
    exit 1
  fi
  
  run_backtest "$STRATEGY" "$config_id"
fi

echo "========================================"
echo "Futures Backtest completed"
echo "結果目錄: $RESULT_DIR"
echo "========================================"
