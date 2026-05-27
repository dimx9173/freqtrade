#!/usr/bin/env python3
"""
Leverage Impact Analysis Script
Tests different leverage settings (1x/3x/5x/10x) by simulating leverage effects
through adjusted stoploss and ROI parameters in backtesting.

Since freqtrade backtesting doesn't directly support leverage, we simulate it:
- Higher leverage = tighter stoploss (liquidation buffer scales)
- Higher leverage = adjusted ROI targets for risk management
"""

import os
import json
import subprocess
import re
from datetime import datetime

# Configuration
WORKDIR = "/home/brian/freqtrade"
CONFIG_PATH = os.path.join(WORKDIR, "user_data/config.json")
RESULTS_DIR = os.path.join(WORKDIR, "user_data/backtest_results")
TIMERANGE = "20250117-20260418"
PAIRS = "BTC/USDT:USDT ETH/USDT:USDT BNB/USDT:USDT SOL/USDT:USDT XRP/USDT:USDT"

# Base strategy parameters (5x implied)
BASE_STOPLEVEL = -0.02  # 2% base stoploss
BASE_ROI = {"0": 0.06, "360": 0.03, "720": 0.02}  # 6% immediate ROI

# Leverage configurations to test
LEVERAGE_CONFIGS = {
    1: {
        "stoploss": -0.02,  # 2%
        "roi_mult": 1.0,  # Keep original ROI
        "desc": "1x - No leverage, conservative",
    },
    3: {
        "stoploss": -0.02 / 3,  # ~0.67%
        "roi_mult": 0.85,  # Slightly lower ROI targets
        "desc": "3x - Moderate leverage",
    },
    5: {
        "stoploss": -0.02 / 5,  # 0.4%
        "roi_mult": 0.70,  # Lower ROI for tighter risk
        "desc": "5x - Current implied leverage",
    },
    10: {
        "stoploss": -0.02 / 10,  # 0.2%
        "roi_mult": 0.50,  # Much lower ROI
        "desc": "10x - High leverage, aggressive",
    },
}


def generate_leverage_strategy(leverage: int, config: dict) -> str:
    """Generate strategy code with adjusted stoploss/ROI for leverage simulation."""
    stoploss = config["stoploss"]
    roi_mult = config["roi_mult"]

    # Adjust ROI based on multiplier
    roi = {
        "0": round(BASE_ROI["0"] * roi_mult, 4),
        "360": round(BASE_ROI["360"] * roi_mult, 4),
        "720": round(BASE_ROI["720"] * roi_mult, 4),
    }

    # Build ROI string properly
    roi_str = (
        "{\n"
        '    "0": ' + str(roi["0"]) + ",    # " + str(int(roi["0"] * 100)) + "% immediate\n"
        '    "360": ' + str(roi["360"]) + ",  # After 6h, " + str(int(roi["360"] * 100)) + "%\n"
        '    "720": ' + str(roi["720"]) + "   # After 12h, " + str(int(roi["720"] * 100)) + "%\n"
        "}"
    )

    protections_str = (
        "[\n"
        '    {"method": "StoplossGuard", "lookback_period_candles": 24, "trade_limit": 2, "stop_duration_candles": 4, "refresh_period_candles": 480},\n'
        '    {"method": "LowProfitPairs", "lookback_period_candles": 24, "trade_limit": 1, "stop_duration_candles": 2, "required_profit": 0.01}\n'
        "]"
    )

    code = """# Pullback_Scalp_v1_ShortOnly_Leverage_{lev}x
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import DecimalParameter, IStrategy

class Pullback_Scalp_v1_ShortOnly_Leverage_{lev}x(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # Stoploss/Takeprofit - Adjusted for {lev}x leverage
    stoploss = {stoploss}
    minimal_roi = {roi_str}
    trailing_stop = False
    trailing_stop_positive = 0
    trailing_stop_positive_offset = 0
    trailing_only_offset_is_reached = False

    # Entry Parameters (same as base)
    buy_rsi_pullback_max = DecimalParameter(40, 50, default=45, space="buy")
    buy_rsi_pullback_min = DecimalParameter(30, 45, default=35, space="buy")
    sell_rsi_pullback_min = DecimalParameter(55, 65, default=60, space="sell")
    sell_rsi_pullback_max = DecimalParameter(75, 80, default=65, space="sell")
    adx_threshold = DecimalParameter(20, 35, default=25, space="buy")

    startup_candle_count: int = 100
    process_only_new_candles = True
    use_exit_signal = False

    @staticmethod
    def informative_1h_indicator(dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df["ema9"] = ta.EMA(df, timeperiod=9)
        df["ema21"] = ta.EMA(df, timeperiod=21)
        df["ema50"] = ta.EMA(df, timeperiod=50)
        df["ema200"] = ta.EMA(df, timeperiod=200)
        df["adx"] = ta.ADX(df, timeperiod=14)
        df["plus_di"] = ta.PLUS_DI(df, timeperiod=14)
        df["minus_di"] = ta.MINUS_DI(df, timeperiod=14)
        df["ema_bullish"] = df["ema9"] > df["ema21"]
        df["ema_bearish"] = df["ema9"] < df["ema21"]
        df["above_ema200"] = df["close"] > df["ema200"]
        return df

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=7)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["bb_middle"] = ta.BBANDS(dataframe, timeperiod=20)["middleband"]
        dataframe["bb_upper"] = ta.BBANDS(dataframe, timeperiod=20)["upperband"]
        dataframe["bb_lower"] = ta.BBANDS(dataframe, timeperiod=20)["lowerband"]

        dataframe["bull_pullback_score"] = (
            (dataframe["ema9"] > dataframe["ema21"]).astype(float) * 0.25
            + (dataframe["adx"] > self.adx_threshold.value).astype(float) * 0.25
            + (dataframe["plus_di"] > dataframe["minus_di"]).astype(float) * 0.20
            + ((dataframe["rsi"] > self.buy_rsi_pullback_min.value) & (dataframe["rsi"] < self.buy_rsi_pullback_max.value)).astype(float) * 0.15
            + (((dataframe["close"] > dataframe["ema50"] * 0.98) & (dataframe["close"] < dataframe["ema50"] * 1.02))).astype(float) * 0.15
        )

        dataframe["bear_pullback_score"] = (
            (dataframe["ema9"] < dataframe["ema21"]).astype(float) * 0.25
            + (dataframe["adx"] > self.adx_threshold.value).astype(float) * 0.25
            + (dataframe["minus_di"] > dataframe["plus_di"]).astype(float) * 0.20
            + ((dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (dataframe["rsi"] < self.sell_rsi_pullback_max.value)).astype(float) * 0.15
            + (((dataframe["close"] > dataframe["ema50"] * 0.98) & (dataframe["close"] < dataframe["ema50"] * 1.02))).astype(float) * 0.15
        )

        dataframe["at_ema9"] = (abs(dataframe["close"] - dataframe["ema9"]) / dataframe["ema9"] < 0.005)
        dataframe["at_ema21"] = (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.005)
        dataframe["at_ema"] = dataframe["at_ema9"] | dataframe["at_ema21"]
        dataframe["rsi_pullback_long"] = (dataframe["rsi"] > self.buy_rsi_pullback_min.value) & (dataframe["rsi"] < self.buy_rsi_pullback_max.value)
        dataframe["rsi_pullback_short"] = (dataframe["rsi"] > self.sell_rsi_pullback_min.value) & (dataframe["rsi"] < self.sell_rsi_pullback_max.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        short_conditions = (
            (dataframe["ema9"] < dataframe["ema21"])
            & (dataframe["adx"] > self.adx_threshold.value)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & dataframe["rsi_pullback_short"]
            & dataframe["at_ema"]
            & (dataframe["close"] < dataframe["ema200"])
            & (dataframe["ema_1h_bearish"] if "ema_1h_bearish" in dataframe.columns else True)
            & (dataframe["adx_1h"] > self.adx_threshold.value if "adx_1h" in dataframe.columns else True)
        )
        dataframe.loc[short_conditions, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    @property
    def protections(self):
        return {protections_str}
""".format(lev=leverage, stoploss=stoploss, roi_str=roi_str, protections_str=protections_str)

    return code


def run_backtest(strategy_name: str, leverage: int) -> dict:
    """Run backtest for a specific leverage configuration."""
    print("\n" + "=" * 60)
    print("Running backtest for {}x leverage".format(leverage))
    print("=" * 60)

    # Generate strategy file
    strategy_code = generate_leverage_strategy(leverage, LEVERAGE_CONFIGS[leverage])
    temp_strategy_path = os.path.join(
        WORKDIR, "user_data/strategies/test/LeverageTest_{}x.py".format(leverage)
    )

    with open(temp_strategy_path, "w") as f:
        f.write(strategy_code)

    # Run backtest
    cmd = [
        "python",
        "-m",
        "freqtrade",
        "backtesting",
        "--config",
        CONFIG_PATH,
        "--strategy",
        "LeverageTest_{}x".format(leverage),
        "--strategy-path",
        os.path.join(WORKDIR, "user_data/strategies/test"),
        "--timerange",
        TIMERANGE,
        "--pairs",
        PAIRS,
        "--timeframe",
        "15m",
        "--dry-run-wallet",
        "10000",
        "--max-open-trades",
        "5",
        "--export",
        "trades",
        "--backtest-filename",
        "leverage_test_{}x".format(leverage),
    ]

    result = subprocess.run(cmd, cwd=WORKDIR, capture_output=True, text=True, timeout=300)

    # Clean up temp strategy
    try:
        os.remove(temp_strategy_path)
    except:
        pass

    # Parse results
    output = result.stdout + result.stderr
    return parse_backtest_output(output, leverage)


def parse_backtest_output(output: str, leverage: int) -> dict:
    """Parse backtest output to extract key metrics."""
    metrics = {
        "leverage": leverage,
        "config": LEVERAGE_CONFIGS[leverage],
    }

    # Extract metrics using regex - updated patterns to match freqtrade output
    patterns = {
        "trades": r"Total/Daily Avg Trades\s+[|\s]+(\d+)\s*/",
        "profit_pct": r"Total profit %\s+[|\s]+([-+]?\d+\.?\d*)%",
        "profit_total": r"Absolute profit\s+[|\s]+([-+]?\d+\.?\d*)\s*USDT",
        "winrate": r"Win Rate\s+[|\s]+(\d+\.?\d*)%",
        "drawdown": r"Absolute drawdown\s+[|\s]+[\d.]+\s*USDT\s*\([-+]?\d+\.?\d*%\)\s*\n.*?(\d+\.?\d*)%",
        "avg_duration": r"Avg\.\s+duration\s+winners\s+[|\s]+(\d+\.?\d+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, output, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                metrics[key] = float(match.group(1))
            except:
                pass

    # Alternative: Parse from strategy summary table
    summary_pattern = r"Pullback_Scalp_v1_ShortOnly_Leverage_{}\s+\|\s+(\d+)\s+\|\s+([-+]?\d+\.?\d*)\s+\|\s+([-+]?\d+\.?\d*)".format(
        leverage
    )
    summary_match = re.search(summary_pattern, output)
    if summary_match:
        metrics["trades"] = float(summary_match.group(1))
        metrics["profit_pct"] = float(summary_match.group(3))

    return metrics


def print_summary_table(results: list):
    """Print a summary table of all leverage tests."""
    print("\n")
    print("=" * 100)
    print("LEVERAGE IMPACT ANALYSIS SUMMARY")
    print("=" * 100)
    print(
        "{:<5} | {:>10} | {:>8} | {:>7} | {:>7} | {:>10} | {:>10}".format(
            "Lev", "Stoploss", "ROI 0", "Trades", "Win%", "Profit%", "Drawdown%"
        )
    )
    print("-" * 100)

    for r in results:
        lev = r.get("leverage", 0)
        cfg = r.get("config", {})
        stoploss = cfg.get("stoploss", 0) * 100
        roi_0 = BASE_ROI["0"] * cfg.get("roi_mult", 1) * 100
        trades = r.get("trades", 0)
        winrate = r.get("winrate", 0)
        profit = r.get("profit_pct", 0)
        drawdown = r.get("drawdown", 0)

        print(
            "{:<5} | {:>9.2f}% | {:>7.1f}% | {:>7.0f} | {:>6.1f}% | {:>9.1f}% | {:>9.1f}%".format(
                str(lev) + "x", stoploss, roi_0, trades, winrate, profit, drawdown
            )
        )

    print("-" * 100)
    print("\nNotes:")
    print("- Stoploss is adjusted: base 2% / leverage")
    print("- ROI targets are scaled by multiplier to account for increased volatility")
    print("- Higher leverage = tighter stoploss = more frequent stops but smaller losses per trade")
    print("- Higher leverage = lower ROI targets = faster take-profits to avoid liquidation")


def main():
    print("Starting Leverage Impact Analysis")
    print("TimeRange: {}".format(TIMERANGE))
    print("Pairs: {}".format(PAIRS))
    print("Strategy: Pullback_Scalp_v1_ShortOnly_Optimized (base)")

    results = []

    for leverage in [1, 3, 5, 10]:
        try:
            metrics = run_backtest("LeverageTest_{}x".format(leverage), leverage)
            results.append(metrics)
            print(
                "  -> Leverage {}x: {} trades, Profit={}%".format(
                    leverage, metrics.get("trades", "N/A"), metrics.get("profit_pct", "N/A")
                )
            )
        except subprocess.TimeoutExpired:
            print("  [TIMEOUT] Leverage {}x backtest timed out".format(leverage))
            results.append({"leverage": leverage, "error": "timeout"})
        except Exception as e:
            print("  [ERROR] Leverage {}x: {}".format(leverage, str(e)))
            results.append({"leverage": leverage, "error": str(e)})

    # Print summary
    print_summary_table(results)

    # Save results to file
    results_file = os.path.join(
        RESULTS_DIR, "leverage_analysis_{}.json".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    )
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to: {}".format(results_file))

    return results


if __name__ == "__main__":
    main()
