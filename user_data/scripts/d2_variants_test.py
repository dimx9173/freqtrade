#!/usr/bin/env python3
"""
D2+ Variants Testing
Test all D2+ variants against D2 baseline (+6.79%)

Variants:
- D2 Baseline: ADX>=30, long only, TP=6%, SL=2.5%
- D2A: ADX>=30 bidirectional (long+short), TP=6%, SL=2.5%
- D2B: ADX>=35 strong trend only (higher ADX threshold)
- D2C: ADX>=30, TP=8%, SL=2% (wider TP)
- D2D: ADX>=30, TP=5%, SL=1.5% (tighter SL)
- D2E: ADX>=35 bidirectional, TP=7%, SL=2%
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json
import os

DATA = "user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather"
OUTDIR = "user_data/reports"
os.makedirs(OUTDIR, exist_ok=True)

# Load and prepare data once
print("Loading data...")
df = pd.read_feather(DATA)
df["date"] = pd.to_datetime(df["date"])
df = df[(df["date"] >= "2026-01-16") & (df["date"] <= "2026-04-30")].set_index("date")
df = (
    df.resample("15min")
    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    .dropna()
    .reset_index()
)
print(
    f"BTC: {df['close'].iloc[0]:.0f} -> {df['close'].iloc[-1]:.0f} ({((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.1f}%)"
)

# Calculate indicators once
print("Calculating indicators...")
df["ema_fast"] = ta.EMA(df["close"], 12)
df["ema_slow"] = ta.EMA(df["close"], 26)
df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
df["rsi"] = ta.RSI(df["close"], 14)

# Long signal: ema_fast > ema_slow, ADX threshold, +DI > -DI, RSI in range
# Short signal: ema_fast < ema_slow, ADX threshold, -DI > +DI, RSI in range


def run_backtest(df, name, adx_thresh, tp_pct, sl_pct, max_bars, pos_pct, direction):
    """Run backtest for a given configuration"""
    # direction: 'long', 'short', 'both'
    if direction == "long":
        signal_col = (
            (df["ema_fast"] > df["ema_slow"])
            & (df["adx"] >= adx_thresh)
            & (df["plus_di"] > df["minus_di"])
            & (df["rsi"] > 30)
            & (df["rsi"] < 68)
        )
    elif direction == "short":
        signal_col = (
            (df["ema_fast"] < df["ema_slow"])
            & (df["adx"] >= adx_thresh)
            & (df["minus_di"] > df["plus_di"])
            & (df["rsi"] > 32)
            & (df["rsi"] < 72)
        )
    else:  # both
        long_sig = (
            (df["ema_fast"] > df["ema_slow"])
            & (df["adx"] >= adx_thresh)
            & (df["plus_di"] > df["minus_di"])
            & (df["rsi"] > 30)
            & (df["rsi"] < 68)
        )
        short_sig = (
            (df["ema_fast"] < df["ema_slow"])
            & (df["adx"] >= adx_thresh)
            & (df["minus_di"] > df["plus_di"])
            & (df["rsi"] > 32)
            & (df["rsi"] < 72)
        )
        signal_col = long_sig.astype(int) + short_sig.astype(int) * -1

    signal_col = signal_col.astype(int)

    capital, position = 1000, 0
    entry_price = entry_idx = position_size = 0
    trades = []
    wins = losses = 0
    win_total = loss_total = 0.0
    max_bal = min_bal = capital

    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        sig = signal_col.iloc[i]

        if position == 0:
            if direction == "long" and sig == 1:
                position = 1
                entry_price = row["close"]
                entry_idx = i
                position_size = capital * pos_pct
            elif direction == "short" and sig == -1:
                position = -1
                entry_price = row["close"]
                entry_idx = i
                position_size = capital * pos_pct
            elif direction == "both":
                if sig == 1:
                    position = 1
                    entry_price = row["close"]
                    entry_idx = i
                    position_size = capital * pos_pct
                elif sig == -1:
                    position = -1
                    entry_price = row["close"]
                    entry_idx = i
                    position_size = capital * pos_pct
        elif position == 1:
            pnl_pct = (row["close"] - entry_price) / entry_price
            exit_reason = ""
            if pnl_pct >= tp_pct / 100:
                exit_reason = "TP"
            elif pnl_pct <= -sl_pct / 100:
                exit_reason = "SL"
            elif i - entry_idx >= max_bars:
                exit_reason = "TIME"
            if exit_reason:
                pnl = position_size * pnl_pct
                capital += pnl
                trades.append({"pnl": pnl, "reason": exit_reason, "dir": "LONG"})
                if pnl > 0:
                    wins += 1
                    win_total += pnl
                else:
                    losses += 1
                    loss_total += abs(pnl)
                position = 0
        elif position == -1:
            pnl_pct = (entry_price - row["close"]) / entry_price
            exit_reason = ""
            if pnl_pct >= tp_pct / 100:
                exit_reason = "TP"
            elif pnl_pct <= -sl_pct / 100:
                exit_reason = "SL"
            elif i - entry_idx >= max_bars:
                exit_reason = "TIME"
            if exit_reason:
                pnl = position_size * pnl_pct
                capital += pnl
                trades.append({"pnl": pnl, "reason": exit_reason, "dir": "SHORT"})
                if pnl > 0:
                    wins += 1
                    win_total += pnl
                else:
                    losses += 1
                    loss_total += abs(pnl)
                position = 0

        if capital > max_bal:
            max_bal = capital
        if capital < min_bal:
            min_bal = capital

    n = len(trades)
    wr = wins / n * 100 if n > 0 else 0
    avg_win = win_total / wins if wins > 0 else 0
    avg_loss = loss_total / losses if losses > 0 else 0
    r = avg_win / avg_loss if avg_loss > 0 else 0
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    dd = ((max_bal - min_bal) / max_bal) * 100
    ret = ((capital - 1000) / 1000) * 100

    print(f"  {name}: {ret:+.2f}% | Trades:{n} | WinRate:{wr:.1f}% | R:{r:.2f} | DD:{dd:.2f}%")

    return {
        "name": name,
        "return": round(ret, 3),
        "trades": n,
        "win_rate": round(wr, 2),
        "r_ratio": round(r, 3),
        "expectancy": round(exp, 4),
        "dd": round(dd, 2),
        "vs_d2_baseline": round(ret - 6.79, 3),
        "wins": wins,
        "losses": losses,
    }


# Configuration variants
variants = [
    # name, adx_thresh, tp, sl, max_bars, pos_pct, direction
    ("D2_baseline", 30, 6, 2.5, 24, 0.50, "long"),  # reference
    ("D2A_bidir", 30, 6, 2.5, 24, 0.50, "both"),  # bidirectional
    ("D2B_strong35", 35, 6, 2.5, 24, 0.50, "long"),  # ADX>=35
    ("D2C_widerTP", 30, 8, 2.0, 24, 0.50, "long"),  # wider TP
    ("D2D_tighterSL", 30, 5, 1.5, 24, 0.50, "long"),  # tighter SL
    ("D2E_bidir35", 35, 7, 2.0, 24, 0.50, "both"),  # both high ADX
]

print("\n" + "=" * 70)
print("D2+ VARIANTS TESTING vs D2 BASELINE (+6.79%)")
print("=" * 70)
print()

results = []
for name, adx_th, tp, sl, max_b, pos, direction in variants:
    r = run_backtest(df, name, adx_th, tp, sl, max_b, pos, direction)
    results.append(r)

print()
print("=" * 70)
print("SUMMARY TABLE")
print("=" * 70)
print(f"{'Name':<18} {'Return':>8} {'Trades':>7} {'WinRate':>8} {'R':>6} {'DD':>7} {'vs D2':>8}")
print("-" * 70)
for r in results:
    flag = " *" if r["vs_d2_baseline"] > 0 else ""
    print(
        f"{r['name']:<18} {r['return']:>+7.2f}% {r['trades']:>7} {r['win_rate']:>7.1f}% {r['r_ratio']:>6.2f} {r['dd']:>6.2f}% {r['vs_d2_baseline']:>+7.2f}%{flag}"
    )
print("=" * 70)
print("* = outperforms D2 baseline")

# Save results
with open(f"{OUTDIR}/d2_variants_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to {OUTDIR}/d2_variants_results.json")
