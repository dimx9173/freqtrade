#!/bin/zsh

# Quick Test for Strategy Fix - 只測試5個epochs

echo "🔧 Quick test for strategy fix"
echo "Testing: EnsembleStrategyPhase5 with fixed thresholds"
echo "Epochs: 50 (just for testing)"
echo "Timerange: 20240601-20240615 (31 days)"

# 運行快速測試
freqtrade hyperopt \
  --config user_data/config/config_ensemble_phase5_ultrafast.json \
  --strategy EnsembleStrategyPhase5 \
  --freqaimodel HybridEnsembleRegressor \
  --epochs 50 \
  --spaces buy sell \
  --hyperopt-loss SortinoHyperOptLossDaily \
  --timerange 20240601-20240615 \
  --job-workers 8 \
  --min-trades 1 \
  --verbose

echo "🔍 Quick test finished - Check for trades!"
