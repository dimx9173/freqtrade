# Multi-Breakthrough POC Results — 2026-06-05

> **作者**: Brian + MiniMax-M3
> **方法**: 1h timeframe 從 Freqtrade 本地資料 (`/home/brian/freqtrade/user_data/data/binance/`)
> **Python**: `freqtrade/.venv/bin/python3` (系統 python 無 pandas)
> **執行時間**: < 5 分鐘

---

## Path 1: Cointegration Pairs Trading ❌ FAILED

### 結論
**BTC-ETH 與 BTC-SOL 沒有 cointegration**。Crypto 主流幣種的 log 價比 spread 不是平穩序列。

### 量化證據

| 指標 | BTC-ETH | BTC-SOL | 判定 |
|------|---------|---------|------|
| Full sample ADF p-value | 0.770 | 0.274 | ❌ p > 0.05 = unit root |
| Rolling 30d p<0.10 | 17.4% | ~10% | ❌ < 50% window pass |
| Rolling 30d p<0.05 | 10.8% | 8.0% | ❌ far below 60% threshold |
| z<-2.0 觸發 | 0 | 0 | ❌ 完全沒信號 |
| z>2.0 觸發 | 0 | 0 | ❌ |
| Half-life mean reversion | 118.2 天 | — | ❌ 不可交易 |
| OLS hedge ratio (beta) | 0.4309 | 0.5706 | 合理但無用 |

### 為什麼失敗（結構性）
1. **Crypto 沒有 mean-reverting spread**：BTC 與 ETH/SOL 在 2024-2026 期間沒有共同平穩的 spread（regime-dependent drift）
2. **Beta 不穩定**：rolling OLS 估計的 hedge ratio 在 regime 變化時漂移
3. **學術文獻衝突**：Engle-Granger (1987) 假設平穩 macro 變數（GDP、利率），crypto 不適用

### 教訓
- 放棄 BTC-ETH / BTC-SOL 配對
- 嘗試其他配對需有「為什麼 cointegrate」的基本面論述（如 ETH-BTC staking 套利）
- 30 天 rolling 中只有 10% 通過 ADF → 即使做配對，edge 也不存在

### 替代方案
- 不再嘗試 crypto-crypto pairs trading
- 若要做，轉向 **跨交易所 funding rate arbitrage**（已在 funding-rate-arbitrage 專案）

---

## Path 2: Random Matrix Eigenvalue (ORCA) 🟡 PARTIAL SUCCESS

### 結論
**Eigenvalue decomposition 確實捕捉到 regime 變化**，但 3 個資產不夠（MSI 永遠 ~3.0 飽和）。

### 量化證據 (3 個資產: BTC, ETH, SOL, 8256 小時資料)

| 指標 | 數值 | 解讀 |
|------|------|------|
| Mean MSI (λ_max/mean) | 2.621 | 接近理論上限 3.0 (3 資產耦合度極高) |
| MSI std | 0.210 | 變化有限 |
| MSI range | 1.614 ~ 2.964 | 飽和 |
| Mean Participation Ratio | 1.309 | 接近 1.0 (一個主導模式) |
| Top eigenvalue λ_1 | 2.621 ± 0.210 | 佔絕對主導 |
| λ_2 | 0.256 ± 0.145 | 次要 |
| λ_3 | 0.123 ± 0.077 | 最小 |
| **MSI-Vol correlation** | **0.509** | ✅ 中等強度正相關 |
| Crisis events (MSI > p95) | 69 (5.0%) | 與已知波動事件對應 |
| Crisis vol / Normal vol | 1.79x | crisis 期間波動顯著上升 |

### Crisis 日期樣本
- 2025-06-13 13:00
- 2025-09-06 01:00
- 2025-09-06 07:00
- 2025-11-... (等)

### 為什麼是「部分成功」
1. ✅ **MSI-Vol 相關 0.509** — eigenvalue 確實捕捉到市場模式
2. ✅ **Crisis detection** — MSI 飆升對應波動率上升
3. ❌ **3 資產飽和** — MSI 永遠接近 3.0，沒有 spread 區分 regime
4. ❌ **單獨使用 eigenvalue 不夠** — 需整合到 Hybrid_v3 的 regime classifier 看是否改善

### 下一步
- **擴展到 9-10 幣種** (Hybrid_v3 已知配置)：BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, TON, SUI
- 計算 eigenvalues 在 N=10 下的 spread（預期 MSI range 1.5~4.0）
- 設計 regime classifier：MSI > 2.0 = uptrend, MSI < 1.5 = downtrend
- 整合到 Hybrid_v3 替換現有 ADX-based regime detection
- A/B 測試：新 regime detection vs 現有，4 個月 OOS backtest

---

## Path 3: Hybrid AI + XGBoost ⏳ NOT STARTED

### 計畫
- 訓練目標：預測「未來 4h 漲跌 > 0.3%」
- 特徵：regime + TA + volume + cross-TF + funding
- 模型：XGBoost binary classifier
- 預期時間：4-6 小時（含訓練 + 4 月 OOS backtest）

### 狀態
未啟動，待 Path 2 結果定案後再決策優先順序。

---

## Path 4: Reinforcement Learning ⏸️ DEFERRED (Phase 2)

待 Path 1-3 至少一個成功才啟動。

---

## 整體決策建議

| 動作 | 優先 | 預估時間 |
|------|------|---------|
| **Path 1 標記 DEPRECATED** | 🟢 立即 | 5 分鐘 |
| **Path 2 擴展到 9 幣種** | 🟡 中 | 30 分鐘 |
| **Path 2 整合到 Hybrid_v3 + OOS backtest** | 🟡 中 | 4-6 小時 |
| **Path 3 XGBoost POC** | 🟢 立即 | 4-6 小時 |
| **Path 4 RL** | 🔴 Phase 2 | 1-2 週 |

### Go/No-Go 矩陣

| 結果 | 下一步 |
|------|--------|
| Path 2 (9 幣種) 改善 AUC > 5% | 整合到 Hybrid_v3 跑 4 月 backtest |
| Path 3 XGBoost OOS > 55% 準確 | 整合為進場過濾器 |
| 兩個都失敗 | 回到 Hybrid_v3 優化 (trailing_stop / ROI 重新 GA) |

---

*Generated: 2026-06-05 by MiniMax-M3*
*Source: `/home/brian/freqtrade/user_data/strategies/math_based/multi_breakthrough_v1/poc_p1_p2.py`*
