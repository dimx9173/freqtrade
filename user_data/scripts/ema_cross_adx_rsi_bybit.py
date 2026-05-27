#!/usr/bin/env python3
"""
Pure Technical EMA Cross + ADX + RSI Strategy on Bybit Futures
Backtest: 2026-01-16 to 2026-04-30 (Same as V70/V94/V95)
Compare vs V70 baseline (-1.88%)
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

print("=" * 70)
print("PURE TECHNICAL: EMA CROSS + ADX + RSI on BYBIT FUTURES")
print("Period: 2026-01-16 to 2026-04-30")
print("=" * 70)

# Load Bybit futures data
df = pd.read_feather("user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather")
df["date"] = pd.to_datetime(df["date"])
print(f"Loaded {len(df)} rows: {df.date.min()} to {df.date.max()}")

# Filter for backtest period
start_date = pd.Timestamp("2026-01-16 00:00:00", tz="UTC")
end_date = pd.Timestamp("2026-04-30 23:59:59", tz="UTC")
df_filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
print(f"Filtered: {len(df_filtered)} rows")
print(
    f"BTC change: {df_filtered['close'].iloc[0]:.2f} -> {df_filtered['close'].iloc[-1]:.2f} ({((df_filtered['close'].iloc[-1] / df_filtered['close'].iloc[0]) - 1) * 100:.1f}%)"
)

# Resample to 15m
df_15m = df_filtered.set_index("date")
df_15m = (
    df_15m.resample("15min")
    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    .dropna()
    .reset_index()
)
print(f"Resampled to 15m: {len(df_15m)} rows")

# Calculate indicators
df_15m["ema_fast"] = ta.EMA(df_15m["close"], timeperiod=12)
df_15m["ema_slow"] = ta.EMA(df_15m["close"], timeperiod=26)
df_15m["adx"] = ta.ADX(df_15m["high"], df_15m["low"], df_15m["close"], timeperiod=14)
df_15m["plus_di"] = ta.PLUS_DI(df_15m["high"], df_15m["low"], df_15m["close"], timeperiod=14)
df_15m["minus_di"] = ta.MINUS_DI(df_15m["high"], df_15m["low"], df_15m["close"], timeperiod=14)
df_15m["rsi"] = ta.RSI(df_15m["close"], timeperiod=14)

# Entry/exit signals
df_15m["ema_cross"] = (df_15m["ema_fast"] > df_15m["ema_slow"]).astype(int)
df_15m["ema_cross_prev"] = df_15m["ema_cross"].shift(1)

# Long: EMA cross up + ADX trend confirmation + RSI filter
long_condition = (
    (df_15m["ema_fast"] > df_15m["ema_slow"])
    & (df_15m["adx"] >= 25)
    & (df_15m["plus_di"] > df_15m["minus_di"])
    & (df_15m["rsi"] > 30)
    & (df_15m["rsi"] < 68)
)
df_15m["signal"] = 0
df_15m.loc[long_condition, "signal"] = 1

# Backtest
capital = 1000
position = 0
entry_price = 0
trades = []
wins = 0
losses = 0
win_total = 0
loss_total = 0
min_balance = capital
max_balance = capital

for i in range(50, len(df_15m) - 1):
    row = df_15m.iloc[i]

    # Entry
    if position == 0 and row["signal"] == 1:
        position = 1
        entry_price = row["close"]
        entry_idx = i

    # Exit: 6% profit OR 2.5% stop OR 24 bars
    elif position == 1:
        exit_price = row["close"]
        pnl_pct = (exit_price - entry_price) / entry_price

        should_exit = False
        exit_reason = ""

        if pnl_pct >= 0.06:
            should_exit = True
            exit_reason = "TP"
        elif pnl_pct <= -0.025:
            should_exit = True
            exit_reason = "SL"
        elif i - entry_idx >= 24:
            should_exit = True
            exit_reason = "TIME"

        if should_exit:
            pnl = capital * pnl_pct
            capital += pnl
            trades.append({"pnl": pnl, "pnl_pct": pnl_pct, "reason": exit_reason})
            if pnl > 0:
                wins += 1
                win_total += pnl
            else:
                losses += 1
                loss_total += abs(pnl)
            position = 0

    # Track balance
    if capital > max_balance:
        max_balance = capital
    if capital < min_balance:
        min_balance = capital

total_return = ((capital - 1000) / 1000) * 100
drawdown = ((max_balance - min_balance) / max_balance) * 100

print(f"\n=== RESULTS ===")
print(f"Initial Capital: $1000.00")
print(f"Final Capital:   ${capital:.2f}")
print(f"Total Return:    {total_return:.2f}%")
print(f"Total Trades:    {len(trades)}")
print(f"Win Rate:        {wins / len(trades) * 100:.1f}% if len(trades) > 0 else 0")
print(f"Drawdown:        {drawdown:.2f}%")
print(f"\nV70 Baseline:    -1.88%")
print(f"Difference:      {total_return - (-1.88):+.2f}%")
if total_return > -1.88:
    print("✓ OUTPERFORMS V70")
else:
    print("✗ UNDERPERFORMS V70")

# Save results
results = {
    "strategy": "EMA_Cross_ADX_RSI_LongOnly",
    "period": "2026-01-16 to 2026-04-30",
    "data": "Bybit BTC/USDT futures 15m",
    "total_return": total_return,
    "trades": len(trades),
    "win_rate": wins / len(trades) * 100 if len(trades) > 0 else 0,
    "drawdown_pct": drawdown,
    "vs_v70": total_return - (-1.88),
    "v70_baseline": -1.88,
}
with open("user_data/reports/ema_cross_bybit_2026.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to user_data/reports/ema_cross_bybit_2026.json")
