#!/bin/bash
# ==============================================
# NASOSv5_mod3 純回測迭代方案
# 5 組混合參數組合測試
# ==============================================

cd /home/brian/freqtrade

# 設定
STRATEGY="NASOSv5_mod3"
STRATEGY_PATH="user_data/strategies/prod"
TIMERANGE="${1:-20250824-20260524}"
RESULT_DIR="user_data/reports/nasosv5_iterations_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$RESULT_DIR"

echo "========================================"
echo "NASOSv5_mod3 純回測迭代方案"
echo "Timerange: $TIMERANGE"
echo "結果目錄: $RESULT_DIR"
echo "========================================"

# 備份原始參數檔
ORIG_PARAMS="user_data/strategies/prod/${STRATEGY}.json"
BACKUP_PARAMS="/tmp/${STRATEGY}_original.json"
if [[ -f "$ORIG_PARAMS" ]]; then
  cp "$ORIG_PARAMS" "$BACKUP_PARAMS"
fi

# 定義 5 組參數組合
# 格式: 組合名稱|參數檔案|說明
combos=(
  "A|user_data/strategies/test/NASOSv5_mod3_combo_A.json|新買舊賣基礎版: 新參數買入+舊參數ROI+舊sell offset"
  "B|user_data/strategies/test/NASOSv5_mod3_combo_B.json|保守獲利版: 收緊lookback/profit_threshold"
  "C|user_data/strategies/test/NASOSv5_mod3_combo_C.json|激進交易版: 新參數全保留+更激進ROI"
  "D|user_data/strategies/test/NASOSv5_mod3_combo_D.json|混合進場版: 舊參數ewo/rsi+新參數lookback"
  "E|user_data/strategies/test/NASOSv5_mod3_combo_E.json|低風險版: 收緊stoploss+trailing"
)

# 基準參數（用於對比）
benchmarks=(
  "舊參數v7|user_data/strategies/prod/NASOSv5_mod3.json|舊參數(ROI 0:6%,30:3%,60:1.5%)"
  "新參數v9|user_data/strategies/NASOSv5_mod3.json|新參數(3x hyperopt來)"
)

run_backtest() {
  local label=$1
  local params_file=$2
  local config_file=$3
  local mode=$4
  local output_file="$RESULT_DIR/${mode}_${label}.log"

  echo ""
  echo "----------------------------------------"
  echo "[$mode] $label"
  echo "Params: $params_file"
  echo "Config: $config_file"
  echo "----------------------------------------"

  if [[ ! -f "$params_file" ]]; then
    echo "WARNING: Params file not found: $params_file"
    return 1
  fi

  # 覆蓋參數檔（freqtrade 會自動讀取同名 json）
  cp "$params_file" "$ORIG_PARAMS"

  # 執行回測
  .venv/bin/python -m freqtrade backtesting \
    --config "$config_file" \
    --strategy "$STRATEGY" \
    --strategy-path "$STRATEGY_PATH" \
    --timerange "$TIMERANGE" \
    --export trades \
    --export-filename "${RESULT_DIR}/${mode}_${STRATEGY}_${label}" \
    2>&1 | tee "$output_file"

  # 提取關鍵結果
  echo ""
  echo "📊 [$mode] $label 結果摘要:"
  grep -E "Tot Profit %|Win  Draw  Loss|Trades|Drawdown|Avg profit|Best|Worst|Max % of account underwater" "$output_file" | tail -10
  echo ""
}

# ========== Spot 回測 ==========
echo ""
echo "########################################"
echo "# SPOT 回測"
echo "########################################"

SPOT_CONFIG="user_data/config/test/config_6.json"

# 基準回測
for b in "${benchmarks[@]}"; do
  IFS='|' read -r label params_file desc <<< "$b"
  run_backtest "$label" "$params_file" "$SPOT_CONFIG" "spot"
done

# 組合回測
for c in "${combos[@]}"; do
  IFS='|' read -r label params_file desc <<< "$c"
  run_backtest "$label" "$params_file" "$SPOT_CONFIG" "spot"
done

# ========== Futures 1x 回測 ==========
echo ""
echo "########################################"
echo "# FUTURES 1x 回測"
echo "########################################"

FUTURES_CONFIG="user_data/config/test/config_futures_1x.json"

# 基準回測
for b in "${benchmarks[@]}"; do
  IFS='|' read -r label params_file desc <<< "$b"
  run_backtest "$label" "$params_file" "$FUTURES_CONFIG" "futures1x"
done

# 組合回測
for c in "${combos[@]}"; do
  IFS='|' read -r label params_file desc <<< "$c"
  run_backtest "$label" "$params_file" "$FUTURES_CONFIG" "futures1x"
done

# 恢復原始參數檔
if [[ -f "$BACKUP_PARAMS" ]]; then
  cp "$BACKUP_PARAMS" "$ORIG_PARAMS"
  rm -f "$BACKUP_PARAMS"
fi

# ========== 結果彙總 ==========
echo ""
echo "========================================"
echo "所有回測完成！"
echo "========================================"
echo ""
echo "📁 結果目錄: $RESULT_DIR"
echo ""

# 提取所有結果做比較
echo "📊 Spot 結果彙總:"
for f in ${RESULT_DIR}/spot_*.log; do
  if [[ -f "$f" ]]; then
    name=$(basename "$f" .log)
    profit=$(grep "Tot Profit %" "$f" | tail -1 | awk '{print $NF}')
    trades=$(grep "Trades" "$f" | head -1 | awk '{print $2}')
    win=$(grep "Win  Draw  Loss" "$f" | tail -1 | awk '{print $2}')
    drawdown=$(grep "Max % of account underwater" "$f" | tail -1 | awk '{print $NF}')
    printf "  %-20s | Profit: %8s | Trades: %4s | Win%%: %6s | DD%%: %8s\n" "$name" "$profit" "$trades" "$win" "$drawdown"
  fi
done

echo ""
echo "📊 Futures 1x 結果彙總:"
for f in ${RESULT_DIR}/futures1x_*.log; do
  if [[ -f "$f" ]]; then
    name=$(basename "$f" .log)
    profit=$(grep "Tot Profit %" "$f" | tail -1 | awk '{print $NF}')
    trades=$(grep "Trades" "$f" | head -1 | awk '{print $2}')
    win=$(grep "Win  Draw  Loss" "$f" | tail -1 | awk '{print $2}')
    drawdown=$(grep "Max % of account underwater" "$f" | tail -1 | awk '{print $NF}')
    printf "  %-20s | Profit: %8s | Trades: %4s | Win%%: %6s | DD%%: %8s\n" "$name" "$profit" "$trades" "$win" "$drawdown"
  fi
done

echo ""
echo "詳細結果請查看: $RESULT_DIR"
