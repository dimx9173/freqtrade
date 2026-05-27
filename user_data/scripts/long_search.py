#!/usr/bin/env python3
"""Fast long strategy search: RSI oversold + trend tuning + regime filter"""

import pandas as pd, talib.abstract as ta, json, sys

FEE = 0.0004
TP = 0.06
SL = 0.03
MAX_BARS = 24
POS = 0.50


def load(start="2025-01-01", end="2026-04-30"):
    df = pd.read_feather("user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather")
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= start) & (df["date"] <= end)].set_index("date")
    df = (
        df.resample("15min")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    df["ema_fast"] = ta.EMA(df["close"], 21)
    df["ema_slow"] = ta.EMA(df["close"], 50)
    df["ema200"] = ta.EMA(df["close"], 200)
    df["adx"] = ta.ADX(df["high"], df["low"], df["close"], 14)
    df["plus_di"] = ta.PLUS_DI(df["high"], df["low"], df["close"], 14)
    df["minus_di"] = ta.MINUS_DI(df["high"], df["low"], df["close"], 14)
    df["rsi"] = ta.RSI(df["close"], 14)
    df["atr"] = ta.ATR(df["high"], df["low"], df["close"], 14)
    df["bb_upper"], df["bb_middle"], df["bb_lower"] = ta.BBANDS(
        df["close"], timeperiod=20, nbdevup=2.0, nbdevdn=2.0
    )
    df["macd"], df["macd_signal"], df["macd_hist"] = ta.MACD(df["close"])
    # RSI yesterday for cross detection
    df["rsi_prev"] = df["rsi"].shift(1)
    return df


def backtest(df, long_cond, short_cond, tp=TP, sl=SL, max_bars=MAX_BARS, pos=POS, name=""):
    capital = 1000.0
    position = 0
    direction = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    wins = losses = 0
    win_total = loss_total = 0.0
    long_trades = short_trades = 0
    long_wins = short_wins = 0
    long_losses = short_losses = 0
    tp_h = sl_h = time_h = 0
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        if position == 0:
            if long_cond(row):
                position_size = capital * pos
                entry_price = row["close"]
                entry_idx = i
                position = 1
                direction = 1
                long_trades += 1
            elif short_cond(row):
                position_size = capital * pos
                entry_price = row["close"]
                entry_idx = i
                position = -1
                direction = -1
                short_trades += 1
        elif position != 0:
            if direction == 1:
                pnl_pct = (row["close"] - entry_price) / entry_price
                if pnl_pct >= tp:
                    exit_reason = "TP"
                    tp_h += 1
                elif pnl_pct <= -sl:
                    exit_reason = "SL"
                    sl_h += 1
                elif i - entry_idx >= max_bars:
                    exit_reason = "TIME"
                    time_h += 1
                else:
                    exit_reason = ""
            else:
                pnl_pct = (entry_price - row["close"]) / entry_price
                if pnl_pct >= tp:
                    exit_reason = "TP"
                    tp_h += 1
                elif pnl_pct <= -sl:
                    exit_reason = "SL"
                    sl_h += 1
                elif i - entry_idx >= max_bars:
                    exit_reason = "TIME"
                    time_h += 1
                else:
                    exit_reason = ""
            if exit_reason:
                pnl = position_size * pnl_pct - position_size * FEE * 2
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
    long_pnl = win_total * (
        long_wins / (long_wins + long_losses) if long_wins + long_losses > 0 else 0
    ) - loss_total * (long_losses / (long_wins + long_losses) if long_wins + long_losses > 0 else 0)
    short_pnl = (win_total - win_total * (long_wins / (wins if wins > 0 else 1))) if wins > 0 else 0
    return {
        "name": name,
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
        "tp": tp_h,
        "sl": sl_h,
        "time": time_h,
    }


# Load data
print("Loading BTC data...")
df = load()
period_days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
btc_ret = ((df["close"].iloc[-1] / df["close"].iloc[0]) - 1) * 100
print(
    f"BTC: {df['close'].iloc[0]:.0f} -> {df['close'].iloc[-1]:.0f} ({btc_ret:+.1f}%) | {period_days} days\n"
)

results = []

# === SHORT ONLY (baseline) ===
short_cond = lambda r: (
    r["ema_fast"] < r["ema_slow"]
    and r["adx"] >= 25
    and r["minus_di"] > r["plus_di"]
    and 32 < r["rsi"] < 72
)
long_cond_false = lambda r: False  # no longs
r = backtest(df, long_cond_false, short_cond, name="Short_Only_Baseline")
print(f"SHORT ONLY: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}")
results.append(r)

# === APPROACH 1: RSI OVERSOLD (buy the dip) ===
print("\n=== RSI OVERSOLD (mean reversion) ===")
configs = [
    ("RSI<30 no filter", lambda r: r["rsi"] < 30, None, 0.04, 0.02, 20),
    (
        "RSI<35+EMAup",
        lambda r: r["rsi"] < 35 and r["ema_fast"] > r["ema_slow"],
        None,
        0.05,
        0.025,
        24,
    ),
    ("RSI<30+BB", lambda r: r["rsi"] < 30 and r["close"] <= r["bb_lower"], None, 0.04, 0.02, 20),
    ("RSI<35+ADX<25", lambda r: r["rsi"] < 35 and r["adx"] < 25, None, 0.05, 0.025, 24),
    ("RSIcross<30", lambda r: r["rsi"] < 30 and r["rsi_prev"] >= 30, None, 0.05, 0.02, 24),
]
for name, lc, sc, tp, sl, mb in configs:
    r = backtest(df, lc, lambda r: False, tp, sl, mb, 0.50, name=f"LONG_{name}")
    r["type"] = "rsi_oversold"
    print(
        f"  {name}: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
    )
    results.append(r)

# === APPROACH 2: TREND TUNING FOR LONGS ===
print("\n=== TREND TUNING FOR LONGS ===")
configs2 = [
    (
        "EMAup+ADX20+DI+",
        lambda r: (
            r["ema_fast"] > r["ema_slow"]
            and r["adx"] >= 20
            and r["plus_di"] > r["minus_di"]
            and 40 < r["rsi"] < 75
        ),
    ),
    (
        "EMAup+ADX15+RSI40_80",
        lambda r: (
            r["ema_fast"] > r["ema_slow"]
            and r["adx"] >= 15
            and r["plus_di"] > r["minus_di"]
            and 40 < r["rsi"] < 80
        ),
    ),
    (
        "EMAup+ADX25+RSIpullback45",
        lambda r: (
            r["ema_fast"] > r["ema_slow"]
            and r["adx"] >= 25
            and r["plus_di"] > r["minus_di"]
            and r["rsi"] < 45
        ),
    ),
    (
        "EMAup+ADX30+noRSI",
        lambda r: r["ema_fast"] > r["ema_slow"] and r["adx"] >= 30 and r["plus_di"] > r["minus_di"],
    ),
    ("MACDhist+RSI45_60", lambda r: r["macd_hist"] > 0 and 45 < r["rsi"] < 60),
    ("Breakout+HIGH20+EMAup", lambda r: r["close"] > r["high"] and r["ema_fast"] > r["ema_slow"]),
]
for name, lc in configs2:
    r = backtest(df, lc, lambda r: False, 0.06, 0.03, 24, 0.50, name=f"LONG_{name}")
    r["type"] = "trend_tuning"
    print(
        f"  {name}: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
    )
    results.append(r)

# === APPROACH 3: REGIME FILTER ===
print("\n=== REGIME FILTER ===")


# SMA200 filter
def long_sma_filter(r):
    return (
        r["ema_fast"] > r["ema_slow"]
        and r["adx"] >= 25
        and r["plus_di"] > r["minus_di"]
        and 32 < r["rsi"] < 72
        and r["close"] > r["ema200"]
        and r["ema_fast"] > r["ema_prev"]
        if "ema_prev" in dir()
        else True
    )


# Hmm can't reference ema_prev easily. Let me simplify
def long_sma(r):
    return (
        r["close"] > r["ema200"]
        and r["ema_fast"] > r["ema_slow"]
        and r["adx"] >= 25
        and r["plus_di"] > r["minus_di"]
        and 32 < r["rsi"] < 72
    )


def short_sma(r):
    return (
        r["close"] < r["ema200"]
        and r["ema_fast"] < r["ema_slow"]
        and r["adx"] >= 25
        and r["minus_di"] > r["plus_di"]
        and 32 < r["rsi"] < 72
    )


r = backtest(df, long_sma, short_sma, 0.06, 0.03, 24, 0.50, name="SMA200_Filter_LongShort")
r["type"] = "regime"
print(
    f"  SMA200 regime filter: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
)
results.append(r)

# Volatility filter (ATR > median)
atr_median = df["atr"].rolling(50).median().iloc[-1]


def long_vol(r):
    return (
        r["close"] > r["ema200"]
        and r["ema_fast"] > r["ema_slow"]
        and r["adx"] >= 25
        and r["plus_di"] > r["minus_di"]
        and 32 < r["rsi"] < 72
        and r["atr"] > atr_median
    )


def short_vol(r):
    return (
        r["close"] < r["ema200"]
        and r["ema_fast"] < r["ema_slow"]
        and r["adx"] >= 25
        and r["minus_di"] > r["plus_di"]
        and 32 < r["rsi"] < 72
        and r["atr"] > atr_median
    )


r = backtest(df, long_vol, short_vol, 0.06, 0.03, 24, 0.50, name="ATR_Vol_Filter")
r["type"] = "regime"
print(
    f"  ATR volatility filter: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
)
results.append(r)

# === APPROACH 4: COMBINED BEST LONG + D3e SHORT ===
print("\n=== COMBINED: Best Long + D3e Short ===")


# Best long so far: RSI<35+EMAup with TP5/SL2.5
def long_best(r):
    return r["rsi"] < 35 and r["ema_fast"] > r["ema_slow"]


def short_d3e(r):
    return (
        r["ema_fast"] < r["ema_slow"]
        and r["adx"] >= 25
        and r["minus_di"] > r["plus_di"]
        and 32 < r["rsi"] < 72
    )


# Different TP/SL for long vs short
r = backtest(df, long_best, short_d3e, 0.06, 0.03, 24, 0.50, name="Combined_RSI35_long_D3e_short")
r["type"] = "combined"
print(
    f"  RSI35_long + D3e_short: {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
)
results.append(r)


# Try: RSI oversold LONG (TP5, SL2) + D3e SHORT (TP6, SL3)
def backtest_mixed(df, tp_long, sl_long, tp_short, sl_short, name):
    capital = 1000.0
    position = 0
    direction = 0
    entry_price = 0
    entry_idx = 0
    position_size = 0
    wins = losses = 0
    win_total = loss_total = 0.0
    long_trades = short_trades = 0
    long_wins = short_wins = 0
    long_losses = short_losses = 0
    tp_h = sl_h = time_h = 0
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        if position == 0:
            # LONG: RSI oversold + EMA uptrend
            if row["rsi"] < 35 and row["ema_fast"] > row["ema_slow"]:
                position_size = capital * POS
                entry_price = row["close"]
                entry_idx = i
                position = 1
                direction = 1
                long_trades += 1
            # SHORT: D3e
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
        elif position != 0:
            if direction == 1:
                pnl_pct = (row["close"] - entry_price) / entry_price
                tp_use = tp_long
                sl_use = sl_long
            else:
                pnl_pct = (entry_price - row["close"]) / entry_price
                tp_use = tp_short
                sl_use = sl_short
            if pnl_pct >= tp_use:
                exit_reason = "TP"
                tp_h += 1
            elif pnl_pct <= -sl_use:
                exit_reason = "SL"
                sl_h += 1
            elif i - entry_idx >= MAX_BARS:
                exit_reason = "TIME"
                time_h += 1
            else:
                exit_reason = ""
            if exit_reason:
                pnl = position_size * pnl_pct - position_size * FEE * 2
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
    r_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    exp = (wr / 100 * avg_win - (1 - wr / 100) * avg_loss) / 10 if n > 0 else 0
    ret = ((capital - 1000) / 1000) * 100
    return {
        "name": name,
        "return": round(ret, 2),
        "trades": n,
        "win_rate": round(wr, 1),
        "r": round(r_ratio, 2),
        "expectancy": round(exp, 4),
        "long_trades": long_trades,
        "short_trades": short_trades,
        "final_capital": round(capital, 2),
        "type": "combined",
    }


r = backtest_mixed(df, 0.05, 0.025, 0.06, 0.03, "RSI35_long+EMA_D3e_short_TP5_SL2.5")
print(
    f"  RSI_long(TP5/SL2.5) + D3e_short(TP6/SL3): {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
)
results.append(r)

r = backtest_mixed(df, 0.04, 0.02, 0.06, 0.03, "RSI30_long_TP4_SL2_D3e_short")
print(
    f"  RSI_long(TP4/SL2) + D3e_short(TP6/SL3): {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
)
results.append(r)

r = backtest_mixed(df, 0.06, 0.03, 0.06, 0.03, "RSI35_EMAup_long_D3e_short_same")
print(
    f"  RSI35_EMAup_long + D3e_short (same TP/SL): {r['return']:+.2f}% | {r['trades']}tr | {r['win_rate']:.1f}W | R={r['r']:.2f}"
)
results.append(r)

# === FINAL RANKING ===
print("\n" + "=" * 75)
print("=== FINAL RANKING (full year, with fees) ===")
print(f"{'Strategy':>45} {'Return':>8} {'Trades':>6} {'Win%':>7} {'R':>6} {'E':>8}")
print("-" * 75)
sorted_results = sorted(results, key=lambda x: x["return"], reverse=True)
for r in sorted_results:
    print(
        f"{r['name']:>45} {r['return']:>+7.2f}% {r['trades']:>6} {r['win_rate']:>6.1f}% {r['r']:>6.2f} {r['expectancy']:>8.4f}"
    )

print(f"\nBTC Buy & Hold: {btc_ret:+.1f}%")
print(f"Best vs B&H: {sorted_results[0]['return'] - btc_ret:+.2f}%")

# Save
with open("user_data/reports/long_search_results.json", "w") as f:
    json.dump({"results": results, "btc_return": btc_ret, "period_days": period_days}, f, indent=2)
print(f"\nSaved: user_data/reports/long_search_results.json")
