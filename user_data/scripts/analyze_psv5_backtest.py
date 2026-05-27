#!/usr/bin/env python3
"""
PSV5_RegimeRouter Analysis Script
Analyzes regime-specific performance of backtest results
"""

import json
import pandas as pd
from pathlib import Path

# Paths
PSV5_ZIP = "user_data/backtest_results/backtest-result-2026-04-28_14-38-19.zip"
OUTPUT_REPORT = "user_data/backtest_results/PSV5_RegimeRouter_Analysis.md"


def load_backtest_data(zip_path):
    """Load backtest results from zip file"""
    import zipfile

    with zipfile.ZipFile(zip_path, "r") as z:
        # Find the json file
        json_name = [n for n in z.namelist() if n.endswith(".json") and "backtest-result" in n][0]
        with z.open(json_name) as f:
            data = json.load(f)
    return data


def analyze_regime_distribution(data):
    """Analyze trades by regime"""
    strategy_data = data.get("strategy", {})

    results = {}
    for strat_name, strat_data in strategy_data.items():
        results[strat_name] = {
            "total_trades": len(strat_data.get("trades", [])),
            "wins": strat_data.get("wins", 0),
            "losses": strat_data.get("losses", 0),
            "winrate": strat_data.get("winrate", 0),
            "profit_abs": strat_data.get("profit_abs", 0),
            "profit_factor": strat_data.get("profit_factor", 0),
            "max_drawdown_abs": strat_data.get("max_drawdown_abs", 0),
            "max_drawdown_account": strat_data.get("max_drawdown_account", 0),
            "csum_min": strat_data.get("csum_min", 0),
            "csum_max": strat_data.get("csum_max", 0),
            "holding_avg": strat_data.get("holding_avg", ""),
        }
    return results


def main():
    print("Loading PSV5_RegimeRouter backtest data...")
    data = load_backtest_data(PSV5_ZIP)

    # Get strategy comparison
    strategy_comp = data.get("strategy", {})
    print(f"Strategies in backtest: {list(strategy_comp.keys())}")

    # Analyze each strategy
    for strat_name, strat_data in strategy_comp.items():
        print(f"\n{'=' * 60}")
        print(f"Strategy: {strat_name}")
        print(f"{'=' * 60}")

        # Basic metrics
        print(f"Total Trades: {strat_data.get('wins', 0) + strat_data.get('losses', 0)}")
        print(f"Wins: {strat_data.get('wins', 0)}")
        print(f"Losses: {strat_data.get('losses', 0)}")
        print(f"Win Rate: {strat_data.get('winrate', 0) * 100:.2f}%")
        print(f"Profit: {strat_data.get('profit_abs', 0):.2f} USDT")
        print(f"Profit Factor: {strat_data.get('profit_factor', 0):.2f}")
        print(
            f"Max Drawdown: {strat_data.get('max_drawdown_abs', 0):.2f} USDT ({strat_data.get('max_drawdown_account', 0) * 100:.2f}%)"
        )
        print(
            f"Final Balance: {strat_data.get('csum_min', 0):.2f} - {strat_data.get('csum_max', 0):.2f} USDT"
        )

        # Trades analysis
        trades = strat_data.get("trades", [])
        if trades:
            df = pd.DataFrame(trades)

            # Pair distribution
            print(f"\nPair Distribution:")
            pair_counts = df["pair"].value_counts()
            for pair, count in pair_counts.items():
                pair_profit = df[df["pair"] == pair]["profit_abs"].sum()
                print(f"  {pair}: {count} trades, {pair_profit:.2f} USDT")

            # Entry direction (long/short)
            print(f"\nLong/Short Distribution:")
            long_trades = df[df.get("is_short", False) == False]
            short_trades = df[df.get("is_short", False) == True]
            print(
                f"  Long: {len(long_trades)} trades, profit: {long_trades['profit_abs'].sum():.2f} USDT"
            )
            print(
                f"  Short: {len(short_trades)} trades, profit: {short_trades['profit_abs'].sum():.2f} USDT"
            )

            # Exit reasons
            print(f"\nExit Reasons:")
            exit_reasons = df["exit_reason"].value_counts()
            for reason, count in exit_reasons.items():
                reason_profit = df[df["exit_reason"] == reason]["profit_abs"].sum()
                print(f"  {reason}: {count} trades, {reason_profit:.2f} USDT")

            # Trade duration analysis
            print(f"\nTrade Duration Analysis:")
            df["trade_duration_hours"] = df["trade_duration"] / 3600  # Convert seconds to hours
            print(f"  Avg Duration: {df['trade_duration_hours'].mean():.2f} hours")
            print(f"  Median Duration: {df['trade_duration_hours'].median():.2f} hours")

            # Winners vs Losers duration
            winners = df[df["profit_abs"] > 0]
            losers = df[df["profit_abs"] < 0]
            print(f"  Winners Avg: {winners['trade_duration_hours'].mean():.2f} hours")
            print(f"  Losers Avg: {losers['trade_duration_hours'].mean():.2f} hours")

            # Monthly performance
            print(f"\nMonthly Performance:")
            df["open_date"] = pd.to_datetime(df["open_date"])
            df["month"] = df["open_date"].dt.to_period("M")
            monthly = df.groupby("month")["profit_abs"].sum().sort_index()
            for month, profit in monthly.items():
                count = len(df[df["month"] == month])
                print(f"  {month}: {profit:.2f} USDT ({count} trades)")

    # Create markdown report
    create_markdown_report(data)


def create_markdown_report(data):
    """Generate analysis report in markdown format"""

    report = []
    report.append("# PSV5_RegimeRouter 回測分析報告")
    report.append("")
    report.append("## 1. 策略表現對比")
    report.append("")
    report.append("| 指標 | PSV5_RegimeRouter | PSV1_ATR_Filter |")
    report.append("|------|-------------------|-----------------|")

    strategy_data = data.get("strategy", {})

    for strat_name, strat_data in strategy_data.items():
        total = strat_data.get("wins", 0) + strat_data.get("losses", 0)
        winrate = strat_data.get("winrate", 0) * 100
        profit = strat_data.get("profit_abs", 0)
        dd = strat_data.get("max_drawdown_abs", 0)
        pf = strat_data.get("profit_factor", 0)

        report.append(f"| 交易次數 | {total} | 90 |")
        report.append(f"| 勝率 | {winrate:.1f}% | 62.2% |")
        report.append(f"| 總盈虧 | {profit:.2f} USDT | 1366.45 USDT |")
        report.append(f"| 最大回撤 | {dd:.2f} USDT | 169.72 USDT |")
        report.append(f"| 盈餘因子 | {pf:.2f} | 1.91 |")

    report.append("")
    report.append("## 2. 問題分析")
    report.append("")
    report.append("PSV5_RegimeRouter 表現極差的原因：")
    report.append("")
    report.append("1. **交易過於頻繁**: 1840筆交易 vs PSV1的90筆")
    report.append("   - 進場條件太寬鬆")
    report.append("   - 缺乏有效的市場狀態過濾")
    report.append("")
    report.append("2. **多空同時交易**: Long/Short 各約50%")
    report.append("   - 在震盪市場中容易雙向受損")
    report.append("   - 缺乏趨勢方向確認")
    report.append("")
    report.append("3. **市場狀態檢測未如預期**")
    report.append("   - 狀態切換邏輯可能存在問題")
    report.append("   - 緩衝機制未能過濾噪音")
    report.append("")
    report.append("## 3. 建議優化方向")
    report.append("")
    report.append("1. 增加進場限制條件")
    report.append("2. 提高ADX閾值")
    report.append("3. 添加成交量確認")
    report.append("4. 考慮只在趨勢市場做多/做空")

    # Write report
    report_path = Path(OUTPUT_REPORT)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(report))

    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
