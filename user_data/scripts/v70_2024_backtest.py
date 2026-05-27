#!/usr/bin/env python3
"""
V70 Backtest on 2024 BTC/USDT Bull Market Period - Improved Simulation
Uses proper V70 regime detection and position sizing per regime.
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
import json

print("=" * 70)
print("V70 BACKTEST ON 2024 BTC/USDT BULL MARKET PERIOD")
print("=" * 70)
print()

# Load 2024 data
df = pd.read_feather("user_data/data/binance/BTC_USDT-5m.feather")
print(f"Data loaded: {len(df)} rows")
print(f"Date range: {df.iloc[0]['date']} to {df.iloc[-1]['date']}")
print()

# Resample to 15m for strategy timeframe
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date")
df_15m = (
    df.resample("15min")
    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    .dropna()
)
df_15m = df_15m.reset_index()
print(f"Resampled to 15m: {len(df_15m)} rows")
print()

# Calculate indicators for regime detection (V70 logic)
print("Calculating V70 regime detection indicators...")
df_15m["ema_fast"] = ta.EMA(df_15m["close"].values, timeperiod=12)
df_15m["ema_slow"] = ta.EMA(df_15m["close"].values, timeperiod=26)
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
df_15m["atr"] = ta.ATR(
    df_15m["high"].values, df_15m["low"].values, df_15m["close"].values, timeperiod=14
)
df_15m["rsi"] = ta.RSI(df_15m["close"].values, timeperiod=14)

# BB for volatility
bb_upper, bb_middle, bb_lower = ta.BBANDS(
    df_15m["close"].values, timeperiod=20, nbdevup=2.0, nbdevdn=2.0
)
df_15m["bb_upper"] = pd.Series(bb_upper, index=df_15m.index)
df_15m["bb_middle"] = pd.Series(bb_middle, index=df_15m.index)
df_15m["bb_lower"] = pd.Series(bb_lower, index=df_15m.index)

# Volatility percentile
df_15m["atr_pct"] = (
    df_15m["atr"]
    .rolling(50)
    .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
)

# Detect regime (V70 logic)
df_15m["market_regime"] = "sideways"

# Volatile (highest priority - override others)
volatile_mask = df_15m["atr_pct"] > 0.80
df_15m.loc[volatile_mask, "market_regime"] = "volatile"

# Sideways (ADX < 25)
sideways = (df_15m["adx"] < 25) & (~volatile_mask)
df_15m.loc[sideways, "market_regime"] = "sideways"

# Uptrend
uptrend = (
    (df_15m["ema_fast"] > df_15m["ema_slow"])
    & (df_15m["close"] > df_15m["ema_medium"])
    & (df_15m["adx"] >= 25)
    & (df_15m["plus_di"] > df_15m["minus_di"])
    & (~volatile_mask)
)
df_15m.loc[uptrend, "market_regime"] = "uptrend"

# Downtrend
downtrend = (
    (df_15m["ema_fast"] < df_15m["ema_slow"])
    & (df_15m["close"] < df_15m["ema_medium"])
    & (df_15m["adx"] >= 28)
    & (df_15m["minus_di"] > df_15m["plus_di"])
    & (~volatile_mask)
)
df_15m.loc[downtrend, "market_regime"] = "downtrend"

# Regime distribution
print()
print("REGIME DISTRIBUTION IN 2024 BTC/USDT:")
print("-" * 50)
regime_counts = df_15m["market_regime"].value_counts()
total = len(df_15m)
results = {}
for regime, count in regime_counts.items():
    pct = count / total * 100
    print(f"  {regime.upper():12}: {count:6} candles ({pct:5.1f}%)")

    regime_data = df_15m[df_15m["market_regime"] == regime]
    if len(regime_data) > 0:
        start_price = regime_data.iloc[0]["close"]
        end_price = regime_data.iloc[-1]["close"]
        change_pct = (end_price - start_price) / start_price * 100
        results[regime] = {
            "candles": len(regime_data),
            "start_price": start_price,
            "end_price": end_price,
            "change_pct": change_pct,
        }

print()
print("PRICE PERFORMANCE PER REGIME:")
print("-" * 50)
for regime in ["uptrend", "downtrend", "sideways", "volatile"]:
    if regime in results:
        r = results[regime]
        print(
            f"  {regime.upper():12}: {r['start_price']:,.0f} -> {r['end_price']:,.0f} ({r['change_pct']:+.2f}%)"
        )

print()
print("=" * 70)
print("V70 BACKTEST RESULTS ON 2024 BULL MARKET")
print("=" * 70)
print()

# V70 Backtest with proper regime-based position sizing
initial_capital = 10000
capital = initial_capital
position = None
trades = []
regime_stats = {
    r: {"count": 0, "profit": 0, "wins": 0}
    for r in ["uptrend", "downtrend", "sideways", "volatile"]
}

# V70 Position sizing multipliers
POSITION_MULT = {
    "uptrend": 1.0,  # Full size in uptrend
    "downtrend": 0.5,  # Half size for shorts in downtrend
    "sideways": 0.4,  # Reduced in sideways
    "volatile": 0.3,  # Minimal in volatile
}

# V70 trailing offsets
TRAILING_OFFSET = {"uptrend": 0.025, "downtrend": 0.012, "sideways": 0.008, "volatile": 0.015}

for i, (idx, row) in enumerate(df_15m.iterrows()):
    current_regime = row["market_regime"]

    # Entry logic per V70 regime rules
    if position is None:
        entry_signal = False

        if current_regime == "uptrend":
            # Trend following - enter long on strength
            if row["adx"] >= 25 and row["plus_di"] > row["minus_di"]:
                entry_signal = True
                position_side = "long"
        elif current_regime == "downtrend":
            # Shorting in downtrend - be selective
            if row["adx"] >= 28 and row["minus_di"] > row["plus_di"]:
                if np.random.random() > 0.5:  # 50% chance to enter
                    entry_signal = True
                    position_side = "short"
        elif current_regime == "sideways":
            # Mean reversion in sideways - only on extreme
            bb_lower_val = row["bb_lower"]
            bb_upper_val = row["bb_upper"]
            if not np.isnan(bb_lower_val) and not np.isnan(bb_upper_val):
                bb_range = bb_upper_val - bb_lower_val
                if bb_range > 0:
                    bb_pct = (row["close"] - bb_lower_val) / bb_range
                    if bb_pct < 0.15:  # Oversold - long
                        entry_signal = True
                        position_side = "long"
                    elif bb_pct > 0.85:  # Overbought - short
                        entry_signal = True
                        position_side = "short"

        if entry_signal:
            mult = POSITION_MULT.get(current_regime, 0.3)
            position = {
                "side": position_side,
                "entry_price": row["close"],
                "entry_idx": i,
                "regime": current_regime,
                "mult": mult,
                "trailing_offset": TRAILING_OFFSET.get(current_regime, 0.015),
                "entry_atr": row["atr"],
            }

    # Exit logic
    if position is not None:
        exit_signal = False
        bars_held = i - position["entry_idx"]
        entry_price = position["entry_price"]
        regime = position["regime"]

        # Calculate profit
        if position["side"] == "long":
            profit_pct = (row["close"] - entry_price) / entry_price
        else:
            profit_pct = (entry_price - row["close"]) / entry_price

        # Regime-based exits
        if regime == "uptrend":
            # Exit if trend breaks
            if row["ema_fast"] < row["ema_slow"]:
                exit_signal = True
            # Or if profit target reached
            if profit_pct > 0.08:
                exit_signal = True
        elif regime == "downtrend":
            # Exit short if trend breaks
            if row["ema_fast"] > row["ema_slow"]:
                exit_signal = True
            if profit_pct > 0.04:
                exit_signal = True
        elif regime == "sideways":
            # Quick exits in sideways
            if profit_pct > 0.02:
                exit_signal = True
            if profit_pct < -0.02:
                exit_signal = True
        elif regime == "volatile":
            # Fast exits in volatile
            if profit_pct > 0.03:
                exit_signal = True
            if profit_pct < -0.04:
                exit_signal = True

        # Time-based exit (max 4 hours = 16 candles)
        if bars_held > 16:
            exit_signal = True

        # Stop loss
        if profit_pct < -0.08:
            exit_signal = True

        if exit_signal:
            # Calculate P&L with position sizing
            mult = position["mult"]
            stake = capital * mult * 0.95
            if position["side"] == "long":
                profit = (row["close"] - entry_price) * (stake / entry_price)
            else:
                profit = (entry_price - row["close"]) * (stake / entry_price)

            # Fees (0.1% per trade)
            fees = stake * 0.001 * 2
            profit -= fees

            capital += profit

            trades.append(
                {
                    "regime": regime,
                    "side": position["side"],
                    "profit_pct": profit_pct,
                    "profit": profit,
                    "bars": bars_held,
                    "win": profit > 0,
                }
            )

            regime_stats[regime]["count"] += 1
            regime_stats[regime]["profit"] += profit
            if profit > 0:
                regime_stats[regime]["wins"] += 1

            position = None

# Close open position at end
if position is not None:
    last_row = df_15m.iloc[-1]
    entry_price = position["entry_price"]
    mult = position["mult"]
    stake = capital * mult * 0.95

    if position["side"] == "long":
        profit = (last_row["close"] - entry_price) * (stake / entry_price)
    else:
        profit = (entry_price - last_row["close"]) * (stake / entry_price)

    fees = stake * 0.001 * 2
    profit -= fees
    capital += profit

    regime_stats[position["regime"]]["count"] += 1
    regime_stats[position["regime"]]["profit"] += profit
    if profit > 0:
        regime_stats[position["regime"]]["wins"] += 1

# Results
total_return = (capital - initial_capital) / initial_capital * 100
win_rate = sum(1 for t in trades if t["win"]) / max(1, len(trades)) * 100

print(f"Initial Capital: ${initial_capital:,.2f}")
print(f"Final Capital:   ${capital:,.2f}")
print(f"Total Return:    {total_return:+.2f}%")
print(f"Total Trades:    {len(trades)}")
print(f"Win Rate:        {win_rate:.1f}%")
print()

print("REGIME BREAKDOWN:")
print("-" * 70)
print(f"{'Regime':<12} {'Trades':<8} {'Wins':<6} {'Losses':<8} {'Win%':<8} {'Profit':<12}")
print("-" * 70)

for regime in ["uptrend", "downtrend", "sideways", "volatile"]:
    stats = regime_stats[regime]
    total_trades = stats["count"]
    wins = stats["wins"]
    losses = total_trades - wins
    win_pct = wins / total_trades * 100 if total_trades > 0 else 0
    print(
        f"{regime.upper():<12} {total_trades:<8} {wins:<6} {losses:<8} {win_pct:>5.1f}%   ${stats['profit']:>+8.2f}"
    )

print("-" * 70)
print()

# Save results
results_2024 = {
    "period": "2024-01-01 to 2024-12-31",
    "initial_capital": initial_capital,
    "final_capital": capital,
    "total_return": total_return,
    "total_trades": len(trades),
    "win_rate": win_rate,
    "regime_distribution": {
        regime: {
            "candles": int(results[regime]["candles"]),
            "price_change_pct": results[regime]["change_pct"],
        }
        for regime in results
    },
    "regime_stats": {
        regime: {
            "trades": stats["count"],
            "wins": stats["wins"],
            "losses": stats["count"] - stats["wins"],
            "win_rate": stats["wins"] / stats["count"] * 100 if stats["count"] > 0 else 0,
            "profit": stats["profit"],
        }
        for regime, stats in regime_stats.items()
    },
}

with open("/home/brian/freqtrade/user_data/reports/v70_2024_bull_market_results.json", "w") as f:
    json.dump(results_2024, f, indent=2)

print("Results saved to: user_data/reports/v70_2024_bull_market_results.json")
print()
print("=" * 70)
print("CONCLUSION")
print("=" * 70)
if total_return > 0:
    print(f"✓ V70 IS PROFITABLE IN 2024 BULL MARKET with {total_return:+.2f}% return")
else:
    print(f"✗ V70 IS NOT PROFITABLE IN 2024 BULL MARKET with {total_return:+.2f}% return")
print("=" * 70)
