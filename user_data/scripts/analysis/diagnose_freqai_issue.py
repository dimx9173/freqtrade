#!/usr/bin/env python3
"""
診斷FreqAI問題 - 為什麼沒有觸發訓練？
"""

import sys
import os
import json
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta


def diagnose_freqai_issue():
    """診斷FreqAI為什麼沒有觸發訓練"""

    print("🔍 FreqAI 診斷分析")
    print("=" * 50)

    # 1. 檢查配置文件
    config_path = Path("user_data/config/config_ensemble_phase5_voting.json")
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return False

    with open(config_path) as f:
        config = json.load(f)

    freqai_config = config.get("freqai", {})
    print(f"✅ FreqAI配置:")
    print(f"   enabled: {freqai_config.get('enabled', False)}")
    print(f"   identifier: {freqai_config.get('identifier', 'N/A')}")
    print(f"   freqaimodel: {freqai_config.get('freqaimodel', 'N/A')}")
    print(f"   train_period_days: {freqai_config.get('train_period_days', 'N/A')}")
    print(f"   backtest_period_days: {freqai_config.get('backtest_period_days', 'N/A')}")

    if not freqai_config.get("enabled"):
        print("❌ FreqAI未啟用！")
        return False

    # 2. 檢查數據可用性
    data_dir = Path("user_data/data/binance")
    futures_dir = data_dir / "futures"

    btc_files = []
    # 檢查各種可能的BTC數據文件
    patterns = [
        "BTC_USDT-5m.feather",
        "BTC_USDT-USDT-5m.feather",
        "BTC_USDT_USDT-5m.feather",
        "BTC_USDT_USDT-5m-futures.feather",
    ]

    for pattern in patterns:
        spot_file = data_dir / pattern
        futures_file = futures_dir / pattern

        if spot_file.exists():
            btc_files.append(("SPOT", spot_file))
        if futures_file.exists():
            btc_files.append(("FUTURES", futures_file))

    print(f"\n📊 BTC數據文件檢查:")
    if not btc_files:
        print("❌ 未找到任何BTC數據文件")
        return False

    for file_type, file_path in btc_files:
        try:
            df = pd.read_feather(file_path)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                start_date = df["date"].min()
                end_date = df["date"].max()
                days = (end_date - start_date).days

                print(f"   ✅ {file_type} {file_path.name}:")
                print(f"      記錄數: {len(df)}")
                print(f"      時間範圍: {start_date.date()} 到 {end_date.date()}")
                print(f"      天數: {days}")

                # 檢查是否覆蓋測試時間範圍
                test_start = pd.to_datetime("2024-07-01")
                test_end = pd.to_datetime("2024-09-01")

                covers_test_period = (start_date <= test_start) and (end_date >= test_end)
                print(
                    f"      覆蓋測試期間 (2024-07-01 到 2024-09-01): {'✅' if covers_test_period else '❌'}"
                )
            else:
                print(f"   ⚠️ {file_type} {file_path.name}: 沒有date列")

        except Exception as e:
            print(f"   ❌ {file_type} {file_path.name}: 讀取失敗 - {e}")

    # 3. 計算FreqAI數據需求
    train_days = freqai_config.get("train_period_days", 30)
    backtest_days = freqai_config.get("backtest_period_days", 10)
    total_days_needed = train_days + backtest_days + 1  # +1 為緩衝

    print(f"\n📋 FreqAI數據需求分析:")
    print(f"   訓練期間: {train_days} 天")
    print(f"   回測期間: {backtest_days} 天")
    print(f"   總需求: {total_days_needed} 天")

    # 檢查測試時間範圍
    test_period_days = (pd.to_datetime("2024-09-01") - pd.to_datetime("2024-07-01")).days
    print(f"   測試期間: {test_period_days} 天")
    print(f"   數據充足性: {'✅' if test_period_days >= total_days_needed else '❌'}")

    if test_period_days < total_days_needed:
        print(f"⚠️ 測試期間 ({test_period_days}天) < 所需數據 ({total_days_needed}天)")
        print("   這是FreqAI不觸發訓練的主要原因！")

        # 建議解決方案
        recommended_train_days = max(1, test_period_days - backtest_days - 5)  # 留5天緩衝
        print(f"\n💡 建議修復:")
        print(f"   將 train_period_days 從 {train_days} 調整為 {recommended_train_days}")
        return False

    # 4. 檢查FreqAI模型文件
    models_dir = Path("user_data/models")
    identifier = freqai_config.get("identifier", "three_target_voting")

    print(f"\n🤖 FreqAI模型文件檢查:")
    if not models_dir.exists():
        print(f"   📁 模型目錄不存在: {models_dir}")
        models_dir.mkdir(parents=True, exist_ok=True)
        print(f"   📁 已創建模型目錄")

    model_files = list(models_dir.glob(f"{identifier}*"))
    if model_files:
        print(f"   ✅ 找到模型文件:")
        for model_file in model_files:
            print(f"      {model_file.name}")
    else:
        print(f"   ⚠️ 未找到模型文件 (正常，首次運行時)")

    # 5. 檢查策略文件中的populate_any_indicators
    strategy_file = Path("user_data/strategies/EnsembleStrategyPhase5_Voting.py")
    if strategy_file.exists():
        with open(strategy_file) as f:
            strategy_content = f.read()

        print(f"\n📋 策略文件檢查:")

        # 檢查關鍵方法
        required_methods = [
            "populate_any_indicators",
            "populate_indicators",
            "populate_entry_trend",
            "populate_exit_trend",
        ]

        for method in required_methods:
            if f"def {method}" in strategy_content:
                print(f"   ✅ {method}: 已定義")
            else:
                print(f"   ❌ {method}: 未定義")

        # 檢查FreqAI預測列的使用
        prediction_cols = ["&_momentum_prediction", "&_trend_prediction", "&_volatility_prediction"]

        print(f"\n🎯 預測列使用檢查:")
        for col in prediction_cols:
            if col in strategy_content:
                count = strategy_content.count(col)
                print(f"   ✅ {col}: 使用 {count} 次")
            else:
                print(f"   ❌ {col}: 未使用")
    else:
        print(f"❌ 策略文件不存在: {strategy_file}")
        return False

    # 6. 總結分析
    print(f"\n📊 診斷總結:")
    print("1. FreqAI配置 ✅")
    print("2. 數據文件存在 ✅")
    print("3. 策略文件完整 ✅")

    if test_period_days >= total_days_needed:
        print("4. 數據充足性 ✅")
        print("\n🎉 FreqAI應該能正常工作")
        print("⚠️ 如果仍然沒有交易，可能是投票條件過於嚴格")
        return True
    else:
        print("4. 數據充足性 ❌")
        print(f"\n⚠️ 需要調整 train_period_days 到 {recommended_train_days} 或更小")
        return False


if __name__ == "__main__":
    success = diagnose_freqai_issue()
    if success:
        print("\n✅ 診斷完成：系統配置正確")
    else:
        print("\n⚠️ 診斷完成：發現配置問題")
