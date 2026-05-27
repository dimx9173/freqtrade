#!/usr/bin/env python3
"""All D3+ and D2+ variants - single run"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

DATA = "user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather"
OUT = "user_data/reports/all_d3_d2_variants.json"

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

df["ema_fast"] = ta.EMA(df["close"], 12)
df["ema_slow"] = ta.EMA(df["close"], 26)
df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
df["rsi"] = ta.RSI(df["close"], 14)


def backtest(df, signal_col, tp, sl, max_bars, pos, label):
    capital, position, entry_price, entry_idx, position_size = 1000, 0, 0, 0, 0
    trades = []
    wins = losses = 0
    win_total = loss_total = 0.0
    max_bal = min_bal = capital
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        sig = row.get(signal_col, 0)
        if position == 0 and sig == 1:
            position = 1
            entry_price = row["close"]
            entry_idx = i
            position_size = capital * pos
        elif position == 0 and sig == -1:
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
                trades.append({"pnl": pnl, "reason": exit_reason})
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
                trades.append({"pnl": pnl, "reason": exit_reason})
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
    print(f"{label}: {ret:+.2f}% | {n}tr | {wr:.1f}W | R={r:.2f} | DD={dd:.1f}% | E={exp:.4f}")
    return {
        "label": label,
        "return": round(ret, 3),
        "trades": n,
        "win_rate": round(wr, 2),
        "r_ratio": round(r, 3),
        "expectancy": round(exp, 4),
        "dd": round(dd, 2),
        "vs_v70": round(ret - (-1.88), 3),
        "wins": wins,
        "losses": losses,
    }


results = []

# === D3 VARIANTS (Short Only) ===
# D3a: Kelly 17%
df["sig"] = 0
df.loc[
    (df["ema_fast"] < df["ema_slow"])
    & (df["adx"] >= 25)
    & (df["minus_di"] > df["plus_di"])
    & (df["rsi"] > 32)
    & (df["rsi"] < 72),
    "sig",
] = -1
results.append(backtest(df, "sig", 5, 2, 24, 0.17, "D3a_Kelly17"))

# D3b: Kelly 25%
results.append(backtest(df, "sig", 5, 2, 24, 0.25, "D3b_Kelly25"))

# D3c: SL 1.5%
results.append(backtest(df, "sig", 5, 1.5, 24, 0.50, "D3c_SL1.5"))

# D3d: TP 6%
results.append(backtest(df, "sig", 6, 2, 24, 0.50, "D3d_TP6"))

# D3e: SL 1.5 + TP 6
results.append(backtest(df, "sig", 6, 1.5, 24, 0.50, "D3e_SL1.5_TP6"))

# D3f: Kelly 17 + SL1.5 + TP6
results.append(backtest(df, "sig", 6, 1.5, 24, 0.17, "D3f_Kelly17_SL1.5_TP6"))

# === D2 VARIANTS (ADX>=30 bidirectional) ===
df["sig"] = 0
df.loc[
    (df["ema_fast"] > df["ema_slow"])
    & (df["adx"] >= 30)
    & (df["plus_di"] > df["minus_di"])
    & (df["rsi"] > 30)
    & (df["rsi"] < 68),
    "sig",
] = 1
df.loc[
    (df["ema_fast"] < df["ema_slow"])
    & (df["adx"] >= 30)
    & (df["minus_di"] > df["plus_di"])
    & (df["rsi"] > 32)
    & (df["rsi"] < 72),
    "sig",
] = -1
results.append(backtest(df, "sig", 5, 2, 24, 0.30, "D2a_bidir30"))
results.append(backtest(df, "sig", 6, 2.5, 24, 0.30, "D2b_bidir30_TP6"))
results.append(backtest(df, "sig", 5, 2, 24, 0.50, "D2c_bidir30_pos50"))

# === D5 VARIANTS ===
# Bidirectional with ADX>=30 (need to set signals fresh)
df["sig"] = 0
df.loc[
    (df["ema_fast"] > df["ema_slow"])
    & (df["adx"] >= 30)
    & (df["plus_di"] > df["minus_di"])
    & (df["rsi"] > 30)
    & (df["rsi"] < 68),
    "sig",
] = 1
df.loc[
    (df["ema_fast"] < df["ema_slow"])
    & (df["adx"] >= 30)
    & (df["minus_di"] > df["plus_di"])
    & (df["rsi"] > 32)
    & (df["rsi"] < 72),
    "sig",
] = -1
results.append(backtest(df, "sig", 5, 2, 24, 0.50, "D5d_bidir30_pos50"))

# ADX>=35 short only
df["sig"] = 0
df.loc[
    (df["ema_fast"] < df["ema_slow"])
    & (df["adx"] >= 35)
    & (df["minus_di"] > df["plus_di"])
    & (df["rsi"] > 32)
    & (df["rsi"] < 72),
    "sig",
] = -1
results.append(backtest(df, "sig", 5, 2, 24, 0.50, "D5e_short35"))

print("\n=== BEST performers ===")
sorted_results = sorted(results, key=lambda x: x["return"], reverse=True)
for r in sorted_results[:5]:
    print(f"  {r['label']}: {r['return']:+.2f}%")

with open(OUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved: {OUT}")
