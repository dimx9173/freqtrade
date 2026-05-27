#!/usr/bin/env python3
"""
Parameter Sensitivity Analysis for Pullback_Scalp_v1_ShortOnly_Best
Tests ADX thresholds (18/19/20/21/22) x ROI thresholds (3%/3.5%/4%/4.5%/5%)
"""

import json
import subprocess
import os
import sys
import re
from datetime import datetime

# Configuration
WORKDIR = "/home/brian/freqtrade"
CONFIG_PATH = "/home/brian/freqtrade/user_data/config.json"
TIMERANGE = "20250117-20260418"

# Test parameters
ADX_VALUES = [18, 19, 20, 21, 22]
ROI_VALUES = [0.03, 0.035, 0.04, 0.045, 0.05]

# Base strategy template - using hardcoded values instead of parameters
STRATEGY_TEMPLATE = """# Auto-generated strategy for sensitivity analysis
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy

class Pullback_Scalp_v1_ShortOnly_Sensitivity_ADX{adx}_ROI{roi_pct}(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {{"0": {roi}, "360": 0.02, "720": 0.01}}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    adx_threshold = {adx}

    startup_candle_count = 100
    process_only_new_candles = True
    use_exit_signal = False

    def populate_indicators(self, dataframe, metadata):
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["at_ema"] = (abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005) | (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > 55) & (dataframe["rsi"] < 65)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"]) &
            (dataframe["adx"] > {adx}) &
            (dataframe["minus_di"] > dataframe["plus_di"]) &
            dataframe["rsi_pullback_short"] &
            dataframe["at_ema"] &
            (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe
"""


def run_backtest(strategy_name):
    """Run backtest and return results"""
    cmd = [
        "python",
        "-m",
        "freqtrade",
        "backtesting",
        "--strategy",
        strategy_name,
        "--config",
        CONFIG_PATH,
        "--timerange",
        TIMERANGE,
        "--dry-run-wallet",
        "10000",
        "--stake-amount",
        "1000",
        "--max-open-trades",
        "5",
        "--cache",
        "none",
    ]

    result = subprocess.run(cmd, cwd=WORKDIR, capture_output=True, text=True, timeout=120)

    return result.stdout + result.stderr


def parse_results(output):
    """Parse backtest output for key metrics"""
    # Total profit pattern
    profit_match = re.search(r"Total profit %\s*│\s*([-\d.]+)\s*%", output)
    total_profit_pct = float(profit_match.group(1)) if profit_match else None

    # Sharpe pattern
    sharpe_match = re.search(r"Sharpe\s*│\s*([-\d.]+)", output)
    sharpe = float(sharpe_match.group(1)) if sharpe_match else None

    # Win rate pattern - look for the table row with win rate
    wr_match = re.search(
        r"Pullback[^\│]*│\s*(\d+)\s+│\s*[-\d.]+\s+│\s*[-\d.]+\s+USD.*?│\s*\d+\s+\d+\s+\d+\s+([-\d.]+)",
        output,
    )
    if wr_match:
        win_rate = float(wr_match.group(2))
    else:
        # Try another pattern
        wr_match = re.search(r"\|\s*(\d+)\s+\d+\s+\d+\s+([-\d.]+)\s*%", output)
        win_rate = float(wr_match.group(2)) if wr_match else None

    # trades count from strategy summary table
    trades_match = re.search(r"Pullback[^\│]*│\s*(\d+)\s+│", output)
    trades = int(trades_match.group(1)) if trades_match else None

    # Calmar ratio
    calmar_match = re.search(r"Calmar\s*│\s*([-\d.]+)", output)
    calmar = float(calmar_match.group(1)) if calmar_match else None

    # SQN
    sqn_match = re.search(r"SQN\s*│\s*([-\d.]+)", output)
    sqn = float(sqn_match.group(1)) if sqn_match else None

    return {
        "total_profit_pct": total_profit_pct,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "trades": trades,
        "calmar": calmar,
        "sqn": sqn,
    }


def create_strategy_file(adx, roi, class_name):
    """Create a temporary strategy file"""
    roi_formatted = f"{roi:.3f}"
    roi_pct = int(roi * 100)

    content = STRATEGY_TEMPLATE.format(adx=adx, roi=roi_formatted, roi_pct=roi_pct)

    filepath = f"/home/brian/freqtrade/user_data/strategies/test/{class_name}.py"
    with open(filepath, "w") as f:
        f.write(content)

    return filepath


def main():
    results = []
    errors = []

    print("=" * 70)
    print("Parameter Sensitivity Analysis - ADX x ROI")
    print("=" * 70)
    print(f"Testing {len(ADX_VALUES) * len(ROI_VALUES)} combinations...")
    print(f"Timerange: {TIMERANGE}")
    print("=" * 70)

    total_combinations = len(ADX_VALUES) * len(ROI_VALUES)
    current = 0

    for adx in ADX_VALUES:
        for roi in ROI_VALUES:
            current += 1
            roi_pct = int(roi * 100)
            class_name = f"Pullback_Scalp_v1_ShortOnly_Sensitivity_ADX{adx}_ROI{roi_pct}"

            print(f"\n[{current}/{total_combinations}] Testing ADX={adx}, ROI={roi_pct}%")

            try:
                # Create strategy file
                filepath = create_strategy_file(adx, roi, class_name)

                # Run backtest
                output = run_backtest(class_name)

                # Parse results
                metrics = parse_results(output)

                result = {
                    "adx": adx,
                    "roi_pct": roi_pct,
                    "strategy": class_name,
                    "metrics": metrics,
                }
                results.append(result)

                # Display result
                profit = metrics.get("total_profit_pct", "N/A")
                sharpe = metrics.get("sharpe", "N/A")
                trades = metrics.get("trades", "N/A")
                win_rate = metrics.get("win_rate", "N/A")
                print(
                    f"  -> Profit: {profit}%, Sharpe: {sharpe}, Win%: {win_rate}, Trades: {trades}"
                )

                # Clean up strategy file
                os.remove(filepath)

            except Exception as e:
                print(f"  -> ERROR: {str(e)}")
                errors.append({"adx": adx, "roi_pct": roi_pct, "error": str(e)})
                # Clean up
                if os.path.exists(filepath):
                    os.remove(filepath)

    if errors:
        print(f"\n{len(errors)} combinations failed to run.")

    # Sort by total profit (descending)
    valid_results = [r for r in results if r["metrics"].get("total_profit_pct") is not None]
    valid_results.sort(key=lambda x: x["metrics"].get("total_profit_pct") or -999, reverse=True)

    # Print summary table
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY (sorted by Total Profit)")
    print("=" * 70)
    print(
        f"{'Rank':<5} {'ADX':<5} {'ROI%':<6} {'Profit%':<10} {'Sharpe':<8} {'WinRate%':<10} {'Trades':<8}"
    )
    print("-" * 70)

    for i, r in enumerate(valid_results, 1):
        m = r["metrics"]
        profit_str = f"{m.get('total_profit_pct', 'N/A')}"
        sharpe_str = f"{m.get('sharpe', 'N/A')}"
        wr_str = f"{m.get('win_rate', 'N/A')}"
        trades_str = f"{m.get('trades', 'N/A')}"
        print(
            f"{i:<5} {r['adx']:<5} {r['roi_pct']:<6} {profit_str:<10} {sharpe_str:<8} {wr_str:<10} {trades_str:<8}"
        )

    # Best result
    if valid_results:
        best = valid_results[0]
        print("\n" + "=" * 70)
        print("BEST PARAMETERS")
        print("=" * 70)
        print(f"ADX Threshold: {best['adx']}")
        print(f"ROI Threshold: {best['roi_pct']}%")
        print(f"Total Profit: {best['metrics'].get('total_profit_pct', 'N/A')}%")
        print(f"Sharpe Ratio: {best['metrics'].get('sharpe', 'N/A')}")
        print(f"Win Rate: {best['metrics'].get('win_rate', 'N/A')}%")
        print(f"Total Trades: {best['metrics'].get('trades', 'N/A')}")
        print(f"Calmar: {best['metrics'].get('calmar', 'N/A')}")
        print(f"SQN: {best['metrics'].get('sqn', 'N/A')}")

        # Save results to JSON
        output_json = {
            "analysis_date": datetime.now().isoformat(),
            "timerange": TIMERANGE,
            "best_parameters": {"adx": best["adx"], "roi_pct": best["roi_pct"]},
            "best_metrics": best["metrics"],
            "all_results": results,
            "errors": errors,
        }

        with open(
            "/home/brian/freqtrade/user_data/backtest_results/sensitivity_analysis_results.json",
            "w",
        ) as f:
            json.dump(output_json, f, indent=2, default=str)

        print(f"\nResults saved to: user_data/backtest_results/sensitivity_analysis_results.json")
    else:
        print("\nNo valid results to display.")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
