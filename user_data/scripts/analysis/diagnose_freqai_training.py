#!/usr/bin/env python3
"""
FreqAI三目标投票系统训练诊断脚本
专门诊断为什么FreqAI没有触发模型训练和生成预测
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
import json
from datetime import datetime, timedelta

# 添加freqtrade路径
sys.path.insert(0, "/Users/carlos/pCloud Drive/CryptoWork/freqtrade")


def check_data_availability():
    """检查数据文件可用性"""
    print("🔍 检查数据文件可用性...")

    data_dir = Path("/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/data/binance")
    btc_files = list(data_dir.glob("BTC*USDT*5m.feather"))

    if not btc_files:
        print("❌ 没有找到BTC/USDT 5分钟数据文件")
        return False

    for file_path in btc_files:
        print(f"✅ 找到数据文件: {file_path.name}")
        try:
            df = pd.read_feather(file_path)
            print(f"   📊 数据行数: {len(df)}")
            print(f"   📅 时间范围: {df['date'].min()} 到 {df['date'].max()}")

            # 检查2024年10月到12月的数据
            target_start = pd.Timestamp("2024-10-01")
            target_end = pd.Timestamp("2024-12-01")
            target_data = df[(df["date"] >= target_start) & (df["date"] <= target_end)]
            print(f"   🎯 目标时间范围数据: {len(target_data)}行")

            if len(target_data) < 1000:
                print(f"   ⚠️ 警告：目标时间范围数据量不足，可能影响FreqAI训练")
                return False

        except Exception as e:
            print(f"   ❌ 读取数据文件失败: {e}")
            return False

    return True


def analyze_freqai_config():
    """分析FreqAI配置"""
    print("\n🔧 分析FreqAI配置...")

    config_path = Path(
        "/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/config/config_ensemble_phase5_voting.json"
    )

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        freqai_config = config.get("freqai", {})

        print(f"✅ FreqAI启用状态: {freqai_config.get('enabled', False)}")
        print(f"📊 训练周期: {freqai_config.get('train_period_days', 'N/A')} 天")
        print(f"🔄 回测周期: {freqai_config.get('backtest_period_days', 'N/A')} 天")
        print(f"🎯 标识符: {freqai_config.get('identifier', 'N/A')}")
        print(f"🤖 模型: {freqai_config.get('freqaimodel', 'N/A')}")

        # 检查训练参数
        feature_params = freqai_config.get("feature_parameters", {})
        print(f"📈 标签周期: {feature_params.get('label_period_candles', 'N/A')} K线")
        print(f"📦 缓冲数据: {feature_params.get('buffer_train_data_candles', 'N/A')} K线")

        # 计算最小数据需求
        train_days = freqai_config.get("train_period_days", 30)
        startup_candles = 13320  # 从日志中看到的值
        min_required_days = train_days + (startup_candles * 5 / (24 * 60))  # 5分钟转天数

        print(f"🎯 最小数据需求: ~{min_required_days:.1f} 天")

        return freqai_config

    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return None


def test_model_prediction():
    """测试模型预测功能"""
    print("\n🧪 测试模型预测功能...")

    try:
        # 导入模型
        sys.path.append("/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/freqaimodels")
        from HybridEnsembleClassifier import HybridEnsembleClassifier

        print("✅ 成功导入HybridEnsembleClassifier模型")

        # 创建模型实例
        model = HybridEnsembleClassifier()
        print(f"✅ 模型初始化成功")
        print(f"🎯 目标名称: {model.target_names}")
        print(f"🔢 目标数量: {model.num_targets}")
        print(f"📊 目标类别: {model.target_classes}")

        return True

    except Exception as e:
        print(f"❌ 模型测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_strategy_loading():
    """测试策略加载"""
    print("\n📋 测试策略加载...")

    try:
        sys.path.append("/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/strategies")
        from EnsembleStrategyPhase5_Voting import EnsembleStrategyPhase5_Voting

        print("✅ 成功导入EnsembleStrategyPhase5_Voting策略")

        # 检查关键方法
        strategy = EnsembleStrategyPhase5_Voting()
        print("✅ 策略实例化成功")

        # 检查FreqAI相关方法
        if hasattr(strategy, "set_freqai_targets"):
            print("✅ 找到set_freqai_targets方法")
        else:
            print("❌ 缺少set_freqai_targets方法")

        if hasattr(strategy, "freqai_info"):
            freqai_info = strategy.freqai_info()
            print(f"✅ FreqAI info配置: {len(freqai_info)} 项")
            print(f"🎯 预测目标: {freqai_info.get('prediction_target_cols', 'N/A')}")

        return True

    except Exception as e:
        print(f"❌ 策略测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_freqai_models_directory():
    """检查FreqAI模型目录"""
    print("\n📂 检查FreqAI模型目录...")

    models_dir = Path("/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/models")

    if not models_dir.exists():
        print("❌ 模型目录不存在")
        return False

    # 查找相关的模型文件
    model_files = list(models_dir.glob("*three_target*")) + list(models_dir.glob("*voting*"))

    if not model_files:
        print("⚠️ 没有找到训练过的模型文件")
        print("   这可能意味着FreqAI从未成功训练过模型")
    else:
        print(f"✅ 找到 {len(model_files)} 个相关模型文件:")
        for file_path in model_files:
            print(f"   📦 {file_path.name}")

    return True


def diagnose_training_requirements():
    """诊断训练数据需求"""
    print("\n🔍 诊断FreqAI训练数据需求...")

    # 从配置中获取要求
    train_period_days = 30
    startup_candles = 13320
    timeframe_minutes = 5

    # 计算总需求
    training_candles = train_period_days * 24 * 60 / timeframe_minutes  # 8640 K线
    total_required_candles = startup_candles + training_candles  # 21960 K线
    total_required_days = total_required_candles * timeframe_minutes / (24 * 60)  # 天数

    print(f"📊 训练数据需求分析:")
    print(f"   🎯 训练周期: {train_period_days} 天")
    print(f"   📈 启动K线数: {startup_candles}")
    print(f"   ⏱️ 时间框架: {timeframe_minutes} 分钟")
    print(f"   📊 训练K线数: {training_candles:.0f}")
    print(f"   🎯 总需求K线数: {total_required_candles:.0f}")
    print(f"   📅 总需求天数: {total_required_days:.1f} 天")

    # 检查目标时间范围
    target_days = 61  # 20241001-20241201
    print(f"\n🎯 目标时间范围分析:")
    print(f"   📅 可用天数: {target_days} 天")
    print(f"   📊 可用K线数: {target_days * 24 * 60 / timeframe_minutes:.0f}")

    if target_days < total_required_days:
        print(f"❌ 数据不足！需要至少 {total_required_days:.1f} 天，但只有 {target_days} 天")
        print("💡 建议：扩大时间范围或减少train_period_days")
        return False
    else:
        print(f"✅ 数据充足，满足训练需求")
        return True


def main():
    """主诊断流程"""
    print("🚀 FreqAI三目标投票系统训练诊断开始...")
    print("=" * 60)

    # 诊断步骤
    steps = [
        ("数据文件检查", check_data_availability),
        ("FreqAI配置分析", lambda: analyze_freqai_config() is not None),
        ("训练数据需求诊断", diagnose_training_requirements),
        ("模型加载测试", test_model_prediction),
        ("策略加载测试", test_strategy_loading),
        ("模型目录检查", check_freqai_models_directory),
    ]

    results = {}

    for step_name, step_func in steps:
        print(f"\n{'=' * 20} {step_name} {'=' * 20}")
        try:
            result = step_func()
            results[step_name] = result
            if result:
                print(f"✅ {step_name} - 通过")
            else:
                print(f"❌ {step_name} - 失败")
        except Exception as e:
            print(f"💥 {step_name} - 异常: {e}")
            results[step_name] = False

    # 总结诊断结果
    print(f"\n{'=' * 20} 诊断总结 {'=' * 20}")

    passed = sum(results.values())
    total = len(results)

    print(f"📊 诊断结果: {passed}/{total} 项通过")

    if passed == total:
        print("🎉 所有诊断项目都通过！")
        print("💡 建议检查优化参数是否过于严格")
    else:
        print("⚠️ 发现问题，需要修复：")
        for step_name, result in results.items():
            if not result:
                print(f"   ❌ {step_name}")

    # 具体建议
    print(f"\n💡 修复建议:")
    if not results.get("训练数据需求诊断", True):
        print("1. 扩大时间范围至2024年7月-12月，或减少train_period_days到15天")

    if not results.get("数据文件检查", True):
        print("2. 下载更多BTC/USDT历史数据")

    if not results.get("模型加载测试", True):
        print("3. 检查HybridEnsembleClassifier模型代码错误")

    if not results.get("策略加载测试", True):
        print("4. 检查EnsembleStrategyPhase5_Voting策略代码错误")

    print(
        "5. 降低策略信心度参数 (momentum_confidence_min, trend_confidence_min, overall_consensus_min)"
    )
    print("6. 使用更长的历史数据确保FreqAI有足够训练数据")


if __name__ == "__main__":
    main()
