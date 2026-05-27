#!/bin/bash
# Test/Prod Hyperopt 腳本
# 針對 test/prod 目錄的策略進行優化

cd /home/brian/freqtrade

STRATEGY=${1:-"SMAOffsetProtectOptV1"}
CONFIG_ID=${2:-"5"}
EPOCHS=${3:-"200"}

CONFIG_FILE="user_data/config/test/config_${CONFIG_ID}.json"
STRATEGY_PATH="user_data/strategies/test/prod"

echo "========================================"
echo "Test/Prod Hyperopt"
echo "Strategy: $STRATEGY"
echo "Config: $CONFIG_FILE"
echo "Epochs: $EPOCHS"
echo "========================================"

# 檢查檔案是否存在
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

if [[ ! -f "$STRATEGY_PATH/${STRATEGY}.py" ]]; then
    echo "ERROR: Strategy not found: $STRATEGY_PATH/${STRATEGY}.py"
    exit 1
fi

# 執行 Hyperopt
python3 -m freqtrade hyperopt \
    --config "$CONFIG_FILE" \
    --hyperopt-loss SharpeHyperOptLossDaily \
    --spaces buy sell \
    --strategy "$STRATEGY" \
    --strategy-path "$STRATEGY_PATH" \
    -e "$EPOCHS" \
    -j 6 \
    --timerange 20250824-20260524 \
    --early-stop 100 \
    --min-trades 20 \
    --random-state 42 \
    2>&1 | tee "/tmp/hyperopt_test_${STRATEGY}.log"

echo "========================================"
echo "Hyperopt completed for $STRATEGY"
echo "Log: /tmp/hyperopt_test_${STRATEGY}.log"
echo "========================================"
