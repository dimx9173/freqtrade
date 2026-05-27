#!/usr/bin/env python3
"""D3e multi-pair + EMA parameter scan"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

OUT = "user_data/reports/d3e_multipair_ema.json"


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


def indicators(df, fast, slow):
    df["ema_fast"] = ta.EMA(df["close"], fast)
    df["ema_slow"] = ta.EMA(df["close"], slow)
    df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
    df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
    df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
    df["rsi"] = ta.RSI(df["close"], 14)
    return df


def backtest_single(df, tp, sl, max_bars, pos):
    capital, position, entry_price, entry_idx, position_size = 1000, 0, 0, 0, 0
    trades = []
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
                trades.append({"pnl": pnl})
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
        "wins": wins,
        "losses": losses,
        "final_capital": round(capital, 2),
    }


def backtest_portfolio(pairs_df, tp, sl, max_bars, pos):
    """Run backtest on multiple pairs, each with $1000, combined portfolio"""
    totals = []
    for pair, df in pairs_df.items():
        capital = 1000
        position = 0
        entry_price = 0
        entry_idx = 0
        position_size = 0
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
                    position = 0
        totals.append(capital)
    total_return = ((sum(totals) - 3000) / 3000) * 100
    return total_return, totals


results = []

# === PART 1: Multi-pair D3e (EMA 12/26) ===
print("\n=== MULTI-PAIR (D3e: 1.5%SL 6%TP) ===")
pairs_data = {}
for pair in ["BTC", "ETH", "SOL"]:
    df = load(pair)
    df = indicators(df, 12, 26)
    df["signal"] = 0
    df.loc[
        (df["ema_fast"] < df["ema_slow"])
        & (df["adx"] >= 25)
        & (df["minus_di"] > df["plus_di"])
        & (df["rsi"] > 32)
        & (df["rsi"] < 72),
        "signal",
    ] = -1
    r = backtest_single(df, 6, 1.5, 24, 0.50)
    r["label"] = f"{pair}_D3e"
    r["type"] = "multipair"
    print(
        f"  {pair}: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | DD={r['dd']:.1f}%"
    )
    results.append(r)
    pairs_data[pair] = df

# Combined equal-weight portfolio ($1000 per pair = $3000 total)
port_ret, finals = backtest_portfolio(pairs_data, 6, 1.5, 24, 0.50)
combined = {
    "label": "Combined_3pair",
    "return": round(port_ret, 3),
    "type": "portfolio",
    "trades": "mixed",
    "win_rate": "mixed",
    "r_ratio": "mixed",
    "expectancy": "mixed",
    "dd": "mixed",
    "wins": "mixed",
    "losses": "mixed",
}
print(f"  Combined (3-pair, equal weight): {port_ret:+.2f}% | Finals: {finals}")
results.append(combined)

# === PART 2: EMA parameter scan (BTC only) ===
print("\n=== EMA PARAMETER SCAN (BTC D3e) ===")
df_btc = load("BTC")
for fast, slow in [(8, 21), (8, 26), (10, 20), (10, 30), (12, 26), (21, 50)]:
    df = df_btc.copy()
    df = indicators(df, fast, slow)
    df["signal"] = 0
    df.loc[
        (df["ema_fast"] < df["ema_slow"])
        & (df["adx"] >= 25)
        & (df["minus_di"] > df["plus_di"])
        & (df["rsi"] > 32)
        & (df["rsi"] < 72),
        "signal",
    ] = -1
    r = backtest_single(df, 6, 1.5, 24, 0.50)
    r["label"] = f"EMA{fast}_{slow}"
    r["type"] = "ema_scan"
    print(
        f"  EMA({fast}/{slow}): {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | DD={r['dd']:.1f}%"
    )
    results.append(r)

print("\n=== BEST performers ===")
numeric = [r for r in results if isinstance(r["return"], (int, float))]
for r in sorted(numeric, key=lambda x: x["return"], reverse=True):
    print(f"  {r['label']}: {r['return']:+.2f}% | E={r.get('expectancy', 0)} | DD={r['dd']}%")

with open(OUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved: {OUT}")
