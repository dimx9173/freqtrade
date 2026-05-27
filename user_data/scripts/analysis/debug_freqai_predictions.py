#!/usr/bin/env python3
"""
调试FreqAI预测输出的脚本
检查FreqAI是否正确生成了预测列，以及这些预测值是什么
"""

import subprocess
import sys
import os
import pandas as pd
from pathlib import Path
import json


def run_detailed_backtest():
    """运行详细回测并导出结果"""
    print("🔍 运行详细回测检查FreqAI预测...")

    cmd = [
        "freqtrade",
        "backtesting",
        "--config",
        "user_data/config/config_ensemble_phase5_voting.json",
        "--strategy",
        "EnsembleStrategyPhase5_Voting",
        "--freqaimodel",
        "HybridEnsembleClassifier",
        "--timerange",
        "20240701-20240710",  # 很短的测试期
        "--cache",
        "none",
        "--export",
        "trades,signals",  # 导出交易和信号
        "--export-filename",
        "debug_freqai_test.json",
        "-v",
    ]

    print(f"🚀 执行命令: {' '.join(cmd)}")

    try:
        os.chdir("/Users/carlos/pCloud Drive/CryptoWork/freqtrade")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            print("✅ 详细回测完成")

            # 检查输出中的关键信息
            output_lines = result.stdout.split("\n")
            freqai_training_found = False

            for line in output_lines:
                if "training" in line.lower() or "freqai" in line.lower():
                    print(f"🤖 FreqAI: {line.strip()}")
                    freqai_training_found = True
                elif "prediction" in line.lower():
                    print(f"🎯 预测: {line.strip()}")
                elif any(word in line.lower() for word in ["momentum", "trend", "volatility"]):
                    print(f"📊 指标: {line.strip()}")

            if not freqai_training_found:
                print("⚠️ 在输出中没有找到FreqAI训练相关信息")

            return True
        else:
            print(f"❌ 回测失败 (退出代码: {result.returncode})")
            print("错误输出:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"💥 执行失败: {e}")
        return False


def check_export_files():
    """检查导出的文件"""
    print("\n📂 检查导出文件...")

    export_dir = Path("/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/backtest_results")

    if not export_dir.exists():
        print("❌ 导出目录不存在")
        return False

    # 查找最新的导出文件
    json_files = list(export_dir.glob("*.json"))
    if not json_files:
        print("❌ 没有找到导出的JSON文件")
        return False

    # 找到最新的文件
    latest_file = max(json_files, key=lambda x: x.stat().st_mtime)
    print(f"📄 最新导出文件: {latest_file.name}")

    try:
        with open(latest_file, "r") as f:
            data = json.load(f)

        if "trades" in data:
            trades = data["trades"]
            print(f"💰 交易数量: {len(trades)}")
            if trades:
                print("📊 前3笔交易:")
                for i, trade in enumerate(trades[:3]):
                    print(
                        f"   {i + 1}: 开仓时间={trade.get('open_date', 'N/A')}, "
                        f"方向={trade.get('is_short', False) and 'Short' or 'Long'}"
                    )

        # 检查signals数据
        if "signals" in data:
            signals = data["signals"]
            print(f"📡 信号数据: {len(signals)} 条记录")

            if signals:
                # 转换为DataFrame进行分析
                df = pd.DataFrame(signals)

                print("🔍 可用列:")
                for col in sorted(df.columns):
                    print(f"   📊 {col}")

                # 检查FreqAI预测列
                prediction_cols = [col for col in df.columns if "prediction" in col]
                confidence_cols = [col for col in df.columns if "confidence" in col]

                print(f"\n🎯 FreqAI预测列 ({len(prediction_cols)}):")
                for col in prediction_cols:
                    unique_values = df[col].unique()
                    print(f"   📈 {col}: {unique_values}")

                print(f"\n💯 信心度列 ({len(confidence_cols)}):")
                for col in confidence_cols:
                    mean_val = df[col].mean()
                    min_val = df[col].min()
                    max_val = df[col].max()
                    print(f"   📊 {col}: 均值={mean_val:.3f}, 范围=[{min_val:.3f}, {max_val:.3f}]")

                # 检查进场信号
                entry_signals = ["enter_long", "enter_short"]
                for signal in entry_signals:
                    if signal in df.columns:
                        count = df[signal].sum()
                        print(f"🚪 {signal}: {count} 次触发")

                # 分析为什么没有进场
                if "&_momentum_prediction" in df.columns:
                    momentum_values = df["&_momentum_prediction"].value_counts()
                    print(f"\n📈 动量预测分布: {momentum_values.to_dict()}")

                if "&_trend_prediction" in df.columns:
                    trend_values = df["&_trend_prediction"].value_counts()
                    print(f"📊 趋势预测分布: {trend_values.to_dict()}")

                if "&_volatility_prediction" in df.columns:
                    volatility_values = df["&_volatility_prediction"].value_counts()
                    print(f"📉 波动预测分布: {volatility_values.to_dict()}")

        return True

    except Exception as e:
        print(f"❌ 分析导出文件失败: {e}")
        return False


def check_freqai_model_files():
    """检查FreqAI模型文件是否生成"""
    print("\n🤖 检查FreqAI模型文件...")

    models_dir = Path("/Users/carlos/pCloud Drive/CryptoWork/freqtrade/user_data/models")

    if not models_dir.exists():
        print("❌ 模型目录不存在")
        return False

    # 查找相关模型文件
    model_files = list(models_dir.glob("three_target_voting*"))

    if model_files:
        print(f"✅ 找到 {len(model_files)} 个模型文件:")
        for file_path in model_files:
            stat = file_path.stat()
            size_mb = stat.st_size / (1024 * 1024)
            print(f"   📦 {file_path.name} (大小: {size_mb:.2f} MB)")

            # 检查是否是目录（完整的模型）
            if file_path.is_dir():
                sub_files = list(file_path.glob("*"))
                print(f"      包含 {len(sub_files)} 个子文件")

                # 查找具体的模型文件
                for sub_file in sub_files:
                    if sub_file.suffix in [".pkl", ".joblib", ".h5", ".pt"]:
                        print(f"      🎯 模型文件: {sub_file.name}")
        return True
    else:
        print("❌ 没有找到FreqAI模型文件")
        print("   这表明FreqAI可能没有成功训练")
        return False


def main():
    """主调试流程"""
    print("🔍 FreqAI预测输出调试开始...")
    print("=" * 60)

    steps = [
        ("FreqAI模型文件检查", check_freqai_model_files),
        ("详细回测执行", run_detailed_backtest),
        ("导出文件分析", check_export_files),
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

    # 总结
    print(f"\n{'=' * 20} 调试总结 {'=' * 20}")

    passed = sum(results.values())
    total = len(results)

    print(f"📊 调试结果: {passed}/{total} 项成功")

    if results.get("导出文件分析", False):
        print("🎉 成功获取了FreqAI预测数据！")
        print("💡 现在可以分析为什么没有进场信号了")
    elif results.get("FreqAI模型文件检查", False):
        print("🎯 FreqAI训练成功，但需要检查预测输出")
    else:
        print("⚠️ FreqAI可能没有正确训练，需要进一步诊断")


if __name__ == "__main__":
    main()
