#!/usr/bin/env python3
"""Best EMA(21/50) + Best SL/TP combos on all 3 pairs"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

OUT = "user_data/reports/d3e_best_combos.json"


def load(pair):
    paths = {
        "BTC": "user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather",
        "ETH": "user_data/data/bybit/futures/ETH_USDT_USDT-5m-futures.feather",
        "SOL": "user_data/data/bybit/futures/SOL_USDT_USDT-5m-futures.feather",
    }
    df = pd.read_feather(paths[pair])
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


def run(df, fast, slow, tp, sl, max_bars, pos, label):
    df = df.copy()
    df["ema_fast"] = ta.EMA(df["close"], fast)
    df["ema_slow"] = ta.EMA(df["close"], slow)
    df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
    df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
    df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
    df["rsi"] = ta.RSI(df["close"], 14)
    df["signal"] = 0
    df.loc[
        (df["ema_fast"] < df["ema_slow"])
        & (df["adx"] >= 25)
        & (df["minus_di"] > df["plus_di"])
        & (df["rsi"] > 32)
        & (df["rsi"] < 72),
        "signal",
    ] = -1

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
    print(f"  {label}: {ret:+.2f}% | {n}tr | {wr:.1f}W | R={r:.2f} | DD={dd:.1f}% | E={exp:.4f}")
    return {
        "label": label,
        "return": round(ret, 3),
        "trades": n,
        "win_rate": round(wr, 2),
        "r_ratio": round(r, 3),
        "expectancy": round(exp, 4),
        "dd": round(dd, 2),
        "vs_v70": round(ret - (-1.88), 3),
    }


results = []
pairs_data = {}

# Test best combos on BTC
print("\n=== BTC: EMA(21/50) + best SL/TP combos ===")
df_btc = load("BTC")
for tp, sl in [(6, 1.5), (7, 2), (5, 1), (8, 2), (6, 2)]:
    r = run(df_btc, 21, 50, tp, sl, 24, 0.50, f"BTC_EMA21_50_TP{tp}_SL{sl}")
    r["type"] = "ema_sl_tp"
    results.append(r)

# Test best combos on ETH
print("\n=== ETH: EMA(21/50) + best SL/TP combos ===")
df_eth = load("ETH")
for tp, sl in [(6, 1.5), (7, 2), (5, 1), (8, 2), (6, 2)]:
    r = run(df_eth, 21, 50, tp, sl, 24, 0.50, f"ETH_EMA21_50_TP{tp}_SL{sl}")
    r["type"] = "ema_sl_tp"
    results.append(r)

# Test best combos on SOL
print("\n=== SOL: EMA(21/50) + best SL/TP combos ===")
df_sol = load("SOL")
for tp, sl in [(6, 1.5), (7, 2), (5, 1), (8, 2), (6, 2)]:
    r = run(df_sol, 21, 50, tp, sl, 24, 0.50, f"SOL_EMA21_50_TP{tp}_SL{sl}")
    r["type"] = "ema_sl_tp"
    results.append(r)

# Also test EMA(10/30) on BTC (second best)
print("\n=== BTC: EMA(10/30) combos ===")
for tp, sl in [(6, 1.5), (7, 2), (5, 1), (8, 2)]:
    r = run(df_btc, 10, 30, tp, sl, 24, 0.50, f"BTC_EMA10_30_TP{tp}_SL{sl}")
    r["type"] = "ema_sl_tp"
    results.append(r)

# 3-pair portfolio with best BTC setup (EMA21/50, TP6, SL1.5)
print("\n=== 3-PAIR PORTFOLIO (EMA21/50, TP6, SL1.5) ===")
for pair, df in [("BTC", df_btc), ("ETH", df_eth), ("SOL", df_sol)]:
    df2 = df.copy()
    df2["ema_fast"] = ta.EMA(df2["close"], 21)
    df2["ema_slow"] = ta.EMA(df2["close"], 50)
    df2["adx"] = ta.ADX(df2["high"], df2["low"], df2["close"], 14)
    df2["plus_di"] = ta.PLUS_DI(df2["high"], df2["low"], df2["close"], 14)
    df2["minus_di"] = ta.MINUS_DI(df2["high"], df2["low"], df2["close"], 14)
    df2["rsi"] = ta.RSI(df2["close"], 14)
    df2["signal"] = 0
    df2.loc[
        (df2["ema_fast"] < df2["ema_slow"])
        & (df2["adx"] >= 25)
        & (df2["minus_di"] > df2["plus_di"])
        & (df2["rsi"] > 32)
        & (df2["rsi"] < 72),
        "signal",
    ] = -1
    pairs_data[pair] = df2

capitals = []
for pair, df_p in pairs_data.items():
    capital = 1000
    position = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    for i in range(50, len(df_p) - 1):
        row = df_p.iloc[i]
        sig = row.get("signal", 0)
        if position == 0 and sig == -1:
            position = -1
            entry_price = row["close"]
            entry_idx = i
            position_size = (capital / 3) * 0.50
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
                capital += position_size * pnl_pct
                position = 0
    capitals.append(capital)
port_ret = ((sum(capitals) - 3000) / 3000) * 100
print(f"  3-pair portfolio: {port_ret:+.2f}% | Finals: {[round(c, 2) for c in capitals]}")
results.append({"label": "3pair_EMA21_50", "return": round(port_ret, 3), "type": "portfolio"})

print("\n=== TOP 10 ===")
sorted_results = sorted(
    [r for r in results if isinstance(r.get("return"), (int, float))],
    key=lambda x: x["return"],
    reverse=True,
)
for r in sorted_results[:10]:
    print(
        f"  {r['label']}: {r['return']:+.2f}% | E={r.get('expectancy', 0):.4f} | DD={r.get('dd', '?')}%"
    )

with open(OUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved: {OUT}")
