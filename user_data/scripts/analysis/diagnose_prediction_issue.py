#!/usr/bin/env python3
"""
Diagnostic Script for HybridEnsembleClassifier Zero Prediction Issue

This script will:
1. Load a trained HybridEnsembleClassifier model
2. Examine the trained models and their capabilities
3. Run predictions on sample data
4. Trace the prediction pipeline step by step
5. Identify where the zero predictions are coming from
"""

import sys
import os
import numpy as np
import pandas as pd
import logging
from pathlib import Path

# Add freqtrade to Python path
sys.path.append("/Users/carlos/pCloud Drive/CryptoWork/freqtrade")

# Import required modules
from user_data.freqaimodels.HybridEnsembleClassifier import HybridEnsembleClassifier
from freqtrade.freqai.data_kitchen import FreqaiDataKitchen

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mock_data_kitchen():
    """Create a mock data kitchen for testing"""

    class MockDataKitchen:
        def __init__(self):
            self.data = {"labels_mean": {}, "labels_std": {}}
            self.label_list = ["&_momentum", "&_trend", "&_volatility"]
            self.training_features_list = [f"feature_{i}" for i in range(20)]

    return MockDataKitchen()


def create_sample_training_data(n_samples=1000):
    """Create sample training data that mimics the real data structure"""
    np.random.seed(42)

    # Features
    X = np.random.randn(n_samples, 20)
    X_df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(20)])

    # Labels - create realistic class distributions
    # Momentum: -2,-1,0,1,2 with center bias
    momentum = np.random.choice([-2, -1, 0, 1, 2], size=n_samples, p=[0.1, 0.2, 0.4, 0.2, 0.1])
    # Trend: -1,0,1 with center bias
    trend = np.random.choice([-1, 0, 1], size=n_samples, p=[0.3, 0.4, 0.3])
    # Volatility: 0,1 balanced
    volatility = np.random.choice([0, 1], size=n_samples, p=[0.4, 0.6])

    y = np.column_stack([momentum, trend, volatility])
    y_df = pd.DataFrame(y, columns=["&_momentum", "&_trend", "&_volatility"])

    logger.info(f"Created sample training data:")
    logger.info(f"  X shape: {X.shape}")
    logger.info(f"  y shape: {y.shape}")
    logger.info(f"  Momentum distribution: {np.bincount(momentum + 2)}")  # Shift for bincount
    logger.info(f"  Trend distribution: {np.bincount(trend + 1)}")  # Shift for bincount
    logger.info(f"  Volatility distribution: {np.bincount(volatility)}")

    return X_df, y_df


def diagnose_individual_model_predictions(model, X_test, target_name, model_name):
    """Diagnose predictions from individual models"""
    logger.info(f"\n=== Diagnosing {model_name} for {target_name} ===")

    try:
        # Get raw predictions
        raw_preds = model.predict(X_test)
        raw_proba = model.predict_proba(X_test)

        logger.info(f"Raw predictions shape: {raw_preds.shape}")
        logger.info(f"Raw predictions unique values: {np.unique(raw_preds)}")
        logger.info(f"Raw predictions distribution: {np.bincount(raw_preds.astype(int))}")

        logger.info(f"Raw probabilities shape: {raw_proba.shape}")
        logger.info(f"Raw probabilities sample (first 5): {raw_proba[:5]}")

        return raw_preds, raw_proba

    except Exception as e:
        logger.error(f"Error in {model_name} prediction: {e}")
        return None, None


def diagnose_prediction_pipeline():
    """Main diagnostic function"""
    logger.info("Starting HybridEnsembleClassifier Prediction Diagnostic")

    # Create sample data
    X_train, y_train = create_sample_training_data(1000)
    X_test, y_test = create_sample_training_data(100)

    # Create data dictionary for training
    data_dict = {"train_features": X_train, "train_labels": y_train}

    # Create mock data kitchen
    dk = create_mock_data_kitchen()

    # Initialize and configure the model
    try:
        logger.info("\n=== Initializing HybridEnsembleClassifier ===")
        model = HybridEnsembleClassifier(
            freqai_info={
                "model_training_parameters": {
                    "lightgbm": {"n_estimators": 100, "max_depth": 3, "learning_rate": 0.1},
                    "xgboost": {"n_estimators": 100, "max_depth": 3, "learning_rate": 0.1},
                    "deep_learning": {"sequence_length": 10, "batch_size": 32, "epochs": 10},
                }
            }
        )

        logger.info("✅ Model initialized successfully")

    except Exception as e:
        logger.error(f"❌ Error initializing model: {e}")
        return

    # Train the model
    try:
        logger.info("\n=== Training Model ===")
        model.fit(data_dict, dk)
        logger.info("✅ Model training completed")

    except Exception as e:
        logger.error(f"❌ Error during training: {e}")
        import traceback

        traceback.print_exc()
        return

    # Examine trained models
    logger.info(f"\n=== Examining Trained Models ===")
    logger.info(f"Available models: {list(model.models.keys())}")

    # Test individual model predictions
    for model_type, models_list in model.models.items():
        logger.info(f"\n--- Testing {model_type} models ---")
        if isinstance(models_list, list):
            for i, individual_model in enumerate(models_list):
                target_name = (
                    model.target_names[i] if i < len(model.target_names) else f"target_{i}"
                )
                diagnose_individual_model_predictions(
                    individual_model, X_test.values, target_name, f"{model_type}_{i}"
                )
        else:
            logger.info(f"{model_type} model: {type(models_list)}")

    # Test full ensemble prediction
    try:
        logger.info(f"\n=== Testing Full Ensemble Prediction ===")

        # Create test dataframe with required columns
        test_df = X_test.copy()

        # Run prediction
        pred_df, do_pred_df = model.predict(test_df, dk)

        logger.info(f"Prediction DataFrame shape: {pred_df.shape}")
        logger.info(f"Prediction DataFrame columns: {list(pred_df.columns)}")

        # Analyze each prediction column
        for col in pred_df.columns:
            if col.endswith("_prediction"):
                values = pred_df[col].values
                logger.info(f"{col}:")
                logger.info(f"  Unique values: {np.unique(values)}")
                logger.info(f"  Value range: [{values.min()}, {values.max()}]")
                logger.info(
                    f"  Distribution: {np.bincount(values - values.min()) if len(np.unique(values)) > 1 else [len(values)]}"
                )
                logger.info(f"  Sample values (first 10): {values[:10]}")

        logger.info("✅ Ensemble prediction completed")

    except Exception as e:
        logger.error(f"❌ Error during prediction: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    diagnose_prediction_pipeline()
