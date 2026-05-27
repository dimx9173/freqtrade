#!/usr/bin/env python3
"""
診斷FreqAI三目標投票系統 - 零交易問題分析
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import sys
import os

# 添加freqtrade路徑
sys.path.append("/Users/carlos/pCloud Drive/CryptoWork/freqtrade")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_freqai_predictions():
    """分析FreqAI預測結果"""

    logger.info("🔍 開始診斷FreqAI三目標投票系統...")

    # 檢查模型文件
    models_path = "/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/models"
    if not os.path.exists(models_path):
        logger.error("❌ 模型目錄不存在")
        return

    # 列出所有模型文件
    model_dirs = [d for d in os.listdir(models_path) if os.path.isdir(os.path.join(models_path, d))]
    logger.info(f"📁 發現 {len(model_dirs)} 個模型目錄")

    for model_dir in model_dirs[:3]:  # 檢查前3個
        logger.info(f"   - {model_dir}")

    # 檢查最近的預測文件
    latest_model_dir = None
    latest_time = 0

    for model_dir in model_dirs:
        model_path = os.path.join(models_path, model_dir)
        try:
            # 檢查目錄修改時間
            dir_time = os.path.getmtime(model_path)
            if dir_time > latest_time:
                latest_time = dir_time
                latest_model_dir = model_dir
        except:
            continue

    if latest_model_dir:
        logger.info(f"🕐 最新模型目錄: {latest_model_dir}")
        model_path = os.path.join(models_path, latest_model_dir)

        # 檢查預測文件
        predictions_file = None
        for file in os.listdir(model_path):
            if "predictions" in file.lower() and file.endswith(".pkl"):
                predictions_file = os.path.join(model_path, file)
                break

        if predictions_file and os.path.exists(predictions_file):
            logger.info(f"📊 預測文件: {predictions_file}")
            try:
                # 嘗試加載預測數據
                import pickle

                with open(predictions_file, "rb") as f:
                    predictions = pickle.load(f)

                if isinstance(predictions, pd.DataFrame):
                    logger.info(f"✅ 預測數據形狀: {predictions.shape}")
                    logger.info(f"✅ 預測列名: {list(predictions.columns)}")

                    # 檢查三目標預測
                    target_cols = [
                        col
                        for col in predictions.columns
                        if any(target in col for target in ["momentum", "trend", "volatility"])
                    ]
                    logger.info(f"🎯 目標預測列: {target_cols}")

                    if target_cols:
                        for col in target_cols:
                            if col in predictions.columns:
                                values = predictions[col].value_counts().to_dict()
                                logger.info(f"   {col}: {values}")

                    # 檢查信心度
                    confidence_cols = [col for col in predictions.columns if "confidence" in col]
                    logger.info(f"🔍 信心度列: {confidence_cols}")

                    if confidence_cols:
                        for col in confidence_cols:
                            if col in predictions.columns:
                                mean_conf = predictions[col].mean()
                                std_conf = predictions[col].std()
                                logger.info(f"   {col}: mean={mean_conf:.3f}, std={std_conf:.3f}")
                else:
                    logger.info(f"⚠️ 預測數據類型: {type(predictions)}")

            except Exception as e:
                logger.error(f"❌ 讀取預測文件失敗: {e}")
        else:
            logger.warning("⚠️ 未找到預測文件")

    # 模擬簡單的投票邏輯測試
    logger.info("\n🧪 模擬投票邏輯測試...")

    # 創建測試數據
    test_data = pd.DataFrame(
        {
            "&_momentum_prediction": [2, 1, 0, -1, -2] * 10,  # 5級分類
            "&_trend_prediction": [1, 0, -1, 1, 0] * 10,  # 3級分類
            "&_volatility_prediction": [1, 1, 0, 1, 0] * 10,  # 2級分類
            "momentum_confidence": [0.8, 0.6, 0.5, 0.7, 0.9] * 10,
            "trend_confidence": [0.7, 0.8, 0.4, 0.6, 0.8] * 10,
            "volatility_confidence": [0.9, 0.7, 0.6, 0.8, 0.7] * 10,
        }
    )

    logger.info(f"📊 測試數據形狀: {test_data.shape}")

    # 測試完美信號條件
    perfect_long_signal = (
        (test_data["&_momentum_prediction"] == 2)  # strong_up
        & (test_data["&_trend_prediction"] == 1)  # up
        & (test_data["&_volatility_prediction"] == 1)  # low_risk
    )

    perfect_count = perfect_long_signal.sum()
    logger.info(f"🎯 完美做多信號數量: {perfect_count}")

    # 測試優秀信號條件
    excellent_long_signal = (
        (test_data["&_momentum_prediction"] >= 1)  # weak_up 或 strong_up
        & (test_data["&_trend_prediction"] == 1)  # up
        & (test_data["&_volatility_prediction"] == 1)  # low_risk
    )

    excellent_count = excellent_long_signal.sum()
    logger.info(f"⭐ 優秀做多信號數量: {excellent_count}")

    # 測試良好信號條件
    good_long_signal = (
        (test_data["&_momentum_prediction"] >= 1)  # weak_up 或 strong_up
        & (test_data["&_trend_prediction"] >= 0)  # side 或 up
        & (test_data["&_volatility_prediction"] == 1)  # low_risk
    )

    good_count = good_long_signal.sum()
    logger.info(f"👍 良好做多信號數量: {good_count}")

    # 測試可接受信號條件
    acceptable_long_signal = (
        (test_data["&_momentum_prediction"] >= 0)  # 至少不負向
        & (test_data["&_trend_prediction"] >= 0)  # 至少不下跌
        & (test_data["&_volatility_prediction"] == 1)  # low_risk
    )

    acceptable_count = acceptable_long_signal.sum()
    logger.info(f"✅ 可接受做多信號數量: {acceptable_count}")

    # 信心度測試
    base_confidence_check = (
        (test_data["momentum_confidence"] >= 0.5)
        & (test_data["trend_confidence"] >= 0.5)
        & (test_data["volatility_confidence"] >= 0.5)
    )

    confidence_count = base_confidence_check.sum()
    logger.info(f"🔍 通過信心度檢查數量: {confidence_count}")

    # 綜合測試
    final_signals = perfect_long_signal & base_confidence_check
    final_count = final_signals.sum()
    logger.info(f"🎯 最終完美信號數量: {final_count}")

    logger.info("\n📋 診斷總結:")
    logger.info(f"   - 測試數據中有 {perfect_count} 個完美信號")
    logger.info(f"   - 測試數據中有 {excellent_count} 個優秀信號")
    logger.info(f"   - 測試數據中有 {good_count} 個良好信號")
    logger.info(f"   - 測試數據中有 {acceptable_count} 個可接受信號")
    logger.info(f"   - 通過信心度檢查: {confidence_count}")
    logger.info(f"   - 最終信號: {final_count}")

    if final_count == 0:
        logger.warning("⚠️ 可能的問題:")
        logger.warning("   1. 模型預測質量不足")
        logger.warning("   2. 投票條件過於嚴格")
        logger.warning("   3. 信心度閾值設置過高")
        logger.warning("   4. 數據不足或質量問題")


def check_data_availability():
    """檢查數據可用性"""
    logger.info("\n📊 檢查數據可用性...")

    data_path = "/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/data/binance"
    if not os.path.exists(data_path):
        logger.error("❌ 數據目錄不存在")
        return

    # 檢查BTC數據
    btc_file = os.path.join(data_path, "BTC_USDT_USDT-5m.feather")
    if os.path.exists(btc_file):
        logger.info(f"✅ BTC數據文件存在: {btc_file}")

        try:
            df = pd.read_feather(btc_file)
            logger.info(f"   數據形狀: {df.shape}")
            logger.info(f"   日期範圍: {df['date'].min()} 到 {df['date'].max()}")

            # 檢查目標時間範圍的數據
            target_start = pd.Timestamp("2025-08-10")
            target_end = pd.Timestamp("2025-08-27")

            target_data = df[(df["date"] >= target_start) & (df["date"] <= target_end)]
            logger.info(f"   目標範圍數據: {target_data.shape[0]} 行")

            if target_data.shape[0] < 100:
                logger.warning("⚠️ 目標時間範圍數據不足")

        except Exception as e:
            logger.error(f"❌ 讀取數據失敗: {e}")
    else:
        logger.error("❌ BTC數據文件不存在")


if __name__ == "__main__":
    analyze_freqai_predictions()
    check_data_availability()
    logger.info("\n🎉 診斷完成!")
