#!/usr/bin/env python3
"""
Heatmap Robustness Test Script
Tests ADX thresholds (15-25) × ROI primary values (0.03-0.06)
Outputs results to CSV
"""

import os
import sys
import json
import csv
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# Paths
FREQTRADE_DIR = Path.home() / "freqtrade"
USER_DATA_DIR = FREQTRADE_DIR / "user_data"
STRATEGY_DIR = USER_DATA_DIR / "strategies" / "test"
CONFIG_FILE = USER_DATA_DIR / "config.json"
BACKTEST_DIR = USER_DATA_DIR / "backtest_results"
SCRIPT_DIR = USER_DATA_DIR / "scripts"

# Test parameters
ADX_THRESHOLDS = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
ROI_PRIMARY_VALUES = [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06]

# Strategy template - we will modify minimal_roi and adx_threshold
STRATEGY_TEMPLATE = """# HeatmapStrategy - ADX={adx}, ROI={roi}
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import DecimalParameter, IStrategy

class HeatmapStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    stoploss = -0.02
    minimal_roi = {{"0": {roi}, "360": 0.015, "720": 0.0075}}
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    sell_rsi_pullback_min = DecimalParameter(40, 60, default=50, space="sell")
    sell_rsi_pullback_max = DecimalParameter(55, 75, default=60, space="sell")
    adx_threshold = DecimalParameter(15, 25, default={adx}, space="buy")

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


def create_strategy_file(adx: int, roi: float) -> Path:
    """Create a strategy file with specific ADX and ROI values."""
    strategy_content = STRATEGY_TEMPLATE.format(adx=adx, roi=roi)
    filename = f"Heatmap_ADX{adx}_ROI{int(roi * 1000)}.py"
    filepath = STRATEGY_DIR / filename
    with open(filepath, "w") as f:
        f.write(strategy_content)
    return filepath


def run_backtest(strategy_name: str, export_file: str) -> dict:
    """Run backtest and return results."""
    cmd = [
        sys.executable,
        "-m",
        "freqtrade",
        "backtesting",
        "--strategy",
        strategy_name,
        "--config",
        str(CONFIG_FILE),
        "--userdir",
        str(USER_DATA_DIR),
        "--export",
        "trades",
        "--backtest-filename",
        export_file,
        "--timerange",
        "20250401-20260426",  # Use more recent data
    ]

    result = subprocess.run(
        cmd,
        cwd=FREQTRADE_DIR,
        capture_output=True,
        text=True,
        env={**os.environ, "VIRTUAL_ENV": str(FREQTRADE_DIR / ".venv")},
    )

    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def parse_backtest_results(backtest_file: Path) -> dict:
    """Parse backtest results from trades file."""
    if not backtest_file.exists():
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_mean": 0.0,
            "profit_total": 0.0,
            "profit_pct": 0.0,
        }

    try:
        with open(backtest_file, "r") as f:
            data = json.load(f)

        trades = data.get("trades", [])
        total_trades = len(trades)

        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "profit_mean": 0.0,
                "profit_total": 0.0,
                "profit_pct": 0.0,
            }

        winning_trades = sum(1 for t in trades if t.get("profit_abs", 0) > 0)
        losing_trades = sum(1 for t in trades if t.get("profit_abs", 0) < 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        profits = [t.get("profit_abs", 0) for t in trades]
        profit_total = sum(profits)
        profit_mean = profit_total / total_trades if total_trades > 0 else 0.0

        # Calculate profit percentage
        initial_balance = 10000  # from config dry_run_wallet
        profit_pct = (profit_total / initial_balance) * 100

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "profit_mean": profit_mean,
            "profit_total": profit_total,
            "profit_pct": profit_pct,
        }
    except Exception as e:
        print(f"Error parsing backtest results: {e}")
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_mean": 0.0,
            "profit_total": 0.0,
            "profit_pct": 0.0,
        }


def main():
    """Main function to run heatmap tests."""
    print("=" * 60)
    print("ADX × ROI Heatmap Robustness Test")
    print("=" * 60)
    print(f"ADX thresholds: {ADX_THRESHOLDS}")
    print(f"ROI primary values: {ROI_PRIMARY_VALUES}")
    print(f"Total combinations: {len(ADX_THRESHOLDS) * len(ROI_PRIMARY_VALUES)}")
    print()

    # Ensure backtest results directory exists
    BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

    # CSV output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = BACKTEST_DIR / f"heatmap_results_{timestamp}.csv"

    results = []
    total_runs = len(ADX_THRESHOLDS) * len(ROI_PRIMARY_VALUES)
    run_num = 0

    for roi in ROI_PRIMARY_VALUES:
        for adx in ADX_THRESHOLDS:
            run_num += 1
            print(f"\n[{run_num}/{total_runs}] Testing ADX={adx}, ROI={roi}")

            # Create strategy file
            strategy_file = create_strategy_file(adx, roi)
            strategy_name = strategy_file.stem

            # Export file for this run
            export_file = f"heatmap_adx{adx}_roi{int(roi * 1000)}_{timestamp}"

            # Run backtest
            result = run_backtest(strategy_name, export_file)

            if result["returncode"] != 0:
                print(f"  ERROR: Backtest failed")
                print(f"  stderr: {result['stderr'][:500]}")
                metrics = {
                    "adx": adx,
                    "roi": roi,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "profit_mean": 0.0,
                    "profit_total": 0.0,
                    "profit_pct": 0.0,
                    "error": True,
                }
            else:
                # Parse results
                backtest_file = BACKTEST_DIR / f"{export_file}-trades.json"
                metrics = parse_backtest_results(backtest_file)
                metrics["adx"] = adx
                metrics["roi"] = roi
                metrics["error"] = False

                print(
                    f"  Trades: {metrics['total_trades']}, Win Rate: {metrics['win_rate']:.2%}, "
                    f"Profit: {metrics['profit_pct']:.2f}%"
                )

            results.append(metrics)

            # Clean up strategy file
            try:
                os.remove(strategy_file)
            except:
                pass

    # Write CSV
    print(f"\n{'=' * 60}")
    print(f"Writing results to {csv_file}")

    fieldnames = [
        "adx",
        "roi",
        "total_trades",
        "winning_trades",
        "losing_trades",
        "win_rate",
        "profit_mean",
        "profit_total",
        "profit_pct",
        "error",
    ]

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Done! Results saved to {csv_file}")

    # Create pivot table for heatmap visualization
    pivot_profit = [[0 for _ in range(len(ADX_THRESHOLDS))] for _ in range(len(ROI_PRIMARY_VALUES))]
    pivot_trades = [[0 for _ in range(len(ADX_THRESHOLDS))] for _ in range(len(ROI_PRIMARY_VALUES))]
    pivot_winrate = [
        [0.0 for _ in range(len(ADX_THRESHOLDS))] for _ in range(len(ROI_PRIMARY_VALUES))
    ]

    for r in results:
        adx_idx = ADX_THRESHOLDS.index(r["adx"])
        roi_idx = ROI_PRIMARY_VALUES.index(r["roi"])
        pivot_profit[roi_idx][adx_idx] = r["profit_pct"]
        pivot_trades[roi_idx][adx_idx] = r["total_trades"]
        pivot_winrate[roi_idx][adx_idx] = r["win_rate"]

    print("\n" + "=" * 60)
    print("PROFIT % HEATMAP (ROI × ADX)")
    print("=" * 60)
    print(f"{'ROI/ADX':>10}", end="")
    for adx in ADX_THRESHOLDS:
        print(f"{adx:>8}", end="")
    print()
    for i, roi in enumerate(ROI_PRIMARY_VALUES):
        print(f"{roi:>10.3f}", end="")
        for j, adx in enumerate(ADX_THRESHOLDS):
            val = pivot_profit[i][j]
            print(f"{val:>8.2f}", end="")
        print()

    print("\n" + "=" * 60)
    print("TOTAL TRADES HEATMAP (ROI × ADX)")
    print("=" * 60)
    print(f"{'ROI/ADX':>10}", end="")
    for adx in ADX_THRESHOLDS:
        print(f"{adx:>8}", end="")
    print()
    for i, roi in enumerate(ROI_PRIMARY_VALUES):
        print(f"{roi:>10.3f}", end="")
        for j, adx in enumerate(ADX_THRESHOLDS):
            val = pivot_trades[i][j]
            print(f"{val:>8}", end="")
        print()

    return csv_file


if __name__ == "__main__":
    main()
