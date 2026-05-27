#!/bin/bash
#
# Freqtrade hyperopt script for EnsembleStrategyPhase5
#
# Usage:
# ./hyperopt_ensemble_phase5.sh
#

# --- Configuration ---
STRATEGY="EnsembleStrategyPhase5"
CONFIG="user_data/config/config_ensemble_phase5_prod.json"
FREQAI_MODEL="HybridEnsembleRegressor"
HYPEROPT_LOSS="SortinoHyperOptLossDaily"
EPOCHS="20"
# Set a default timerange, e.g., last 6 months. Adjust if needed.
# FreqAI requires a fixed end date for hyperopt.
TIMERANGE="20240501-20240601"
# Use all available CPU cores
CPU_CORES=$(sysctl -n hw.ncpu 2>/dev/null || nproc)

# Add a fallback if CPU core detection fails
if [ -z "$CPU_CORES" ]; then
    echo "Warning: Could not automatically detect CPU cores. Falling back to 2 cores."
    CPU_CORES=2
fi

# --- Command ---
echo "Starting hyperopt for strategy: $STRATEGY"
echo "Using config: $CONFIG"
echo "Using FreqAI model: $FREQAI_MODEL"
echo "Epochs: $EPOCHS"
echo "Spaces: buy sell"
echo "Timerange: $TIMERANGE"
echo "CPU Cores: $CPU_CORES"

python3 -m freqtrade hyperopt \
    --config "$CONFIG" \
    --strategy "$STRATEGY" \
    --freqaimodel "$FREQAI_MODEL" \
    --hyperopt-loss "$HYPEROPT_LOSS" \
    --epochs "$EPOCHS" \
    --spaces buy sell \
    --timerange "$TIMERANGE" \
    --job-workers "$CPU_CORES"

echo "Hyperopt finished."
