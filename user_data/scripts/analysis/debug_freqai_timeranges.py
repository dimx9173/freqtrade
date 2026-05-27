#!/usr/bin/env python3

"""
Debug script to investigate why FreqAI training ranges are not being created properly
"""

import sys
import logging
from pathlib import Path

# Add freqtrade to path
sys.path.append("/Users/carlos/pCloud Drive/CryptoWork/freqtrade")

from freqtrade.configuration import Configuration
from freqtrade.freqai.data_kitchen import FreqaiDataKitchen

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_freqai_timeranges():
    """Test FreqAI timerange creation"""

    # Load config (same as hyperopt)
    config_path = "/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/config/config_ensemble_phase5_voting.json"

    config = Configuration.from_files([config_path])

    # Add timerange used in hyperopt
    config["timerange"] = "20240801-20240820"

    logger.info("=== FreqAI Timerange Debug ===")
    logger.info(f"Config timerange: {config.get('timerange')}")
    logger.info(f"FreqAI train_period_days: {config['freqai'].get('train_period_days')}")
    logger.info(f"FreqAI backtest_period_days: {config['freqai'].get('backtest_period_days')}")

    # Create FreqaiDataKitchen (same as in backtesting)
    live = False  # Backtesting mode
    pair = "BTC/USDT:USDT"

    try:
        dk = FreqaiDataKitchen(config, live, pair)

        logger.info(f"Live mode: {dk.live}")
        logger.info(f"Backtest live models: {dk.backtest_live_models}")

        # Check if training ranges were created
        if hasattr(dk, "training_timeranges"):
            logger.info(f"Training timeranges count: {len(dk.training_timeranges)}")
            for i, tr in enumerate(dk.training_timeranges):
                logger.info(f"  Training range {i}: {tr}")
        else:
            logger.error("No training_timeranges attribute found!")

        if hasattr(dk, "backtesting_timeranges"):
            logger.info(f"Backtesting timeranges count: {len(dk.backtesting_timeranges)}")
            for i, tr in enumerate(dk.backtesting_timeranges):
                logger.info(f"  Backtesting range {i}: {tr}")
        else:
            logger.error("No backtesting_timeranges attribute found!")

        # Check full timerange
        if hasattr(dk, "full_timerange"):
            logger.info(f"Full timerange: {dk.full_timerange}")
        else:
            logger.error("No full_timerange attribute found!")

    except Exception as e:
        logger.error(f"Error creating FreqaiDataKitchen: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_freqai_timeranges()
