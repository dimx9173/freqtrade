"""
Path 3 v2: XGBoost + MSI (10-asset eigenvalue) as additional feature.
- BTC: Binance 1h (28 months history)
- Other 9 assets: Bybit 1h (12 months, compute MSI)
- MSI 前段用 ffill 處理
"""
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

DATA_BINANCE = Path('/home/brian/freqtrade/user_data/data/binance')
DATA_BYBIT = Path('/home/brian/freqtrade/user_data/data/bybit')
ASSETS = ['BTC', 'ETH', 'SOL', 'BNB', 'LINK', 'DOGE', 'ADA', 'AVAX', 'TON', 'SUI']

print("="*70)
print("Path 3 v2: XGBoost + MSI Feature (BTC 1h, MSI 10-asset)")
print("="*70)

# Load BTC 1h (Binance for full history)
btc = pd.read_feather(DATA_BINANCE / 'BTC_USDT-1h.feather')
btc['date'] = pd.to_datetime(btc['date'])
btc = btc.sort_values('date').reset_index(drop=True)
print(f"BTC 1h (Binance): {len(btc)} rows, {btc['date'].min()} to {btc['date'].max()}")

# === Feature engineering ===
import talib.abstract as ta
df = btc.copy()
df['ema_12'] = ta.EMA(df, timeperiod=12)
df['ema_26'] = ta.EMA(df, timeperiod=26)
df['ema_50'] = ta.EMA(df, timeperiod=50)
df['adx'] = ta.ADX(df, timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df, timeperiod=14)
df['minus_di'] = ta.MINUS_DI(df, timeperiod=14)
df['rsi'] = ta.RSI(df, timeperiod=14)
bb = ta.BBANDS(df, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
df['bb_upper'] = bb['upperband']
df['bb_middle'] = bb['middleband']
df['bb_lower'] = bb['lowerband']
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
df['atr'] = ta.ATR(df, timeperiod=14)
df['tr'] = ta.TRANGE(df)
df['natr'] = ta.NATR(df, timeperiod=14)
df['volume_ma'] = df['volume'].rolling(20).mean()
df['volume_ma_ratio'] = df['volume'] / df['volume_ma']
df['obv'] = ta.OBV(df)
df['ret_1h'] = df['close'].pct_change()
df['ret_4h'] = df['close'].pct_change(4)
df['ret_24h'] = df['close'].pct_change(24)
df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
df['h1_ema_slope'] = (df['ema_12'] - df['ema_12'].shift(24)) / df['ema_12'].shift(24)
df['h4_ema_slope'] = (df['ema_12'] - df['ema_12'].shift(96)) / df['ema_12'].shift(96)

# === Compute MSI from 9 Bybit assets (1h) ===
print("\nComputing 10-asset MSI (Bybit 9 + Binance BTC 1h)...")
ret_dict = {}
# Use Binance BTC 1h (consistent with main df)
ret_dict['BTC'] = btc.set_index('date')['close'].pct_change()
# Use Bybit 9 others
for asset in ASSETS[1:]:
    fp = DATA_BYBIT / f'{asset}_USDT-1h.feather'
    if not fp.exists():
        print(f"⚠️ Missing: {asset}")
        continue
    adf = pd.read_feather(fp)
    adf['date'] = pd.to_datetime(adf['date'])
    ret_dict[asset] = adf.set_index('date')['close'].pct_change()

ret_df = pd.DataFrame(ret_dict).dropna()
print(f"Aligned 10-asset returns: {len(ret_df)} rows, {ret_df.index[0]} to {ret_df.index[-1]}")

window = 24
msi_list = []
pr_list = []
dates_list = []
for i in range(window, len(ret_df)):
    seg = ret_df.iloc[i-window:i]
    try:
        corr = seg.corr().values
        eigvals = np.linalg.eigvalsh(corr)
        eigvals = np.sort(eigvals)[::-1]
        eigvals_norm = eigvals / eigvals.sum() * len(eigvals)
        msi = eigvals_norm[0] / np.mean(eigvals_norm)
        pr = (eigvals_norm.sum() ** 2) / (eigvals_norm ** 2).sum()
        msi_list.append(msi)
        pr_list.append(pr)
        dates_list.append(ret_df.index[i])
    except:
        continue

msi_series = pd.Series(msi_list, index=dates_list, name='msi')
pr_series = pd.Series(pr_list, index=dates_list, name='pr')
print(f"MSI computed: {len(msi_series)} values, range {msi_series.min():.2f}~{msi_series.max():.2f}, mean={msi_series.mean():.2f}")

# Merge MSI to BTC df (ffill for early period)
df['msi'] = msi_series.reindex(df['date']).ffill().values
df['pr'] = pr_series.reindex(df['date']).ffill().values
print(f"MSI in df: {(~df['msi'].isna()).sum()}/{len(df)} non-NaN")

# === Label ===
LOOKAHEAD = 4
THRESHOLD = 0.003
df['future_ret_4h'] = df['close'].pct_change(LOOKAHEAD).shift(-LOOKAHEAD)
df['label'] = (df['future_ret_4h'] > THRESHOLD).astype(int)
print(f"\nLabel: {(df['label'] == 1).sum()} positive ({100 * (df['label'] == 1).mean():.1f}%)")

# === Feature columns ===
feature_cols_v1 = [
    'ema_12', 'ema_26', 'ema_50', 'adx', 'plus_di', 'minus_di',
    'rsi', 'bb_width', 'bb_position',
    'atr', 'natr', 'tr',
    'volume_ma_ratio', 'obv',
    'ret_1h', 'ret_4h', 'ret_24h', 'log_ret',
    'h1_ema_slope', 'h4_ema_slope',
]
feature_cols_v2 = feature_cols_v1 + ['msi', 'pr']

# Drop NaN
df_v1 = df.dropna(subset=feature_cols_v1 + ['label']).copy()
df_v2 = df.dropna(subset=feature_cols_v2 + ['label']).copy()
print(f"\nAfter dropna: v1={len(df_v1)} rows, v2={len(df_v2)} rows")

# === Walk-forward split ===
train_start = '2024-06-01'
train_end = '2025-12-01'
test_start = '2026-01-01'
test_end = '2026-05-07'

v1_train = df_v1[(df_v1['date'] >= train_start) & (df_v1['date'] < train_end)].copy()
v1_test = df_v1[(df_v1['date'] >= test_start) & (df_v1['date'] <= test_end)].copy()
v2_train = df_v2[(df_v2['date'] >= train_start) & (df_v2['date'] < train_end)].copy()
v2_test = df_v2[(df_v2['date'] >= test_start) & (df_v2['date'] <= test_end)].copy()

print(f"\nv1 (TA only): train={len(v1_train)} ({v1_train['date'].min()} to {v1_train['date'].max()}), test={len(v1_test)} ({v1_test['date'].min()} to {v1_test['date'].max()})")
print(f"v2 (TA+MSI):  train={len(v2_train)} ({v2_train['date'].min()} to {v2_train['date'].max()}), test={len(v2_test)} ({v2_test['date'].min()} to {v2_test['date'].max()})")
print(f"v1 train positive rate: {100 * v1_train['label'].mean():.2f}%")
print(f"v1 test positive rate:  {100 * v1_test['label'].mean():.2f}%")
print(f"v2 train positive rate: {100 * v2_train['label'].mean():.2f}%")
print(f"v2 test positive rate:  {100 * v2_test['label'].mean():.2f}%")

# === Check that we have training data ===
if len(v1_train) == 0 or len(v2_train) == 0:
    print("❌ Empty training set, exiting")
    import sys
    sys.exit(0)

import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score

def train_and_eval(X_train, y_train, X_test, y_test, name, feature_names, scale_pos_weight=2.0):
    print(f"\n{'='*70}")
    print(f"Training {name}...")
    print(f"{'='*70}")
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='auc',
        early_stopping_rounds=20,
        verbosity=0,
        scale_pos_weight=scale_pos_weight,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    print(f"Best iteration: {model.best_iteration}")

    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    y_test_proba = model.predict_proba(X_test)[:, 1]

    train_acc = (y_train_pred == y_train).mean()
    test_acc = (y_test_pred == y_test).mean()
    test_auc = roc_auc_score(y_test, y_test_proba)
    print(f"Train acc: {train_acc:.4f}, Test acc: {test_acc:.4f}, Test AUC: {test_auc:.4f}")
    print(f"\nTest classification report:")
    print(classification_report(y_test, y_test_pred, target_names=['No', 'Yes']))

    importance = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    print(f"Top 10 feature importance:")
    print(importance.head(10).to_string(index=False))
    return model, y_test_pred, y_test_proba, test_auc, importance

# v1 (TA only)
print("\n" + "="*70)
print("v1: XGBoost (TA only) — baseline")
print("="*70)
model_v1, pred_v1, proba_v1, auc_v1, imp_v1 = train_and_eval(
    v1_train[feature_cols_v1].values, v1_train['label'].values,
    v1_test[feature_cols_v1].values, v1_test['label'].values,
    "v1 (TA only)", feature_cols_v1, scale_pos_weight=2.0
)

# v2 (TA + MSI)
print("\n" + "="*70)
print("v2: XGBoost (TA + MSI + PR)")
print("="*70)
model_v2, pred_v2, proba_v2, auc_v2, imp_v2 = train_and_eval(
    v2_train[feature_cols_v2].values, v2_train['label'].values,
    v2_test[feature_cols_v2].values, v2_test['label'].values,
    "v2 (TA + MSI + PR)", feature_cols_v2, scale_pos_weight=2.0
)

# === Comparison ===
print(f"\n{'='*70}")
print("v1 vs v2 COMPARISON")
print("="*70)
print(f"{'Metric':<30} {'v1 (TA)':<20} {'v2 (TA+MSI)':<20} {'Δ':<15}")
print(f"{'-'*85}")
print(f"{'Train rows':<30} {len(v1_train):<20} {len(v2_train):<20}")
print(f"{'Test rows':<30} {len(v1_test):<20} {len(v2_test):<20}")
print(f"{'Features':<30} {len(feature_cols_v1):<20} {len(feature_cols_v2):<20}")
print(f"{'Test AUC':<30} {auc_v1:<20.4f} {auc_v2:<20.4f} {(auc_v2-auc_v1):<+15.4f}")
print(f"{'Best iteration':<30} {model_v1.best_iteration:<20} {model_v2.best_iteration:<20}")

# === Backtest comparison ===
v2_test_bt = v2_test.copy()
v2_test_bt['pred'] = pred_v2
v2_test_bt['pred_proba'] = proba_v2
v1_test_bt = v1_test.copy()
v1_test_bt['pred'] = pred_v1
v1_test_bt['pred_proba'] = proba_v1

print(f"\n{'='*70}")
print("v1 vs v2 Backtest (proba > 0.4 threshold)")
print("="*70)

for name, bt, proba in [('v1 (TA)', v1_test_bt, proba_v1), ('v2 (TA+MSI)', v2_test_bt, proba_v2)]:
    print(f"\n{name}:")
    for thresh in [0.4, 0.5, 0.6, 0.7]:
        n = (proba > thresh).sum()
        if n == 0:
            continue
        subset = bt[proba > thresh]
        win_rate = (subset['future_ret_4h'] > 0).mean() * 100
        avg_ret = subset['future_ret_4h'].mean() * 100
        cum_ret = subset['future_ret_4h'].sum() * 100
        print(f"  proba > {thresh}: {n} trades, {win_rate:.1f}% WR, avg {avg_ret:.3f}%, cum {cum_ret:.2f}%")

# === Summary ===
print(f"\n{'='*70}")
print("PATH 3 v2 SUMMARY")
print("="*70)
print(f"  v1 (TA only):       Test AUC = {auc_v1:.4f}")
print(f"  v2 (TA + MSI + PR): Test AUC = {auc_v2:.4f}")
print(f"  Improvement: {(auc_v2-auc_v1)*100:+.2f} pp AUC")
if auc_v2 > auc_v1 + 0.02:
    print("  ✅ MSI feature improves XGBoost by >2% AUC")
elif auc_v2 > auc_v1:
    print("  🟡 MSI marginally improves XGBoost")
else:
    print("  ❌ MSI does not improve XGBoost (or marginally hurts)")

# Save
v2_test_bt[['date', 'close', 'pred', 'pred_proba', 'future_ret_4h', 'label', 'msi']].to_csv(
    '/tmp/path3_v2_xgb_msi_predictions.csv', index=False
)
print(f"\nSaved v2 predictions to /tmp/path3_v2_xgb_msi_predictions.csv")
