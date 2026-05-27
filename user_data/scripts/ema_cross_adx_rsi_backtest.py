#!/usr/bin/env python3
"""
Pure Technical Indicator Strategy: EMA Cross + ADX + RSI
Backtest on 2026-01-16 to 2026-04-30 (using available 2024 data)
Compare vs V70 baseline (-1.88%)
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json
from datetime import datetime

print("=" * 70)
print("PURE TECHNICAL STRATEGY: EMA CROSS + ADX + RSI")
print("=" * 70)
print()

# Load data
df = pd.read_feather("user_data/data/binance/BTC_USDT-5m.feather")
df["date"] = pd.to_datetime(df["date"])
print(f"Data loaded: {len(df)} rows")
print(f"Date range: {df.iloc[0]['date']} to {df.iloc[-1]['date']}")

# Filter for backtest period - using 2024 equivalent to 2026 dates
# 20260116-20260430 maps to approximately 2024 dates if data is 2024
start_date = pd.Timestamp("2024-01-16 00:00:00", tz="UTC")
end_date = pd.Timestamp("2024-04-30 23:59:59", tz="UTC")

df_filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)].copy()
print(f"Filtered to backtest period: {len(df_filtered)} rows")
print(f"Backtest period: {df_filtered.iloc[0]['date']} to {df_filtered.iloc[-1]['date']}")
print()

# Resample to 15m for strategy timeframe
df_15m = df_filtered.set_index("date")
df_15m = (
    df_15m.resample("15min")
    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    .dropna()
)
df_15m = df_15m.reset_index()
print(f"Resampled to 15m: {len(df_15m)} rows")

# Calculate Technical Indicators
print("Calculating indicators...")

# EMA - Fast (12), Medium (50), Slow (26)
df_15m["ema_fast"] = ta.EMA(df_15m["close"].values, timeperiod=12)
df_15m["ema_slow"] = ta.EMA(df_15m["close"].values, timeperiod=26)
df_15m["ema_medium"] = ta.EMA(df_15m["close"].values, timeperiod=50)

# ADX (trend strength)
df_15m["adx"] = ta.ADX(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)
df_15m["plus_di"] = ta.PLUS_DI(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)
df_15m["minus_di"] = ta.MINUS_DI(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)

# RSI
df_15m["rsi"] = ta.RSI(df_15m["close"].values, timeperiod=14)

# ATR for stops
df_15m["atr"] = ta.ATR(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)

# BB for additional confirmation
bb_upper, bb_middle, bb_lower = ta.BBANDS(
    df_15m["close"].values, timeperiod=20, nbdevup=2.0, nbdevdn=2.0
)
df_15m["bb_upper"] = pd.Series(bb_upper, index=df_15m.index)
df_15m["bb_middle"] = pd.Series(bb_middle, index=df_15m.index)
df_15m["bb_lower"] = pd.Series(bb_lower, index=df_15m.index)

print(f"Indicators calculated")
print()

# Strategy Parameters
ADX_TREND_THRESHOLD = 25  # ADX above 25 confirms trend
ADX_STRONG_TREND = 30  # ADX above 30 = strong trend
RSI_OVERSOLD = 35  # RSI oversold for long entries
RSI_OVERBOUGHT = 65  # RSI overbought for short entries
RSI_NEUTRAL_LOW = 45  # RSI below this for long confirmation
RSI_NEUTRAL_HIGH = 55  # RSI above this for short confirmation

# Backtest Configuration
initial_capital = 10000
capital = initial_capital
position = None
trades = []
equity_curve = []

print("=" * 70)
print("BACKTEST RESULTS: EMA CROSS + ADX + RSI")
print("=" * 70)
print()

# Backtest Loop
for i, (idx, row) in enumerate(df_15m.iterrows()):
    current_close = row["close"]
    current_ema_fast = row["ema_fast"]
    current_ema_slow = row["ema_slow"]
    current_ema_medium = row["ema_medium"]
    current_adx = row["adx"]
    current_plus_di = row["plus_di"]
    current_minus_di = row["minus_di"]
    current_rsi = row["rsi"]
    current_atr = row["atr"]

    # Skip if indicators not ready
    if np.isnan(current_ema_fast) or np.isnan(current_adx) or np.isnan(current_rsi):
        equity_curve.append(capital)
        continue

    # === ENTRY LOGIC ===
    if position is None:
        entry_signal = False
        position_side = None
        entry_reason = ""

        # Long Entry: EMA Fast crosses above EMA Slow + ADX confirms + RSI not overbought
        # EMA Bullish Cross
        ema_bullish_cross = (
            i > 0
            and df_15m.iloc[i - 1]["ema_fast"] <= df_15m.iloc[i - 1]["ema_slow"]
            and current_ema_fast > current_ema_slow
        )

        # Short Entry: EMA Fast crosses below EMA Slow + ADX confirms
        ema_bearish_cross = (
            i > 0
            and df_15m.iloc[i - 1]["ema_fast"] >= df_15m.iloc[i - 1]["ema_slow"]
            and current_ema_fast < current_ema_slow
        )

        # Long conditions
        if ema_bullish_cross:
            # Trend confirmation: ADX above threshold
            if current_adx >= ADX_TREND_THRESHOLD:
                # Direction confirmed: +DI > -DI
                if current_plus_di > current_minus_di:
                    # RSI filter: not overbought, ideally in neutral or oversold territory
                    if current_rsi < RSI_OVERBOUGHT:
                        entry_signal = True
                        position_side = "long"
                        entry_reason = f"EMA_BullCross_ADX{current_adx:.1f}_RSI{current_rsi:.1f}"

        # Short conditions
        elif ema_bearish_cross:
            # Trend confirmation: ADX above threshold
            if current_adx >= ADX_TREND_THRESHOLD:
                # Direction confirmed: -DI > +DI
                if current_minus_di > current_plus_di:
                    # RSI filter: not oversold
                    if current_rsi > RSI_OVERSOLD:
                        entry_signal = True
                        position_side = "short"
                        entry_reason = f"EMA_BearCross_ADX{current_adx:.1f}_RSI{current_rsi:.1f}"

        if entry_signal:
            position = {
                "side": position_side,
                "entry_price": current_close,
                "entry_idx": i,
                "entry_reason": entry_reason,
                "entry_atr": current_atr,
                "high_price": current_close,
                "low_price": current_close,
            }

    # === EXIT LOGIC ===
    if position is not None:
        exit_signal = False
        exit_reason = ""
        bars_held = i - position["entry_idx"]
        entry_price = position["entry_price"]

        # Track high/low for trailing
        if position["side"] == "long":
            position["high_price"] = max(position["high_price"], current_close)
        else:
            position["low_price"] = min(position["low_price"], current_close)

        # Calculate profit
        if position["side"] == "long":
            profit_pct = (current_close - entry_price) / entry_price
            unrealized_profit = (position["high_price"] - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_close) / entry_price
            unrealized_profit = (entry_price - position["low_price"]) / entry_price

        # Exit conditions

        # 1. Trend reversal exit (EMA cross opposite direction)
        if position["side"] == "long":
            if current_ema_fast < current_ema_slow:
                exit_signal = True
                exit_reason = "EMA_Reversal"
        else:
            if current_ema_fast > current_ema_slow:
                exit_signal = True
                exit_reason = "EMA_Reversal"

        # 2. ADX drops below threshold (trend weakening)
        if not exit_signal and current_adx < 20:
            exit_signal = True
            exit_reason = f"ADX_Drop({current_adx:.1f})"

        # 3. Profit target (based on ATR multiplier)
        if not exit_signal:
            atr_multiplier = 3 if position["side"] == "long" else 2.5
            if unrealized_profit > atr_multiplier * (position["entry_atr"] / entry_price):
                exit_signal = True
                exit_reason = f"ProfitTarget({unrealized_profit * 100:.2f}%)"

        # 4. Stop loss (2x ATR from entry)
        if not exit_signal:
            stop_pct = 1.5 * (position["entry_atr"] / entry_price)
            if profit_pct < -stop_pct:
                exit_signal = True
                exit_reason = f"StopLoss({profit_pct * 100:.2f}%)"

        # 5. RSI overbought/oversold exit
        if not exit_signal:
            if position["side"] == "long" and current_rsi > 75:
                exit_signal = True
                exit_reason = f"RSI_Overbought({current_rsi:.1f})"
            elif position["side"] == "short" and current_rsi < 30:
                exit_signal = True
                exit_reason = f"RSI_Oversold({current_rsi:.1f})"

        # 6. Time-based exit (max 4 hours = 16 candles at 15m)
        if not exit_signal and bars_held >= 16:
            exit_signal = True
            exit_reason = f"TimeExit({bars_held} bars)"

        if exit_signal:
            # Calculate P&L
            stake = capital * 0.95  # 95% of capital per trade
            if position["side"] == "long":
                profit = (current_close - entry_price) * (stake / entry_price)
            else:
                profit = (entry_price - current_close) * (stake / entry_price)

            # Fees (0.1% per trade, 2 trades = entry + exit)
            fees = stake * 0.001 * 2
            profit -= fees

            capital += profit

            trades.append(
                {
                    "side": position["side"],
                    "entry_price": entry_price,
                    "exit_price": current_close,
                    "profit_pct": profit_pct * 100,
                    "profit": profit,
                    "bars": bars_held,
                    "win": profit > 0,
                    "entry_reason": position["entry_reason"],
                    "exit_reason": exit_reason,
                }
            )

            position = None

    equity_curve.append(capital)

# Close open position at end
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

    trades.append(
        {
            "side": position["side"],
            "entry_price": entry_price,
            "exit_price": last_row["close"],
            "profit_pct": (profit / stake) * 100,
            "profit": profit,
            "bars": i - position["entry_idx"],
            "win": profit > 0,
            "entry_reason": position["entry_reason"],
            "exit_reason": "EndOfPeriod",
        }
    )

# === RESULTS ===
total_return = (capital - initial_capital) / initial_capital * 100
win_rate = sum(1 for t in trades if t["win"]) / max(1, len(trades)) * 100
total_trades = len(trades)

# Separate longs and shorts
long_trades = [t for t in trades if t["side"] == "long"]
short_trades = [t for t in trades if t["side"] == "short"]

print(f"Initial Capital: ${initial_capital:,.2f}")
print(f"Final Capital:   ${capital:,.2f}")
print(f"Total Return:    {total_return:+.2f}%")
print(f"VS V70 Baseline: -1.88%")
print(f"Difference:      {total_return - (-1.88):+.2f}%")
print()
print(f"Total Trades:    {total_trades}")
print(f"  Long Trades:   {len(long_trades)} ({sum(1 for t in long_trades if t['win'])} wins)")
print(f"  Short Trades:  {len(short_trades)} ({sum(1 for t in short_trades if t['win'])} wins)")
print(f"Win Rate:        {win_rate:.1f}%")
print()

# Average trade stats
if trades:
    avg_profit = sum(t["profit"] for t in trades) / len(trades)
    avg_bars = sum(t["bars"] for t in trades) / len(trades)
    print(f"Average Profit per Trade: ${avg_profit:+.2f}")
    print(f"Average Bars Held:         {avg_bars:.1f}")
    print()

# Max drawdown
peak_capital = initial_capital
max_drawdown = 0
for eq in equity_curve:
    if eq > peak_capital:
        peak_capital = eq
    drawdown = (peak_capital - eq) / peak_capital * 100
    if drawdown > max_drawdown:
        max_drawdown = drawdown
print(f"Max Drawdown:             {max_drawdown:.2f}%")
print()

print("TRADE BREAKDOWN:")
print("-" * 70)
print(f"{'Side':<8} {'Entry':>10} {'Exit':>10} {'Return%':>10} {'Bars':>6} {'Win':>5}")
print("-" * 70)
for t in trades:
    print(
        f"{t['side']:<8} {t['entry_price']:>10,.0f} {t['exit_price']:>10,.0f} {t['profit_pct']:>+10.2f}% {t['bars']:>6} {'Y' if t['win'] else 'N':>5}"
    )
print("-" * 70)
print()

# Save results
results = {
    "strategy": "EMA_Cross_ADX_RSI",
    "period": f"{start_date.date()} to {end_date.date()}",
    "initial_capital": initial_capital,
    "final_capital": capital,
    "total_return": total_return,
    "vs_v70_baseline": -1.88,
    "difference_vs_v70": total_return - (-1.88),
    "total_trades": total_trades,
    "long_trades": len(long_trades),
    "short_trades": len(short_trades),
    "win_rate": win_rate,
    "max_drawdown": max_drawdown,
    "avg_profit_per_trade": avg_profit if trades else 0,
    "avg_bars_held": avg_bars if trades else 0,
    "trades": trades,
}

with open("/home/brian/freqtrade/user_data/reports/ema_cross_adx_rsi_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print("Results saved to: user_data/reports/ema_cross_adx_rsi_results.json")
print()
print("=" * 70)
print("COMPARISON SUMMARY")
print("=" * 70)
print(f"  V70 Baseline:              -1.88%")
print(f"  EMA+ADX+RSI Strategy:       {total_return:+.2f}%")
if total_return > -1.88:
    print(f"  Outperformance:           {total_return - (-1.88):+.2f}% ✓")
else:
    print(f"  Underperformance:         {total_return - (-1.88):+.2f}%")
print("=" * 70)
