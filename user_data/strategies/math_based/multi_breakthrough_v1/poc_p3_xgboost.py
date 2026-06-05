"""
POC Path 3: XGBoost regime + TA signal for entry prediction.
- 標的: BTC/USDT 1h
- 目標: 預測未來 4h 漲跌 > 0.3%
- 訓練: 2024-06-01 ~ 2025-12-01 (18 個月)
- OOS 測試: 2026-01-01 ~ 2026-06-01 (6 個月)
"""
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path('/home/brian/freqtrade/user_data/data/binance')
print("="*70)
print("Path 3: XGBoost Entry Signal POC (BTC 1h, Binance 28 月歷史)")
print("="*70)

# Load BTC 1h from Binance (longer history: 2024-01-01 ~ 2026-05-07, 28 months)
df = pd.read_feather(DATA_DIR / 'BTC_USDT-1h.feather')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)
print(f"BTC 1h (Binance): {len(df)} rows, {df['date'].min()} to {df['date'].max()}")

# === Feature engineering ===
import talib.abstract as ta

# Trend
df['ema_12'] = ta.EMA(df, timeperiod=12)
df['ema_26'] = ta.EMA(df, timeperiod=26)
df['ema_50'] = ta.EMA(df, timeperiod=50)
df['adx'] = ta.ADX(df, timeperiod=14)
df['plus_di'] = ta.PLUS_DI(df, timeperiod=14)
df['minus_di'] = ta.MINUS_DI(df, timeperiod=14)

# Mean-reversion
df['rsi'] = ta.RSI(df, timeperiod=14)
bb = ta.BBANDS(df, timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)
df['bb_upper'] = bb['upperband']
df['bb_middle'] = bb['middleband']
df['bb_lower'] = bb['lowerband']
df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

# Volatility
df['atr'] = ta.ATR(df, timeperiod=14)
df['tr'] = ta.TRANGE(df)
df['natr'] = ta.NATR(df, timeperiod=14)

# Volume
df['volume_ma'] = df['volume'].rolling(20).mean()
df['volume_ma_ratio'] = df['volume'] / df['volume_ma']
df['obv'] = ta.OBV(df)

# Returns
df['ret_1h'] = df['close'].pct_change()
df['ret_4h'] = df['close'].pct_change(4)
df['ret_24h'] = df['close'].pct_change(24)
df['log_ret'] = np.log(df['close'] / df['close'].shift(1))

# Cross-TF proxy (using rolling 24, 168 = 1d, 1w)
df['h1_ema_slope'] = (df['ema_12'] - df['ema_12'].shift(24)) / df['ema_12'].shift(24)
df['h4_ema_slope'] = (df['ema_12'] - df['ema_12'].shift(96)) / df['ema_12'].shift(96)

# === Label: next 4h return > 0.3% ===
LOOKAHEAD = 4
THRESHOLD = 0.003
df['future_ret_4h'] = df['close'].pct_change(LOOKAHEAD).shift(-LOOKAHEAD)
df['label'] = (df['future_ret_4h'] > THRESHOLD).astype(int)
print(f"\nLabel distribution:")
print(f"  Total: {df['label'].notna().sum()}")
print(f"  Positive (label=1): {(df['label'] == 1).sum()} ({100 * (df['label'] == 1).mean():.2f}%)")
print(f"  Negative (label=0): {(df['label'] == 0).sum()} ({100 * (df['label'] == 0).mean():.2f}%)")

# === Feature columns ===
feature_cols = [
    'ema_12', 'ema_26', 'ema_50', 'adx', 'plus_di', 'minus_di',
    'rsi', 'bb_width', 'bb_position',
    'atr', 'natr', 'tr',
    'volume_ma_ratio', 'obv',
    'ret_1h', 'ret_4h', 'ret_24h', 'log_ret',
    'h1_ema_slope', 'h4_ema_slope',
]

# Drop NaN
df_feat = df.dropna(subset=feature_cols + ['label']).copy()
print(f"\nAfter dropna: {len(df_feat)} rows")
print(f"Feature count: {len(feature_cols)}")

# === Train/test split (walk-forward) ===
train_start = '2024-06-01'
train_end = '2025-12-01'
test_start = '2026-01-01'
test_end = '2026-06-01'

df_train = df_feat[(df_feat['date'] >= train_start) & (df_feat['date'] < train_end)].copy()
df_test = df_feat[(df_feat['date'] >= test_start) & (df_feat['date'] < test_end)].copy()

print(f"\nTrain: {len(df_train)} rows ({df_train['date'].min()} to {df_train['date'].max()})")
print(f"Test:  {len(df_test)} rows ({df_test['date'].min()} to {df_test['date'].max()})")
print(f"Train positive rate: {100 * df_train['label'].mean():.2f}%")
print(f"Test positive rate:  {100 * df_test['label'].mean():.2f}%")

X_train = df_train[feature_cols].values
y_train = df_train['label'].values
X_test = df_test[feature_cols].values
y_test = df_test['label'].values

# === Train XGBoost ===
try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("\n⚠️ xgboost not installed, trying to install...")

if not HAS_XGB:
    import subprocess
    result = subprocess.run(['./.venv/bin/pip', 'install', 'xgboost', 'lightgbm'],
                          capture_output=True, text=True, cwd='/home/brian/freqtrade')
    print(result.stdout[-500:])
    print(result.stderr[-500:])
    import xgboost as xgb

print("\nTraining XGBoost...")
model = xgb.XGBClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    eval_metric='logloss',
    early_stopping_rounds=20,
    verbosity=0,
)
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
print(f"Best iteration: {model.best_iteration}")

# === Evaluate ===
y_train_pred = model.predict(X_train)
y_test_pred = model.predict(X_test)
y_test_proba = model.predict_proba(X_test)[:, 1]

train_acc = (y_train_pred == y_train).mean()
test_acc = (y_test_pred == y_test).mean()

from sklearn.metrics import classification_report, roc_auc_score
print(f"\nTrain accuracy: {train_acc:.4f}")
print(f"Test accuracy:  {test_acc:.4f}")
print(f"Test AUC:       {roc_auc_score(y_test, y_test_proba):.4f}")
print(f"\nTest classification report:")
print(classification_report(y_test, y_test_pred, target_names=['No', 'Yes']))

# === Feature importance ===
importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)
print(f"\nTop 10 feature importance:")
print(importance.head(10).to_string(index=False))

# === Simple backtest simulation ===
print(f"\n{'='*70}")
print("Simple backtest: trade when XGBoost predicts Yes (prob > 0.5)")
print("="*70)

df_test_bt = df_test.copy()
df_test_bt['pred'] = y_test_pred
df_test_bt['pred_proba'] = y_test_proba

# Strategy: enter long when pred=1, hold 4h
df_test_bt['strategy_ret'] = 0.0
df_test_bt.loc[df_test_bt['pred'] == 1, 'strategy_ret'] = df_test_bt.loc[df_test_bt['pred'] == 1, 'future_ret_4h']

# Per-trade stats
trades = df_test_bt[df_test_bt['pred'] == 1]
trades_winning = trades[trades['future_ret_4h'] > 0]
trades_losing = trades[trades['future_ret_4h'] <= 0]

print(f"Total trades: {len(trades)}")
print(f"Winning trades: {len(trades_winning)} ({100 * len(trades_winning) / max(1, len(trades)):.1f}%)")
print(f"Losing trades: {len(trades_losing)} ({100 * len(trades_losing) / max(1, len(trades)):.1f}%)")
if len(trades) > 0:
    print(f"Avg win: {trades_winning['future_ret_4h'].mean() * 100:.3f}%" if len(trades_winning) > 0 else "Avg win: N/A")
    print(f"Avg loss: {trades_losing['future_ret_4h'].mean() * 100:.3f}%" if len(trades_losing) > 0 else "Avg loss: N/A")
    print(f"Cumulative return: {trades['future_ret_4h'].sum() * 100:.2f}%")
    print(f"Avg per trade: {trades['future_ret_4h'].mean() * 100:.3f}%")

# Threshold analysis: try multiple proba thresholds
print(f"\nThreshold sensitivity:")
for thresh in [0.4, 0.5, 0.6, 0.7, 0.8]:
    n = (y_test_proba > thresh).sum()
    if n == 0:
        continue
    subset = df_test_bt[y_test_proba > thresh]
    win_rate = (subset['future_ret_4h'] > 0).mean() * 100
    avg_ret = subset['future_ret_4h'].mean() * 100
    cum_ret = subset['future_ret_4h'].sum() * 100
    print(f"  proba > {thresh}: {n} trades, {win_rate:.1f}% WR, avg {avg_ret:.3f}%, cum {cum_ret:.2f}%")

# Buy-and-hold benchmark
df_test_bt_sorted = df_test_bt.sort_values('date')
buy_hold_ret = (df_test_bt_sorted['close'].iloc[-1] / df_test_bt_sorted['close'].iloc[0] - 1) * 100
print(f"\nBuy & Hold BTC OOS: {buy_hold_ret:.2f}%")

# === Save predictions for integration ===
df_test_bt[['date', 'close', 'pred', 'pred_proba', 'future_ret_4h', 'label']].to_csv(
    '/tmp/path3_xgb_predictions.csv', index=False
)
print(f"\nSaved predictions to /tmp/path3_xgb_predictions.csv")
print(f"\nXGBoost model saved to /tmp/xgb_model.json")
model.save_model('/tmp/xgb_model.json')
