#!/usr/bin/env python3
"""D5: Low-DD bidirectional combining D2's ADX>=30 filter + D3's short bias"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json
from itertools import product

NAME = "d5_low_dd_bidir"
DATA = "user_data/data/binance/BTC_USDT-5m.feather"

print(f"Loading data from {DATA}...")
df = pd.read_feather(DATA)
df["date"] = pd.to_datetime(df["date"])
df = df[(df["date"] >= "2024-01-16") & (df["date"] <= "2024-04-30")].set_index("date")
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
df["ema_fast"] = ta.EMA(df["close"], 12)
df["ema_slow"] = ta.EMA(df["close"], 26)
df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
df["rsi"] = ta.RSI(df["close"], 14)

# D5: ADX>=30 (from D2) + short bias conditions from D3 + bidirectional
# Long: ema_fast > ema_slow, adx >= 30, plus_di > minus_di, rsi > 30 & < 68
# Short: ema_fast < ema_slow, adx >= 30, minus_di > plus_di, rsi > 32 & < 72


def run_backtest(df, tp, sl, max_bars, pos, adx_thresh=30, rsi_long=(30, 68), rsi_short=(32, 72)):
    long_cond = (
        (df["ema_fast"] > df["ema_slow"])
        & (df["adx"] >= adx_thresh)
        & (df["plus_di"] > df["minus_di"])
        & (df["rsi"] > rsi_long[0])
        & (df["rsi"] < rsi_long[1])
    )
    short_cond = (
        (df["ema_fast"] < df["ema_slow"])
        & (df["adx"] >= adx_thresh)
        & (df["minus_di"] > df["plus_di"])
        & (df["rsi"] > rsi_short[0])
        & (df["rsi"] < rsi_short[1])
    )

    signal = 0
    signal = np.where(long_cond, 1, signal)
    signal = np.where(short_cond, -1, signal)
    df["signal"] = signal

    capital, position, entry_price, entry_idx, position_size = 1000, 0, 0, 0, 0
    trades = []
    wins = losses = 0
    win_total = loss_total = 0.0
    max_bal = min_bal = capital

    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        if position == 0 and row["signal"] == 1:
            position = 1
            entry_price = row["close"]
            entry_idx = i
            position_size = capital * pos
        elif position == 0 and row["signal"] == -1:
            position = -1
            entry_price = row["close"]
            entry_idx = i
            position_size = capital * pos
        elif position == 1:
            pnl_pct = (row["close"] - entry_price) / entry_price
            exit_reason = ""
            if pnl_pct >= tp / 100:
                exit_reason = "TP"
            elif pnl_pct <= -sl / 100:
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
            if pnl_pct >= tp / 100:
                exit_reason = "TP"
            elif pnl_pct <= -sl / 100:
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

    return {
        "return": round(ret, 3),
        "trades": n,
        "win_rate": round(wr, 2),
        "r_ratio": round(r, 3),
        "expectancy": round(exp, 4),
        "dd": round(dd, 2),
        "vs_v70": round(ret - (-1.88), 3),
        "wins": wins,
        "losses": losses,
        "tp": tp,
        "sl": sl,
        "max_bars": max_bars,
        "pos": pos,
    }


# Test multiple parameter combinations - focus on Low-DD
print("\n" + "=" * 80)
print("D5: Low-DD Bidirectional (ADX>=30 + D3 short bias conditions)")
print("=" * 80)

# Parameter grid - emphasizing low DD
tp_vals = [4, 5, 6]
sl_vals = [2, 2.5, 3]
max_bars_vals = [20, 24, 30]
pos_vals = [0.25, 0.30, 0.40]

results = []
combo_count = 0

for tp, sl, max_bars, pos in product(tp_vals, sl_vals, max_bars_vals, pos_vals):
    combo_count += 1
    result = run_backtest(df.copy(), tp, sl, max_bars, pos)
    results.append(result)

# Sort by DD (lowest first), then by return (highest)
results_sorted = sorted(results, key=lambda x: (x["dd"], -x["return"]))

print(f"\nTested {combo_count} parameter combinations")
print("\nTop 10 Low-DD configurations:")
print("-" * 100)
print(
    f"{'TP':>3} {'SL':>4} {'MB':>4} {'POS':>5} {'Return':>8} {'DD':>6} {'WR':>6} {'R':>6} {'Exp':>8} {'Trades':>6}"
)
print("-" * 100)

for i, r in enumerate(results_sorted[:10]):
    print(
        f"{r['tp']:>3} {r['sl']:>4} {r['max_bars']:>4} {r['pos']:>5.2f} {r['return']:>8.2f} {r['dd']:>6.2f} {r['win_rate']:>6.1f} {r['r_ratio']:>6.2f} {r['expectancy']:>8.4f} {r['trades']:>6}"
    )

# Best low-DD config
best = results_sorted[0]
print(f"\n*** BEST LOW-DD CONFIG ***")
print(f"TP:{best['tp']}% SL:{best['sl']}% MaxBars:{best['max_bars']} Pos:{best['pos'] * 100:.0f}%")
print(
    f"Return: {best['return']:.2f}% | DD: {best['dd']:.2f}% | Win%: {best['win_rate']:.1f} | R:{best['r_ratio']}:1 | Exp:{best['expectancy']:.4f}"
)
print(f"vs V70: {best['vs_v70']:+.2f}%")

# Also show best return config for comparison
best_return = max(results, key=lambda x: x["return"])
print(f"\n*** BEST RETURN CONFIG ***")
print(
    f"TP:{best_return['tp']}% SL:{best_return['sl']}% MaxBars:{best_return['max_bars']} Pos:{best_return['pos'] * 100:.0f}%"
)
print(
    f"Return: {best_return['return']:.2f}% | DD: {best_return['dd']:.2f}% | Win%: {best_return['win_rate']:.1f} | R:{best_return['r_ratio']}:1 | Exp:{best_return['expectancy']:.4f}"
)

# Save results
with open("user_data/reports/d5_results.json", "w") as f:
    json.dump(
        {
            "strategy": NAME,
            "best_low_dd": best,
            "best_return": best_return,
            "all_results": results_sorted[:20],
        },
        f,
        indent=2,
    )
print(f"\nResults saved to user_data/reports/d5_results.json")
