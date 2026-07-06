#!/bin/zsh
cd $HOME/freqtrade

# ==============================================
# Auto Hyperopt Pipeline
# ==============================================
#
# 用法:
#   bash hyperopt.sh [threads] [strategy_id_or_name]
#
# 引數:
#   threads              執行緒數（預設 4），建議 4-8
#   strategy_id_or_name  只優化特定策略，不傳則跑全部 6 個
#
# strategy_id_or_name 可用:
#   1          → NASOSv4
#   2          → PSV5_Hybrid
#   3          → BB_RPB_TSL_BI
#   4          → NASOSv5_mod3
#   5          → SMAOffsetProtectOptV1
#   6          → ElliotV5_SMA_ninja
#   NASOSv4    → 只跑 NASOSv4（可用策略名）
#
# 範例:
#   bash hyperopt.sh                          # 跑全部 6 個策略，4 執行緒
#   bash hyperopt.sh 8                        # 跑全部，8 執行緒
#   bash hyperopt.sh 4 1                      # 只跑策略 1（NASOSv4），4 執行緒
#   bash hyperopt.sh 4 NASOSv5_mod3           # 只跑 NASOSv5_mod3
#   bash hyperopt.sh 2 ElliotV5_SMA_ninja    # 只跑 ElliotV5，2 執行緒
#   bash hyperopt.sh 8 5                      # 只跑 SMAOffsetProtectOptV1，8 執行緒
#
# 流程:
#   1. 停止對應 Bot（如有執行）
#   2. 執行 hyperopt（timerange 自動計算）
#   3. 匯出最佳參數到 strategies/prod/{strategy}.json
#   4. 重啟 Bot
#   5. 自動 commit + push 到 brian/main
#   6. 冷卻 10 秒後執行下一策略
#
# 策略 Spaces 對照:
#   1  NASOSv4              → buy, sell
#   2  PSV5_Hybrid          → buy, stoploss, trailing, roi
#   3  BB_RPB_TSL_BI        → buy, sell
#   4  NASOSv5_mod3         → buy, sell
#   5  SMAOffsetProtectOptV1 → buy, sell（9 個月）
#   6  ElliotV5_SMA_ninja    → buy, sell（ProfitDrawOptLoss）
#
# 輸出:
#   user_data/hyperopt_results/summary_results_{strategy}.log
#   user_data/logs/freqtrade_{strategy}.log
#   user_data/strategies/prod/{strategy}.json
#
# ==============================================

THREADS=${1:-4}
TARGET_ID=${2:-""}

echo "========================================"
echo "Auto Hyperopt started at $(date)"
echo "Threads: ${THREADS}"
echo "Target: ${TARGET_ID:-ALL}"
echo "========================================"

# 定義策略列表 (ID|config|strategy|months|epochs|spaces|loss)
configs=(
  "1|$HOME/freqtrade/user_data/config/prod/slot_1.json|NASOSv4|6|500|buy,sell|ProfitDrawDownHyperOptLoss"
  "2|$HOME/freqtrade/user_data/config/prod/slot_2.json|PSV5_Hybrid|6|500|buy|ProfitDrawDownHyperOptLoss"
  "3|$HOME/freqtrade/user_data/config/prod/slot_3.json|BB_RPB_TSL_BI|6|500|buy,sell|MultiMetricHyperOptLoss"
  "4|$HOME/freqtrade/user_data/config/prod/slot_4.json|NASOSv5_mod3|6|500|buy,sell|ProfitDrawDownHyperOptLoss"
  "5|$HOME/freqtrade/user_data/config/prod/slot_5.json|SMAOffsetProtectOptV1|9|500|buy,sell|ProfitDrawDownHyperOptLoss"
  "6|$HOME/freqtrade/user_data/config/prod/slot_6.json|ElliotV5_SMA_ninja|6|400|buy,sell|ProfitDrawOptLoss"
)

# 確保結果目錄存在
mkdir -p user_data/hyperopt_results
mkdir -p user_data/logs

# 清理舊結果（可選：保留最近 30 天的 .fthypt）
find user_data/hyperopt_results -name "*.fthypt" -mtime +30 -delete 2>/dev/null

# 統一使用 venv 中的 freqtrade
FT="$HOME/freqtrade/.venv/bin/freqtrade"

for config in "${configs[@]}"; do
  IFS='|' read -r ID config_file strategy_name months epochs spaces hyperopt_loss <<< "$config"

  # 若指定了 TARGET_ID，只處理匹配的（支援數字 ID 或策略名稱）
  if [[ -n "$TARGET_ID" ]]; then
    if [[ "$ID" != "$TARGET_ID" && "$strategy_name" != "$TARGET_ID" ]]; then
      continue
    fi
  fi

  echo ""
  echo "----------------------------------------"
  echo "[$ID] $strategy_name — started at $(date)"
  echo "----------------------------------------"

  summary_results_file="user_data/hyperopt_results/summary_results_${strategy_name}.log"
  rm -f "$summary_results_file"

  # 計算 timerange
  cal_months=$(($months))
  TIME_RANGE=$(bash "$HOME/freqtrade/user_data/scripts/utilities/get_time_range.sh" $cal_months)
  echo "Timerange: $TIME_RANGE | Epochs: $epochs | Threads: $THREADS | Spaces: $spaces" | tee -a "$summary_results_file"

  # ===== 1. 停止對應 Bot =====
  echo "[$ID] Stopping $strategy_name..."
  if pgrep -f "freqtrade trade.*--strategy $strategy_name" > /dev/null; then
    zsh "$HOME/freqtrade/user_data/scripts/stop_by_ps.sh" "$config_file" "$strategy_name" 2>&1 | tee -a "$summary_results_file"
    sleep 5
    # 確認已停止
    if pgrep -f "freqtrade trade.*--strategy $strategy_name" > /dev/null; then
      echo "WARNING: $strategy_name still running after stop attempt!" | tee -a "$summary_results_file"
    else
      echo "Bot stopped successfully." | tee -a "$summary_results_file"
    fi
  else
    echo "Bot not running, skip stop." | tee -a "$summary_results_file"
  fi

  # ===== 2. 執行 Hyperopt =====
  echo "[$ID] Running hyperopt..."
  $FT hyperopt \
    --config "$config_file" \
    --logfile "user_data/logs/freqtrade_${strategy_name}.log" \
    --hyperopt-loss "$hyperopt_loss" \
    --spaces $(echo "$spaces" | tr ',' ' ') \
    --strategy-path user_data/strategies/prod \
    -e "$epochs" \
    -j "$THREADS" \
    --timerange "$TIME_RANGE" \
    --strategy "$strategy_name" \
    2>&1 | tee -a "$summary_results_file"

  # 正確取得 tee 中 hyperopt 的 exit code
  HYPEROPT_EXIT=${pipestatus[1]:-$?}

  if [[ $HYPEROPT_EXIT -ne 0 ]]; then
    echo "ERROR: Hyperopt failed for $strategy_name (exit: $HYPEROPT_EXIT)" | tee -a "$summary_results_file"
    echo "[$ID] $strategy_name — FAILED at $(date)" | tee -a "$summary_results_file"
    # 失敗也要嘗試重啟 Bot（用舊參數）
    bash "$HOME/freqtrade/user_data/scripts/start_all_bots.sh" "$ID"
    continue
  fi

  # ===== 3. 自動匯出最佳參數 =====
  echo "[$ID] Exporting best parameters..."

  # 只取當前策略的 fthypt（檔名格式：strategy_{name}_{timestamp}.fthypt）
  LATEST_RESULT=$(ls -t "user_data/hyperopt_results/strategy_${strategy_name}_"*.fthypt 2>/dev/null | head -1)

  if [[ -z "$LATEST_RESULT" ]]; then
    # 相容舊格式（部分 fthypt 可能沒有 strategy_ 前綴）
    LATEST_RESULT=$(ls -t user_data/hyperopt_results/*.fthypt 2>/dev/null | grep -v 'Elli' | head -1)
  fi

  if [[ -f "$LATEST_RESULT" ]]; then
    FTHYPT_BASENAME=$(basename "$LATEST_RESULT")
    OUTPUT_JSON="user_data/strategies/prod/${strategy_name}.json"

    # 使用 Python 解析 JSON（避免 grep 截斷 / 取錯行的問題）
    python3 - << 'PYEOF' "$FTHYPT_BASENAME" "$OUTPUT_JSON" "$strategy_name"
import sys, json, subprocess, os

fthypt_file = sys.argv[1]
output_file = sys.argv[2]
strategy_name = sys.argv[3]

# 執行 hyperopt-show --print-json，只取最後一個 JSON 物件
result = subprocess.run(
    [os.path.expanduser("~/freqtrade/.venv/bin/freqtrade"), "hyperopt-show",
     "--hyperopt-filename", fthypt_file,
     "--best", "-n", "1",
     "--print-json"],
    capture_output=True, text=True, cwd=os.path.expanduser("~/freqtrade")
)

# 找最後一個以 { 開頭的行（JSON 物件）
json_lines = [line for line in result.stdout.split('\n') if line.strip().startswith('{')]
if not json_lines:
    print("ERROR: No JSON found in hyperopt-show output", file=sys.stderr)
    sys.exit(1)

try:
    data = json.loads(json_lines[-1])
except json.JSONDecodeError as e:
    print(f"JSON parse error: {e}", file=sys.stderr)
    sys.exit(1)

if 'params' not in data:
    print("ERROR: No params in hyperopt JSON", file=sys.stderr)
    sys.exit(1)

flat = data['params']

# 將 flat hyperopt params 映射到 strategy JSON 的 nested 格式
# buy 空間參數
buy_keys = ['base_nb_candles_buy', 'lookback_candles', 'profit_threshold',
            'ewo_high', 'ewo_high_2', 'ewo_low', 'low_offset', 'low_offset_2', 'rsi_buy']
# sell 空間參數
sell_keys = ['base_nb_candles_sell', 'high_offset', 'high_offset_2']
# protection 空間參數
protection_keys = ['pHSL', 'pPF_1', 'pPF_2', 'pSL_1', 'pSL_2']
# roi 空間（minimal_roi 的 key 是 epoch 數字字串）
roi_keys = [k for k in flat.keys() if k.isdigit()]
# trailing 空間的 key
trailing_keys = ['trailing_stop', 'trailing_stop_positive',
                 'trailing_stop_positive_offset', 'trailing_only_offset_is_reached']
# max_open_trades
max_open_trades = flat.get('max_open_trades', data.get('max_open_trades', 1))

# 重建 nested params
params_nested = {
    "buy": {k: flat[k] for k in buy_keys if k in flat},
    "sell": {k: flat[k] for k in sell_keys if k in flat},
}
if any(k in flat for k in protection_keys):
    params_nested["protection"] = {k: flat[k] for k in protection_keys if k in flat}
if any(k in flat for k in roi_keys):
    params_nested["roi"] = {k: flat[k] for k in roi_keys}
if any(k in flat for k in ['stoploss']):
    params_nested["stoploss"] = {"stoploss": flat.get('stoploss', data.get('stoploss', -0.15))}
if any(k in flat for k in trailing_keys):
    params_nested["trailing"] = {k: flat[k] for k in trailing_keys if k in flat}
if 'max_open_trades' in flat or 'max_open_trades' in data:
    params_nested["max_open_trades"] = {"max_open_trades": max_open_trades}

# 重建完整格式（與策略 JSON 格式一致）
export_data = {
    "strategy_name": strategy_name,
    "params": params_nested,
    "minimal_roi": data.get("minimal_roi", {}),
    "stoploss": data.get("stoploss", -0.15),
    "trailing_stop": data.get("trailing_stop", False),
    "trailing_stop_positive": data.get("trailing_stop_positive", 0),
    "trailing_stop_positive_offset": data.get("trailing_stop_positive_offset", 0),
    "trailing_only_offset_is_reached": data.get("trailing_only_offset_is_reached", False),
    "max_open_trades": max_open_trades
}

with open(output_file, 'w') as f:
    json.dump(export_data, f, indent=2)
print(f"OK: {output_file}")
sys.exit(0)
PYEOF

    EXPORT_STATUS=$?
    if [[ $EXPORT_STATUS -eq 0 ]]; then
      echo "Parameters exported to: $OUTPUT_JSON" | tee -a "$summary_results_file"
    else
      echo "WARNING: JSON export failed, falling back to raw extraction..." | tee -a "$summary_results_file"
      # fallback：直接 pipe 输出到 JSON 檔
      $FT hyperopt-show \
        --hyperopt-filename "$FTHYPT_BASENAME" \
        --best -n 1 \
        --print-json 2>/dev/null | grep -E '^\s*\{' | tail -1 \
        > "$OUTPUT_JSON"
      echo "Parameters exported (fallback) to: $OUTPUT_JSON" | tee -a "$summary_results_file"
    fi

    # 顯示最佳結果摘要到 log
    echo "--- Best Epoch Summary ---" | tee -a "$summary_results_file"
    $FT hyperopt-show \
      --hyperopt-filename "$FTHYPT_BASENAME" \
      --best -n 1 \
      --no-header 2>/dev/null | head -30 | tee -a "$summary_results_file"
  else
    echo "WARNING: No .fthypt result file found for $strategy_name!" | tee -a "$summary_results_file"
  fi

  # ===== 4. 重啟 Bot =====
  echo "[$ID] Restarting $strategy_name..."
  bash "$HOME/freqtrade/user_data/scripts/start_all_bots.sh" "$ID" > /dev/null 2>&1

  # 確認啟動成功
  sleep 3
  if pgrep -f "freqtrade trade.*--strategy $strategy_name" > /dev/null; then
    echo "Bot restarted successfully." | tee -a "$summary_results_file"
  else
    echo "WARNING: Bot may not have started! Check tmux." | tee -a "$summary_results_file"
  fi

  echo "[$ID] $strategy_name — finished at $(date)" | tee -a "$summary_results_file"

  # ===== 5. 檔案整理：清理過期備份 =====
  echo "[$ID] Cleaning up stale backups..."
  find user_data/strategies/prod -name "*.bak.*" -mtime +7 -delete 2>/dev/null
  find user_data/strategies/prod -name "*backup*" -mtime +7 -delete 2>/dev/null
  find user_data/config -name "*.bak.*" -mtime +7 -delete 2>/dev/null

  # ===== 6. 自動 commit/push 所有策略與設定變更 =====
  echo "[$ID] Committing all strategy and config changes..."
  # 在 user_data repo 內執行（獨立於 freqtrade 主 repo）
  cd "$HOME/freqtrade/user_data"
  # 策略參數
  git add "strategies/prod/${strategy_name}.json" 2>/dev/null
  # 策略程式碼（如果有修改）
  git add "strategies/prod/${strategy_name}.py" 2>/dev/null
  # 所有 config
  git add config/*.json 2>/dev/null
  # 腳本
  git add scripts/*.sh 2>/dev/null
  git add scripts/utilities/*.sh 2>/dev/null
  # AGENTS.md
  git add AGENTS.md 2>/dev/null

  # 檢查 staged 是否有變更
  if git diff --cached --quiet; then
    echo "No changes to commit." | tee -a "$summary_results_file"
  else
    git commit -m "auto(hyperopt): ${strategy_name} @ $(date -u '+%Y-%m-%d %H:%M UTC')" 2>/dev/null
    if [[ $? -eq 0 ]]; then
      git push origin master 2>/dev/null
      if [[ $? -eq 0 ]]; then
        echo "All changes committed and pushed to freqtrade-user_data." | tee -a "$summary_results_file"
      else
        echo "WARNING: Push failed (check auth/network)." | tee -a "$summary_results_file"
      fi
    else
      echo "WARNING: Commit failed." | tee -a "$summary_results_file"
    fi
  fi

  # 確保工作目錄回到 freqtrade 根，目錄污染會導致後續策略路徑錯誤
  cd "$HOME/freqtrade"

  # 策略間冷卻（避免資源衝突）
  if [[ -z "$TARGET_ID" ]]; then
    echo "Cooling down 5 minutes..."
    sleep 10
  fi
done

echo ""
echo "========================================"
echo "All hyperopt finished at $(date)"
echo "========================================"
