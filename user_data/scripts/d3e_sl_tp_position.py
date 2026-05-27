#!/usr/bin/env python3
"""D3e: SL/TP grid + position sizing + time-of-day analysis"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

OUT = "user_data/reports/d3e_sl_tp_position.json"


def load(pair="BTC"):
    df = pd.read_feather(f"user_data/data/bybit/futures/{pair}_USDT_USDT-5m-futures.feather")
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= "2026-01-16") & (df["date"] <= "2026-04-30")].set_index("date")
    df = (
        df.resample("15min")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    print(
        f"{pair}: {df['close'].iloc[0]:.0f}->{df['close'].iloc[-1]:.0f} ({((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.1f}%)"
    )
    return df


def indicators(df, fast=21, slow=50):
    df = df.copy()
    df["ema_fast"] = ta.EMA(df["close"], fast)
    df["ema_slow"] = ta.EMA(df["close"], slow)
    df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
    df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
    df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
    df["rsi"] = ta.RSI(df["close"], 14)
    df["hour"] = df["date"].dt.hour
    return df


def signal(df):
    df = df.copy()
    df["signal"] = 0
    df.loc[
        (df["ema_fast"] < df["ema_slow"])
        & (df["adx"] >= 25)
        & (df["minus_di"] > df["plus_di"])
        & (df["rsi"] > 32)
        & (df["rsi"] < 72),
        "signal",
    ] = -1
    return df


def backtest(df, tp, sl, max_bars, pos, label):
    capital, position, entry_price, entry_idx, position_size = 1000, 0, 0, 0, 0
    wins = losses = 0
    win_total = loss_total = 0.0
    max_bal = min_bal = capital
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        sig = row.get("signal", 0)
        if position == 0 and sig == -1:
            position = -1
            entry_price = row["close"]
            entry_idx = i
            position_size = capital * pos
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
    n = wins + losses
    wr = wins / n * 100 if n > 0 else 0
    avg_win = win_total / wins if wins > 0 else 0
    avg_loss = loss_total / losses if losses > 0 else 0
    r = avg_win / avg_loss if avg_loss > 0 else 0
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    dd = ((max_bal - min_bal) / max_bal) * 100
    ret = ((capital - 1000) / 1000) * 100
    sharpe_like = exp / (dd / 100) if dd > 0 else 0
    print(
        f"  {label}: {ret:+.2f}% | {n}tr | {wr:.1f}W | R={r:.2f} | DD={dd:.1f}% | E={exp:.4f} | SR={sharpe_like:.3f}"
    )
    return {
        "label": label,
        "return": round(ret, 3),
        "trades": n,
        "win_rate": round(wr, 2),
        "r_ratio": round(r, 3),
        "expectancy": round(exp, 4),
        "dd": round(dd, 2),
        "sharpe_like": round(sharpe_like, 4),
        "final_capital": round(capital, 2),
    }


results = []
df_btc = load("BTC")
df_btc = indicators(df_btc)
df_btc = signal(df_btc)

print("\n=== SL/TP GRID (BTC, EMA21/50, pos=50%) ===")
for tp in [4, 5, 6, 7, 8, 10, 12]:
    for sl in [1.0, 1.5, 2.0, 2.5, 3.0]:
        if sl >= tp:
            continue
        label = f"TP{tp}_SL{sl}"
        r = backtest(df_btc, tp, sl, 24, 0.50, label)
        r["type"] = "sl_tp_grid"
        results.append(r)

print("\n=== POSITION SIZING (BTC, EMA21/50, TP6, SL1.5) ===")
for pos in [0.25, 0.33, 0.40, 0.50, 0.60, 0.75, 1.0]:
    label = f"pos_{int(pos * 100)}pct"
    r = backtest(df_btc, 6, 1.5, 24, pos, label)
    r["type"] = "position_sizing"
    results.append(r)

print("\n=== MAX BARS (time exit) SCAN ===")
for max_bars in [12, 18, 24, 36, 48, 72]:
    label = f"bars_{max_bars}"
    capital, position, entry_price, entry_idx, position_size = 1000, 0, 0, 0, 0
    wins = losses = 0
    win_total = loss_total = 0.0
    max_bal = min_bal = capital
    for i in range(50, len(df_btc) - 1):
        row = df_btc.iloc[i]
        sig = row.get("signal", 0)
        if position == 0 and sig == -1:
            position = -1
            entry_price = row["close"]
            entry_idx = i
            position_size = capital * 0.50
        elif position == -1:
            pnl_pct = (entry_price - row["close"]) / entry_price
            exit_reason = ""
            if pnl_pct >= 0.06:
                exit_reason = "TP"
            elif pnl_pct <= -0.015:
                exit_reason = "SL"
            elif i - entry_idx >= max_bars:
                exit_reason = "TIME"
            if exit_reason:
                pnl = position_size * pnl_pct
                capital += pnl
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
    n = wins + losses
    wr = wins / n * 100 if n > 0 else 0
    avg_win = win_total / wins if wins > 0 else 0
    avg_loss = loss_total / losses if losses > 0 else 0
    r_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    dd = ((max_bal - min_bal) / max_bal) * 100
    ret = ((capital - 1000) / 1000) * 100
    sharpe_like = exp / (dd / 100) if dd > 0 else 0
    print(
        f"  {label}: {ret:+.2f}% | {n}tr | {wr:.1f}W | R={r_ratio:.2f} | DD={dd:.1f}% | E={exp:.4f} | SR={sharpe_like:.3f}"
    )
    results.append(
        {
            "label": label,
            "return": round(ret, 3),
            "trades": n,
            "win_rate": round(wr, 2),
            "r_ratio": round(r_ratio, 3),
            "expectancy": round(exp, 4),
            "dd": round(dd, 2),
            "sharpe_like": round(sharpe_like, 4),
            "type": "max_bars",
        }
    )

print("\n=== HOUR OF DAY (BTC, EMA21/50, TP6, SL1.5, pos=50%) ===")
df_h = df_btc.copy()
for start_h, end_h in [(0, 8), (4, 12), (8, 16), (12, 20), (16, 24), (0, 24)]:
    df_sub = df_h[(df_h["hour"] >= start_h) & (df_h["hour"] < end_h)]
    if len(df_sub) < 100:
        continue
    capital, position, entry_price, entry_idx, position_size = 1000, 0, 0, 0, 0
    wins = losses = 0
    win_total = loss_total = 0.0
    max_bal = min_bal = capital
    for i in range(50, len(df_sub) - 1):
        row = df_sub.iloc[i]
        sig = row.get("signal", 0)
        if position == 0 and sig == -1:
            position = -1
            entry_price = row["close"]
            entry_idx = i
            position_size = capital * 0.50
        elif position == -1:
            pnl_pct = (entry_price - row["close"]) / entry_price
            exit_reason = ""
            if pnl_pct >= 0.06:
                exit_reason = "TP"
            elif pnl_pct <= -0.015:
                exit_reason = "SL"
            elif i - entry_idx >= 24:
                exit_reason = "TIME"
            if exit_reason:
                pnl = position_size * pnl_pct
                capital += pnl
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
    n = wins + losses
    wr = wins / n * 100 if n > 0 else 0
    avg_win = win_total / wins if wins > 0 else 0
    avg_loss = loss_total / losses if losses > 0 else 0
    r_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    dd = ((max_bal - min_bal) / max_bal) * 100
    ret = ((capital - 1000) / 1000) * 100
    sharpe_like = exp / (dd / 100) if dd > 0 else 0
    print(
        f"  h{start_h:02d}-{end_h:02d}: {ret:+.2f}% | {n}tr | {wr:.1f}W | DD={dd:.1f}% | SR={sharpe_like:.3f}"
    )
    results.append(
        {
            "label": f"hour_{start_h:02d}_{end_h:02d}",
            "return": round(ret, 3),
            "trades": n,
            "win_rate": round(wr, 2),
            "expectancy": round(exp, 4),
            "dd": round(dd, 2),
            "sharpe_like": round(sharpe_like, 4),
            "type": "time_of_day",
        }
    )

print("\n=== TOP 10 by RETURN ===")
sorted_r = sorted(
    [
        r
        for r in results
        if isinstance(r.get("return"), (int, float))
        and r.get("type") in ("sl_tp_grid", "position_sizing", "max_bars")
    ],
    key=lambda x: x["return"],
    reverse=True,
)
for r in sorted_r[:10]:
    print(
        f"  {r['label']}: {r['return']:+.2f}% | E={r.get('expectancy', 0):.4f} | SR={r.get('sharpe_like', 0):.4f} | DD={r.get('dd', '?')}%"
    )

print("\n=== TOP 10 by SHARPE-LIKE (return/dd) ===")
for r in sorted_r[:10]:
    r["score"] = r.get("sharpe_like", 0)
sorted_by_sr = sorted(sorted_r, key=lambda x: x["score"], reverse=True)
for r in sorted_by_sr[:10]:
    print(
        f"  {r['label']}: SR={r.get('sharpe_like', 0):.4f} | {r['return']:+.2f}% | DD={r.get('dd', '?')}%"
    )

with open(OUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved: {OUT}")
