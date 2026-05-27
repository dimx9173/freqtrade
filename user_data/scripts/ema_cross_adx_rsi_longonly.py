#!/usr/bin/env python3
"""
Pure Technical Indicator Strategy: EMA Cross + ADX + RSI - LONG ONLY
Backtest on 2026-01-16 to 2026-04-30
Compare vs V70 baseline (-1.88%)
Designed for bull market - long bias with tight risk management
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

print("=" * 70)
print("PURE TECHNICAL STRATEGY: EMA CROSS + ADX + RSI (LONG ONLY)")
print("=" * 70)
print()

# Load data
df = pd.read_feather("user_data/data/binance/BTC_USDT-5m.feather")
df["date"] = pd.to_datetime(df["date"])

# Filter for backtest period (using 2024 dates which mirror 2026 period)
start_date = pd.Timestamp("2026-01-16 00:00:00", tz="UTC")
end_date = pd.Timestamp("2026-04-30 23:59:59", tz="UTC")
df_filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()

# Resample to 15m
df_15m = df_filtered.set_index("date")
df_15m = (
    df_15m.resample("15min")
    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    .dropna()
)
df_15m = df_15m.reset_index()

# Calculate Technical Indicators
df_15m["ema_fast"] = ta.EMA(df_15m["close"].values, timeperiod=12)
df_15m["ema_slow"] = ta.EMA(df_15m["close"].values, timeperiod=26)
df_15m["adx"] = ta.ADX(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)
df_15m["plus_di"] = ta.PLUS_DI(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)
df_15m["minus_di"] = ta.MINUS_DI(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)
df_15m["rsi"] = ta.RSI(df_15m["close"].values, timeperiod=14)
df_15m["atr"] = ta.ATR(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)

# Simple strategy parameters
ADX_MIN = 25  # ADX must be above this to confirm trend
RSI_MAX_LONG = 68  # RSI below this for long entry (not overbought)
RSI_MIN_LONG = 38  # RSI above this for long entry (not oversold)
PROFIT_TARGET = 0.06  # 6% profit target
STOP_LOSS = 0.025  # 2.5% stop loss
MAX_BARS = 24  # Max 6 hours (24 x 15min)

initial_capital = 10000
capital = initial_capital
position = None
trades = []

print("=" * 70)
print("BACKTEST RESULTS: EMA CROSS + ADX + RSI (LONG ONLY)")
print("=" * 70)
print()

for i, (idx, row) in enumerate(df_15m.iterrows()):
    current_close = row["close"]
    current_ema_fast = row["ema_fast"]
    current_ema_slow = row["ema_slow"]
    current_adx = row["adx"]
    current_plus_di = row["plus_di"]
    current_minus_di = row["minus_di"]
    current_rsi = row["rsi"]
    current_atr = row["atr"]

    if np.isnan(current_ema_fast) or np.isnan(current_adx) or np.isnan(current_rsi):
        continue

    # === ENTRY LOGIC ===
    if position is None:
        # Bullish EMA crossover
        ema_bullish_cross = (
            i > 0
            and df_15m.iloc[i - 1]["ema_fast"] <= df_15m.iloc[i - 1]["ema_slow"]
            and current_ema_fast > current_ema_slow
        )

        if ema_bullish_cross:
            # Trend confirmation: ADX above threshold and +DI > -DI
            if current_adx >= ADX_MIN and current_plus_di > current_minus_di:
                # RSI in valid range (not overbought, not oversold)
                if RSI_MIN_LONG <= current_rsi <= RSI_MAX_LONG:
                    position = {
                        "entry_price": current_close,
                        "entry_idx": i,
                        "entry_atr": current_atr,
                    }

    # === EXIT LOGIC ===
    if position is not None:
        exit_signal = False
        exit_reason = ""
        bars_held = i - position["entry_idx"]
        entry_price = position["entry_price"]
        profit_pct = (current_close - entry_price) / entry_price

        # EMA reversal (fast crosses below slow)
        if current_ema_fast < current_ema_slow:
            exit_signal = True
            exit_reason = "EMA_Reversal"

        # Profit target
        if not exit_signal and profit_pct >= PROFIT_TARGET:
            exit_signal = True
            exit_reason = f"ProfitTarget({profit_pct * 100:.1f}%)"

        # Stop loss
        if not exit_signal and profit_pct <= -STOP_LOSS:
            exit_signal = True
            exit_reason = f"StopLoss({profit_pct * 100:.2f}%)"

        # Time exit
        if not exit_signal and bars_held >= MAX_BARS:
            exit_signal = True
            exit_reason = f"TimeExit({bars_held})"

        if exit_signal:
            stake = capital * 0.95
            profit = (current_close - entry_price) * (stake / entry_price)
            fees = stake * 0.001 * 2
            profit -= fees
            capital += profit

            trades.append(
                {
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit_pct": profit_pct * 100,
                    "profit": profit,
                    "bars": bars_held,
                    "win": profit > 0,
                    "exit_reason": exit_reason,
                }
            )

            position = None

# Close open position at end
if position is not None:
    last_row = df_15m.iloc[-1]
    entry_price = position["entry_price"]
    stake = capital * 0.95
    profit = (last_row["close"] - entry_price) * (stake / entry_price)
    fees = stake * 0.001 * 2
    profit -= fees
    capital += profit
    profit_pct = (last_row["close"] - entry_price) / entry_price

    trades.append(
        {
            "entry_price": entry_price,
            "exit_price": last_row["close"],
            "profit_pct": profit_pct * 100,
            "profit": profit,
            "bars": i - position["entry_idx"],
            "win": profit > 0,
            "exit_reason": "EndOfPeriod",
        }
    )

# Results
total_return = (capital - initial_capital) / initial_capital * 100
total_trades = len(trades)
win_rate = sum(1 for t in trades if t["win"]) / max(1, total_trades) * 100

print(f"Initial Capital: ${initial_capital:,.2f}")
print(f"Final Capital:   ${capital:,.2f}")
print(f"Total Return:    {total_return:+.2f}%")
print(f"VS V70 Baseline: -1.88%")
print(f"Difference:      {total_return - (-1.88):+.2f}%")
print()
print(f"Total Trades:    {total_trades}")
print(f"Win Rate:        {win_rate:.1f}%")
print()

if trades:
    avg_profit = sum(t["profit"] for t in trades) / len(trades)
    avg_bars = sum(t["bars"] for t in trades) / len(trades)
    print(f"Average Profit per Trade: ${avg_profit:+.2f}")
    print(f"Average Bars Held:         {avg_bars:.1f}")

# Save results
results = {
    "strategy": "EMA_Cross_ADX_RSI_LongOnly",
    "period": f"{start_date.date()} to {end_date.date()}",
    "initial_capital": initial_capital,
    "final_capital": capital,
    "total_return": total_return,
    "vs_v70_baseline": -1.88,
    "difference_vs_v70": total_return - (-1.88),
    "total_trades": total_trades,
    "win_rate": win_rate,
}

with open(
    "/home/brian/freqtrade/user_data/reports/ema_cross_adx_rsi_longonly_results.json", "w"
) as f:
    json.dump(results, f, indent=2)

print()
print("=" * 70)
print("COMPARISON SUMMARY")
print("=" * 70)
print(f"  V70 Baseline:              -1.88%")
print(f"  Long Only Strategy:         {total_return:+.2f}%")
print(f"  Difference:                {total_return - (-1.88):+.2f}%")
if total_return > -1.88:
    print("  ✓ OUTPERFORMS V70")
else:
    print("  ✗ UNDERPERFORMS V70")
print("=" * 70)
