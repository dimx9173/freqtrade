"""
POC Path 2 (extended): 9-asset eigenvalue distribution (1h timeframe).
使用 Bybit 1h 資料, 10 個幣種.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path('/home/brian/freqtrade/user_data/data/bybit')

# 9 assets: Hybrid_v3 已知配置（XRP 沒有 bybit 1h 換 LINK）
ASSETS = ['BTC', 'ETH', 'SOL', 'BNB', 'LINK', 'DOGE', 'ADA', 'AVAX', 'TON', 'SUI']
print(f"Assets: {ASSETS}")
print(f"Count: {len(ASSETS)}")

# Load 1h data
ret_dict = {}
for asset in ASSETS:
    fp = DATA_DIR / f'{asset}_USDT-1h.feather'
    if not fp.exists():
        print(f"⚠️ Missing: {asset}")
        continue
    df = pd.read_feather(fp)
    df['date'] = pd.to_datetime(df['date'])
    ret = df.set_index('date')['close'].pct_change()
    ret_dict[asset] = ret
    print(f"  {asset}: {len(df)} rows, {df['date'].min()} to {df['date'].max()}")

ret_df = pd.DataFrame(ret_dict).dropna()
print(f"\n1h returns: {len(ret_df)} obs, {ret_df.index[0]} to {ret_df.index[-1]}")
print(f"Assets in final matrix: {list(ret_df.columns)}")

# Rolling correlation matrix + eigendecomp
window_eig = 24  # 24 hours
eigenvalues_list = []
msi_list = []
pr_list = []
dates_list = []
vol_list = []
sample_eigvals = []

print(f"\nComputing rolling {len(ASSETS)}x{len(ASSETS)} eigenvalues for ~{len(ret_df) // 6} windows...")

for i in range(window_eig, len(ret_df), 6):
    seg = ret_df.iloc[i-window_eig:i]
    if len(seg) < window_eig * 0.8:
        continue
    try:
        corr = seg.corr().values
        eigvals = np.linalg.eigvalsh(corr)
        eigvals = np.sort(eigvals)[::-1]
        eigvals_norm = eigvals / eigvals.sum() * len(eigvals)

        # MSI = max / mean (regime concentration)
        msi = eigvals_norm[0] / np.mean(eigvals_norm)
        # Participation Ratio (PR) = (sum)^2 / sum(squared)
        pr = (eigvals_norm.sum() ** 2) / (eigvals_norm ** 2).sum()

        eigenvalues_list.append(eigvals_norm)
        msi_list.append(msi)
        pr_list.append(pr)
        dates_list.append(ret_df.index[i])
        vol_list.append(seg['BTC'].std())
        if i == window_eig:  # 記一份 sample eigenvalues
            sample_eigvals = eigvals_norm
    except Exception:
        continue

eig_arr = np.array(eigenvalues_list) if eigenvalues_list else np.array([])
msi_arr = np.array(msi_list) if msi_list else np.array([])
pr_arr = np.array(pr_list) if pr_list else np.array([])
vol_arr = np.array(vol_list) if vol_list else np.array([])

if len(msi_arr) == 0:
    print("❌ No eigenvalue data")
    import sys
    sys.exit(0)

n = len(ASSETS)
print(f"\n{'='*70}")
print(f"Path 2 Extended: {n}-asset Eigenvalue Distribution POC")
print(f"{'='*70}")
print(f"  Computed {len(msi_arr)} windows ({len(ret_df) // 6} attempted)")
print(f"\nMarket State Index (MSI = λ_max / mean):")
print(f"  mean={msi_arr.mean():.3f}, std={msi_arr.std():.3f}")
print(f"  min={msi_arr.min():.3f}, max={msi_arr.max():.3f}")
print(f"  median={np.median(msi_arr):.3f}, p10={np.percentile(msi_arr, 10):.3f}, p90={np.percentile(msi_arr, 90):.3f}, p99={np.percentile(msi_arr, 99):.3f}")
print(f"  Theory: MSI > 2.0 = strong regime concentration, MSI < 1.5 = dispersed")

print(f"\nParticipation Ratio (PR):")
print(f"  mean={pr_arr.mean():.3f}, std={pr_arr.std():.3f}")
print(f"  min={pr_arr.min():.3f}, max={pr_arr.max():.3f}")
print(f"  N={n} assets, max PR = {n} (each asset independent)")

print(f"\nTop-{min(5, n)} eigenvalues (mean over all windows):")
for i in range(min(5, n)):
    print(f"  λ_{i+1} = {eig_arr[:, i].mean():.3f} ± {eig_arr[:, i].std():.3f}")

# Crisis detection
msi_threshold = np.percentile(msi_arr, 95)
crisis_idx = np.where(msi_arr > msi_threshold)[0]
print(f"\nMSI > p95 ({msi_threshold:.3f}) detected in {len(crisis_idx)} windows ({100*len(crisis_idx)/len(msi_arr):.1f}%)")
if len(crisis_idx) > 0:
    print(f"  Crisis date samples: {[dates_list[i].strftime('%Y-%m-%d %H:%M') for i in crisis_idx[:3]]}")
    crisis_dates_idx = crisis_idx
    crisis_vol = np.array([vol_list[i] for i in crisis_idx])
    normal_vol_mask = np.ones(len(vol_arr), dtype=bool)
    normal_vol_mask[crisis_idx] = False
    normal_vol = vol_arr[normal_vol_mask]
    print(f"  Crisis hour vol: {crisis_vol.mean():.4f}, Normal vol: {normal_vol.mean():.4f}")
    if normal_vol.mean() > 0:
        print(f"  Vol ratio (crisis/normal): {crisis_vol.mean() / normal_vol.mean():.2f}x")

# Trend detection
msi_low_threshold = np.percentile(msi_arr, 10)
trending_idx = np.where(msi_arr < msi_low_threshold)[0]
print(f"\nMSI < p10 ({msi_low_threshold:.3f}) (dispersed regime) in {len(trending_idx)} windows ({100*len(trending_idx)/len(msi_arr):.1f}%)")

# MSI-Vol correlation
msi_vol_corr = np.corrcoef(msi_arr, vol_arr)[0, 1]
print(f"\nCorrelation between MSI and BTC hourly volatility: {msi_vol_corr:.3f}")

# Regime detection test: high MSI vs future volatility
# Look at next 4h vol after each window
lookahead = 4
future_vols = []
window_dates_used = []
for i in range(len(dates_list) - lookahead):
    if dates_list[i] in ret_df.index:
        future_window = ret_df.loc[dates_list[i]:dates_list[i] + pd.Timedelta(hours=lookahead)]
        if len(future_window) >= lookahead * 0.8:
            future_vols.append(future_window['BTC'].std())
            window_dates_used.append(dates_list[i])

future_vols = np.array(future_vols[:len(msi_arr) - lookahead])
if len(future_vols) > 0 and len(future_vols) == len(msi_arr) - lookahead:
    msi_lead = msi_arr[:len(future_vols)]
    lead_corr = np.corrcoef(msi_lead, future_vols)[0, 1]
    print(f"\nPredictive power test (next {lookahead}h vol):")
    print(f"  MSI(t) → BTC_vol(t+{lookahead}h) correlation: {lead_corr:.3f}")
    print(f"  {'✅' if lead_corr > 0.3 else '⚠️' if lead_corr > 0.1 else '❌'} predictive")

# === Summary ===
print(f"\n{'='*70}")
print(f"Path 2 Extended ({n}-asset) SUMMARY")
print(f"{'='*70}")
print(f"  Mean MSI: {msi_arr.mean():.3f} (range: {msi_arr.min():.2f} ~ {msi_arr.max():.2f})")
print(f"  Std MSI: {msi_arr.std():.3f}")
print(f"  MSI-Vol correlation: {msi_vol_corr:.3f}")
if len(future_vols) > 0 and len(future_vols) == len(msi_arr) - lookahead:
    print(f"  MSI(t)→Vol(t+{lookahead}h) corr: {lead_corr:.3f}")
print(f"  Crisis detection (MSI > p95): {100*len(crisis_idx)/len(msi_arr):.1f}% windows, {crisis_vol.mean() / normal_vol.mean():.2f}x vol")

# Save data for Path 3 integration
np.savez('/tmp/path2_eigenvalue_data.npz',
         msi=msi_arr, pr=pr_arr, vol=vol_arr, dates=np.array(dates_list, dtype='datetime64[ns]'))
print(f"\nSaved to /tmp/path2_eigenvalue_data.npz for Path 3 integration")
