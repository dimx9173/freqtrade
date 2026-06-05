# Path 1: 跨幣種 Cointegration 配對交易 — DEPRECATED

> **棄用日期**: 2026-06-05
> **根本原因**: BTC-ETH / BTC-SOL 配對在 2024-2026 1h 資料中**未通過 cointegration 檢定**（ADF p-value 0.77/0.27，遠超 0.05 閾值）
> **狀態**: ❌ DO NOT USE

## 棄用詳情

### POC 結果摘要
| 指標 | BTC-ETH | BTC-SOL |
|------|---------|---------|
| Full sample ADF p-value | 0.770 | 0.274 |
| Rolling 30d p<0.05 | 10.8% | 8.0% |
| z-score 觸發 | 0 | 0 |
| Half-life mean reversion | 118.2 天 (不可交易) | — |

詳細 POC 結果見 `user_data/reports/multi_breakthrough_poc_results_20260605.md`。

## 為什麼保留
- 理論探索紀錄 (Engle-Granger / Johansen 框架在 crypto 的適用性測試)
- 負面教材 (避免重蹈覆轍浪費時間)
- 符合 skill 規範：「保留所有檔案」

## 替代方案
- **跨交易所 funding rate arbitrage**：已移交 `~/project/funding-rate-arbitrage` 專案 (delta-neutral, 適合 1000 USDT 資金)
- **多幣種 regime detection**：Path 2 隨機矩陣 eigenvalue (9 幣種擴展中)

## 為什麼不適用
1. Crypto 主流幣種沒有共同平穩的 spread (regime-dependent drift)
2. Rolling OLS hedge ratio 在 regime 變化時漂移
3. Engle-Granger (1987) 假設平穩 macro 變數，crypto 不適用

---

*DEPRECATED by MiniMax-M3 on 2026-06-05*
*Source: `user_data/strategies/math_based/multi_breakthrough_v1/poc_p1_p2.py`*
