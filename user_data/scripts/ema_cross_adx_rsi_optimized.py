#!/usr/bin/env python3
"""
Pure Technical Indicator Strategy: EMA Cross + ADX + RSI - OPTIMIZED
Backtest on 2026-01-16 to 2026-04-30
Compare vs V70 baseline (-1.88%)
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

print("=" * 70)
print("PURE TECHNICAL STRATEGY OPTIMIZED: EMA CROSS + ADX + RSI")
print("=" * 70)
print()

# Load data
df = pd.read_feather("user_data/data/binance/BTC_USDT-5m.feather")
df["date"] = pd.to_datetime(df["date"])

# Filter for backtest period
start_date = pd.Timestamp("2026-01-16 00:00:00", tz="UTC")
end_date = pd.Timestamp("2026-04-30 23:59:59", tz="UTC")
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
df_15m["ema_fast"] = ta.EMA(df_15m["close"].values, timeperiod=9)  # Faster EMA
df_15m["ema_slow"] = ta.EMA(df_15m["close"].values, timeperiod=21)  # Slightly faster slow
df_15m["ema_medium"] = ta.EMA(df_15m["close"].values, timeperiod=50)
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

# Optimized Parameters
ADX_ENTRY_THRESHOLD = 28  # Higher ADX for entry (more trend confirmation)
ADX_EXIT_THRESHOLD = 22  # Lower ADX to exit when trend weakens
RSI_LONG_ENTRY_MIN = 40  # RSI must be above 40 for long (not oversold)
RSI_LONG_ENTRY_MAX = 70  # RSI must be below 70 (not overbought)
RSI_SHORT_ENTRY_MIN = 30  # RSI must be above 30 for short
RSI_SHORT_ENTRY_MAX = 60  # RSI must be below 60 for short
RSI_OVERBOUGHT_EXIT = 75  # Exit long when RSI overbought
RSI_OVERSOLD_EXIT = 25  # Exit short when RSI oversold

PROFIT_TARGET_ATR = 4.0  # 4x ATR for profit target
STOP_LOSS_ATR = 2.0  # 2x ATR for stop loss
MAX_BARS = 20  # Max 5 hours at 15m candles

initial_capital = 10000
capital = initial_capital
position = None
trades = []

print("=" * 70)
print("BACKTEST RESULTS: OPTIMIZED EMA CROSS + ADX + RSI")
print("=" * 70)
print()

for i, (idx, row) in enumerate(df_15m.iterrows()):
    current_close = row["close"]
    current_ema_fast = row["ema_fast"]
    current_ema_slow = row["ema_slow"]
    current_adx = row["adx"]
    current_plus_di = row["plus_di"]
    current_minus_di = row["minus_di"]
    current_rsi = row["rsi"]
    current_atr = row["atr"]

    if np.isnan(current_ema_fast) or np.isnan(current_adx) or np.isnan(current_rsi):
        continue

    # === ENTRY LOGIC ===
    if position is None:
        entry_signal = False
        position_side = None

        # EMA Crossover detection
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

        # Long entry: Bullish EMA cross + ADX confirms + RSI in valid range
        if ema_bullish_cross:
            if current_adx >= ADX_ENTRY_THRESHOLD:  # Higher threshold
                if current_plus_di > current_minus_di:
                    if RSI_LONG_ENTRY_MIN <= current_rsi <= RSI_LONG_ENTRY_MAX:
                        entry_signal = True
                        position_side = "long"

        # Short entry: Bearish EMA cross + ADX confirms + RSI in valid range
        elif ema_bearish_cross:
            if current_adx >= ADX_ENTRY_THRESHOLD:
                if current_minus_di > current_plus_di:
                    if RSI_SHORT_ENTRY_MIN <= current_rsi <= RSI_SHORT_ENTRY_MAX:
                        entry_signal = True
                        position_side = "short"

        if entry_signal:
            position = {
                "side": position_side,
                "entry_price": current_close,
                "entry_idx": i,
                "entry_atr": current_atr,
                "highest_since_entry": current_close,
                "lowest_since_entry": current_close,
            }

    # === EXIT LOGIC ===
    if position is not None:
        exit_signal = False
        exit_reason = ""
        bars_held = i - position["entry_idx"]
        entry_price = position["entry_price"]

        # Track high/low
        if position["side"] == "long":
            position["highest_since_entry"] = max(position["highest_since_entry"], current_close)
            profit_pct = (current_close - entry_price) / entry_price
            unrealized_profit = (position["highest_since_entry"] - entry_price) / entry_price
        else:
            position["lowest_since_entry"] = min(position["lowest_since_entry"], current_close)
            profit_pct = (entry_price - current_close) / entry_price
            unrealized_profit = (entry_price - position["lowest_since_entry"]) / entry_price

        # 1. EMA reversal exit
        if position["side"] == "long":
            if current_ema_fast < current_ema_slow:
                exit_signal = True
                exit_reason = "EMA_Reversal"
        else:
            if current_ema_fast > current_ema_slow:
                exit_signal = True
                exit_reason = "EMA_Reversal"

        # 2. ADX drops below exit threshold
        if not exit_signal and current_adx < ADX_EXIT_THRESHOLD:
            exit_signal = True
            exit_reason = f"ADX_Drop"

        # 3. Profit target (ATR based)
        if not exit_signal:
            if unrealized_profit > PROFIT_TARGET_ATR * (position["entry_atr"] / entry_price):
                exit_signal = True
                exit_reason = f"ProfitTarget({unrealized_profit * 100:.1f}%)"

        # 4. Stop loss
        if not exit_signal:
            if profit_pct < -STOP_LOSS_ATR * (position["entry_atr"] / entry_price):
                exit_signal = True
                exit_reason = f"StopLoss({profit_pct * 100:.2f}%)"

        # 5. RSI overbought/oversold
        if not exit_signal:
            if position["side"] == "long" and current_rsi > RSI_OVERBOUGHT_EXIT:
                exit_signal = True
                exit_reason = f"RSI_OB({current_rsi:.0f})"
            elif position["side"] == "short" and current_rsi < RSI_OVERSOLD_EXIT:
                exit_signal = True
                exit_reason = f"RSI_OS({current_rsi:.0f})"

        # 6. Time exit
        if not exit_signal and bars_held >= MAX_BARS:
            exit_signal = True
            exit_reason = f"TimeExit({bars_held})"

        if exit_signal:
            stake = capital * 0.95
            if position["side"] == "long":
                profit = (current_close - entry_price) * (stake / entry_price)
            else:
                profit = (entry_price - current_close) * (stake / entry_price)

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
                    "exit_reason": exit_reason,
                }
            )

            position = None

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
            "exit_reason": "EndOfPeriod",
        }
    )

# Results
total_return = (capital - initial_capital) / initial_capital * 100
total_trades = len(trades)
win_rate = sum(1 for t in trades if t["win"]) / max(1, total_trades) * 100
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

if trades:
    avg_profit = sum(t["profit"] for t in trades) / len(trades)
    avg_bars = sum(t["bars"] for t in trades) / len(trades)
    print(f"Average Profit per Trade: ${avg_profit:+.2f}")
    print(f"Average Bars Held:         {avg_bars:.1f}")

# Save results
results = {
    "strategy": "EMA_Cross_ADX_RSI_Optimized",
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
}

with open(
    "/home/brian/freqtrade/user_data/reports/ema_cross_adx_rsi_optimized_results.json", "w"
) as f:
    json.dump(results, f, indent=2)

print()
print("=" * 70)
print("COMPARISON SUMMARY")
print("=" * 70)
print(f"  V70 Baseline:              -1.88%")
print(f"  Optimized Strategy:        {total_return:+.2f}%")
print(f"  Difference:                {total_return - (-1.88):+.2f}%")
if total_return > -1.88:
    print("  ✓ OUTPERFORMS V70")
else:
    print("  ✗ UNDERPERFORMS V70")
print("=" * 70)
