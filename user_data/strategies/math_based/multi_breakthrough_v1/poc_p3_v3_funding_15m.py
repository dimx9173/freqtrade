"""
Path 3 v3: XGBoost + 15m TF + Funding Rate Features
====================================================
v2 → v3 升級:
  - 1h → 15m (4x 顆粒度, 噪音少, 結構多)
  - TA features 不變 (rolling on 15m)
  - + Funding Rate Features (perp sentiment): lag, cumsum, streak, std
  - + PR (v2 已經有, 沿用)

目標: 驗證 15m TF + funding rate 是否能突破 v2 的 AUC 0.5797 瓶頸
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path("/home/brian/freqtrade")
sys.path.insert(0, str(PROJECT_ROOT / "user_data/strategies/math_based/multi_breakthrough_v1"))

# ====================================================================
# Step 0: 載入資料
# ====================================================================
print("=" * 70)
print("Step 0: 載入資料")
print("=" * 70)

# 主: binance BTC 15m
btc_15m = pd.read_feather(PROJECT_ROOT / "user_data/data/binance/BTC_USDT-15m.feather")
btc_15m["date"] = pd.to_datetime(btc_15m["date"])
btc_15m = btc_15m.set_index("date").sort_index()
print(f"  BTC 15m: {len(btc_15m)} rows, {btc_15m.index.min()} → {btc_15m.index.max()}")

# Funding rate: bybit BTC 1h
fr_1h = pd.read_feather(PROJECT_ROOT / "user_data/data/bybit/futures/BTC_USDT_USDT-1h-funding_rate.feather")
fr_1h["date"] = pd.to_datetime(fr_1h["date"])
fr_1h = fr_1h.set_index("date")[["close"]].rename(columns={"close": "funding_rate"})
fr_1h = fr_1h.sort_index()
print(f"  Funding 1h: {len(fr_1h)} rows, {fr_1h.index.min()} → {fr_1h.index.max()}")

# v3 範圍決策: binance BTC 15m (2024-01-01 ~ 2025-01-09) 與 bybit 9 幣種 1h (2025-05-01 起) 不重疊
# 結論: v3 放棄 cross-asset MSI (因 binance 沒有 9 幣種 1h 歷史)
# v3 純 15m + funding rate, v2 純 1h + MSI+PR, 兩者獨立比較 alpha 來源
print("  v3 scope: 15m TF + funding rate (no cross-asset MSI - binance lacks 9-asset 1h history)")

# ====================================================================
# Step 1: 對齊 funding rate 到 15m
# ====================================================================
print()
print("=" * 70)
print("Step 1: 對齊 funding rate 到 15m (FFill)")
print("=" * 70)

# Funding rate 1h → 15m (FFill)
fr_reindexed = fr_1h.reindex(btc_15m.index, method="ffill", limit=4)
fr_reindexed = fr_reindexed.ffill()
btc_15m["funding_rate"] = fr_reindexed["funding_rate"]

print(f"  Merged: {btc_15m.shape}, NaN count: {btc_15m.isna().sum().sum()}")

# ====================================================================
# Step 2: 計算特徵
# ====================================================================
print()
print("=" * 70)
print("Step 2: 特徵工程")
print("=" * 70)

df = btc_15m.copy()

# === TA features (on 15m) ===
# 注意: 1h 的 60 bars → 15m 的 240 bars (4x 擴展)
# 為保持跨時段可比性, 用同樣的 window sizes
df["tr"] = pd.concat([
    df["high"] - df["low"],
    (df["high"] - df["close"].shift()).abs(),
    (df["low"] - df["close"].shift()).abs()
], axis=1).max(axis=1)

df["atr_14"] = df["tr"].rolling(14).mean()

# EMA (12 = 3h, 26 = 6.5h, 50 = 12.5h, 200 = 50h)
for span in [12, 26, 50, 200]:
    df[f"ema_{span}"] = df["close"].ewm(span=span, adjust=False).mean()

# NATR (normalized ATR, 跨時段可比)
df["natr"] = (df["atr_14"] / df["close"]) * 100

# Bollinger Bands (20 = 5h)
df["bb_mid"] = df["close"].rolling(20).mean()
df["bb_std"] = df["close"].rolling(20).std()
df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

# RSI
delta = df["close"].diff()
gain = (delta.where(delta > 0, 0)).rolling(14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
rs = gain / (loss + 1e-10)
df["rsi_14"] = 100 - (100 / (1 + rs))

# ADX (簡化)
df["up_move"] = df["high"] - df["high"].shift()
df["down_move"] = df["low"].shift() - df["low"]
df["plus_dm"] = ((df["up_move"] > df["down_move"]) & (df["up_move"] > 0)) * df["up_move"]
df["minus_dm"] = ((df["down_move"] > df["up_move"]) & (df["down_move"] > 0)) * df["down_move"]
df["plus_di"] = 100 * (df["plus_dm"].rolling(14).mean() / (df["atr_14"] + 1e-10))
df["minus_di"] = 100 * (df["minus_dm"].rolling(14).mean() / (df["atr_14"] + 1e-10))
df["dx"] = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"] + 1e-10)
df["adx_14"] = df["dx"].rolling(14).mean()

# Volume features
df["volume_ma_ratio"] = df["volume"] / (df["volume"].rolling(20).mean() + 1e-10)

# === NEW: Funding rate features (15m-aligned via FFill) ===
df["fr_lag1"] = df["funding_rate"].shift(1)   # 15m ago
df["fr_lag4"] = df["funding_rate"].shift(4)   # 1h ago
df["fr_lag8"] = df["funding_rate"].shift(8)   # 2h ago
df["fr_lag24"] = df["funding_rate"].shift(24) # 6h ago (was 24h in 1h)

# Funding rate rolling stats (15m bars)
df["fr_ma_8"] = df["funding_rate"].rolling(8).mean()    # 2h mean
df["fr_ma_32"] = df["funding_rate"].rolling(32).mean()  # 8h mean
df["fr_std_32"] = df["funding_rate"].rolling(32).std() # 8h std
df["fr_cumsum_32"] = df["funding_rate"].rolling(32).sum()  # 8h 累積

# Funding rate streak (連續正/負 bar count)
def calc_streak(series):
    streak = pd.Series(0, index=series.index, dtype=float)
    cur = 0
    for i, val in enumerate(series):
        if pd.isna(val):
            cur = 0
        elif val > 0:
            cur = cur + 1 if cur > 0 else 1
        elif val < 0:
            cur = cur - 1 if cur < 0 else -1
        else:
            cur = 0
        streak.iloc[i] = cur
    return streak

df["fr_streak_8"] = calc_streak(df["funding_rate"]).rolling(8).mean()

# === v2 沿用: PR (cross-asset) ===
# 已經對齊

# === Target: 未來 4h (16 bars of 15m) 漲跌 ===
# 改用 16 bars 15m = 4h (保持 v2 的 4 bars of 1h 預測範圍)
df["target"] = (df["close"].shift(-16) > df["close"]).astype(int)

# Drop NaN
df = df.dropna()
print(f"  After dropna: {len(df)} rows")

# === Feature list ===
TA_FEATURES = ["tr", "natr", "bb_width", "rsi_14", "adx_14", "plus_di", "minus_di",
               "ema_12", "ema_26", "ema_50", "ema_200", "volume_ma_ratio",
               "bb_upper", "bb_lower"]
FUNDING_FEATURES = ["fr_lag1", "fr_lag4", "fr_lag8", "fr_lag24",
                    "fr_ma_8", "fr_ma_32", "fr_std_32", "fr_cumsum_32", "fr_streak_8"]
# v3 放棄 cross-asset MSI (data alignment 問題)
CROSS_ASSET_FEATURES = []

ALL_FEATURES = TA_FEATURES + FUNDING_FEATURES + CROSS_ASSET_FEATURES
print(f"  TA features: {len(TA_FEATURES)}")
print(f"  Funding features (NEW): {len(FUNDING_FEATURES)}")
print(f"  Cross-asset features: {len(CROSS_ASSET_FEATURES)}")
print(f"  Total features: {len(ALL_FEATURES)}")

# ====================================================================
# Step 3: 訓練 / 測試分割
# ====================================================================
print()
print("=" * 70)
print("Step 3: 訓練/測試分割 (v3 改用 15m 1年資料)")
print("=" * 70)

# 訓練: 2024-01-01 ~ 2024-09-30 (9 月)
# 測試: 2024-10-01 ~ 2025-01-09 (3.3 月 OOS)
train = df.loc["2024-01-01":"2024-09-30"]
test = df.loc["2024-10-01":"2025-01-09"]

X_train = train[ALL_FEATURES].values
y_train = train["target"].values
X_test = test[ALL_FEATURES].values
y_test = test["target"].values

print(f"  Train: {len(X_train)} rows, target up: {y_train.mean():.3f}")
print(f"  Test:  {len(X_test)} rows, target up: {y_test.mean():.3f}")

# ====================================================================
# Step 4: 訓練 v3
# ====================================================================
print()
print("=" * 70)
print("Step 4: XGBoost v3 Training")
print("=" * 70)

# 與 v2 一致的超參數
model_v3 = XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=10,
    random_state=42,
    eval_metric="logloss",
)

model_v3.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

# ====================================================================
# Step 5: 評估
# ====================================================================
print()
print("=" * 70)
print("Step 5: 評估 v3")
print("=" * 70)

y_proba = model_v3.predict_proba(X_test)[:, 1]
y_pred = (y_proba > 0.5).astype(int)

auc = roc_auc_score(y_test, y_proba)
acc = accuracy_score(y_test, y_pred)
print(f"  Test AUC:    {auc:.4f}")
print(f"  Test Acc:    {acc:.4f}")

# 交易模擬: proba > 0.5 時 long, 16 bars 後 exit
test_df = test.copy()
test_df["proba"] = y_proba
test_df["signal"] = (y_proba > 0.5).astype(int)

# 計算 long-then-flat cum return (16 bars = 4h hold)
test_df["fwd_ret_16"] = (test_df["close"].shift(-16) / test_df["close"] - 1)
trades = test_df[test_df["signal"] == 1].dropna(subset=["fwd_ret_16"])
n_trades = len(trades)
wr = (trades["fwd_ret_16"] > 0).mean() if n_trades > 0 else 0
cum_ret = (1 + trades["fwd_ret_16"]).prod() - 1 if n_trades > 0 else 0
avg_ret = trades["fwd_ret_16"].mean() if n_trades > 0 else 0

print(f"  proba > 0.5 trades: {n_trades}")
print(f"  Win rate:           {wr:.1%}")
print(f"  Avg return:         {avg_ret:.4%}")
print(f"  Cum return:         {cum_ret:.4%}")

# 寬鬆門檻
trades_loose = test_df[test_df["proba"] > 0.4].dropna(subset=["fwd_ret_16"])
n_trades_loose = len(trades_loose)
wr_loose = (trades_loose["fwd_ret_16"] > 0).mean() if n_trades_loose > 0 else 0
cum_ret_loose = (1 + trades_loose["fwd_ret_16"]).prod() - 1 if n_trades_loose > 0 else 0
print(f"\n  [proba > 0.4]")
print(f"  trades: {n_trades_loose}, WR: {wr_loose:.1%}, cum: {cum_ret_loose:.4%}")

# ====================================================================
# Step 6: Feature Importance
# ====================================================================
print()
print("=" * 70)
print("Step 6: Top 15 Features")
print("=" * 70)

feat_imp = pd.DataFrame({
    "feature": ALL_FEATURES,
    "importance": model_v3.feature_importances_
}).sort_values("importance", ascending=False)

print(feat_imp.to_string(index=False))

# 計算 funding rate 總貢獻
funding_total = feat_imp[feat_imp["feature"].isin(FUNDING_FEATURES)]["importance"].sum()
ta_total = feat_imp[feat_imp["feature"].isin(TA_FEATURES)]["importance"].sum()
pr_total = feat_imp[feat_imp["feature"].isin(CROSS_ASSET_FEATURES)]["importance"].sum()

print(f"\n  Funding Rate contribution: {funding_total:.4f} ({funding_total*100:.1f}%)")
print(f"  TA contribution:           {ta_total:.4f} ({ta_total*100:.1f}%)")
print(f"  Cross-asset contribution:  {pr_total:.4f} ({pr_total*100:.1f}%)")

# ====================================================================
# Step 7: v3 vs v2 比較
# ====================================================================
print()
print("=" * 70)
print("Step 7: v3 vs v2 比較")
print("=" * 70)

print(f"""
{'Metric':<25} {'v2 (1h, 7M train)':<25} {'v3 (15m, 9M train)':<25} {'Δ':<10}
{'-' * 85}
{'Test AUC':<25} {'0.5797':<25} {f'{auc:.4f}':<25} {f'{auc-0.5797:+.4f}':<10}
{'proba>0.5 trades':<25} {'660':<25} {f'{n_trades}':<25} {f'{n_trades-660:+d}':<10}
{'proba>0.5 WR':<25} {'55.2%':<25} {f'{wr:.1%}':<25} {f'{(wr-0.552)*100:+.1f}pp':<10}
{'proba>0.5 cum ret':<25} {'+60.36%':<25} {f'{cum_ret:+.2%}':<25} {f'{(cum_ret-0.6036)*100:+.1f}pp':<10}
{'proba>0.4 cum ret':<25} {'?':<25} {f'{cum_ret_loose:+.2%}':<25} {'NEW':<10}
""")

# ====================================================================
# Step 8: Save artifacts
# ====================================================================
print()
print("=" * 70)
print("Step 8: 儲存產出")
print("=" * 70)

# Save predictions for further analysis
test_df[["close", "proba", "signal", "target"]].to_csv(
    PROJECT_ROOT / "user_data/strategies/math_based/multi_breakthrough_v1/poc_p3_v3_predictions.csv",
    index=True
)
print(f"  Predictions saved: poc_p3_v3_predictions.csv ({len(test_df)} rows)")

# Save feature importance
feat_imp.to_csv(
    PROJECT_ROOT / "user_data/strategies/math_based/multi_breakthrough_v1/poc_p3_v3_feat_imp.csv",
    index=False
)
print(f"  Feature importance saved: poc_p3_v3_feat_imp.csv")

print()
print("=" * 70)
print("✅ v3 POC 完成")
print("=" * 70)
