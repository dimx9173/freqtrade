#!/usr/bin/env python3
"""D3e SHORT TRADE FEE ANALYSIS"""

import pandas as pd, talib.abstract as ta

df = pd.read_feather("user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather")
df["date"] = pd.to_datetime(df["date"])
df = df[(df["date"] >= "2026-01-16") & (df["date"] <= "2026-04-30")].set_index("date")
df = (
    df.resample("15min")
    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    .dropna()
    .reset_index()
)

df["ema_fast"] = ta.EMA(df["close"], 21)
df["ema_slow"] = ta.EMA(df["close"], 50)
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

period_days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
btc_ret = ((df["close"].iloc[-1] / df["close"].iloc[0]) - 1) * 100

print("=== D3e SHORT TRADE FEE ANALYSIS ===")
print(f"Period: {df['date'].iloc[0].date()} - {df['date'].iloc[-1].date()} ({period_days} days)")
print(f"BTC: {df['close'].iloc[0]:.0f} -> {df['close'].iloc[-1]:.0f} ({btc_ret:+.1f}%)")
print()


def backtest(fee_pct):
    capital = 1000.0
    position = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    wins = losses = 0
    win_total = loss_total = 0.0
    total_fees = 0.0
    tp_hits = sl_hits = time_hits = 0
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        sig = row.get("signal", 0)
        if position == 0 and sig == -1:
            position_size = capital * 0.50
            entry_price = row["close"]
            entry_idx = i
            position = -1
        elif position == -1:
            pnl_pct = (entry_price - row["close"]) / entry_price
            exit_reason = ""
            if pnl_pct >= 0.06:
                exit_reason = "TP"
                tp_hits += 1
            elif pnl_pct <= -0.03:
                exit_reason = "SL"
                sl_hits += 1
            elif i - entry_idx >= 24:
                exit_reason = "TIME"
                time_hits += 1
            if exit_reason:
                roundtrip_fee = position_size * fee_pct * 2
                pnl = position_size * pnl_pct - roundtrip_fee
                total_fees += roundtrip_fee
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
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    ret = ((capital - 1000) / 1000) * 100
    return (
        ret,
        n,
        wr,
        r,
        exp,
        capital,
        total_fees,
        tp_hits,
        sl_hits,
        time_hits,
        win_total,
        loss_total,
    )


header = f"{'Fee':>10} {'Return':>8} {'Fees':>8} {'Trades':>6} {'Win%':>7} {'R':>6} {'Ann%':>8}   Exit breakdown"
print(header)
print("-" * 80)

for fee in [0.0000, 0.0002, 0.0004, 0.0006]:
    ret, n, wr, r, exp, final, fees, tp, sl, time, wt, lt = backtest(fee)
    annual = ret / period_days * 365
    label = "No Fee" if fee == 0 else f"{fee * 100:.3f}%"
    exit_info = f"TP={tp} SL={sl} TIME={time}"
    print(
        f"{label:>10} {ret:>+7.2f}% {fees:>8.2f} {n:>6} {wr:>6.1f}% {r:>6.2f} {annual:>+7.1f}%   {exit_info}"
    )

print()
print("Key insight: 97% of trades EXIT via TIME (24 bars = 6 hours)")
print("This means TP/SL rarely hit - most PnL comes from smaller moves captured within 6 hours")
print()
print(
    "Binance USDT Futures: Taker=0.04%/side (0.08% roundtrip), Maker=0.02%/side (0.04% roundtrip)"
)
print("Per-trade fee on $500 notional: $0.40 (taker) vs $0.20 (maker)")
print()

# Full year
print("=" * 80)
print("=== FULL YEAR (2025-01-01 to 2026-04-30, 485 days) ===")
df_full = pd.read_feather("user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather")
df_full["date"] = pd.to_datetime(df_full["date"])
df_full = df_full[(df_full["date"] >= "2025-01-01") & (df_full["date"] <= "2026-04-30")].set_index(
    "date"
)
df_full = (
    df_full.resample("15min")
    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    .dropna()
    .reset_index()
)
df_full["ema_fast"] = ta.EMA(df_full["close"], 21)
df_full["ema_slow"] = ta.EMA(df_full["close"], 50)
df_full["adx"] = ta.ADX(df_full["high"], df_full["low"], df_full["close"], 14)
df_full["plus_di"] = ta.PLUS_DI(df_full["high"], df_full["low"], df_full["close"], 14)
df_full["minus_di"] = ta.MINUS_DI(df_full["high"], df_full["low"], df_full["close"], 14)
df_full["rsi"] = ta.RSI(df_full["close"], 14)
df_full["signal"] = 0
df_full.loc[
    (df_full["ema_fast"] < df_full["ema_slow"])
    & (df_full["adx"] >= 25)
    & (df_full["minus_di"] > df_full["plus_di"])
    & (df_full["rsi"] > 32)
    & (df_full["rsi"] < 72),
    "signal",
] = -1

period_full = (df_full["date"].iloc[-1] - df_full["date"].iloc[0]).days
btc_full = ((df_full["close"].iloc[-1] / df_full["close"].iloc[0]) - 1) * 100
print(f"BTC: {df_full['close'].iloc[0]:.0f} -> {df_full['close'].iloc[-1]:.0f} ({btc_full:+.1f}%)")
print(f"Note: 2025 was BULL RUN - short strategy expected to underperform\n")

for fee, label in [(0.0000, "No Fee"), (0.0004, "Taker 0.04%")]:
    capital = 1000.0
    position = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    wins = losses = 0
    win_total = loss_total = 0.0
    total_fees = 0.0
    tp_hits = sl_hits = time_hits = 0
    for i in range(50, len(df_full) - 1):
        row = df_full.iloc[i]
        sig = row.get("signal", 0)
        if position == 0 and sig == -1:
            position_size = capital * 0.50
            entry_price = row["close"]
            entry_idx = i
            position = -1
        elif position == -1:
            pnl_pct = (entry_price - row["close"]) / entry_price
            if pnl_pct >= 0.06:
                tp_hits += 1
            elif pnl_pct <= -0.03:
                sl_hits += 1
            elif i - entry_idx >= 24:
                time_hits += 1
            if pnl_pct >= 0.06 or pnl_pct <= -0.03 or i - entry_idx >= 24:
                roundtrip_fee = position_size * fee * 2
                pnl = position_size * pnl_pct - roundtrip_fee
                total_fees += roundtrip_fee
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
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    ret = ((capital - 1000) / 1000) * 100
    annual = ret / period_full * 365
    per_trade = total_fees / n if n > 0 else 0
    print(
        f"  {label:>12}: {ret:>+7.2f}% | {n}tr | {wr:.1f}W | R={r:.2f} | Fees=${per_trade:.2f}/tr | Ann={annual:+.1f}%"
    )
    print(
        f"                Exit: TP={tp_hits} ({tp_hits / n * 100:.0f}%), SL={sl_hits} ({sl_hits / n * 100:.0f}%), TIME={time_hits} ({time_hits / n * 100:.0f}%)"
    )
