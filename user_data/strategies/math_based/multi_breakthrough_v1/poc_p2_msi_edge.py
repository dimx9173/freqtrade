"""
POC: Verify if MSI 10-asset filter has real edge for BTC entry timing.
Quick backtest on BTC 1h (Binance 28 月歷史).
"""
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path('/home/brian/freqtrade/user_data/data/bybit')

ASSETS = ['BTC', 'ETH', 'SOL', 'BNB', 'LINK', 'DOGE', 'ADA', 'AVAX', 'TON', 'SUI']

print("="*70)
print("POC: MSI Filter Edge Validation (BTC 1h)")
print("="*70)

# Load BTC from Bybit (1h, shorter history but consistent with other 9 assets)
btc = pd.read_feather(DATA_DIR / 'BTC_USDT-1h.feather')
btc['date'] = pd.to_datetime(btc['date'])
btc = btc.sort_values('date').reset_index(drop=True)
print(f"BTC 1h (Bybit): {len(btc)} rows, {btc['date'].min()} to {btc['date'].max()}")

# Compute BTC features
import talib.abstract as ta
btc['ema_12'] = ta.EMA(btc, timeperiod=12)
btc['ema_26'] = ta.EMA(btc, timeperiod=26)
btc['ema_50'] = ta.EMA(btc, timeperiod=50)
btc['rsi'] = ta.RSI(btc, timeperiod=14)
btc['adx'] = ta.ADX(btc, timeperiod=14)
btc['atr'] = ta.ATR(btc, timeperiod=14)

# Load 10 assets and compute 1h returns
ret_dict = {}
for asset in ASSETS:
    if asset == 'BTC':
        ret_dict[asset] = btc.set_index('date')['close'].pct_change()
    else:
        df = pd.read_feather(DATA_DIR / f'{asset}_USDT-1h.feather')
        df['date'] = pd.to_datetime(df['date'])
        ret_dict[asset] = df.set_index('date')['close'].pct_change()

ret_df = pd.DataFrame(ret_dict)
# Drop rows where any asset has NaN (preserve alignment)
ret_df = ret_df.dropna()
print(f"Returns: {ret_df.shape}, after dropna: {len(ret_df)} rows")
print(f"Date range: {ret_df.index[0]} to {ret_df.index[-1]}")

# Compute rolling 24h MSI
print("\nComputing 24h rolling MSI for 10 assets...")
window = 24
msi_list = []
dates_list = []
for i in range(window, len(ret_df)):
    seg = ret_df.iloc[i-window:i]
    if seg.isna().any().any():
        msi_list.append(np.nan)
        dates_list.append(ret_df.index[i])
        continue
    try:
        corr = seg.corr().values
        eigvals = np.linalg.eigvalsh(corr)
        eigvals = np.sort(eigvals)[::-1]
        eigvals_norm = eigvals / eigvals.sum() * len(eigvals)
        msi = eigvals_norm[0] / np.mean(eigvals_norm)
        msi_list.append(msi)
    except:
        msi_list.append(np.nan)
    dates_list.append(ret_df.index[i])

msi_series = pd.Series(msi_list, index=dates_list, name='msi')
print(f"MSI computed: {msi_series.notna().sum()} values")

# Merge MSI with BTC features (forward fill to BTC index)
btc_indexed = btc.set_index('date')
msi_aligned = msi_series.reindex(btc_indexed.index)
btc['msi'] = msi_aligned.ffill().values
btc = btc.dropna(subset=['msi', 'ema_50', 'rsi', 'adx'])
print(f"After merge: {len(btc)} rows ({btc['date'].min()} to {btc['date'].max()})")

# Simple entry signal: trend-following (Hybrid_v3 regime=2 style)
btc['enter_long'] = (
    (btc['ema_12'] > btc['ema_26'])
    & (btc['adx'] > 20)
    & (btc['close'] > btc['ema_50'])
).astype(int)

# Forward 4h return (for evaluation)
btc['future_ret_4h'] = btc['close'].pct_change(4).shift(-4)
btc['future_ret_24h'] = btc['close'].pct_change(24).shift(-24)

# === Edge analysis: Group A vs B vs C ===
print(f"\n{'='*70}")
print("Edge Analysis: MSI Filter Impact on Entry Performance")
print("="*70)

# Group definitions based on POC results (mean MSI = 7.7, range 4.97~9.21)
msi_high = 8.0   # high coupling (crisis-ish)
msi_low = 6.5    # low coupling (dispersed)

btc['msi_group'] = pd.cut(
    btc['msi'],
    bins=[0, msi_low, msi_high, 10],
    labels=['low (<6.5)', 'mid (6.5-8.0)', 'high (>8.0)']
)

# Performance by MSI group
print(f"\nMSI distribution:")
print(f"  Low  (<6.5): {(btc['msi_group'] == 'low (<6.5)').sum()} rows ({100 * (btc['msi_group'] == 'low (<6.5)').mean():.1f}%)")
print(f"  Mid  (6.5-8.0): {(btc['msi_group'] == 'mid (6.5-8.0)').sum()} rows ({100 * (btc['msi_group'] == 'mid (6.5-8.0)').mean():.1f}%)")
print(f"  High (>8.0): {(btc['msi_group'] == 'high (>8.0)').sum()} rows ({100 * (btc['msi_group'] == 'high (>8.0)').mean():.1f}%)")

# === Filter A: Only trade when MSI > 8.0 (high coupling) ===
print(f"\n{'='*70}")
print("Strategy A: Trade only when MSI > 8.0 (high regime concentration)")
print("="*70)
A_entries = btc[(btc['enter_long'] == 1) & (btc['msi'] > msi_high)].copy()
print(f"Total entries: {len(A_entries)}")
if len(A_entries) > 0:
    print(f"Avg 4h return: {A_entries['future_ret_4h'].mean() * 100:.3f}%")
    print(f"Avg 24h return: {A_entries['future_ret_24h'].mean() * 100:.3f}%")
    print(f"Win rate (4h > 0): {100 * (A_entries['future_ret_4h'] > 0).mean():.1f}%")
    print(f"Win rate (24h > 0): {100 * (A_entries['future_ret_24h'] > 0).mean():.1f}%")
    print(f"Sum 4h return: {A_entries['future_ret_4h'].sum() * 100:.2f}%")
    print(f"Sum 24h return: {A_entries['future_ret_24h'].sum() * 100:.2f}%")

# === Filter B: Only trade when MSI < 6.5 (low coupling) ===
print(f"\n{'='*70}")
print("Strategy B: Trade only when MSI < 6.5 (low regime concentration)")
print("="*70)
B_entries = btc[(btc['enter_long'] == 1) & (btc['msi'] < msi_low)].copy()
print(f"Total entries: {len(B_entries)}")
if len(B_entries) > 0:
    print(f"Avg 4h return: {B_entries['future_ret_4h'].mean() * 100:.3f}%")
    print(f"Avg 24h return: {B_entries['future_ret_24h'].mean() * 100:.3f}%")
    print(f"Win rate (4h > 0): {100 * (B_entries['future_ret_4h'] > 0).mean():.1f}%")
    print(f"Win rate (24h > 0): {100 * (B_entries['future_ret_24h'] > 0).mean():.1f}%")
    print(f"Sum 4h return: {B_entries['future_ret_4h'].sum() * 100:.2f}%")
    print(f"Sum 24h return: {B_entries['future_ret_24h'].sum() * 100:.2f}%")

# === Baseline: Trade whenever enter_long (no MSI filter) ===
print(f"\n{'='*70}")
print("Strategy C: Baseline (no MSI filter)")
print("="*70)
C_entries = btc[btc['enter_long'] == 1].copy()
print(f"Total entries: {len(C_entries)}")
print(f"Avg 4h return: {C_entries['future_ret_4h'].mean() * 100:.3f}%")
print(f"Avg 24h return: {C_entries['future_ret_24h'].mean() * 100:.3f}%")
print(f"Win rate (4h > 0): {100 * (C_entries['future_ret_4h'] > 0).mean():.1f}%")
print(f"Win rate (24h > 0): {100 * (C_entries['future_ret_24h'] > 0).mean():.1f}%")
print(f"Sum 4h return: {C_entries['future_ret_4h'].sum() * 100:.2f}%")
print(f"Sum 24h return: {C_entries['future_ret_24h'].sum() * 100:.2f}%")

# === Statistical test ===
from scipy import stats
print(f"\n{'='*70}")
print("Statistical Test: A vs C (t-test on 4h return)")
print("="*70)
if len(A_entries) > 5 and len(C_entries) > 5:
    t_stat, p_value = stats.ttest_ind(
        A_entries['future_ret_4h'].dropna(),
        C_entries['future_ret_4h'].dropna(),
        equal_var=False
    )
    print(f"t-statistic: {t_stat:.3f}, p-value: {p_value:.4f}")
    if p_value < 0.05:
        if A_entries['future_ret_4h'].mean() > C_entries['future_ret_4h'].mean():
            print("✅ A significantly outperforms C (p<0.05)")
        else:
            print("❌ A significantly underperforms C (p<0.05)")
    else:
        print(f"⚠️ No significant difference (p={p_value:.4f})")

print(f"\nStatistical Test: B vs C (t-test on 4h return)")
t_stat, p_value = stats.ttest_ind(
    B_entries['future_ret_4h'].dropna(),
    C_entries['future_ret_4h'].dropna(),
    equal_var=False
)
print(f"t-statistic: {t_stat:.3f}, p-value: {p_value:.4f}")
if p_value < 0.05:
    if B_entries['future_ret_4h'].mean() > C_entries['future_ret_4h'].mean():
        print("✅ B significantly outperforms C (p<0.05)")
    else:
        print("❌ B significantly underperforms C (p<0.05)")
else:
    print(f"⚠️ No significant difference (p={p_value:.4f})")

# === Recommendation ===
print(f"\n{'='*70}")
print("RECOMMENDATION")
print("="*70)
A_mean = A_entries['future_ret_4h'].mean() * 100 if len(A_entries) > 0 else 0
B_mean = B_entries['future_ret_4h'].mean() * 100 if len(B_entries) > 0 else 0
C_mean = C_entries['future_ret_4h'].mean() * 100

if A_mean > C_mean * 1.5:  # 50% improvement
    print(f"✅ Integrate MSI > 8.0 filter (avg return {A_mean:.3f}% vs baseline {C_mean:.3f}%)")
elif B_mean > C_mean * 1.5:
    print(f"✅ Integrate MSI < 6.5 filter (avg return {B_mean:.3f}% vs baseline {C_mean:.3f}%)")
else:
    print(f"⚠️ No clear edge from MSI filter (A={A_mean:.3f}%, B={B_mean:.3f}%, C={C_mean:.3f}%)")
    print(f"   Consider: 1) Different MSI thresholds, 2) Different entry logic, 3) Longer holding period")
