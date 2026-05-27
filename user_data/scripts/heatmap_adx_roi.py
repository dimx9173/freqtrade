#!/usr/bin/env python3
"""
ADX x ROI Robustness Heatmap
Tests combinations of ADX thresholds (15-25) and primary ROI values (0.03-0.06)
Outputs results to CSV for heatmap visualization.
"""

import os
import json
import subprocess
import re
import csv
from datetime import datetime

# Configuration
STRATEGIES_DIR = "/home/brian/freqtrade/user_data/strategies/test"
CONFIG_PATH = "/home/brian/freqtrade/user_data/config.json"
OUTPUT_CSV = "/home/brian/freqtrade/user_data/backtest_results/heatmap_adx_roi.csv"
PAIRS = "BTC/USDT:USDT ETH/USDT:USDT BNB/USDT:USDT SOL/USDT:USDT XRP/USDT:USDT"
TIMERANGE = "20250117-20260418"
STRATEGY_FILE = os.path.join(STRATEGIES_DIR, "HeatmapStrategy.py")


def generate_strategy_code(adx_threshold, roi_primary, rsi_min=50, rsi_max=60):
    """Generate strategy code with given ADX and ROI parameters."""
    roi_str = f'{{"0": {roi_primary}, "360": {roi_primary / 2}, "720": {roi_primary / 4}}}'

    code = f"""# HeatmapStrategy - ADX={adx_threshold}, ROI={roi_primary}
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import DecimalParameter, IStrategy

class HeatmapStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {roi_str}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(40, 60, default={rsi_min}, space="sell")
    sell_rsi_pullback_max = DecimalParameter(55, 75, default={rsi_max}, space="sell")
    adx_threshold = DecimalParameter(15, 25, default={adx_threshold}, space="buy")

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
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (dataframe["rsi"] < self.sell_rsi_pullback_max.value)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["at_ema"]
            & (dataframe["close"] < dataframe["ema200"])
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe
"""
    return code


def create_strategy(adx_threshold, roi_primary):
    """Create strategy file with given parameters."""
    code = generate_strategy_code(adx_threshold, roi_primary)
    with open(STRATEGY_FILE, "w") as f:
        f.write(code)


def run_backtest():
    """Run backtest and parse results."""
    cmd = [
        "/home/brian/freqtrade/.venv/bin/freqtrade",
        "backtesting",
        "--strategy",
        "HeatmapStrategy",
        "--config",
        CONFIG_PATH,
        "--pairs",
        PAIRS,
        "--timerange",
        TIMERANGE,
        "--timeframe",
        "15m",
        "--dry-run-wallet",
        "1000",
        "--cache",
        "none",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd="/home/brian/freqtrade"
        )
        output = result.stdout + result.stderr

        # Parse results
        metrics = {"profit": None, "trades": None, "winrate": None, "drawdown": None}

        # Profit - look for "│ Total profit %                │ -0.53%                         │"
        m = re.search(r"Total profit %\s+\|\s*([\-\d.]+)%", output)
        if m:
            metrics["profit"] = float(m.group(1))

        # Trades & Winrate - look for "HeatmapStrategy │    167 │...│ 52.7 │"
        # Pattern: Strategy | Trades | ... | Win%
        m = re.search(r"HeatmapStrategy\s+\|\s+(\d+).*?\s+(\d+\.\d+)\s+\|", output)
        if m:
            metrics["trades"] = int(m.group(1))
            metrics["winrate"] = float(m.group(2))

        # Drawdown - look for "│ Absolute drawdown             │ 45.387 USDT (4.51%)            │"
        m = re.search(r"Absolute drawdown.*?\(\s*([\-\d.]+)%", output)
        if m:
            metrics["drawdown"] = abs(float(m.group(1)))

        return metrics, output
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}, ""
    except Exception as e:
        return {"error": str(e)}, ""


def main():
    os.makedirs(STRATEGIES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    # Test parameters - exact values from task
    adx_values = [15, 16, 17, 18, 19, 20]  # 6 values
    roi_values = [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06]  # 7 values

    results = []
    total = len(adx_values) * len(roi_values)
    count = 0

    print("=" * 70)
    print("ADX x ROI Robustness Heatmap")
    print("=" * 70)
    print(f"ADX values: {adx_values}")
    print(f"ROI values: {roi_values}")
    print(f"Total combinations: {total}")
    print("=" * 70)

    for roi in roi_values:
        for adx in adx_values:
            count += 1
            print(f"\n[{count}/{total}] Testing ADX={adx}, ROI={roi}")

            create_strategy(adx, roi)
            metrics, output = run_backtest()

            if "error" in metrics:
                print(f"  ERROR: {metrics['error']}")
                profit = None
                trades = None
                winrate = None
                drawdown = None
            else:
                profit = metrics.get("profit")
                trades = metrics.get("trades")
                winrate = metrics.get("winrate")
                drawdown = metrics.get("drawdown")

                profit_str = f"{profit:.2f}%" if profit is not None else "N/A"
                trades_str = str(trades) if trades is not None else "N/A"
                winrate_str = f"{winrate:.1f}%" if winrate is not None else "N/A"
                dd_str = f"{drawdown:.2f}%" if drawdown is not None else "N/A"

                print(
                    f"  Profit: {profit_str}, Trades: {trades_str}, Winrate: {winrate_str}, DD: {dd_str}"
                )

            results.append(
                {
                    "adx": adx,
                    "roi": roi,
                    "profit": profit,
                    "trades": trades,
                    "winrate": winrate,
                    "drawdown": drawdown,
                }
            )

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["adx", "roi", "profit_pct", "trades", "winrate_pct", "drawdown_pct", "timestamp"]
        )

        for r in results:
            writer.writerow(
                [
                    r["adx"],
                    r["roi"],
                    r["profit"] if r["profit"] is not None else "",
                    r["trades"] if r["trades"] is not None else "",
                    r["winrate"] if r["winrate"] is not None else "",
                    r["drawdown"] if r["drawdown"] is not None else "",
                    datetime.now().isoformat(),
                ]
            )

    print("\n" + "=" * 70)
    print("HEATMAP RESULTS SUMMARY")
    print("=" * 70)

    # Find best and worst
    valid = [r for r in results if r["profit"] is not None]

    if valid:
        best = max(valid, key=lambda x: x["profit"])
        worst = min(valid, key=lambda x: x["profit"])

        print(
            f"\nBest:  ADX={best['adx']}, ROI={best['roi']} -> Profit={best['profit']:.2f}%, Trades={best['trades']}"
        )
        print(
            f"Worst: ADX={worst['adx']}, ROI={worst['roi']} -> Profit={worst['profit']:.2f}%, Trades={worst['trades']}"
        )

        # Average profit
        avg_profit = sum(r["profit"] for r in valid) / len(valid)
        print(f"Average profit: {avg_profit:.2f}%")

    print(f"\nCSV saved to: {OUTPUT_CSV}")
    print("=" * 70)

    # Print CSV content preview
    print("\nCSV Preview:")
    with open(OUTPUT_CSV, "r") as f:
        print(f.read())


if __name__ == "__main__":
    main()
