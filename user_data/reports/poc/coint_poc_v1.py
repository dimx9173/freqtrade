"""
POC v1: 跨幣種 cointegration 配對研究
路徑 1 公式驗證 (PLAN.md §1.2)

功能:
  1. 讀取 Bybit 15m futures 資料 (BTC/ETH/SOL)
  2. Rolling OLS hedge ratio (30-day window)
  3. Rolling Engle-Granger adfuller test on spread
  4. z-score 進場觸發統計
  5. Half-life (AR(1) Ornstein-Uhlenbeck) 分佈
  6. 共 cointegration 持續存在比例 (p < 0.05)

執行: /home/brian/freqtrade/.venv/bin/python3 coint_poc_v1.py
預估時間: < 5 分鐘
"""
import os
import sys
import time
import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------
# 0. 路徑與參數
# ----------------------------------------------------------------------
FUTURES_DIR = "/home/brian/freqtrade/user_data/data/bybit/futures"
REPORT_DIR  = "/home/brian/freqtrade/user_data/reports/poc"
os.makedirs(REPORT_DIR, exist_ok=True)

# 30 天 × 96 根/天 = 2880 根 15m candles (rolling OLS 與 EG test window)
WINDOW = 2880
# 1 天 = 96 根 15m candles (sample frequency for rolling stats)
SAMPLE_FREQ = 96
# z-score 進場門檻 (PLAN.md §1.2)
Z_ENTRY  = 2.0
Z_EXIT   = 0.5
Z_STOP   = 3.5
# 顯著水準
ALPHA    = 0.05

# 資料範圍 (BTC 限制: 2025-12-01 之後)
START_DATE = "2025-12-01"
END_DATE   = "2026-05-31"

PAIRS = [
    ("BTC", "ETH"),
    ("BTC", "SOL"),
    ("ETH", "SOL"),
]


# ----------------------------------------------------------------------
# 1. 載入資料
# ----------------------------------------------------------------------
def load_pair(symbol: str) -> pd.DataFrame:
    fname = f"{symbol}_USDT_USDT-15m-futures.feather"
    path  = os.path.join(FUTURES_DIR, fname)
    df    = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df        = df.set_index("date").sort_index()
    df        = df.loc[START_DATE:END_DATE]
    return df[["close"]].rename(columns={"close": symbol})


print("=" * 70)
print(f"POC v1 — 跨幣種 Cointegration 配對研究")
print(f"資料範圍: {START_DATE} ~ {END_DATE}")
print(f"Rolling window: {WINDOW} candles ({WINDOW/96:.0f} 天)")
print("=" * 70)

t0 = time.time()
data = {sym: load_pair(sym) for sym in ["BTC", "ETH", "SOL"]}
for sym, df in data.items():
    print(f"  {sym}: {df.shape[0]} candles, {df.index[0]} ~ {df.index[-1]}")

# 對齊索引 (join on index)
df_all = data["BTC"].join(data["ETH"], how="inner").join(data["SOL"], how="inner")
df_all = df_all.dropna()
print(f"\n對齊後: {df_all.shape[0]} candles, {df_all.index[0]} ~ {df_all.index[-1]}")


# ----------------------------------------------------------------------
# 2. 公式輔助函式
# ----------------------------------------------------------------------
def hedge_ratio_ols(y: pd.Series, x: pd.Series) -> float:
    """OLS 估計 log(y) = α + β log(x) 的 β (hedge ratio)"""
    X = add_constant(np.log(x.values))
    res = OLS(np.log(y.values), X).fit()
    return res.params[1]  # β


def half_life_ou(spread: pd.Series) -> float:
    """
    Ornstein-Uhlenbeck half-life via AR(1):
        Δs_t = α + φ * s_{t-1} + ε
    Half-life = -log(2) / log(1 + φ)   (in candle units)
    回傳 15m candles 數 (1 天 = 96 根)
    """
    s     = spread.values
    s_lag = s[:-1]
    d_s   = np.diff(s)
    X     = add_constant(s_lag)
    res   = OLS(d_s, X).fit()
    phi   = res.params[1]
    if phi >= 0:
        return np.inf  # 沒有 mean reversion
    hl     = -np.log(2) / np.log(1 + phi)
    return float(hl)


def zscore_indicators(spread: pd.Series, mean_win: int = 2880, std_win: int = 2880):
    """
    Rolling mean / std → z-score
    PLAN.md §1.2
    """
    mu  = spread.rolling(mean_win, min_periods=mean_win // 2).mean()
    sig = spread.rolling(std_win,  min_periods=std_win  // 2).std()
    z   = (spread - mu) / sig
    return z


# ----------------------------------------------------------------------
# 3. 對每個 pair 跑 cointegration POC
# ----------------------------------------------------------------------
def analyse_pair(df: pd.DataFrame, base: str, quote: str) -> dict:
    """
    對一個 pair 跑 rolling EG + z-score + half-life 分析
    為節省時間,EG 與 hedge ratio 每 SAMPLE_FREQ 根 candles 才算一次
    """
    n = df.shape[0]
    print(f"\n>>> 分析 pair: {base}/{quote}  ({n} candles)")

    log_base  = np.log(df[base])
    log_quote = np.log(df[quote])

    # 用 full sample 算單一 hedge ratio 作為 baseline
    beta_full = hedge_ratio_ols(df[base], df[quote])
    print(f"  Full-sample hedge ratio β = {beta_full:.4f}")

    # Rolling 計算 (sample at SAMPLE_FREQ 間隔以內加速)
    sample_idx  = np.arange(WINDOW, n, SAMPLE_FREQ)
    betas       = np.full(n, np.nan)
    eg_pvalues  = np.full(n, np.nan)
    spread_full = log_base - beta_full * log_quote

    t_start = time.time()
    for i, idx in enumerate(sample_idx):
        # 在 [idx-WINDOW, idx] 範圍內估計
        win_y = log_base.iloc[idx - WINDOW:idx]
        win_x = log_quote.iloc[idx - WINDOW:idx]
        betas[idx] = hedge_ratio_ols(win_y.to_frame(name=base), win_x.to_frame(name=quote))

        # 算 spread 並跑 ADF
        win_spread = win_y - betas[idx] * win_x
        try:
            adf_res   = adfuller(win_spread.values, maxlag=1, autolag=None)
            eg_pvalues[idx] = adf_res[1]
        except Exception:
            eg_pvalues[idx] = np.nan

        if (i + 1) % 20 == 0:
            elapsed = time.time() - t_start
            eta     = elapsed / (i + 1) * (len(sample_idx) - i - 1)
            print(f"    rolling: {i+1}/{len(sample_idx)} (elapsed {elapsed:.1f}s, ETA {eta:.1f}s)")

    # 完整 spread (使用 full-sample β) 與 z-score
    z_full = zscore_indicators(spread_full, mean_win=WINDOW, std_win=WINDOW)

    # 在 sample 點算 half-life
    half_lives = []
    for idx in sample_idx:
        hl = half_life_ou(spread_full.iloc[idx - WINDOW:idx])
        half_lives.append(hl)
    half_lives = np.array(half_lives)

    # 統計
    valid_p  = eg_pvalues[~np.isnan(eg_pvalues)]
    pct_coint = (valid_p < ALPHA).mean() * 100  # % windows p < 0.05

    # z-score 進場觸發
    z_valid        = z_full.dropna()
    long_trigger   = (z_valid < -Z_ENTRY).sum()
    short_trigger  = (z_valid >  Z_ENTRY).sum()
    stop_trigger   = ((z_valid < -Z_STOP) | (z_valid > Z_STOP)).sum()

    # hedge ratio 穩定性
    valid_betas = betas[~np.isnan(betas)]
    beta_mean   = valid_betas.mean()
    beta_std    = valid_betas.std()
    beta_drift  = (valid_betas[-1] - valid_betas[0]) / valid_betas[0] * 100 if len(valid_betas) > 1 else 0

    return {
        "pair":            f"{base}/{quote}",
        "n_candles":       n,
        "n_windows":       len(sample_idx),
        "beta_full":       beta_full,
        "beta_rolling_mean": beta_mean,
        "beta_rolling_std":  beta_std,
        "beta_drift_pct":     beta_drift,
        "coint_pct":       pct_coint,
        "eg_p_median":     float(np.median(valid_p)),
        "eg_p_p25":        float(np.percentile(valid_p, 25)),
        "eg_p_p75":        float(np.percentile(valid_p, 75)),
        "long_triggers":   int(long_trigger),
        "short_triggers":  int(short_trigger),
        "stop_triggers":   int(stop_trigger),
        "hl_median_candles": float(np.median(half_lives[np.isfinite(half_lives)])),
        "hl_median_hours":    float(np.median(half_lives[np.isfinite(half_lives)]) * 15 / 60),
        "hl_p25_candles":    float(np.percentile(half_lives[np.isfinite(half_lives)], 25)),
        "hl_p75_candles":    float(np.percentile(half_lives[np.isfinite(half_lives)], 75)),
        "hl_inf_count":    int(np.sum(np.isinf(half_lives))),
    }


results = []
for base, quote in PAIRS:
    res = analyse_pair(df_all, base, quote)
    results.append(res)


# ----------------------------------------------------------------------
# 4. 額外: 跑 Johansen test 一次 (full sample, BTC/ETH)
# ----------------------------------------------------------------------
print("\n>>> Johansen test (BTC/ETH, full sample) — 用 statsmodels API")
try:
    from statsmodels.tsa.vector_ar.vecm import coint_johansen
    log_data = np.log(df_all[["BTC", "ETH"]].values)
    # det_order: -1 (no det, no trend), -0 (constant), 1 (trend)
    joh_res   = coint_johansen(log_data, det_order=-1, k_ar_diff=1)
    print(f"  Trace statistic for r=0: {joh_res.lr1[0]:.2f} (cv90={joh_res.cvt[0,0]:.2f}, cv95={joh_res.cvt[0,1]:.2f}, cv99={joh_res.cvt[0,2]:.2f})")
    print(f"  Trace statistic for r=1: {joh_res.lr1[1]:.2f} (cv90={joh_res.cvt[1,0]:.2f}, cv95={joh_res.cvt[1,1]:.2f}, cv99={joh_res.cvt[1,2]:.2f})")
    if joh_res.lr1[0] > joh_res.cvt[0, 1]:
        print("  → Johansen 95% 拒絕 r=0 假設 → 存在 cointegration")
    else:
        print("  → Johansen 95% 無法拒絕 r=0 → 不存在 cointegration")
    joh_btc_eth = {
        "trace_r0":   float(joh_res.lr1[0]),
        "cv95_r0":    float(joh_res.cvt[0, 1]),
        "coint":      bool(joh_res.lr1[0] > joh_res.cvt[0, 1]),
    }
except Exception as e:
    print(f"  Johansen test 失敗: {e}")
    joh_btc_eth = None


# ----------------------------------------------------------------------
# 5. 結果摘要
# ----------------------------------------------------------------------
print("\n" + "=" * 70)
print("POC 結果摘要")
print("=" * 70)

summary = pd.DataFrame(results)
print("\n", summary.to_string(index=False), "\n")

# 儲存
out_csv = os.path.join(REPORT_DIR, "coint_poc_results.csv")
summary.to_csv(out_csv, index=False)
print(f"\n結果已存: {out_csv}")

elapsed = time.time() - t0
print(f"\n總執行時間: {elapsed:.1f}s ({elapsed/60:.1f} min)")

# 驗證 PLAN.md §1.3 標準
print("\n" + "=" * 70)
print("PLAN.md §1.3 驗證標準檢查")
print("=" * 70)

for r in results:
    pair = r["pair"]
    print(f"\n  {pair}:")
    print(f"    [1] Cointegration 持續 > 60% ?    實際: {r['coint_pct']:.1f}%   {'✅' if r['coint_pct'] > 60 else '❌'}")
    print(f"    [2] z-score 進場觸發 > 30 (6個月)?  實際: {r['long_triggers'] + r['short_triggers']:>4}  {'✅' if r['long_triggers'] + r['short_triggers'] > 30 else '❌'}")
    print(f"    [3] Half-life < 24h (96 candles)?  實際: {r['hl_median_hours']:.1f}h  {'✅' if r['hl_median_hours'] < 24 else '❌'}")
    print(f"    [4] Hedge ratio drift < 10%?        實際: {r['beta_drift_pct']:.2f}%  {'✅' if abs(r['beta_drift_pct']) < 10 else '❌'}")
