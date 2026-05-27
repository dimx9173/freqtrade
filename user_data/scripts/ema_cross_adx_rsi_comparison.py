#!/usr/bin/env python3
"""
Pure Technical Indicator Strategy: EMA Cross + ADX + RSI - COMPARISON REPORT
Backtest on 2026-01-16 to 2026-04-30
Compare vs V70 baseline (-1.88%)
Tests multiple variants to find best pure technical approach
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

print("=" * 70)
print("PURE TECHNICAL STRATEGY: EMA CROSS + ADX + RSI")
print("COMPARISON vs V70 (-1.88%)")
print("=" * 70)
print()

# Load data
df = pd.read_feather("user_data/data/binance/BTC_USDT-5m.feather")
df["date"] = pd.to_datetime(df["date"])

# Filter for backtest period
start_date = pd.Timestamp("2024-01-16 00:00:00", tz="UTC")
end_date = pd.Timestamp("2024-04-30 23:59:59", tz="UTC")
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

# ============================================================
# VARIANT 1: BIDIRECTIONAL (EMA Cross + ADX + RSI)
# ============================================================
print("Testing Variant 1: Bidirectional (Long + Short)...")
print("-" * 50)

ADX_MIN = 25
RSI_MAX_LONG = 68
RSI_MIN_LONG = 38
RSI_MAX_SHORT = 62
RSI_MIN_SHORT = 32
PROFIT_TARGET = 0.05
STOP_LOSS = 0.025
MAX_BARS = 20

initial_capital = 10000
capital = initial_capital
position = None
trades_bi = []

for i, (idx, row) in enumerate(df_15m.iterrows()):
    current_close = row["close"]
    current_ema_fast = row["ema_fast"]
    current_ema_slow = row["ema_slow"]
    current_adx = row["adx"]
    current_plus_di = row["plus_di"]
    current_minus_di = row["minus_di"]
    current_rsi = row["rsi"]

    if np.isnan(current_ema_fast) or np.isnan(current_adx) or np.isnan(current_rsi):
        continue

    if position is None:
        entry_signal = False
        position_side = None

        ema_bullish_cross = (
            i > 0
            and df_15m.iloc[i - 1]["ema_fast"] <= df_15m.iloc[i - 1]["ema_slow"]
            and current_ema_fast > current_ema_slow
        )

        ema_bearish_cross = (
            i > 0
            and df_15m.iloc[i - 1]["ema_fast"] >= df_15m.iloc[i - 1]["ema_slow"]
            and current_ema_fast < current_ema_slow
        )

        if ema_bullish_cross:
            if current_adx >= ADX_MIN and current_plus_di > current_minus_di:
                if RSI_MIN_LONG <= current_rsi <= RSI_MAX_LONG:
                    entry_signal = True
                    position_side = "long"

        elif ema_bearish_cross:
            if current_adx >= ADX_MIN and current_minus_di > current_plus_di:
                if RSI_MIN_SHORT <= current_rsi <= RSI_MAX_SHORT:
                    entry_signal = True
                    position_side = "short"

        if entry_signal:
            position = {"side": position_side, "entry_price": current_close, "entry_idx": i}

    if position is not None:
        exit_signal = False
        bars_held = i - position["entry_idx"]
        entry_price = position["entry_price"]

        if position["side"] == "long":
            profit_pct = (current_close - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_close) / entry_price

        if position["side"] == "long" and current_ema_fast < current_ema_slow:
            exit_signal = True
        elif position["side"] == "short" and current_ema_fast > current_ema_slow:
            exit_signal = True

        if not exit_signal and profit_pct >= PROFIT_TARGET:
            exit_signal = True
        if not exit_signal and profit_pct <= -STOP_LOSS:
            exit_signal = True
        if not exit_signal and bars_held >= MAX_BARS:
            exit_signal = True

        if exit_signal:
            stake = capital * 0.95
            if position["side"] == "long":
                profit = (current_close - entry_price) * (stake / entry_price)
            else:
                profit = (entry_price - current_close) * (stake / entry_price)
            fees = stake * 0.001 * 2
            profit -= fees
            capital += profit
            trades_bi.append({"side": position["side"], "profit": profit, "win": profit > 0})
            position = None

if position is not None:
    last_row = df_15m.iloc[-1]
    entry_price = position["entry_price"]
    stake = capital * 0.95
    if position["side"] == "long":
        profit = (last_row["close"] - entry_price) * (stake / entry_price)
    else:
        profit = (entry_price - last_row["close"]) * (stake / entry_price)
    fees = stake * 0.001 * 2
    profit -= fees
    capital += profit
    trades_bi.append({"side": position["side"], "profit": profit, "win": profit > 0})

bi_return = (capital - initial_capital) / initial_capital * 100
bi_winrate = sum(1 for t in trades_bi if t["win"]) / max(1, len(trades_bi)) * 100
print(f"  Return: {bi_return:+.2f}% | Trades: {len(trades_bi)} | Win Rate: {bi_winrate:.1f}%")

# ============================================================
# VARIANT 2: LONG ONLY (EMA Cross + ADX + RSI)
# ============================================================
print("\nTesting Variant 2: Long Only...")
print("-" * 50)

capital = initial_capital
position = None
trades_long = []

PROFIT_TARGET_LONG = 0.06
STOP_LOSS_LONG = 0.025
MAX_BARS_LONG = 24

for i, (idx, row) in enumerate(df_15m.iterrows()):
    current_close = row["close"]
    current_ema_fast = row["ema_fast"]
    current_ema_slow = row["ema_slow"]
    current_adx = row["adx"]
    current_plus_di = row["plus_di"]
    current_minus_di = row["minus_di"]
    current_rsi = row["rsi"]

    if np.isnan(current_ema_fast) or np.isnan(current_adx) or np.isnan(current_rsi):
        continue

    if position is None:
        ema_bullish_cross = (
            i > 0
            and df_15m.iloc[i - 1]["ema_fast"] <= df_15m.iloc[i - 1]["ema_slow"]
            and current_ema_fast > current_ema_slow
        )

        if ema_bullish_cross:
            if current_adx >= ADX_MIN and current_plus_di > current_minus_di:
                if RSI_MIN_LONG <= current_rsi <= RSI_MAX_LONG:
                    position = {"entry_price": current_close, "entry_idx": i}

    if position is not None:
        bars_held = i - position["entry_idx"]
        entry_price = position["entry_price"]
        profit_pct = (current_close - entry_price) / entry_price

        exit_signal = False

        if current_ema_fast < current_ema_slow:
            exit_signal = True
        if not exit_signal and profit_pct >= PROFIT_TARGET_LONG:
            exit_signal = True
        if not exit_signal and profit_pct <= -STOP_LOSS_LONG:
            exit_signal = True
        if not exit_signal and bars_held >= MAX_BARS_LONG:
            exit_signal = True

        if exit_signal:
            stake = capital * 0.95
            profit = (current_close - entry_price) * (stake / entry_price)
            fees = stake * 0.001 * 2
            profit -= fees
            capital += profit
            trades_long.append({"profit": profit, "win": profit > 0})
            position = None

if position is not None:
    last_row = df_15m.iloc[-1]
    entry_price = position["entry_price"]
    stake = capital * 0.95
    profit = (last_row["close"] - entry_price) * (stake / entry_price)
    fees = stake * 0.001 * 2
    profit -= fees
    capital += profit
    trades_long.append({"profit": profit, "win": profit > 0})

long_return = (capital - initial_capital) / initial_capital * 100
long_winrate = sum(1 for t in trades_long if t["win"]) / max(1, len(trades_long)) * 100
print(f"  Return: {long_return:+.2f}% | Trades: {len(trades_long)} | Win Rate: {long_winrate:.1f}%")

# ============================================================
# VARIANT 3: TREND CONFIRMATION (No EMA cross, ADX + RSI only)
# ============================================================
print("\nTesting Variant 3: Trend Confirmation (ADX + RSI only)...")
print("-" * 50)

capital = initial_capital
position = None
trades_trend = []

ADX_STRONG = 30
RSI_CONFIRM = 55

for i, (idx, row) in enumerate(df_15m.iterrows()):
    current_close = row["close"]
    current_adx = row["adx"]
    current_plus_di = row["plus_di"]
    current_minus_di = row["minus_di"]
    current_rsi = row["rsi"]

    if np.isnan(current_adx) or np.isnan(current_rsi):
        continue

    if position is None:
        # Strong uptrend confirmation
        if (
            current_adx >= ADX_STRONG
            and current_plus_di > current_minus_di
            and current_rsi < RSI_CONFIRM
        ):
            position = {"entry_price": current_close, "entry_idx": i, "entry_rsi": current_rsi}

    if position is not None:
        bars_held = i - position["entry_idx"]
        entry_price = position["entry_price"]
        profit_pct = (current_close - entry_price) / entry_price

        exit_signal = False

        # Exit if trend breaks
        if current_minus_di > current_plus_di:
            exit_signal = True
        # Exit if RSI overbought
        if current_rsi > 70:
            exit_signal = True
        # Profit target
        if profit_pct >= 0.05:
            exit_signal = True
        # Stop
        if profit_pct <= -0.02:
            exit_signal = True
        # Time
        if bars_held >= 20:
            exit_signal = True

        if exit_signal:
            stake = capital * 0.95
            profit = (current_close - entry_price) * (stake / entry_price)
            fees = stake * 0.001 * 2
            profit -= fees
            capital += profit
            trades_trend.append({"profit": profit, "win": profit > 0})
            position = None

if position is not None:
    last_row = df_15m.iloc[-1]
    entry_price = position["entry_price"]
    stake = capital * 0.95
    profit = (last_row["close"] - entry_price) * (stake / entry_price)
    fees = stake * 0.001 * 2
    profit -= fees
    capital += profit
    trades_trend.append({"profit": profit, "win": profit > 0})

trend_return = (capital - initial_capital) / initial_capital * 100
trend_winrate = sum(1 for t in trades_trend if t["win"]) / max(1, len(trades_trend)) * 100
print(
    f"  Return: {trend_return:+.2f}% | Trades: {len(trades_trend)} | Win Rate: {trend_winrate:.1f}%"
)

# ============================================================
# FINAL SUMMARY
# ============================================================
print()
print("=" * 70)
print("FINAL COMPARISON vs V70 BASELINE (-1.88%)")
print("=" * 70)
print()
print(f"{'Strategy Variant':<35} {'Return':>10} {'vs V70':>10} {'Trades':>8}")
print("-" * 70)
print(f"{'V70 Baseline (Regime-Based)':<35} {'-1.88%':>10} {'--':>10} {'--':>8}")
print(
    f"{'Variant 1: Bidirectional (L+S)':<35} {bi_return:>+10.2f}% {bi_return - (-1.88):>+10.2f}% {len(trades_bi):>8}"
)
print(
    f"{'Variant 2: Long Only':<35} {long_return:>+10.2f}% {long_return - (-1.88):>+10.2f}% {len(trades_long):>8}"
)
print(
    f"{'Variant 3: Trend Confirmation':<35} {trend_return:>+10.2f}% {trend_return - (-1.88):>+10.2f}% {len(trades_trend):>8}"
)
print("-" * 70)
print()

# Save final report
results = {
    "backtest_period": f"{start_date.date()} to {end_date.date()}",
    "v70_baseline": -1.88,
    "variants": {
        "bidirectional": {
            "return": bi_return,
            "trades": len(trades_bi),
            "win_rate": bi_winrate,
            "vs_v70": bi_return - (-1.88),
        },
        "long_only": {
            "return": long_return,
            "trades": len(trades_long),
            "win_rate": long_winrate,
            "vs_v70": long_return - (-1.88),
        },
        "trend_confirmation": {
            "return": trend_return,
            "trades": len(trades_trend),
            "win_rate": trend_winrate,
            "vs_v70": trend_return - (-1.88),
        },
    },
    "best_variant": "long_only"
    if long_return >= max(bi_return, trend_return)
    else "bidirectional"
    if bi_return >= trend_return
    else "trend_confirmation",
    "best_return": max(long_return, bi_return, trend_return),
    "best_vs_v70": max(long_return, bi_return, trend_return) - (-1.88),
}

with open("/home/brian/freqtrade/user_data/reports/ema_cross_adx_rsi_comparison.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Results saved to: user_data/reports/ema_cross_adx_rsi_comparison.json")
print()
print("=" * 70)
