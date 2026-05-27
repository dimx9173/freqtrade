#!/usr/bin/env python3
"""
D1: Wider R (1% SL, 4% TP) - improve expectancy by cutting losses faster
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

NAME = "d1_wider_r"
DATA = "user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather"
TP, SL, MAX_BARS, POS = 4, 1, 24, 0.50

print(f"Strategy: {NAME} | TP:{TP}% SL:{SL}% Pos:{POS * 100:.0f}%")
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

df["signal"] = 0
cond = (
    (df["ema_fast"] > df["ema_slow"])
    & (df["adx"] >= 25)
    & (df["plus_di"] > df["minus_di"])
    & (df["rsi"] > 30)
    & (df["rsi"] < 68)
)
df.loc[cond, "signal"] = 1

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
        position_size = capital * POS
    elif position == 1:
        pnl_pct = (row["close"] - entry_price) / entry_price
        exit_reason = ""
        if pnl_pct >= TP / 100:
            exit_reason = "TP"
        elif pnl_pct <= -SL / 100:
            exit_reason = "SL"
        elif i - entry_idx >= MAX_BARS:
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
print(
    f"Return: {ret:.2f}% | Trades: {n} | Win%: {wr:.1f} | R:{r:.2f}:1 | DD:{dd:.2f}% | Exp:{exp:.4f}"
)
print(f"vs V70: {ret - (-1.88):+.2f}%")

with open(f"user_data/reports/d1_results.json", "w") as f:
    json.dump(
        {
            "strategy": NAME,
            "return": round(ret, 3),
            "trades": n,
            "win_rate": round(wr, 2),
            "r_ratio": round(r, 3),
            "expectancy": round(exp, 4),
            "dd": round(dd, 2),
            "vs_v70": round(ret - (-1.88), 3),
            "wins": wins,
            "losses": losses,
        },
        f,
        indent=2,
    )
