"""
POC for Path 1 (cointegration) + Path 2 (eigenvalue distribution).
使用 1h timeframe 取得更長歷史.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd


warnings.filterwarnings("ignore")

DATA_DIR = Path("/home/brian/freqtrade/user_data/data/binance")

print("=" * 70)
print("PATH 1: BTC-ETH Cointegration POC (1h timeframe)")
print("=" * 70)

btc_1h = pd.read_feather(DATA_DIR / "BTC_USDT-1h.feather")
eth_15m = pd.read_feather(DATA_DIR / "ETH_USDT-15m.feather")
btc_1h["date"] = pd.to_datetime(btc_1h["date"])
eth_15m["date"] = pd.to_datetime(eth_15m["date"])

# Resample ETH 15m to 1h
eth_1h = eth_15m.set_index("date").resample("1h").agg({"close": "last"}).dropna().reset_index()

print(f"BTC 1h: {len(btc_1h)} candles, {btc_1h['date'].min()} to {btc_1h['date'].max()}")
print(f"ETH 1h (resampled from 15m): {len(eth_1h)} candles")

df = (
    btc_1h[["date", "close"]]
    .rename(columns={"close": "btc"})
    .merge(eth_1h[["date", "close"]].rename(columns={"close": "eth"}), on="date", how="inner")
    .dropna()
    .sort_values("date")
    .reset_index(drop=True)
)
print(f"Aligned: {len(df)} candles ({len(df) / 24:.0f} days)")

df["log_btc"] = np.log(df["btc"])
df["log_eth"] = np.log(df["eth"])

X = df["log_eth"].values
Y = df["log_btc"].values
beta = np.cov(X, Y, ddof=1)[0, 1] / np.var(X, ddof=1)
alpha = np.mean(Y) - beta * np.mean(X)
print(f"OLS hedge ratio: beta={beta:.4f}, alpha={alpha:.4f}")

spread = Y - (alpha + beta * X)

from statsmodels.tsa.stattools import adfuller


nobs = len(spread)
maxlag = min(5, nobs // 4)
adf_stat, adf_p, _, _, crit, _ = adfuller(spread, maxlag=maxlag, autolag="AIC")
print(f"\nADF on spread: stat={adf_stat:.3f}, p-value={adf_p:.4f}")
print(f"Critical values: 1%={crit['1%']:.2f}, 5%={crit['5%']:.2f}, 10%={crit['10%']:.2f}")
if adf_p < 0.05:
    print("✅ Cointegrated at 5% level (full sample)")
else:
    print("❌ NOT cointegrated at 5% level (full sample)")

rolling_window = 30 * 24
print(f"Rolling window: {rolling_window} hours ({rolling_window / 24:.0f} days)")

rolling_p = []
for i in range(rolling_window, len(df)):
    seg = spread[i - rolling_window : i]
    try:
        _, p, _, _, _, _ = adfuller(seg, maxlag=3, autolag="AIC")
        rolling_p.append(p)
    except:
        rolling_p.append(np.nan)
rolling_p = np.array(rolling_p)
pct_coint_5pct = np.nanmean(rolling_p < 0.05) * 100
pct_coint_1pct = np.nanmean(rolling_p < 0.01) * 100
pct_coint_10pct = np.nanmean(rolling_p < 0.10) * 100
print("\nRolling 30-day cointegration:")
print(f"  p<0.10: {pct_coint_10pct:.1f}% of windows")
print(f"  p<0.05: {pct_coint_5pct:.1f}% of windows")
print(f"  p<0.01: {pct_coint_1pct:.1f}% of windows")

spread_mean = spread.mean()
spread_std = spread.std()
z = (spread - spread_mean) / spread_std
print(f"\nSpread z-score: min={z.min():.2f}, max={z.max():.2f}, std={z.std():.2f}")

enter_long = (z < -2.0).sum()
enter_short = (z > 2.0).sum()
print(f"z<-2.0 (long spread): {enter_long} triggers")
print(f"z>2.0 (short spread): {enter_short} triggers")
print(f"Total entry signals: {enter_long + enter_short}")
print(f"Daily average: {(enter_long + enter_short) / (len(df) / 24):.2f}")

delta_spread = np.diff(spread)
lag_spread = spread[:-1]
beta_hl = np.polyfit(lag_spread, delta_spread, 1)[0]
half_life_h = -np.log(2) / beta_hl if beta_hl < 0 else np.inf
half_life_d = half_life_h / 24
print(f"\nHalf-life of mean reversion: {half_life_d:.2f} days ({half_life_h:.1f} hours)")
if half_life_h < 0:
    print("❌ Spread is NOT mean-reverting (diverging)")
elif half_life_d > 60:
    print("⚠️ Mean reversion very slow (>60 days, not tradeable)")
elif half_life_d > 7:
    print("⚠️ Mean reversion slow (7-60 days)")
else:
    print(f"✅ Mean reversion fast ({half_life_d:.1f} days, tradeable)")

# === BTC-SOL ===
print("\n" + "=" * 70)
print("BTC-SOL Cointegration POC (1h timeframe)")
print("=" * 70)

sol_5m = pd.read_feather(DATA_DIR / "SOL_USDT-5m.feather")
sol_5m["date"] = pd.to_datetime(sol_5m["date"])
sol_1h = sol_5m.set_index("date").resample("1h").agg({"close": "last"}).dropna().reset_index()

df_sol = (
    btc_1h[["date", "close"]]
    .rename(columns={"close": "btc"})
    .merge(sol_1h[["date", "close"]].rename(columns={"close": "sol"}), on="date", how="inner")
    .dropna()
    .sort_values("date")
    .reset_index(drop=True)
)
print(f"Aligned: {len(df_sol)} candles ({len(df_sol) / 24:.0f} days)")

X_sol = np.log(df_sol["sol"].values)
Y_sol = np.log(df_sol["btc"].values)
beta_sol = np.cov(X_sol, Y_sol, ddof=1)[0, 1] / np.var(X_sol, ddof=1)
alpha_sol = np.mean(Y_sol) - beta_sol * np.mean(X_sol)
spread_sol = Y_sol - (alpha_sol + beta_sol * X_sol)
adf_sol_stat, adf_sol_p, _, _, _, _ = adfuller(spread_sol, maxlag=5, autolag="AIC")
print(f"OLS hedge ratio: beta={beta_sol:.4f}")
print(f"ADF: stat={adf_sol_stat:.3f}, p={adf_sol_p:.4f}")
if adf_sol_p < 0.05:
    print("✅ BTC-SOL cointegrated (full sample)")
else:
    print("❌ BTC-SOL NOT cointegrated (full sample)")

rolling_p_sol = []
spread_sol_arr = spread_sol
for i in range(rolling_window, len(df_sol)):
    seg = spread_sol_arr[i - rolling_window : i]
    try:
        _, p, _, _, _, _ = adfuller(seg, maxlag=3, autolag="AIC")
        rolling_p_sol.append(p)
    except:
        rolling_p_sol.append(np.nan)
pct_sol = np.nanmean(np.array(rolling_p_sol) < 0.05) * 100
print(f"Rolling 30-day coint p<0.05: {pct_sol:.1f}% of windows")

# === PATH 2: Eigenvalue distribution POC (1h timeframe) ===
print("\n" + "=" * 70)
print("PATH 2: Eigenvalue Distribution POC (1h timeframe, 3 assets)")
print("=" * 70)

# Use BTC 1h + ETH 1h + SOL 1h
btc_1h_ret = btc_1h.set_index("date")["close"].pct_change()
eth_1h_ret = eth_1h.set_index("date")["close"].pct_change()
sol_1h_ret = sol_1h.set_index("date")["close"].pct_change()

ret_1h = pd.DataFrame(
    {
        "btc": btc_1h_ret,
        "eth": eth_1h_ret,
        "sol": sol_1h_ret,
    }
).dropna()
print(f"1h returns: {len(ret_1h)} obs, {ret_1h.index[0]} to {ret_1h.index[-1]}")

if len(ret_1h) < 100:
    print("⚠️ Not enough data for eigenvalue computation")
    print("\n" + "=" * 70)
    print("POC SUMMARY")
    print("=" * 70)
    print("\n[Path 1: Cointegration] ❌ FAILED on both pairs")
    print("[Path 2: Eigenvalue] ⚠️ Insufficient data")
    import sys

    sys.exit(0)

window_eig = 24
eigenvalues_list = []
msi_list = []
pr_list = []
dates_list = []
vol_list = []

print(f"Computing rolling eigenvalues for ~{len(ret_1h) // 6} windows...")

for i in range(window_eig, len(ret_1h), 6):
    seg = ret_1h.iloc[i - window_eig : i]
    if len(seg) < window_eig * 0.8:
        continue
    try:
        corr = seg.corr().values
        eigvals = np.linalg.eigvalsh(corr)
        eigvals = np.sort(eigvals)[::-1]
        eigvals_norm = eigvals / eigvals.sum() * len(eigvals)
        msi = eigvals_norm[0] / np.mean(eigvals_norm)
        pr = (eigvals_norm.sum() ** 2) / (eigvals_norm**2).sum()
        eigenvalues_list.append(eigvals_norm)
        msi_list.append(msi)
        pr_list.append(pr)
        dates_list.append(ret_1h.index[i])
        vol_list.append(seg["btc"].std())
    except Exception:
        continue

eig_arr = np.array(eigenvalues_list) if eigenvalues_list else np.array([])
msi_arr = np.array(msi_list) if msi_list else np.array([])
pr_arr = np.array(pr_list) if pr_list else np.array([])
vol_arr = np.array(vol_list) if vol_list else np.array([])

if len(msi_arr) == 0:
    print("No eigenvalue data computed")
    import sys

    sys.exit(0)

print("\n3-asset (BTC, ETH, SOL) eigenvalue distribution:")
print(f"  Computed {len(msi_arr)} windows")
print("\nMarket State Index (MSI = λ_max / mean):")
print(f"  mean={msi_arr.mean():.3f}, std={msi_arr.std():.3f}")
print(f"  min={msi_arr.min():.3f}, max={msi_arr.max():.3f}")
print(
    f"  median={np.median(msi_arr):.3f}, p90={np.percentile(msi_arr, 90):.3f}, p99={np.percentile(msi_arr, 99):.3f}"
)

print("\nParticipation Ratio (PR):")
print(f"  mean={pr_arr.mean():.3f}, std={pr_arr.std():.3f}")
print(f"  min={pr_arr.min():.3f}, max={pr_arr.max():.3f}")
print(f"  N={ret_1h.shape[1]} assets, max PR = {ret_1h.shape[1]}")

print("\nTop-3 eigenvalues (mean over all windows):")
for i in range(min(3, eig_arr.shape[1])):
    print(f"  λ_{i + 1} = {eig_arr[:, i].mean():.3f} ± {eig_arr[:, i].std():.3f}")

msi_threshold = np.percentile(msi_arr, 95)
crisis_idx = np.where(msi_arr > msi_threshold)[0]
print(
    f"\nMSI > p95 ({msi_threshold:.3f}) detected in {len(crisis_idx)} windows ({100 * len(crisis_idx) / len(msi_arr):.1f}%)"
)
if len(crisis_idx) > 0:
    print(
        f"  Crisis date samples: {[dates_list[i].strftime('%Y-%m-%d %H:%M') for i in crisis_idx[:3]]}"
    )
    crisis_dates = [dates_list[i] for i in crisis_idx]
    crisis_vol = np.array([vol_list[i] for i in crisis_idx])
    normal_vol_mask = np.ones(len(vol_arr), dtype=bool)
    normal_vol_mask[crisis_idx] = False
    normal_vol = vol_arr[normal_vol_mask]
    print(f"  Crisis hour vol: {crisis_vol.mean():.4f}, Normal vol: {normal_vol.mean():.4f}")
    if normal_vol.mean() > 0:
        print(f"  Vol ratio (crisis/normal): {crisis_vol.mean() / normal_vol.mean():.2f}x")

msi_vol_corr = np.corrcoef(msi_arr, vol_arr)[0, 1]
print(f"\nCorrelation between MSI and BTC hourly volatility: {msi_vol_corr:.3f}")

# === Summary ===
print("\n" + "=" * 70)
print("POC SUMMARY")
print("=" * 70)
print("\n[Path 1: Cointegration]")
print(
    f"  BTC-ETH: ADF p={adf_p:.4f} ({'✅' if adf_p < 0.05 else '❌'}), rolling p<0.05: {pct_coint_5pct:.0f}%"
)
print(
    f"  BTC-SOL: ADF p={adf_sol_p:.4f} ({'✅' if adf_sol_p < 0.05 else '❌'}), rolling p<0.05: {pct_sol:.0f}%"
)
print(f"  BTC-ETH half-life: {half_life_d:.1f} days ({'✅' if 0 < half_life_d < 30 else '⚠️/❌'})")
print(
    f"  Entry signals: {enter_long + enter_short} over {len(df) / 24:.0f} days = {(enter_long + enter_short) / (len(df) / 24):.2f}/day"
)

print("\n[Path 2: Eigenvalue]")
print(f"  Mean MSI: {msi_arr.mean():.3f} (>1.5 = regime concentration)")
print(f"  p95 MSI threshold: {msi_threshold:.3f}")
print(f"  Crisis detection: {len(crisis_idx)} events ({100 * len(crisis_idx) / len(msi_arr):.1f}%)")
if len(crisis_idx) > 0:
    print(f"  Vol ratio: {crisis_vol.mean() / normal_vol.mean():.2f}x (crisis vs normal)")
print(f"  MSI-Vol correlation: {msi_vol_corr:.3f} ({'✅' if msi_vol_corr > 0.3 else '⚠️'})")
