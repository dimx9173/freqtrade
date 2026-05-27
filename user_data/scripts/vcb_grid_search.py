#!/usr/bin/env python3
"""
VCB Grid Search - Batch Backtest Runner
Runs backtests for all 320 parameter combinations and collects results.
"""

import itertools
import json
import subprocess
import re
import os
from datetime import datetime

# Grid parameters
ATR_VALUES = [0.25, 0.30, 0.35, 0.40]
VRANK_VALUES = [0.05, 0.10, 0.15, 0.20]
TP_VALUES = [0.03, 0.04, 0.05, 0.06, 0.08]
SL_VALUES = [0.005, 0.008, 0.010, 0.015]


def format_strategy_name(atr, vrank, tp, sl):
    """Generate strategy name from parameters."""
    return f"VCB_grid_1h_A{int(atr * 100)}_V{int(vrank * 100)}_TP{int(tp * 100)}_SL{int(sl * 1000)}"


def run_backtest(strategy_name, timerange="20240101-20250109"):
    """Run backtest for a single strategy."""
    cmd = [
        "python",
        "-m",
        "freqtrade",
        "backtesting",
        "--config",
        "/home/brian/freqtrade/user_data/config/config_vcb_backtest_1h.json",
        "--strategy",
        strategy_name,
        "--strategy-path",
        "/home/brian/freqtrade/user_data/strategies/test",
        "--timerange",
        timerange,
        "--cache",
        "none",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "Timeout"
    except Exception as e:
        return -1, str(e)


def parse_backtest_metrics(output):
    """Parse backtest output to extract key metrics."""
    metrics = {"trades": 0, "win_rate": 0.0, "annual_return": 0.0, "drawdown": 0.0, "sqn": 0.0}

    # Pattern matches
    trades_match = re.search(r"Total/Daily Avg Trades\s+\|\s+(\d+)\s+/", output)
    if trades_match:
        metrics["trades"] = int(trades_match.group(1))

    win_rate_match = re.search(r"(\d+)\s+\+\s+\d+\s+-\s+\d+\s+(\d+\.?\d*)\s*%", output)
    if win_rate_match:
        metrics["win_rate"] = float(win_rate_match.group(2))

    sqn_match = re.search(r"SQN\s+\|\s+(-?\d+\.?\d*)", output)
    if sqn_match:
        metrics["sqn"] = float(sqn_match.group(1))

    dd_match = re.search(r"Absolute drawdown.*?(\d+\.?\d*)\s+USDT\s+\((\d+\.?\d*)%", output)
    if dd_match:
        metrics["drawdown"] = float(dd_match.group(2))

    annual_match = re.search(r"CAGR\s+%\s+\|\s+(-?\d+\.?\d*)", output)
    if annual_match:
        metrics["annual_return"] = float(annual_match.group(1))

    return metrics


def main():
    print("=" * 80)
    print("VCB Grid Search - Batch Backtest Runner")
    print("=" * 80)
    print(
        f"Total combinations: {len(list(itertools.product(ATR_VALUES, VRANK_VALUES, TP_VALUES, SL_VALUES)))}"
    )

    # Ensure output directory exists
    os.makedirs("/home/brian/freqtrade/user_data/backtest_results", exist_ok=True)

    results = []
    total_combos = len(list(itertools.product(ATR_VALUES, VRANK_VALUES, TP_VALUES, SL_VALUES)))
    combo_idx = 0

    for atr, vrank, tp, sl in itertools.product(ATR_VALUES, VRANK_VALUES, TP_VALUES, SL_VALUES):
        combo_idx += 1
        strategy_name = format_strategy_name(atr, vrank, tp, sl)

        print(f"[{combo_idx}/{total_combos}] {strategy_name}...", end=" ", flush=True)

        returncode, output = run_backtest(strategy_name)

        if returncode == 0:
            metrics = parse_backtest_metrics(output)
            print(
                f"Trades: {metrics['trades']}, WR: {metrics['win_rate']:.1f}%, Ann: {metrics['annual_return']:.2f}%, SQN: {metrics['sqn']:.2f}"
            )
        else:
            metrics = {
                "trades": 0,
                "win_rate": 0.0,
                "annual_return": 0.0,
                "drawdown": 0.0,
                "sqn": 0.0,
            }
            print(f"Error (exit code {returncode})")

        results.append(
            {
                "atr": atr,
                "vrank": vrank,
                "tp": tp,
                "sl": sl,
                "strategy": strategy_name,
                "trades": metrics["trades"],
                "win_rate": metrics["win_rate"],
                "annual_return": metrics["annual_return"],
                "drawdown": metrics["drawdown"],
                "sqn": metrics["sqn"],
            }
        )

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = (
        f"/home/brian/freqtrade/user_data/backtest_results/grid_search_results_{timestamp}.json"
    )

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")

    # Sort and display top 5 by annual return
    results_sorted = sorted(results, key=lambda x: x["annual_return"], reverse=True)

    print("\n" + "=" * 80)
    print("TOP 5 PARAMETER COMBINATIONS (by Annual Return)")
    print("=" * 80)
    print(
        f"{'Rank':<5} {'ATR':<6} {'Vrank':<6} {'TP%':<6} {'SL%':<6} {'Trades':<8} {'WR%':<8} {'Ann%':<10} {'DD%':<8} {'SQN':<6}"
    )
    print("-" * 80)

    for i, r in enumerate(results_sorted[:5], 1):
        print(
            f"{i:<5} {r['atr']:<6} {r['vrank']:<6} {r['tp']:<6} {r['sl']:<6} {r['trades']:<8} {r['win_rate']:<8.1f} {r['annual_return']:<10.2f} {r['drawdown']:<8.1f} {r['sqn']:<6.2f}"
        )

    # Also sort by SQN
    results_by_sqn = sorted(results, key=lambda x: x["sqn"], reverse=True)
    print("\n" + "=" * 80)
    print("TOP 5 PARAMETER COMBINATIONS (by SQN)")
    print("=" * 80)
    print(
        f"{'Rank':<5} {'ATR':<6} {'Vrank':<6} {'TP%':<6} {'SL%':<6} {'Trades':<8} {'WR%':<8} {'Ann%':<10} {'DD%':<8} {'SQN':<6}"
    )
    print("-" * 80)

    for i, r in enumerate(results_by_sqn[:5], 1):
        print(
            f"{i:<5} {r['atr']:<6} {r['vrank']:<6} {r['tp']:<6} {r['sl']:<6} {r['trades']:<8} {r['win_rate']:<8.1f} {r['annual_return']:<10.2f} {r['drawdown']:<8.1f} {r['sqn']:<6.2f}"
        )

    # Save CSV
    csv_file = results_file.replace(".json", ".csv")
    with open(csv_file, "w") as f:
        f.write("atr,vrank,tp,sl,strategy,trades,win_rate,annual_return,drawdown,sqn\n")
        for r in results_sorted:
            f.write(
                f"{r['atr']},{r['vrank']},{r['tp']},{r['sl']},{r['strategy']},{r['trades']},{r['win_rate']},{r['annual_return']},{r['drawdown']},{r['sqn']}\n"
            )

    print(f"\nCSV saved to: {csv_file}")

    return results_sorted[:5]


if __name__ == "__main__":
    main()
