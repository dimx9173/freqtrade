#!/usr/bin/env python3
"""D3e Symmetrical Strategy: Long + Short, full year test with fees"""

import pandas as pd, talib.abstract as ta

FEE = 0.0004  # 0.04% taker per side
TP = 0.06
SL = 0.03
MAX_BARS = 24
POS = 0.50


def load(pair="BTC", start="2026-01-16", end="2026-04-30"):
    df = pd.read_feather(f"user_data/data/bybit/futures/{pair}_USDT_USDT-5m-futures.feather")
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= start) & (df["date"] <= end)].set_index("date")
    df = (
        df.resample("15min")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    return df


def indicators(df):
    df["ema_fast"] = ta.EMA(df["close"], 21)
    df["ema_slow"] = ta.EMA(df["close"], 50)
    df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
    df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
    df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
    df["rsi"] = ta.RSI(df["close"], 14)
    return df


def backtest_sym(df, fee=FEE):
    """Long+Short symmetrical with fees"""
    capital = 1000.0
    position = 0
    direction = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    wins = losses = 0
    win_total = loss_total = 0.0
    long_wins = short_wins = long_losses = short_losses = 0
    long_trades = short_trades = 0
    tp_hits = sl_hits = time_hits = 0
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        # Entry signals
        if position == 0:
            # LONG: EMA uptrend + DI confirms + RSI neutral
            if (
                row["ema_fast"] > row["ema_slow"]
                and row["adx"] >= 25
                and row["plus_di"] > row["minus_di"]
                and 32 < row["rsi"] < 72
            ):
                position_size = capital * POS
                entry_price = row["close"]
                entry_idx = i
                position = 1
                direction = 1
                long_trades += 1
            # SHORT: EMA downtrend + DI confirms + RSI neutral
            elif (
                row["ema_fast"] < row["ema_slow"]
                and row["adx"] >= 25
                and row["minus_di"] > row["plus_di"]
                and 32 < row["rsi"] < 72
            ):
                position_size = capital * POS
                entry_price = row["close"]
                entry_idx = i
                position = -1
                direction = -1
                short_trades += 1
        # Exit
        elif position != 0:
            if direction == 1:  # LONG
                pnl_pct = (row["close"] - entry_price) / entry_price
                if pnl_pct >= TP:
                    exit_reason = "TP"
                    tp_hits += 1
                elif pnl_pct <= -SL:
                    exit_reason = "SL"
                    sl_hits += 1
                elif i - entry_idx >= MAX_BARS:
                    exit_reason = "TIME"
                    time_hits += 1
                else:
                    exit_reason = ""
            else:  # SHORT
                pnl_pct = (entry_price - row["close"]) / entry_price
                if pnl_pct >= TP:
                    exit_reason = "TP"
                    tp_hits += 1
                elif pnl_pct <= -SL:
                    exit_reason = "SL"
                    sl_hits += 1
                elif i - entry_idx >= MAX_BARS:
                    exit_reason = "TIME"
                    time_hits += 1
                else:
                    exit_reason = ""

            if exit_reason:
                pnl = position_size * pnl_pct - position_size * fee * 2
                capital += pnl
                if pnl > 0:
                    wins += 1
                    win_total += pnl
                    if direction == 1:
                        long_wins += 1
                    else:
                        short_wins += 1
                else:
                    losses += 1
                    loss_total += abs(pnl)
                    if direction == 1:
                        long_losses += 1
                    else:
                        short_losses += 1
                position = 0
                direction = 0
    n = wins + losses
    wr = wins / n * 100 if n > 0 else 0
    avg_win = win_total / wins if wins > 0 else 0
    avg_loss = loss_total / losses if losses > 0 else 0
    r = avg_win / avg_loss if avg_loss > 0 else 0
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    ret = ((capital - 1000) / 1000) * 100
    return {
        "return": round(ret, 2),
        "trades": n,
        "win_rate": round(wr, 1),
        "r": round(r, 2),
        "expectancy": round(exp, 4),
        "long_trades": long_trades,
        "short_trades": short_trades,
        "long_wins": long_wins,
        "long_losses": long_losses,
        "short_wins": short_wins,
        "short_losses": short_losses,
        "final_capital": round(capital, 2),
        "tp": tp_hits,
        "sl": sl_hits,
        "time": time_hits,
    }


# PART 1: 104-DAY BEAR PERIOD (Jan 16 - Apr 30, 2026)
print("=" * 75)
print("=== PART 1: BEAR MARKET (104 days, Jan16-Apr30 2026) ===")
df_bear = load("BTC", "2026-01-16", "2026-04-30")
df_bear = indicators(df_bear)
period = (df_bear["date"].iloc[-1] - df_bear["date"].iloc[0]).days
btc_ret = ((df_bear["close"].iloc[-1] / df_bear["close"].iloc[0]) - 1) * 100
print(f"BTC: {df_bear['close'].iloc[0]:.0f} -> {df_bear['close'].iloc[-1]:.0f} ({btc_ret:+.1f}%)")

r_bear = backtest_sym(df_bear)
print(f"\nD3e SYMMETRICAL (with {FEE * 100:.2f}% fee/side):")
print(
    f"  Return: {r_bear['return']:+.2f}% | Trades: {r_bear['trades']} (L={r_bear['long_trades']}, S={r_bear['short_trades']})"
)
print(f"  Win Rate: {r_bear['win_rate']:.1f}% | R={r_bear['r']:.2f} | E={r_bear['expectancy']:.4f}")
print(
    f"  Long: {r_bear['long_wins']}W/{r_bear['long_losses']}L | Short: {r_bear['short_wins']}W/{r_bear['short_losses']}L"
)
print(f"  Exit: TP={r_bear['tp']} SL={r_bear['sl']} TIME={r_bear['time']}")
print(f"  Final: ${r_bear['final_capital']:.2f}")

# PART 2: FULL YEAR (2025-01-01 to 2026-04-30, 485 days)
print("\n" + "=" * 75)
print("=== PART 2: FULL YEAR (485 days, Jan 2025 - Apr 2026) ===")
df_full = load("BTC", "2025-01-01", "2026-04-30")
df_full = indicators(df_full)
period_full = (df_full["date"].iloc[-1] - df_full["date"].iloc[0]).days
btc_full = ((df_full["close"].iloc[-1] / df_full["close"].iloc[0]) - 1) * 100
print(f"BTC: {df_full['close'].iloc[0]:.0f} -> {df_full['close'].iloc[-1]:.0f} ({btc_full:+.1f}%)")
print(f"Note: 2025 H1 was BULL RUN (BTC ~$60K->$110K), 2025 H2 was sideways, 2026 Q1-Q2 was BEAR")

r_full = backtest_sym(df_full)
annual = r_full["return"] / period_full * 365
print(f"\nD3e SYMMETRICAL (full year, {FEE * 100:.2f}% fee/side):")
print(
    f"  Return: {r_full['return']:+.2f}% ({annual:+.1f}% annualized) | Trades: {r_full['trades']} (L={r_full['long_trades']}, S={r_full['short_trades']})"
)
print(f"  Win Rate: {r_full['win_rate']:.1f}% | R={r_full['r']:.2f} | E={r_full['expectancy']:.4f}")
print(
    f"  Long: {r_full['long_wins']}W/{r_full['long_losses']}L | Short: {r_full['short_wins']}W/{r_full['short_losses']}L"
)
print(f"  Final: ${r_full['final_capital']:.2f}")

# Compare vs Buy & Hold
print(f"\n  vs BTC Buy & Hold: {btc_full:+.1f}%")
print(f"  Alpha: {r_full['return'] - btc_full:+.1f}%")

# PART 3: Compare SHORT-ONLY vs LONG-ONLY vs SYMMETRICAL (full year)
print("\n" + "=" * 75)
print("=== COMPARISON: SHORT-ONLY vs LONG-ONLY vs SYMMETRICAL (full year) ===")


def backtest_direction(df, direction, fee=FEE):
    """direction: 1=long only, -1=short only"""
    capital = 1000.0
    position = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    wins = losses = 0
    win_total = loss_total = 0.0
    total_fees = 0.0
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        if position == 0:
            if direction == 1:  # LONG only
                if (
                    row["ema_fast"] > row["ema_slow"]
                    and row["adx"] >= 25
                    and row["plus_di"] > row["minus_di"]
                    and 32 < row["rsi"] < 72
                ):
                    position_size = capital * POS
                    entry_price = row["close"]
                    entry_idx = i
                    position = 1
            else:  # SHORT only
                if (
                    row["ema_fast"] < row["ema_slow"]
                    and row["adx"] >= 25
                    and row["minus_di"] > row["plus_di"]
                    and 32 < row["rsi"] < 72
                ):
                    position_size = capital * POS
                    entry_price = row["close"]
                    entry_idx = i
                    position = -1
        elif position != 0:
            if direction == 1:
                pnl_pct = (row["close"] - entry_price) / entry_price
                if pnl_pct >= TP or pnl_pct <= -SL or i - entry_idx >= MAX_BARS:
                    pnl = position_size * pnl_pct - position_size * fee * 2
                    capital += pnl
                    if pnl > 0:
                        wins += 1
                        win_total += pnl
                    else:
                        losses += 1
                        loss_total += abs(pnl)
                    position = 0
            else:
                pnl_pct = (entry_price - row["close"]) / entry_price
                if pnl_pct >= TP or pnl_pct <= -SL or i - entry_idx >= MAX_BARS:
                    pnl = position_size * pnl_pct - position_size * fee * 2
                    capital += pnl
                    if pnl > 0:
                        wins += 1
                        win_total += pnl
                    else:
                        losses += 1
                        loss_total += abs(pnl)
                    position = 0
    n = wins + losses
    wr = wins / n * 100 if n > 0 else 0
    avg_win = win_total / wins if wins > 0 else 0
    avg_loss = loss_total / losses if losses > 0 else 0
    r = avg_win / avg_loss if avg_loss > 0 else 0
    ret = ((capital - 1000) / 1000) * 100
    return {"return": round(ret, 2), "trades": n, "win_rate": round(wr, 1), "r": round(r, 2)}


r_short = backtest_direction(df_full, -1)
r_long = backtest_direction(df_full, 1)
annual_short = r_short["return"] / period_full * 365
annual_long = r_long["return"] / period_full * 365

print(f"{'Strategy':>20} {'Return':>8} {'Ann%':>7} {'Trades':>6} {'Win%':>7} {'R':>6}")
print("-" * 60)
print(
    f"{'Short Only':>20} {r_short['return']:>+7.2f}% {annual_short:>+6.1f}% {r_short['trades']:>6} {r_short['win_rate']:>6.1f}% {r_short['r']:>6.2f}"
)
print(
    f"{'Long Only':>20} {r_long['return']:>+7.2f}% {annual_long:>+6.1f}% {r_long['trades']:>6} {r_long['win_rate']:>6.1f}% {r_long['r']:>6.2f}"
)
print(
    f"{'Symmetrical (L+S)':>20} {r_full['return']:>+7.2f}% {annual:>+6.1f}% {r_full['trades']:>6} {r_full['win_rate']:>6.1f}% {r_full['r']:>6.2f}"
)
print(f"{'BTC Buy & Hold':>20} {btc_full:>+7.1f}% {'N/A':>7} {'N/A':>6}")
print(f"\nSymmetrical beats Short-Only by: {r_full['return'] - r_short['return']:+.2f}%")
print(f"Symmetrical beats Buy&Hold by: {r_full['return'] - btc_full:+.2f}%")
