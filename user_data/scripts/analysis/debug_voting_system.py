#!/usr/bin/env python3
"""
三目標投票系統分析腳本
分析為什麼沒有交易信號產生
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import importlib.util


def load_strategy():
    """載入策略類"""
    try:
        strategy_path = Path("user_data/strategies/EnsembleStrategyPhase5_Voting.py")
        spec = importlib.util.spec_from_file_location(
            "EnsembleStrategyPhase5_Voting", strategy_path
        )
        strategy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(strategy_module)
        return strategy_module.EnsembleStrategyPhase5_Voting
    except Exception as e:
        print(f"❌ 無法載入策略: {e}")
        return None


def create_test_data():
    """創建測試數據"""
    np.random.seed(42)
    n_samples = 2000

    # 創建真實的BTC價格波動模式
    price_base = 65000
    dates = pd.date_range("2024-10-01", periods=n_samples, freq="5min")

    # 生成更現實的價格數據
    returns = np.random.normal(0, 0.002, n_samples)  # 0.2%標準差
    returns = np.cumsum(returns)

    prices = price_base * np.exp(returns)

    # 添加一些趨勢和波動
    trend = np.sin(np.arange(n_samples) / 100) * 0.1
    prices *= 1 + trend

    high = prices * (1 + np.random.uniform(0.001, 0.005, n_samples))
    low = prices * (1 - np.random.uniform(0.001, 0.005, n_samples))

    data = {
        "open": prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": np.random.uniform(1000, 5000, n_samples),
    }

    df = pd.DataFrame(data, index=dates)
    return df


def analyze_targets(strategy_class):
    """分析目標生成情況"""
    print("🔍 分析三目標投票系統...")

    # 創建策略實例
    mock_config = {
        "freqai": {
            "identifier": "test",
            "feature_parameters": {"label_period_candles": 48},
            "enabled": True,
        },
        "timeframe": "5m",
        "stake_currency": "USDT",
        "dry_run": True,
    }
    strategy = strategy_class(config=mock_config)

    # 創建測試數據
    df = create_test_data()
    print(f"📊 測試數據: {len(df)} 個數據點")

    # 生成目標
    df_with_targets = strategy.set_freqai_targets(df, {"pair": "BTC/USDT:USDT"})

    # 分析每個目標的分佈
    targets = ["&_momentum", "&_trend", "&_volatility"]

    print("\n📈 目標分佈分析:")
    print("=" * 60)

    for target in targets:
        if target in df_with_targets.columns:
            values = df_with_targets[target].dropna()
            unique_values, counts = np.unique(values, return_counts=True)

            print(f"\n{target}:")
            print(f"  總數據點: {len(values)}")
            print(f"  分佈:")
            for val, count in zip(unique_values, counts):
                percentage = (count / len(values)) * 100
                print(f"    {val:2d}: {count:4d} ({percentage:5.1f}%)")

    # 分析交易信號
    print("\n🎯 交易信號分析:")
    print("=" * 60)

    # 檢查完美信號條件 (根據策略文件的正確邏輯)
    momentum_perfect = df_with_targets["&_momentum"] == 2  # 強上漲
    trend_perfect = df_with_targets["&_trend"] == 1  # 上漲趨勢
    volatility_perfect = df_with_targets["&_volatility"] == 0  # 低風險 (0=low_risk)

    perfect_signals = momentum_perfect & trend_perfect & volatility_perfect
    perfect_count = perfect_signals.sum()

    print(
        f"🔸 momentum=2 (強上漲): {momentum_perfect.sum()} 次 ({(momentum_perfect.sum() / len(df_with_targets)) * 100:.1f}%)"
    )
    print(
        f"🔸 trend=1 (上漲趨勢): {trend_perfect.sum()} 次 ({(trend_perfect.sum() / len(df_with_targets)) * 100:.1f}%)"
    )
    print(
        f"🔸 volatility=0 (低風險): {volatility_perfect.sum()} 次 ({(volatility_perfect.sum() / len(df_with_targets)) * 100:.1f}%)"
    )
    print(
        f"🎯 三重完美信號: {perfect_count} 次 ({(perfect_count / len(df_with_targets)) * 100:.2f}%)"
    )

    # 分析放寬條件的信號
    print(f"\n📊 放寬條件分析:")
    print("-" * 40)

    # 檢查不同信號組合
    momentum_good = df_with_targets["&_momentum"] >= 1  # 弱上漲或更強
    trend_good = df_with_targets["&_trend"] >= 0  # 平穩或上漲
    volatility_good = df_with_targets["&_volatility"] == 0  # 低風險

    relaxed_signals = momentum_good & trend_good & volatility_good
    relaxed_count = relaxed_signals.sum()

    print(
        f"🔹 momentum≥1 + trend≥0 + volatility=0: {relaxed_count} 次 ({(relaxed_count / len(df_with_targets)) * 100:.1f}%)"
    )

    # 更寬鬆的條件
    very_relaxed = (df_with_targets["&_momentum"] >= 0) & (df_with_targets["&_trend"] >= 0)
    very_relaxed_count = very_relaxed.sum()

    print(
        f"🔹 momentum≥0 + trend≥0 (任何波動): {very_relaxed_count} 次 ({(very_relaxed_count / len(df_with_targets)) * 100:.1f}%)"
    )

    # 建議調整
    print(f"\n💡 建議調整:")
    print("=" * 60)
    if perfect_count == 0:
        print("🔴 當前設置過於嚴格，無任何交易信號")
        print("建議調整策略參數：")
        print("  1. 降低信心閾值：momentum_confidence_min: 0.8 → 0.6")
        print("  2. 降低信心閾值：trend_confidence_min: 0.75 → 0.6")
        print("  3. 降低信心閾值：volatility_confidence_min: 0.7 → 0.6")
        print("  4. 或者調整交易條件為 momentum≥1 + trend≥0")
    elif perfect_count < 10:
        print("🟡 信號較少，可能需要適度放寬")
        print("建議小幅降低信心閾值")
    else:
        print("🟢 信號數量合理")

    return df_with_targets


def main():
    """主函數"""
    print("🎯 FreqAI 三目標投票系統分析")
    print("=" * 60)

    # 載入策略
    strategy_class = load_strategy()
    if not strategy_class:
        sys.exit(1)

    # 分析目標生成
    try:
        df_result = analyze_targets(strategy_class)
        print(f"\n✅ 分析完成！數據點: {len(df_result)}")
    except Exception as e:
        print(f"❌ 分析失敗: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
