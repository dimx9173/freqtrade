#!/bin/zsh

# Phase 5 Ensemble Fast Hyperopt Script
# 快速訓練版本 - 大幅縮短訓練時間

echo "Starting FAST hyperopt for strategy: EnsembleStrategyPhase5"
echo "Using config: user_data/config/config_ensemble_phase5_fast.json"
echo "Using FreqAI model: HybridEnsembleRegressor"
echo "Epochs: 20"
echo "Spaces: buy sell"
echo "Timerange: 20240515-20240601"
echo "CPU Cores: 10"
echo ""

# 運行 hyperopt
freqtrade hyperopt \
  --config user_data/config/config_ensemble_phase5_fast.json \
  --strategy EnsembleStrategyPhase5 \
  --freqaimodel HybridEnsembleRegressor \
  --epochs 20 \
  --spaces buy sell \
  --hyperopt-loss SortinoHyperOptLossDaily \
  --timerange 20240515-20240601 \
  --job-workers 10 \
  --min-trades 1 \
  --verbose

echo "Hyperopt finished."
