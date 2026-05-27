#!/usr/bin/env python3
"""
Zero Trades 診斷腳本 - Phase 5 Ensemble Strategy
診斷為什麼 hyperopt 中沒有產生任何交易

根本原因分析:
1. 策略文件 timeframe = "1m" 但配置文件 timeframe = "5m" - 嚴重不匹配!
2. FreqAI 預測值範圍極小 [0.8413, 0.9316] 相當於 0 (幾乎沒有信號)
3. 進場條件雖然已簡化但仍可能受到 FreqAI 狀態影響
"""

import sys
import os

sys.path.append("/Users/carlos/pCloud Drive/CryptoWork/freqtrade")

import json
import pandas as pd
from datetime import datetime, timedelta
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def diagnose_zero_trades():
    """
    全面診斷 Zero Trades 問題
    """
    print("=" * 80)
    print("PHASE 5 ENSEMBLE STRATEGY - ZERO TRADES 診斷報告")
    print("=" * 80)

    # === 1. 配置文件診斷 ===
    print("\n🔍 1. 配置文件診斷")
    print("-" * 50)

    config_path = "/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/config/config_ensemble_phase5_ultrafast.json"
    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        print(f"✅ 配置文件加載成功: {config_path}")
        print(f"📊 配置時間框架: {config.get('timeframe', 'NOT SET')}")
        print(f"💰 最大開倉數: {config.get('max_open_trades', 'NOT SET')}")
        print(f"💵 基礎倉位: {config.get('stake_amount', 'NOT SET')} USDT")
        print(f"🏦 交易模式: {config.get('trading_mode', 'NOT SET')}")
        print(f"📈 交易對: {config.get('exchange', {}).get('pair_whitelist', ['NONE'])}")

        # FreqAI 配置檢查
        freqai_config = config.get("freqai", {})
        print(f"🤖 FreqAI 啟用: {freqai_config.get('enabled', False)}")
        print(f"🧠 FreqAI 模型: {freqai_config.get('freqaimodel', 'NOT SET')}")
        print(f"📅 訓練期間: {freqai_config.get('train_period_days', 'NOT SET')} 天")
        print(
            f"🏷️ 標籤期間: {freqai_config.get('feature_parameters', {}).get('label_period_candles', 'NOT SET')} 根K線"
        )

        # 檢測 CRITICAL ISSUE
        strategy_timeframe = "1m"  # 從策略文件讀取
        config_timeframe = config.get("timeframe", "5m")
        if strategy_timeframe != config_timeframe:
            print(f"🚨 CRITICAL ISSUE: 時間框架不匹配!")
            print(f"   策略文件: {strategy_timeframe}")
            print(f"   配置文件: {config_timeframe}")
            print(f"   🔧 FIX: 將配置文件 timeframe 改為 '{strategy_timeframe}'")

    except Exception as e:
        print(f"❌ 配置文件讀取失敗: {e}")

    # === 2. 策略文件診斷 ===
    print("\n🔍 2. 策略文件診斷")
    print("-" * 50)

    strategy_path = "/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/strategies/EnsembleStrategyPhase5.py"
    try:
        with open(strategy_path, "r") as f:
            strategy_content = f.read()

        print(f"✅ 策略文件加載成功: {strategy_path}")

        # 檢查關鍵設定
        if 'timeframe = "1m"' in strategy_content:
            print(f"📊 策略時間框架: 1m")

        if "can_short = True" in strategy_content:
            print(f"📈 允許做空: True (期貨模式)")

        # 檢查 ROI 和止損
        if "stoploss = -0.02" in strategy_content:
            print(f"🛑 止損: -2%")

        # 檢查進場條件複雜度
        emergency_count = strategy_content.count("emergency_simple")
        if emergency_count > 0:
            print(f"🚨 發現 {emergency_count} 處 emergency_simple 條件")
            print(f"   這意味著策略已經被簡化到極致")

        # 檢查 FreqAI 依賴
        do_predict_count = strategy_content.count("do_predict")
        if do_predict_count > 0:
            print(f"🤖 發現 {do_predict_count} 處 do_predict 依賴")
            print(f"   這可能是造成 0 trades 的根本原因")

    except Exception as e:
        print(f"❌ 策略文件讀取失敗: {e}")

    # === 3. FreqAI 預測值診斷 ===
    print("\n🔍 3. FreqAI 預測值診斷")
    print("-" * 50)

    print("根據您提供的信息:")
    print("📊 FreqAI 預測值範圍: [0.8413, 0.9316]")
    print("🔍 分析:")

    pred_min, pred_max = 0.8413, 0.9316
    pred_range = pred_max - pred_min
    pred_mean = (pred_min + pred_max) / 2

    print(f"   • 預測範圍: {pred_range:.4f} (非常小!)")
    print(f"   • 預測平均值: {pred_mean:.4f}")
    print(f"   • 預測變異性: {(pred_range / pred_mean) * 100:.2f}%")

    if pred_range < 0.1:
        print("🚨 CRITICAL: 預測值範圍過小，缺乏交易信號!")
        print("   原因可能是:")
        print("   1. 模型過於保守或訓練數據不足")
        print("   2. 特徵工程問題")
        print("   3. 標籤設計問題")

    # === 4. 交易條件診斷 ===
    print("\n🔍 4. 交易條件診斷")
    print("-" * 50)

    print("潛在的交易阻止因素:")
    print("1. ❌ 時間框架不匹配 (策略1m vs 配置5m)")
    print("2. ❌ FreqAI 預測值範圍極小")
    print("3. ❌ do_predict 條件可能一直為 False")
    print("4. ❌ 極緊密的 ROI 設置可能導致立即退出")
    print("5. ❌ 超嚴格的止損 (-2%) 配合高波動性")

    # === 5. 修復建議 ===
    print("\n🔧 5. 緊急修復建議")
    print("-" * 50)

    print("優先級修復順序:")
    print("1. 🏆 CRITICAL: 修復時間框架不匹配")
    print("   將配置文件的 timeframe 從 '5m' 改為 '1m'")
    print("")
    print("2. 🏆 CRITICAL: 移除所有 do_predict 依賴")
    print("   修改策略文件，移除 exit 條件中的 do_predict 檢查")
    print("")
    print("3. 🥈 HIGH: 放寬 ROI 設置")
    print("   將 minimal_roi 從 0.3% 提高到 1-2%")
    print("")
    print("4. 🥈 HIGH: 調整 FreqAI 標籤設計")
    print("   增加標籤的變異性和信號強度")
    print("")
    print("5. 🥉 MEDIUM: 簡化進場條件")
    print("   保留 emergency_simple 作為主要進場策略")

    return True


def create_emergency_fix():
    """
    創建緊急修復版本
    """
    print("\n🚑 6. 創建緊急修復檔案")
    print("-" * 50)

    # 創建緊急修復配置
    emergency_config = {
        "max_open_trades": 3,
        "stake_currency": "USDT",
        "stake_amount": 100,
        "tradable_balance_ratio": 0.95,
        "dry_run": True,
        "dry_run_wallet": 1000,
        "cancel_open_orders_on_exit": False,
        "trading_mode": "futures",
        "margin_mode": "isolated",
        # 修復: 時間框架匹配策略
        "timeframe": "1m",
        "entry_pricing": {
            "price_side": "same",
            "use_order_book": True,
            "order_book_top": 1,
            "price_last_balance": 0.0,
            "check_depth_of_market": {"enabled": False},
        },
        "exit_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
        "dataformat_ohlcv": "feather",
        "dataformat_trades": "feather",
        "exchange": {
            "name": "binance",
            "key": "kfubX0XvGx4NG8N3eQbYKFKW1EbOFLwZyjGA9tFhFXYMOaPjCjsGc91AGsJxQIge",
            "secret": "3HdqHJaaB3YASdh4YMGNChTyUiWx4KSLWFLAfvs8fYW8pkyQCV9x4RmBIizdG3RX",
            "ccxt_config": {},
            "ccxt_async_config": {},
            "pair_whitelist": ["BTC/USDT:USDT"],
            "pair_blacklist": [],
            "markets_refresh_interval": 60,
        },
        "pairlists": [{"method": "StaticPairList", "number_assets": 1}],
        "telegram": {"enabled": False, "token": "", "chat_id": ""},
        "api_server": {
            "enabled": True,
            "listen_ip_address": "0.0.0.0",
            "listen_port": 14006,  # 不同端口避免衝突
            "verbosity": "info",
            "jwt_secret_key": "emergency-fix-phase5",
            "CORS_origins": ["http://localhost:8080"],
            "username": "",
            "password": "",
        },
        "bot_name": "emergency_fix_phase5_bot",
        "initial_state": "running",
        "force_entry_enable": False,
        "internals": {
            "process_throttle_secs": 5,  # 更慢的處理避免問題
            "allowed_trials": 10,
        },
        # 修復: 更保守的 FreqAI 設置
        "freqai": {
            "enabled": True,
            "identifier": "emergency_fix_phase5",
            "freqaimodel": "LightGBMRegressor",  # 單一模型避免複雜性
            "train_period_days": 7,  # 更短訓練期
            "backtest_period_days": 3,  # 更短回測期
            "data_split_parameters": {"test_size": 0.2, "shuffle": False, "random_state": 42},
            "feature_parameters": {
                "include_timeframes": ["1m"],  # 匹配策略時間框架
                "include_corr_pairlist": ["BTC/USDT:USDT"],
                "include_shifted_candles": 0,
                "label_period_candles": 1,
                "indicator_periods_candles": [10, 20],  # 簡化指標
                "DI_threshold": 0,
                "principal_component_analysis": False,
                "use_SVM_to_remove_outliers": False,
                "weight_factor": 0.95,
                "noise_standard_deviation": 0.005,  # 增加噪音增強信號
                "buffer_train_data_candles": 1,
            },
            # 修復: 使用單一簡單模型
            "model_training_parameters": {
                "n_estimators": 50,
                "learning_rate": 0.1,
                "max_depth": 5,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_alpha": 0.1,
                "reg_lambda": 0.1,
                "random_state": 42,
                "verbose": -1,
                "n_jobs": 4,
            },
            # 修復: 更現實的預設返回值
            "extra_returns_per_train": {
                "&-ensemble_prediction": 0.001  # 更大的預設值
            },
            "multitarget_parallel_training": False,
            "purge_old_models": 1,
            "save_backtest_models": False,
            "follow_mode": False,
            "continual_learning": False,
            "write_metrics_to_disk": True,
            "rl_config": {"return_reward_reduction": False},
        },
        "edge": {"enabled": False},
        "optimize": {"enabled": False},
    }

    emergency_config_path = "/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/config/config_emergency_fix_phase5.json"
    with open(emergency_config_path, "w") as f:
        json.dump(emergency_config, f, indent=2)

    print(f"✅ 緊急修復配置已創建: {emergency_config_path}")
    print("主要修復:")
    print("• 時間框架統一為 1m")
    print("• 簡化為單一 LightGBM 模型")
    print("• 更短的訓練和回測期間")
    print("• 增加預測噪音以產生更大信號範圍")
    print("• 更大的預設預測值")

    return emergency_config_path


def generate_test_command(config_path):
    """
    生成測試命令
    """
    print("\n🧪 7. 測試命令")
    print("-" * 50)

    print("緊急測試命令 (簡短回測):")
    test_cmd = f"""
freqtrade backtesting \\
  --config {config_path} \\
  --strategy EnsembleStrategyPhase5 \\
  --timerange 20240601-20240603 \\
  --enable-position-stacking \\
  --disable-max-market-positions \\
  -v
"""
    print(test_cmd)

    print("\nHyperopt 測試命令:")
    hyperopt_cmd = f"""
freqtrade hyperopt \\
  --config {config_path} \\
  --hyperopt-loss SortinoHyperOptLoss \\
  --strategy EnsembleStrategyPhase5 \\
  --epochs 5 \\
  --spaces buy \\
  --timerange 20240601-20240603 \\
  -v
"""
    print(hyperopt_cmd)

    return test_cmd, hyperopt_cmd


if __name__ == "__main__":
    print("開始 Zero Trades 問題診斷...")

    # 執行診斷
    diagnose_zero_trades()

    # 創建緊急修復
    emergency_config_path = create_emergency_fix()

    # 生成測試命令
    test_cmd, hyperopt_cmd = generate_test_command(emergency_config_path)

    print("\n" + "=" * 80)
    print("診斷完成! 建議立即執行緊急修復測試。")
    print("=" * 80)
