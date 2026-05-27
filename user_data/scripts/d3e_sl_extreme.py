#!/usr/bin/env python3
"""D3e extreme stop-loss scan on BTC with EMA21/50 strategy"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

OUT = "/home/brian/freqtrade/user_data/reports/d3e_sl_extreme.json"


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


results = []

# Load BTC data with EMA21/50 strategy
print("=== D3e EXTREME STOP-LOSS SCAN (BTC, EMA21/50) ===\n")
df_btc = load("BTC")
df_btc = indicators(df_btc, 21, 50)
df_btc["signal"] = 0
df_btc.loc[
    (df_btc["ema_fast"] < df_btc["ema_slow"])
    & (df_btc["adx"] >= 25)
    & (df_btc["minus_di"] > df_btc["plus_di"])
    & (df_btc["rsi"] > 32)
    & (df_btc["rsi"] < 72),
    "signal",
] = -1

# Reference: original 1.5% SL
r_orig = backtest_single(df_btc.copy(), 6, 1.5, 24, 0.50)
r_orig["label"] = "EMA21_50_SL1.5"
r_orig["type"] = "reference"
print(
    f"Reference SL 1.5%: {r_orig['return']:+.2f}% | {r_orig['trades']}tr | {r_orig['win_rate']:.1f}W | E={r_orig['expectancy']} | DD={r_orig['dd']}%"
)
results.append(r_orig)

# Extreme wide SL values: 4%, 5%, 6%
for sl in [4, 5, 6]:
    df_test = df_btc.copy()
    r = backtest_single(df_test, 6, sl, 24, 0.50)
    r["label"] = f"EMA21_50_SL{sl}"
    r["type"] = "extreme_sl"
    print(
        f"  SL {sl}%: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | E={r['expectancy']} | DD={r['dd']}% | Final=${r['final_capital']}"
    )
    results.append(r)

print("\n=== SUMMARY ===")
for r in results:
    print(
        f"  {r['label']}: {r['return']:+.2f}% | E={r['expectancy']} | DD={r['dd']}% | Trades={r['trades']} | WinRate={r['win_rate']}%"
    )

with open(OUT, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved: {OUT}")
