#!/bin/bash
# ==============================================
# 所有策略 Hyperopt 腳本
# ==============================================

cd /home/brian/freqtrade

CONFIG="user_data/config/test/config_futures_2x.json"
STRATEGY_PATH="user_data/strategies/test/prod"
TIMERANGE="20240101-20260526"
DATADIR="user_data/data/bybit"
EPOCHS=100

STRATEGIES=("ElliotV5_SMA_ninja" "NASOSv4" "NASOSv5_mod3" "BB_RPB_TSL_BI" "SMAOffsetProtectOptV1" "PSV5_Hybrid")

echo "========================================"
echo "🚀 Hyperopt All Strategies"
echo "Timerange: $TIMERANGE"
echo "Epochs: $EPOCHS"
echo "========================================"

for strategy in "${STRATEGIES[@]}"; do
  echo ""
  echo "========================================"
  echo "🚀 Hyperopt: $strategy"
  echo "========================================"

  python3 -m freqtrade hyperopt \
    --config "$CONFIG" \
    --strategy "$strategy" \
    --strategy-path "$STRATEGY_PATH" \
    --hyperopt-loss SharpeHyperOptLossDaily \
    --timerange "$TIMERANGE" \
    --datadir "$DATADIR" \
    --spaces buy sell trailing stoploss \
    --epochs "$EPOCHS" \
    2>&1 | tail -40

  echo ""
  echo "✅ $strategy Hyperopt completed"
  echo "========================================"
done

echo ""
echo "========================================"
echo "🎉 All Hyperopt completed!"
echo "========================================"
