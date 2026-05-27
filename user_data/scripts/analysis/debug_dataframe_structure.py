#!/usr/bin/env python3
"""
Debug script to understand the DataFrame structure mismatch in FreqAI
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging

# Set up paths
script_dir = Path(__file__).parent
freqtrade_root = script_dir
sys.path.insert(0, str(freqtrade_root))

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_dataframe_structure():
    """Test what HybridEnsembleClassifier returns vs what data_kitchen expects"""

    # 1. Simulate HybridEnsembleClassifier prediction output
    logger.info("🔍 Testing HybridEnsembleClassifier output structure...")

    # This is what HybridEnsembleClassifier.predict() returns
    target_names = ["momentum", "trend", "volatility"]
    n_samples = 100

    # Create prediction data (same as in HybridEnsembleClassifier)
    predictions = np.zeros((n_samples, 3), dtype=int)
    predictions[:, 0] = np.random.choice([-2, -1, 0, 1, 2], n_samples)  # momentum: -2 to 2
    predictions[:, 1] = np.random.choice([-1, 0, 1], n_samples)  # trend: -1 to 1
    predictions[:, 2] = np.random.choice([0, 1], n_samples)  # volatility: 0 or 1

    confidence_scores = np.random.uniform(0.1, 0.9, (n_samples, 3))

    # Create pred_df as HybridEnsembleClassifier does
    pred_columns = [f"&_{name}_prediction" for name in target_names]
    pred_df = pd.DataFrame(predictions, columns=pred_columns)

    # Add confidence scores
    for i, target_name in enumerate(target_names):
        pred_df[f"{target_name}_confidence"] = confidence_scores[:, i]

    logger.info(f"✅ HybridEnsembleClassifier pred_df structure:")
    logger.info(f"   Columns: {list(pred_df.columns)}")
    logger.info(f"   Shape: {pred_df.shape}")
    logger.info(f"   Data types: {pred_df.dtypes.to_dict()}")

    # Empty do_predict (as returned by HybridEnsembleClassifier)
    do_predict = pd.DataFrame()
    logger.info(f"✅ do_predict structure: {do_predict.shape}, columns: {list(do_predict.columns)}")

    # 2. Simulate data_kitchen.get_predictions_to_append() processing
    logger.info("\n🔍 Testing data_kitchen.get_predictions_to_append() processing...")

    # This simulates what data_kitchen does
    append_df = pd.DataFrame()

    # Process each column from predictions DataFrame
    for label in pred_df.columns:
        append_df[label] = pred_df[label]
        if append_df[label].dtype == object:
            continue
        # Note: labels_mean and labels_std would be added here if they exist

    logger.info(f"✅ After processing pred_df columns:")
    logger.info(f"   append_df shape: {append_df.shape}")
    logger.info(f"   append_df columns: {list(append_df.columns)}")

    # Process extra_returns_per_train (would be empty dict normally)
    extra_returns_per_train = {}  # Simulate empty extra returns
    for extra_col in extra_returns_per_train:
        append_df[f"{extra_col}"] = extra_returns_per_train[extra_col]

    logger.info(f"✅ After processing extra_returns_per_train:")
    logger.info(f"   append_df shape: {append_df.shape}")
    logger.info(f"   append_df columns: {list(append_df.columns)}")

    # Now the critical line that fails
    try:
        # Simulate do_predict array
        do_predict_array = np.ones(n_samples, dtype=bool)
        append_df["do_predict"] = do_predict_array
        logger.info(f"✅ Successfully added do_predict column")
        logger.info(f"   Final append_df shape: {append_df.shape}")
        logger.info(f"   Final append_df columns: {list(append_df.columns)}")
    except Exception as e:
        logger.error(f"❌ FAILED to add do_predict: {e}")
        logger.error(
            f"   append_df state: shape={append_df.shape}, columns={list(append_df.columns)}"
        )

    # 3. Test what happens when append_df is empty
    logger.info("\n🔍 Testing empty DataFrame scenario...")
    empty_df = pd.DataFrame()
    try:
        do_predict_array = np.ones(n_samples, dtype=bool)
        empty_df["do_predict"] = do_predict_array
        logger.info(f"✅ Successfully added do_predict to empty DataFrame")
        logger.info(f"   Result: shape={empty_df.shape}, columns={list(empty_df.columns)}")
    except Exception as e:
        logger.error(f"❌ FAILED to add do_predict to empty DataFrame: {e}")

    # 4. Check if the issue is with column filtering
    logger.info("\n🔍 Testing column filtering logic...")

    # Simulate a case where all columns are filtered out
    test_df = pd.DataFrame()
    test_df["object_column"] = ["a", "b", "c"]  # object dtype

    filtered_df = pd.DataFrame()
    for col in test_df.columns:
        if test_df[col].dtype == object:
            logger.info(f"   Skipping object column: {col}")
            continue
        filtered_df[col] = test_df[col]

    logger.info(f"✅ After filtering object columns:")
    logger.info(f"   filtered_df shape: {filtered_df.shape}")
    logger.info(f"   filtered_df columns: {list(filtered_df.columns)}")

    try:
        do_predict_array = np.ones(3, dtype=bool)
        filtered_df["do_predict"] = do_predict_array
        logger.info(f"✅ Successfully added do_predict after filtering")
    except Exception as e:
        logger.error(f"❌ FAILED to add do_predict after filtering: {e}")


if __name__ == "__main__":
    test_dataframe_structure()
