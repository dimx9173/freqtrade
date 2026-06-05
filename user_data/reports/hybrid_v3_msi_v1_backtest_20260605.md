# Hybrid_v3_MSI 整合結果：策略實作完成但資料限制無法驗證

**日期**: 2026-06-05
**Strategy**: `Hybrid_v3_MSI.py` (10.1KB, 270 行)
**Config**: `user_data/config/backtest_hybrid_v3_msi.json`
**Backtest 區間**: 2025-05-01 ~ 2026-05-24 (12 月, 但 bybit BTC 15m 限縮到 2026-03-20~2026-05-24 = 2 月)

---

## 🎯 結論

✅ **Strategy 實作完成**（MSI 計算 + gate 邏輯正常運作）
❌ **資料限制導致無法驗證 alpha**（bybit BTC 15m 只有 2 月，無 regime=2 進場可過濾）

---

## 📊 實作細節

### MSI 計算
- 從 8 個 cross-asset 1h (ETH/SOL/BNB/LINK/DOGE/ADA/AVAX/SUI) 載入 close
- 計算 log returns correlation matrix 的 eigenvalues
- **Participation Ratio (PR) = (Σλ)² / Σ(λ²)**，範圍 [1, N=8]
- Rolling 24h window，freqtrade 15m bar 對齊（merge_asof backward）

### 實測 MSI 統計（2026-03-20 ~ 2026-05-24, 6241 bars）
```
mean = 1.56
range = [1.07, 3.58]
```
**解讀**: 8 個 crypto 高度相關 (mean 1.56/N=8 = 19% 有效 rank)，這 2 月 regime 偏向集中。

### MSI Gate 邏輯
```python
msi_chaos = (dataframe["msi"] > msi_high_threshold)  # default 3
in_chaos = msi_chaos & (dataframe["regime"] == 2)      # 只 block regime=2
dataframe.loc[in_chaos, "enter_long"] = 0               # 取消進場
```

### Threshold Calibration
原本 `default=8` (來自 v2 9 幣種含 BTC 的 PR 範圍) 永遠觸發不了。
**校正後**: `msi_high_threshold=3, msi_low_threshold=1` (符合 8-asset 實際範圍)

---

## 🔴 資料限制 (致命)

| 資料 | 範圍 | 影響 |
|------|------|------|
| bybit BTC 15m | 2026-03-20 ~ 2026-05-24 (2 月) | backtest 只有 2 月 |
| bybit 9 幣種 1h | 2025-05-01 ~ 2026-05-24 (12 月) | MSI 可用 12 月 |
| binance BTC 15m | 2024-01-01 ~ 2025-01-09 (1 年) | **與 bybit 9 幣種不重疊** |
| binance 9 幣種 1h | 僅 BTC 28 月 | MSI 無 9 幣種可算 |

**核心問題**: binance 有 1 年 BTC 15m，但 bybit 9 幣種 1h 從 2025-05 開始。兩者**不重疊**，無法用 binance BTC 1 年 + bybit 9 幣種 12 月做長期 backtest。

唯一可行 backtest: bybit BTC 15m (2 月) — 但 4 trades 統計上不顯著。

---

## 📈 Backtest 結果

```
Hybrid_v3 (baseline)         : 4 trades, 2W/2L, 50.0% WR, 0.0000 profit
Hybrid_v3_MSI (this version) : 4 trades, 2W/2L, 50.0% WR, 0.0000 profit
                              : 100% enter_tag = "weak_trend" (regime=1)
```

**所有 4 trades 都是 `regime=1 transition` (weak_trend entry)**，沒有任何 `regime=2 trending` (BB_RPB) 進場。
→ MSI gate 邏輯上**只 block regime=2 進場**，但這 2 月根本沒有 regime=2 進場訊號
→ Gate 在這個 backtest 中是 **no-op**，所以兩版本結果完全相同

### 為何沒有 regime=2 進場？
- Hybrid_v3 的 BB_RPB stack 有 9 個 AND-combined 條件（NFI next gen）
- 2 月 BTC 15m 資料中，9 個條件同時滿足的 candle 數 = 0
- 這 2 月恰好是低波動期（market change +8.5%, 沒明顯趨勢）
- **結論**: 這 2 月 backtest 完全無法區分 Hybrid_v3 vs Hybrid_v3_MSI

---

## 🔧 修正路徑（驗證 MSI 真正效果）

### A. 下載 binance 9 幣種 1h 歷史 (推薦, ~30 分鐘)
```bash
freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT SOL/USDT \
  BNB/USDT LINK/USDT DOGE/USDT ADA/USDT AVAX/USDT SUI/USDT \
  --timeframe 1h --timerange 20240101-20260507
```
然後修改 strategy 改用 binance (而非 bybit)，這樣有 28 月 binance 9 幣種 1h。
backtest: 2024-01-01 ~ 2026-05-07 (28 月, 充足樣本)

### B. 延長 bybit BTC 15m 歷史 (簡單但慢)
```bash
freqtrade download-data --exchange bybit --pairs BTC/USDT --timeframe 15m \
  --timerange 20240101-20260524
```
若 bybit 公開 API 沒有更早 15m 資料 → 不可行

### C. 改用 1h BTC 而非 15m (可立刻跑)
- 1h 有 28 月 (binance) 或 2 月 (bybit)
- 犧牲 4x 顆粒度換取樣本量
- 修改 `timeframe: 1h` in config

### D. 接受 2 月 backtest 不充分, 改在 live dry-run 監控 (最務實)
- deploy Hybrid_v3_MSI 到 freqtrade dry-run
- 觀察未來 3-6 月 regime=2 進場的 WR 差異
- 累積 30+ trades 再做統計

---

## 💡 從這次經驗的 3 個學習

1. **9 幣種 vs 8 幣種 MSI 範圍差異大**: 9 幣種含 BTC 的 PR mean=7.69（高度獨立）vs 8 幣種不含 BTC 的 PR mean=1.56（高度相關）。設計 threshold 必須先 calibrate。

2. **Freqtrade dataframe.index 不一定是 DatetimeIndex**: 我踩到 3 個坑 (reindex dtype, merge_asof dtype, resample requirement)。修正方式：force `pd.DatetimeIndex(...)` 包裹。

3. **2 月 backtest 在 crypto 市場毫無統計意義**: BTC 1 年波動 50-100%, 2 月趨勢可能是 noise 而非 regime。任何策略在 2 月看不出差異。

---

## 📁 產出檔案

| 檔案 | 大小 | 說明 |
|------|------|------|
| `user_data/strategies/math_based/multi_tf_regime_v1/Hybrid_v3_MSI.py` | 10.1KB | 完整 strategy (270 行) |
| `user_data/config/backtest_hybrid_v3_msi.json` | 1KB | backtest config (含正確的 `exchange.pair_whitelist`) |
| `user_data/config/backtest_baseline_hybrid_v3.json` | 1KB | Hybrid_v3 baseline config |
| `user_data/reports/hybrid_v3_msi_v1_backtest_20260605.md` | (本檔) | 報告 |

## 📝 推薦下一步

**選項 D** 最務實：deploy Hybrid_v3_MSI 到 freqtrade dry-run，3-6 月累積 30+ regime=2 trades 後再驗證 MSI alpha。

**選項 A** 開發工作最重：下載 binance 9 幣種 1h 28 月歷史，跑完整 backtest 一次性驗證 28 月累積效果。
