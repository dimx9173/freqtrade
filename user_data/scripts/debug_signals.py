#!/usr/bin/env python3
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

print(f"Total rows: {len(df)}")
print(f"Signal count (short): {(df['signal'] == -1).sum()}")
cond1 = df["ema_fast"] < df["ema_slow"]
cond2 = df["adx"] >= 25
cond3 = df["minus_di"] > df["plus_di"]
cond4 = (df["rsi"] > 32) & (df["rsi"] < 72)
all_conds = cond1 & cond2 & cond3 & cond4
print(f"All conditions met: {all_conds.sum()}")
print(f"Breakdown: ema<={cond1.sum()}, adx>={cond2.sum()}, di-={cond3.sum()}, rsi={cond4.sum()}")

# Simple backtest
print("\n=== Simple backtest (ORIGINAL logic, no fees) ===")
capital = 1000
position = 0
entry_price = 0
entry_idx = 0
position_size = 0
wins = losses = 0
win_total = loss_total = 0.0
for i in range(50, len(df) - 1):
    row = df.iloc[i]
    sig = row.get("signal", 0)
    if position == 0 and sig == -1:
        position = -1
        entry_price = row["close"]
        entry_idx = i
        position_size = capital * 0.50
    elif position == -1:
        pnl_pct = (entry_price - row["close"]) / entry_price
        exit_reason = ""
        if pnl_pct >= 0.06:
            exit_reason = "TP"
        elif pnl_pct <= -0.03:
            exit_reason = "SL"
        elif i - entry_idx >= 24:
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
n = wins + losses
print(
    f"Return: {((capital - 1000) / 1000) * 100:+.2f}% | Trades: {n} | Wins: {wins} | Losses: {losses}"
)

# Now test the corrected SHORT PnL formula
print("\n=== CORRECTED SHORT PnL (entry_price - exit_price)/entry_price ===")
capital = 1000
position = 0
entry_price = 0
entry_idx = 0
wins = losses = 0
win_total = loss_total = 0.0
total_fees = 0.0
for i in range(50, len(df) - 1):
    row = df.iloc[i]
    sig = row.get("signal", 0)
    if position == 0 and sig == -1:
        position_size = capital * 0.50
        entry_price = row["close"]
        entry_idx = i
        position = -1
    elif position == -1:
        # CORRECTED: For SHORT, profit when exit_price < entry_price
        pnl_pct = (row["close"] - entry_price) / entry_price
        exit_reason = ""
        if pnl_pct <= -0.06:
            exit_reason = "TP"  # price dropped 6%
        elif pnl_pct >= 0.03:
            exit_reason = "SL"  # price rose 3%
        elif i - entry_idx >= 24:
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
n = wins + losses
print(
    f"No fee: {((capital - 1000) / 1000) * 100:+.2f}% | Trades: {n} | Wins: {wins} | Losses: {losses}"
)

# Now WITH fees (correct)
print("\n=== WITH FEES (corrected short PnL) ===")
for fee_pct in [0.0000, 0.0002, 0.0004, 0.0006]:
    capital = 1000
    position = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    wins = losses = 0
    win_total = loss_total = 0.0
    total_fees = 0.0
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        sig = row.get("signal", 0)
        if position == 0 and sig == -1:
            position_size = capital * 0.50
            fee_entry = position_size * fee_pct
            total_fees += fee_entry
            position = -1
            entry_price = row["close"]
            entry_idx = i
        elif position == -1:
            pnl_pct = (row["close"] - entry_price) / entry_price
            if pnl_pct <= -0.06:
                exit_reason = "TP"
            elif pnl_pct >= 0.03:
                exit_reason = "SL"
            elif i - entry_idx >= 24:
                exit_reason = "TIME"
            else:
                exit_reason = ""
            if exit_reason:
                fee_exit = position_size * fee_pct
                pnl = position_size * pnl_pct - fee_exit
                total_fees += fee_exit
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
    print(
        f"  Fee {fee_pct * 100:.3f}%: {ret:>+7.2f}% | {n}tr | {wr:.1f}W | R={r:.2f} | Fees={total_fees:.2f}"
    )
