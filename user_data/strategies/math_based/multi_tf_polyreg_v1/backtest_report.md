# MultiTFPolyReg_v1 — 回測驗證報告

## 測試環境

- **工作目錄**: `/home/brian/freqtrade/user_data/`
- **策略路徑**: `strategies/math_based/multi_tf_polyreg_v1/MultiTFPolyReg_v1.py`
- **Config**: `strategies/math_based/multi_tf_polyreg_v1/config.json`
- **Timerange**: TBD
- **Timeframe**: 5m (+ 15m, 1h, 4h informative)
- **Exchange**: Bybit (Spot)
- **起始資金**: 1000 USDT
- **Stake**: 50 USDT
- **Max Open Trades**: 5
- **幣種**: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT

---

## 回測結果

| 指標 | 數值 |
|------|------|
| 總交易數 | TBD |
| 總利潤 | TBD |
| 勝率 | TBD |
| 平均獲利 | TBD |
| 平均持倉時間 | TBD |
| 最大回撤 | TBD |
| Sharpe Ratio | TBD |
| Sortino Ratio | TBD |
| Profit Factor | TBD |
| 市場變化 | TBD |

---

## 幣種表現

| 幣種 | 交易數 | 利潤 | 勝率 |
|------|--------|------|------|
| BTC/USDT | TBD | TBD | TBD |
| ETH/USDT | TBD | TBD | TBD |
| SOL/USDT | TBD | TBD | TBD |
| BNB/USDT | TBD | TBD | TBD |
| XRP/USDT | TBD | TBD | TBD |

---

## 主要出場原因

| 原因 | 次數 | 佔比 |
|------|------|------|
| exit_signal | TBD | TBD |
| trailing_stop_loss | TBD | TBD |
| stop_loss | TBD | TBD |
| roi | TBD | TBD |

---

## 參數敏感度分析

| 參數 | 使用值 | 備註 |
|------|--------|------|
| degree | 2（硬約束） | - |
| window | 300 | - |
| forecast_horizon | 12 | - |
| ridge_alpha | 0.1 | - |
| entry_threshold | 0.002 | - |
| max_features | 20 | - |
| retrain_interval | 50 | - |

---

## 與基線比較

| 指標 | 基線策略 | MultiTFPolyReg_v1 | 差異 |
|------|----------|-------------------|------|
| 總利潤 | TBD | TBD | TBD |
| 勝率 | TBD | TBD | TBD |
| Sharpe | TBD | TBD | TBD |

---

## 數學理論驗證

| 理論約束 | 是否遵守 | 備註 |
|----------|----------|------|
| degree ≤ 2 | ✅ | 硬約束，PolynomialFeatures(degree=2) |
| Ridge（非 Lasso） | ✅ | sklearn.linear_model.Ridge |
| 預測收益率（連續值） | ✅ | log-return，再 sign() 轉方向 |
| 滾動窗口 | ✅ | window=300，每 50 bar 重訓 |
| 多 TF 特徵 | ✅ | 5m/15m/1h/4h 獨立特徵 |
| BIC / SelectKBest | ✅ | f_regression + k=20 |

---

## 觀察與結論

*待回測完成後填入*

### 優勢
- TBD

### 劣勢
- TBD

### 改善方向
- TBD

---

## 版本歷史

| 日期 | 版本 | 變更 |
|------|------|------|
| 2026-05-29 | v1 | 初始版本，建立數學策略架構 |
| TBD | TBD | 回測完成 |
