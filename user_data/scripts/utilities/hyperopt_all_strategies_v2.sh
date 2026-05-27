#!/bin/bash
# ==============================================
# 所有策略 Hyperopt 腳本 v2 - 減少記憶體使用
# ==============================================

cd /home/brian/freqtrade

CONFIG="user_data/config/test/config_futures_2x.json"
STRATEGY_PATH="user_data/strategies/test/prod"
TIMERANGE="20250824-20260524"
DATADIR="user_data/data/bybit"
EPOCHS=50

STRATEGIES=("ElliotV5_SMA_ninja" "NASOSv4" "NASOSv5_mod3" "BB_RPB_TSL_BI" "SMAOffsetProtectOptV1" "PSV5_Hybrid")

echo "========================================"
echo "🚀 Hyperopt All Strategies (v2)"
echo "Timerange: $TIMERANGE"
echo "Epochs: $EPOCHS"
echo "========================================"

for strategy in "${STRATEGIES[@]}"; do
  echo ""
  echo "========================================"
  echo "🚀 Hyperopt: $strategy"
  echo "========================================"
  
  # 使用單一 worker 減少記憶體
  python3 -m freqtrade hyperopt \
    --config "$CONFIG" \
    --strategy "$strategy" \
    --strategy-path "$STRATEGY_PATH" \
    --hyperopt-loss SharpeHyperOptLossDaily \
    --timerange "$TIMERANGE" \
    --datadir "$DATADIR" \
    --spaces buy sell \
    --epochs "$EPOCHS" \
    -j 1 \
    2>&1 | tail -30
  
  echo ""
  echo "✅ $strategy Hyperopt completed"
  echo "========================================"
done

echo ""
echo "========================================"
echo "🎉 All Hyperopt completed!"
echo "========================================"
