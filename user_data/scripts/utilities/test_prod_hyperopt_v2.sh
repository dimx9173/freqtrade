#!/bin/zsh
cd $HOME/freqtrade

# ==============================================
# Test/Prod Hyperopt V2 腳本
# ==============================================

STRATEGY_ID=${1:-"3"}
THREADS=6

# 統一優化參數
EARLY_STOP=150
MIN_TRADES=20
RANDOM_STATE=42

# Test/Prod 路徑
STRATEGY_PATH="user_data/strategies/test/prod"
CONFIG_PATH="user_data/config/test"

configs=(
  "1|$CONFIG_PATH/config_1.json|NASOSv4|6|400|buy,sell|MultiMetricHyperOptLoss"
  "2|$CONFIG_PATH/config_2.json|PSV5_Hybrid|6|500|buy|MultiMetricHyperOptLoss"
  "3|$CONFIG_PATH/config_3.json|BB_RPB_TSL_BI|6|600|buy,sell|MultiMetricHyperOptLoss"
  "4|$CONFIG_PATH/config_4.json|NASOSv5_mod3|6|400|buy,sell|MultiMetricHyperOptLoss"
  "5|$CONFIG_PATH/config_5.json|SMAOffsetProtectOptV1|9|450|buy,sell|MultiMetricHyperOptLoss"
  "6|$CONFIG_PATH/config_6.json|ElliotV5_SMA_ninja|6|400|buy,sell|ProfitDrawDownHyperOptLoss"
)

echo "========================================"
echo "Test/Prod Hyperopt V2 started at $(date)"
echo "Strategy: ${STRATEGY_ID}"
echo "Threads: ${THREADS}"
echo "Strategy Path: ${STRATEGY_PATH}"
echo "========================================"

mkdir -p user_data/hyperopt_results
mkdir -p user_data/logs
mkdir -p user_data/reports

FT="$HOME/freqtrade/.venv/bin/freqtrade"

for config in "${configs[@]}"; do
  IFS='|' read -r ID config_file strategy_name months epochs spaces hyperopt_loss <<< "$config"

  if [[ "$ID" != "$STRATEGY_ID" && "$strategy_name" != "$STRATEGY_ID" ]]; then
    continue
  fi

  echo ""
  echo "----------------------------------------"
  echo "[$ID] $strategy_name — Test/Prod V2"
  echo "----------------------------------------"

  summary_results_file="user_data/hyperopt_results/summary_results_${strategy_name}_test_prod_v2.log"
  rm -f "$summary_results_file"

  cal_months=$(($months))
  TIME_RANGE=$(bash "$HOME/freqtrade/user_data/scripts/utilities/get_time_range.sh" $cal_months)
  echo "Timerange: $TIME_RANGE | Epochs: $epochs | Loss: $hyperopt_loss | Spaces: $spaces" | tee -a "$summary_results_file"

  echo "[$ID] Running hyperopt..."
  $FT hyperopt \
    --config "$config_file" \
    --logfile "user_data/logs/freqtrade_${strategy_name}_test_prod_v2.log" \
    --hyperopt-loss "$hyperopt_loss" \
    --spaces $(echo "$spaces" | tr ',' ' ') \
    --strategy-path "$STRATEGY_PATH" \
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

  echo "[$ID] Best epoch summary:"
  LATEST_RESULT=$(ls -t "user_data/hyperopt_results/strategy_${strategy_name}_"*.fthypt 2>/dev/null | head -1)
  if [[ -f "$LATEST_RESULT" ]]; then
    FTHYPT_BASENAME=$(basename "$LATEST_RESULT")
    $FT hyperopt-show \
      --hyperopt-filename "$FTHYPT_BASENAME" \
      --best -n 1 \
      --no-header 2>/dev/null | head -40 | tee -a "$summary_results_file"
  fi

  echo "[$ID] $strategy_name — finished at $(date)" | tee -a "$summary_results_file"
  echo ""
  echo "✅ 請檢查: $summary_results_file"
  echo ""

done

echo "========================================"
echo "Test/Prod V2 completed at $(date)"
echo "========================================"
