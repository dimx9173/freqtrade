#!/usr/bin/env python3

"""
FreqAI 三目標投票系統 - 問題診斷分析

這個腳本分析 FreqAI 系統無法訓練模型的根本原因
"""

import json
import os
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta


def analyze_freqai_configuration():
    """分析 FreqAI 配置參數"""
    print("🔧 FreqAI 配置分析")
    print("=" * 60)

    config_path = "user_data/config/config_ensemble_phase5_voting.json"
    with open(config_path, "r") as f:
        config = json.load(f)

    freqai_config = config.get("freqai", {})

    print(f"📊 識別名稱: {freqai_config.get('identifier')}")
    print(f"🧠 模型類別: {freqai_config.get('freqaimodel')}")
    print(f"📅 訓練期間: {freqai_config.get('train_period_days')} 天")
    print(f"🔄 回測期間: {freqai_config.get('backtest_period_days')} 天")

    # 檢查數據分割參數
    data_split = freqai_config.get("data_split_parameters", {})
    print(f"🔀 測試集大小: {data_split.get('test_size', 0.25) * 100}%")

    # 檢查特徵參數
    feature_params = freqai_config.get("feature_parameters", {})
    print(f"📈 時間框架: {feature_params.get('include_timeframes', [])}")
    print(f"🏷️  標籤期間: {feature_params.get('label_period_candles', 48)} 根K線")

    return freqai_config


def analyze_data_availability():
    """分析可用數據"""
    print("\n📊 數據可用性分析")
    print("=" * 60)

    data_dir = Path("user_data/data/binance")
    btc_file = data_dir / "BTC_USDT-USDT-5m.feather"

    if btc_file.exists():
        try:
            df = pd.read_feather(btc_file)
            print(f"📁 數據文件: {btc_file}")
            print(f"📊 數據形狀: {df.shape}")
            print(f"📅 開始時間: {df['date'].iloc[0]}")
            print(f"📅 結束時間: {df['date'].iloc[-1]}")

            # 計算可用天數
            start_date = pd.to_datetime(df["date"].iloc[0])
            end_date = pd.to_datetime(df["date"].iloc[-1])
            available_days = (end_date - start_date).days
            print(f"🗓️  可用天數: {available_days} 天")

            return available_days, start_date, end_date
        except Exception as e:
            print(f"❌ 讀取數據文件失敗: {e}")
            return None, None, None
    else:
        print(f"❌ 數據文件不存在: {btc_file}")
        return None, None, None


def analyze_training_requirements():
    """分析訓練需求"""
    print("\n🧮 訓練需求分析")
    print("=" * 60)

    freqai_config = analyze_freqai_configuration()
    available_days, start_date, end_date = analyze_data_availability()

    if available_days is None:
        print("❌ 無法分析，數據不可用")
        return

    train_period_days = freqai_config.get("train_period_days", 45)
    backtest_period_days = freqai_config.get("backtest_period_days", 10)

    # 計算 FreqAI 訓練需求
    # FreqAI 需要 train_period_days + label_period (以天為單位) + startup_period
    feature_params = freqai_config.get("feature_parameters", {})
    label_period_candles = feature_params.get("label_period_candles", 48)

    # 5分鐘 K 線，每天288根 (24*60/5)
    candles_per_day = 288
    label_period_days = label_period_candles / candles_per_day
    startup_days = 360 / candles_per_day  # startup_candle_count = 360

    total_required_days = train_period_days + label_period_days + startup_days

    print(f"📚 訓練期間需求: {train_period_days} 天")
    print(f"🏷️  標籤期間需求: {label_period_days:.1f} 天")
    print(f"🚀 啟動期間需求: {startup_days:.1f} 天")
    print(f"📏 總需求天數: {total_required_days:.1f} 天")
    print(f"📊 可用天數: {available_days} 天")

    if available_days < total_required_days:
        print(f"❌ 數據不足！缺少 {total_required_days - available_days:.1f} 天")
        print("\n💡 解決方案:")
        print(
            f"   1. 減少 train_period_days 從 {train_period_days} 到 {int(available_days - label_period_days - startup_days - 5)} 天"
        )
        print(f"   2. 或下載更多歷史數據 (建議至少 {int(total_required_days + 10)} 天)")
    else:
        print("✅ 數據充足，應該可以訓練模型")


def analyze_model_directory():
    """分析模型目錄狀況"""
    print("\n📂 模型目錄分析")
    print("=" * 60)

    model_dir = Path("user_data/models/three_target_voting")

    if model_dir.exists():
        files = list(model_dir.iterdir())
        print(f"📁 模型目錄: {model_dir}")
        print(f"📊 文件數量: {len(files)}")

        for file in files:
            print(f"   📄 {file.name}")

        # 檢查子模型目錄
        sub_dirs = [f for f in files if f.is_dir() and f.name.startswith("sub-train-")]
        print(f"🔍 子模型目錄數量: {len(sub_dirs)}")

        if len(sub_dirs) == 0:
            print("❌ 未發現任何訓練好的子模型")
        else:
            print("✅ 發現訓練好的子模型:")
            for sub_dir in sub_dirs:
                sub_files = list(sub_dir.iterdir())
                print(f"   📂 {sub_dir.name}: {len(sub_files)} 個文件")
    else:
        print(f"❌ 模型目錄不存在: {model_dir}")


def suggest_fixes():
    """建議修復方案"""
    print("\n🔧 修復建議")
    print("=" * 60)

    print("基於分析結果，建議採取以下措施:")
    print("")
    print("1. 📅 調整訓練參數:")
    print("   - 減少 train_period_days 從 45 天到 20-30 天")
    print("   - 或者下載更多歷史數據")
    print("")
    print("2. 🔍 檢查時間範圍:")
    print("   - 確保回測時間範圍有足夠的歷史數據")
    print("   - 使用至少 60-90 天的歷史數據")
    print("")
    print("3. 🧪 測試建議:")
    print("   - 先使用較短的訓練期間進行測試")
    print("   - 確認模型能夠成功訓練後再調整參數")
    print("")
    print("4. 📊 數據驗證:")
    print("   - 確保 BTC/USDT:USDT 5分鐘數據完整")
    print("   - 檢查數據中是否有缺失或異常值")


def main():
    """主函數"""
    print("🎯 FreqAI 三目標投票系統 - 問題診斷")
    print("=" * 80)
    print()

    # 切換到 FreqTrade 目錄
    os.chdir("/Users/carlos/pCloud Drive/CryptoWork/freqtrade")

    try:
        analyze_training_requirements()
        analyze_model_directory()
        suggest_fixes()

        print("\n✅ 診斷完成！")

    except Exception as e:
        print(f"❌ 診斷過程中出現錯誤: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
