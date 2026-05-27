#!/bin/zsh

# Phase 5 Ensemble Ultra-Fast Hyperopt Script
# 極速訓練版本 - 最大程度縮短訓練時間

echo "🚀 Starting ULTRA-FAST hyperopt for strategy: EnsembleStrategyPhase5"
echo "Using config: user_data/config/config_ensemble_phase5_ultrafast.json"
echo "Using FreqAI model: HybridEnsembleRegressor"
echo "Epochs: 20"
echo "Spaces: buy sell"
echo "Timerange: 20240515-20240615 (31 days)"
echo "CPU Cores: 12"
echo ""

# 運行 ultra-fast hyperopt
freqtrade hyperopt \
  --config user_data/config/config_ensemble_phase5_ultrafast.json \
  --strategy EnsembleStrategyPhase5 \
  --freqaimodel HybridEnsembleRegressor \
  --epochs 20 \
  --spaces buy sell \
  --hyperopt-loss SortinoHyperOptLossDaily \
  --timerange 20240515-20240615 \
  --job-workers 12 \
  --min-trades 1 \
  --verbose

echo "🎉 Ultra-fast hyperopt finished."
