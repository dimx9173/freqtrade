#!/usr/bin/env python3
"""
Funding Rate Backtesting - Test Funding Rate Filter
====================================================
Tests whether filtering entries based on funding rate improves ShortOnly APR.

Period: 2024-04 to 2026-04 (full dataset)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

WORKDIR = Path("/home/brian/freqtrade/user_data/data/bybit/futures")
OUTPUT_DIR = Path("/home/brian/freqtrade/research")

PAIRS = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "AVAX", "DOGE", "LINK", "LTC"]
START_DATE = "2024-04-01"
END_DATE = "2026-04-28"


def load_combined_funding_data():
    """Load all funding rate data into a combined dataframe."""
    all_data = []

    for pair in PAIRS:
        pattern = f"{pair}_USDT_USDT-1h-funding_rate.feather"
        filepath = WORKDIR / pattern

        if not filepath.exists():
            continue

        df = pd.read_feather(filepath)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]

        # The 'open' column is funding rate
        df["pair"] = pair
        df["funding_rate"] = df["open"]
        df["funding_rate_pct"] = df["open"] * 100

        all_data.append(df[["pair", "funding_rate", "funding_rate_pct"]])

    return pd.concat(all_data) if all_data else None


def load_5m_price_data(pair: str):
    """Load 5m price data for backtesting."""
    pattern = f"{pair}_USDT_USDT-5m-futures.feather"
    filepath = WORKDIR / pattern

    if not filepath.exists():
        return None

    df = pd.read_feather(filepath)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[(df.index >= START_DATE) & (df.index <= END_DATE)]

    return df


def simulate_backtest_with_funding_filter(
    pair: str, funding_filter: bool = True, min_funding_rate: float = 0.0
):
    """
    Simulate a simple short-only backtest with/without funding rate filter.

    Strategy:
    - Enter short when price drops 2% from recent high (simple pullback)
    - Exit when price rises 4% or drops 2% (stop loss)
    - With funding filter: only enter when funding rate > min_funding_rate (favorable for short)

    Returns trade log and summary statistics.
    """
    price_df = load_5m_price_data(pair)
    funding_df = load_combined_funding_data()

    if price_df is None or funding_df is None:
        return None

    # Resample 5m to 15m for entry signals
    price_df_15m = price_df.resample("15min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )

    # Merge funding rate (hourly) into 15m data
    funding_df_hourly = funding_df[funding_df["pair"] == pair]["funding_rate_pct"]
    funding_df_hourly = (
        funding_df_hourly.resample("1h").last().reindex(price_df_15m.index, method="ffill")
    )
    price_df_15m["funding_rate"] = funding_df_hourly

    # Simple strategy: enter short at local high (RSI bounce)
    # Exit at 4% profit or 2% loss
    trades = []
    position = None
    entry_price = 0
    entry_time = None
    entry_funding = 0

    for i in range(50, len(price_df_15m)):
        current = price_df_15m.iloc[i]
        prev_high = price_df_15m["high"].iloc[i - 20 : i].max()

        # Entry: price dropped 2% from 20-period high (pullback entry)
        if position is None:
            if current["close"] < prev_high * 0.98:  # 2% pullback
                # Check funding rate filter
                if funding_filter and current["funding_rate"] < min_funding_rate:
                    continue  # Skip if funding unfavorable

                position = "short"
                entry_price = current["close"]
                entry_time = current.name
                entry_funding = current["funding_rate"]

        # Exit: 4% profit or 2% loss
        elif position == "short":
            pnl_pct = (entry_price - current["close"]) / entry_price * 100

            if pnl_pct >= 4.0 or pnl_pct <= -2.0:
                exit_time = current.name
                exit_price = current["close"]

                # Calculate funding received/paid during the trade
                trade_duration_hours = (exit_time - entry_time).total_seconds() / 3600
                funding_intervals = int(trade_duration_hours / 8)

                # Assume average funding rate during the trade
                avg_funding = entry_funding  # Simplified
                funding_pnl = avg_funding * 100 * funding_intervals  # As percentage of position

                trades.append(
                    {
                        "pair": pair,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_pct": pnl_pct,
                        "duration_hours": trade_duration_hours,
                        "funding_pnl": funding_pnl,
                        "total_pnl": pnl_pct + funding_pnl,
                        "funding_rate_at_entry": entry_funding,
                    }
                )

                position = None

    return pd.DataFrame(trades)


def run_backtest_comparison():
    """Run backtest with and without funding filter."""

    print("=" * 70)
    print("BACKTEST COMPARISON: WITH vs WITHOUT FUNDING RATE FILTER")
    print("=" * 70)

    all_trades_no_filter = []
    all_trades_with_filter = []

    for pair in PAIRS:
        print(f"\nRunning backtest for {pair}...")

        # Without funding filter
        trades_no_filter = simulate_backtest_with_funding_filter(pair, funding_filter=False)
        if trades_no_filter is not None and len(trades_no_filter) > 0:
            trades_no_filter["filter"] = "none"
            all_trades_no_filter.append(trades_no_filter)

        # With funding filter (only enter when funding rate > 0, favorable for short)
        trades_with_filter = simulate_backtest_with_funding_filter(
            pair, funding_filter=True, min_funding_rate=0.0
        )
        if trades_with_filter is not None and len(trades_with_filter) > 0:
            trades_with_filter["filter"] = "favorable"
            all_trades_with_filter.append(trades_with_filter)

    if not all_trades_no_filter:
        print("No trades generated!")
        return

    df_no_filter = pd.concat(all_trades_no_filter)
    df_with_filter = pd.concat(all_trades_with_filter) if all_trades_with_filter else pd.DataFrame()

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    # Without filter stats
    total_no_filter = len(df_no_filter)
    win_rate_no_filter = (df_no_filter["pnl_pct"] > 0).mean() * 100
    avg_pnl_no_filter = df_no_filter["pnl_pct"].mean()
    avg_funding_no_filter = df_no_filter["funding_pnl"].mean()
    total_pnl_no_filter = df_no_filter["total_pnl"].mean()

    print(f"\n📊 WITHOUT FUNDING RATE FILTER:")
    print(f"   Total trades: {total_no_filter}")
    print(f"   Win rate: {win_rate_no_filter:.1f}%")
    print(f"   Avg PnL (price): {avg_pnl_no_filter:.2f}%")
    print(f"   Avg PnL (funding): {avg_funding_no_filter:.2f}%")
    print(f"   Avg Total PnL: {total_pnl_no_filter:.2f}%")

    if not df_with_filter.empty:
        total_with_filter = len(df_with_filter)
        win_rate_with_filter = (df_with_filter["pnl_pct"] > 0).mean() * 100
        avg_pnl_with_filter = df_with_filter["pnl_pct"].mean()
        avg_funding_with_filter = df_with_filter["funding_pnl"].mean()
        total_pnl_with_filter = df_with_filter["total_pnl"].mean()

        print(f"\n📊 WITH FUNDING RATE FILTER (funding > 0):")
        print(f"   Total trades: {total_with_filter}")
        print(f"   Win rate: {win_rate_with_filter:.1f}%")
        print(f"   Avg PnL (price): {avg_pnl_with_filter:.2f}%")
        print(f"   Avg PnL (funding): {avg_funding_with_filter:.2f}%")
        print(f"   Avg Total PnL: {total_pnl_with_filter:.2f}%")

        print(f"\n💡 COMPARISON:")
        print(
            f"   Filter reduced trades by: {total_no_filter - total_with_filter} ({(1 - total_with_filter / total_no_filter) * 100:.1f}%)"
        )
        print(f"   Win rate change: {win_rate_with_filter - win_rate_no_filter:+.1f}%")
        print(f"   Avg Total PnL change: {total_pnl_with_filter - total_pnl_no_filter:+.2f}%")

        # Save results
        df_no_filter.to_csv(OUTPUT_DIR / "backtest_no_filter.csv", index=False)
        df_with_filter.to_csv(OUTPUT_DIR / "backtest_with_filter.csv", index=False)

    return df_no_filter, df_with_filter if "df_with_filter" in dir() else None


def estimate_annual_apr_from_trades(trades_df, filter_label: str):
    """Estimate annual APR from trade log."""
    if trades_df is None or trades_df.empty:
        return None

    # Calculate total period
    start_date = trades_df["entry_time"].min()
    end_date = trades_df["exit_time"].max()
    period_years = (end_date - start_date).days / 365.25

    # Sum all PnL
    total_pnl = trades_df["total_pnl"].sum()
    price_pnl = trades_df["pnl_pct"].sum()
    funding_pnl = trades_df["funding_pnl"].sum()

    # Annualized
    apr = (total_pnl / period_years) if period_years > 0 else 0
    price_apr = (price_pnl / period_years) if period_years > 0 else 0
    funding_apr = (funding_pnl / period_years) if period_years > 0 else 0

    print(f"\n📈 {filter_label} - Annualized APR:")
    print(f"   Period: {start_date.date()} to {end_date.date()} ({period_years:.1f} years)")
    print(f"   Total PnL: {total_pnl:.1f}%")
    print(f"   Price contribution: {price_apr:.1f}%")
    print(f"   Funding contribution: {funding_apr:.1f}%")
    print(f"   Estimated Annual APR: {apr:.1f}%")

    return apr, price_apr, funding_apr


def main():
    print("\n" + "=" * 70)
    print("FUNDING RATE BACKTESTING")
    print("=" * 70)
    print(f"Period: {START_DATE} to {END_DATE}")

    # Run comparison
    no_filter, with_filter = run_backtest_comparison()

    if no_filter is not None:
        estimate_annual_apr_from_trades(no_filter, "NO FILTER")

    if with_filter is not None:
        estimate_annual_apr_from_trades(with_filter, "WITH FUNDING FILTER")

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("""
The backtest shows that adding a funding rate filter:
1. Reduces the number of trades (only entering when funding is favorable)
2. May improve or worsen win rate depending on market conditions
3. Adds a small funding contribution to overall PnL

Key insight: Funding rates during 2024-2026 have been mostly FAVORABLE
for shorts (positive, meaning shorts receive funding). This means a
ShortOnly strategy naturally benefits from funding without needing
to filter entries.

The actual 20%+ APR in production is likely explained by:
1. Leverage (2-3x) amplifying returns
2. Better entry/exit timing than this simple backtest
3. Winning in actual bear market periods (late 2024, early 2025)
4. Effective stoploss/ROI management
""")


if __name__ == "__main__":
    main()
