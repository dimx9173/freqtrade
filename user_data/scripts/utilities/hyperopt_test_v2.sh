#!/bin/zsh
cd $HOME/freqtrade

# ==============================================
# Hyperopt V2 測試腳本（優化參數驗證用）
# ==============================================
#
# 用法:
#   bash hyperopt_test_v2.sh [strategy_id_or_name]
#
# 與 production 的差異:
#   - 使用 MultiMetricHyperOptLoss（懲罰低交易次數）
#   - 加入 --early-stop 150
#   - 加入 --min-trades 20
#   - 加入 --random-state 42
#   - PSV5_Hybrid 加入 sell space
#   - SMAOffset 改為 9 個月
#   - ElliotV5 改用 ProfitDrawDownHyperOptLoss
#
# ==============================================

STRATEGY_ID=${1:-"3"}  # 預設 BB_RPB_TSL_BI
THREADS=6

# 統一優化參數
EARLY_STOP=150
MIN_TRADES=20
RANDOM_STATE=42

# 定義策略列表 (ID|config|strategy|months|epochs|spaces|loss)
# V2 改動:
#   - 所有 loss → MultiMetricHyperOptLoss（除了 ElliotV5）
#   - PSV5: buy → buy,sell
#   - SMAOffset: 12 → 9 個月
#   - ElliotV5: Sharpe → ProfitDrawDownHyperOptLoss
configs=(
  "1|$HOME/freqtrade/user_data/config/config_1.json|NASOSv4|6|400|buy,sell|MultiMetricHyperOptLoss"
  "2|$HOME/freqtrade/user_data/config/config_2.json|PSV5_Hybrid|6|500|buy|MultiMetricHyperOptLoss"
  "3|$HOME/freqtrade/user_data/config/config_3.json|BB_RPB_TSL_BI|6|600|buy,sell|MultiMetricHyperOptLoss"
  "4|$HOME/freqtrade/user_data/config/config_4.json|NASOSv5_mod3|6|400|buy,sell|MultiMetricHyperOptLoss"
  "5|$HOME/freqtrade/user_data/config/config_5.json|SMAOffsetProtectOptV1|9|450|buy,sell|MultiMetricHyperOptLoss"
  "6|$HOME/freqtrade/user_data/config/config_6.json|ElliotV5_SMA_ninja|6|400|buy,sell|ProfitDrawDownHyperOptLoss"
)

echo "========================================"
echo "Hyperopt V2 Test started at $(date)"
echo "Strategy: ${STRATEGY_ID}"
echo "Threads: ${THREADS}"
echo "Early Stop: ${EARLY_STOP}"
echo "Min Trades: ${MIN_TRADES}"
echo "Random State: ${RANDOM_STATE}"
echo "========================================"

mkdir -p user_data/hyperopt_results
mkdir -p user_data/logs
mkdir -p user_data/reports

FT="$HOME/freqtrade/.venv/bin/freqtrade"

for config in "${configs[@]}"; do
  IFS='|' read -r ID config_file strategy_name months epochs spaces hyperopt_loss <<< "$config"

  # 只處理指定的策略
  if [[ "$ID" != "$STRATEGY_ID" && "$strategy_name" != "$STRATEGY_ID" ]]; then
    continue
  fi

  echo ""
  echo "----------------------------------------"
  echo "[$ID] $strategy_name — V2 Test"
  echo "----------------------------------------"

  summary_results_file="user_data/hyperopt_results/summary_results_${strategy_name}_v2.log"
  rm -f "$summary_results_file"

  # 計算 timerange
  cal_months=$(($months))
  TIME_RANGE=$(bash "$HOME/freqtrade/user_data/scripts/utilities/get_time_range.sh" $cal_months)
  echo "Timerange: $TIME_RANGE | Epochs: $epochs | Loss: $hyperopt_loss | Spaces: $spaces" | tee -a "$summary_results_file"

  # ===== 執行 Hyperopt V2 =====
  echo "[$ID] Running hyperopt with V2 params..."
  $FT hyperopt \
    --config "$config_file" \
    --logfile "user_data/logs/freqtrade_${strategy_name}_v2.log" \
    --hyperopt-loss "$hyperopt_loss" \
    --spaces $(echo "$spaces" | tr ',' ' ') \
    --strategy-path user_data/strategies/prod \
    -e "$epochs" \
    -j "$THREADS" \
    --timerange "$TIME_RANGE" \
    --strategy "$strategy_name" \
    --early-stop "$EARLY_STOP" \
    --min-trades "$MIN_TRADES" \
    --random-state "$RANDOM_STATE" \
    2>&1 | tee -a "$summary_results_file"

  HYPEROPT_EXIT=${pipestatus[1]:-$?}

  if [[ $HYPEROPT_EXIT -ne 0 ]]; then
    echo "ERROR: Hyperopt failed for $strategy_name (exit: $HYPEROPT_EXIT)" | tee -a "$summary_results_file"
    continue
  fi

  # ===== 顯示最佳結果 =====
  echo "[$ID] Best epoch summary:"
  LATEST_RESULT=$(ls -t "user_data/hyperopt_results/strategy_${strategy_name}_"*.fthypt 2>/dev/null | head -1)
  if [[ -f "$LATEST_RESULT" ]]; then
    FTHYPT_BASENAME=$(basename "$LATEST_RESULT")
    $FT hyperopt-show \
      --hyperopt-filename "$FTHYPT_BASENAME" \
      --best -n 1 \
      --no-header 2>/dev/null | head -40 | tee -a "$summary_results_file"
  fi

  echo "[$ID] $strategy_name — V2 Test finished at $(date)" | tee -a "$summary_results_file"
  echo ""
  echo "✅ 請檢查: $summary_results_file"
  echo ""

done

echo "========================================"
echo "V2 Test completed at $(date)"
echo "========================================"
