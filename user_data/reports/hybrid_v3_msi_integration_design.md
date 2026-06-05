# Hybrid_v3 + MSI 整合設計書 (未實施)

> **狀態**: ⏸️ 設計完成，待更多資料驗證
> **日期**: 2026-06-05
> **作者**: Brian + MiniMax-M3
> **目標**: 將 Path 2 的 10-asset MSI 特徵整合到 Hybrid_v3 進場邏輯

---

## 1. POC 結論摘要

從 `poc_p2_msi_edge.py` 在 BTC 1h 1523 筆資料的快速驗證：

| MSI 過濾 | 進場數 | 4h WR | 4h avg return | 24h avg | 顯著性 (vs no filter) |
|---------|--------|-------|--------------|---------|---------------------|
| MSI > 8.0 (高耦合) | 202 | 45.5% | 0.016% | -0.251% | p=0.51 (不顯著) |
| **MSI < 6.5 (低耦合)** | 63 | **57.1%** | **0.024%** | 0.032% | p=0.52 (不顯著) |
| 無過濾 (baseline) | 563 | 47.1% | -0.022% | -0.100% | — |

**觀察**:
- ⚠️ 統計不顯著 (p>0.05)，但 MSI < 6.5 過濾器有 trade-off 意義
- ✅ MSI < 6.5 過濾掉 89% 進場，但 WR 從 47.1% 提升到 57.1%
- ⚠️ 2 月 bybit 1h 資料太少（剛下載），結論不穩健

**決策**: ⏸️ **不立即整合**，先累積更多資料或擴大 timeframe 後重跑 POC

---

## 2. 完整整合設計 (待實施)

### 2.1 設計動機

**Hybrid_v3 結構性限制**:
- 現有 regime detection 用 ADX multi-TF consensus (15m/1h/4h)
- ADX 只看單一幣種的方向強度，沒有「跨幣種市場模式」信息
- 在 BTC 與 alt 高度耦合的時期，ADX 可能誤判 regime

**Path 2 MSI 提供**:
- 10 幣種 correlation matrix 的 eigenvalue ratio
- 同步指標 (MSI-Vol 相關 0.689)
- 危機偵測能力 (5% windows, 1.49x 波動)

**預期改善**:
- 在 MSI < 6.5 (regime 分散) 時，Hybrid_v3 進場更精準
- 在 MSI > 8.0 (regime 集中) 時，暫停交易避免同步崩盤

### 2.2 整合架構

```
                  ┌────────────────────┐
                  │ Hybrid_v3 + MSI    │
                  │ (extends Hybrid_v3)│
                  └────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   informative_pairs   populate_indicators   populate_entry_trend
   (新增 9 個 1h)      (加 MSI 計算)         (加 MSI 過濾)
        │                   │                   │
   ETH/SOL/BNB/        10 幣種 corr →         if MSI < 6.5: 允許
   LINK/DOGE/ADA/      eigenvalue →          if MSI > 8.0: 暫停
   AVAX/TON/SUI        MSI 計算              if 6.5 ≤ MSI ≤ 8.0: 預設
   (1h timeframe)
```

### 2.3 程式碼骨架 (Hybrid_v3_MSI.py)

```python
class Hybrid_v3_MSI(Hybrid_v3):
    """
    Hybrid_v3 + 10-asset MSI filter
    """
    MSI_ASSETS = ['ETH', 'SOL', 'BNB', 'LINK', 'DOGE', 'ADA', 'AVAX', 'TON', 'SUI']
    MSI_WINDOW = 24  # 24 hours rolling window
    MSI_HIGH = 8.0   # regime concentration threshold
    MSI_LOW = 6.5    # regime dispersion threshold

    def informative_pairs(self):
        pairs = super().informative_pairs()
        # Add 1h data for 9 additional assets
        for asset in self.MSI_ASSETS:
            pairs.append((f"{asset}/USDT:USDT", "1h", None))
        return pairs

    def populate_indicators(self, dataframe, metadata):
        dataframe = super().populate_indicators(dataframe, metadata)

        # Compute MSI from 10-asset correlation matrix
        msi_df = self._compute_msi()
        if msi_df is not None:
            # Forward fill to 15m
            dataframe = pd.merge_asof(
                dataframe.sort_index(),
                msi_df.sort_index(),
                left_index=True, right_index=True,
                direction='backward'
            )
            dataframe['msi'] = dataframe['msi'].ffill()
        else:
            dataframe['msi'] = 7.5  # neutral default

        return dataframe

    def _compute_msi(self):
        """Compute 10-asset MSI from 1h returns"""
        # Load 1h close for all 10 assets
        ret_dict = {}
        for asset in ['BTC'] + self.MSI_ASSETS:
            try:
                inf = self.dp.get_pair_dataframe(
                    pair=f"{asset}/USDT:USDT", timeframe="1h"
                )
                ret_dict[asset] = inf['close'].pct_change()
            except Exception:
                return None

        ret_df = pd.DataFrame(ret_dict).dropna()
        msi_list = []
        for i in range(self.MSI_WINDOW, len(ret_df)):
            seg = ret_df.iloc[i-self.MSI_WINDOW:i]
            corr = seg.corr().values
            eigvals = np.linalg.eigvalsh(corr)
            eigvals = np.sort(eigvals)[::-1]
            eigvals_norm = eigvals / eigvals.sum() * len(eigvals)
            msi = eigvals_norm[0] / np.mean(eigvals_norm)
            msi_list.append(msi)

        msi_series = pd.Series(
            msi_list,
            index=ret_df.index[self.MSI_WINDOW:],
            name='msi'
        )
        return pd.DataFrame(msi_series)

    def populate_entry_trend(self, dataframe, metadata):
        dataframe = super().populate_entry_trend(dataframe, metadata)

        # MSI filter
        msi = dataframe['msi']
        # High regime concentration: pause trading (avoid synchronized crash)
        dataframe.loc[msi > self.MSI_HIGH, 'enter_long'] = 0
        # Low regime concentration: enable Hybrid_v3's own filter (more permissive)
        # Mid range: use Hybrid_v3 default

        return dataframe
```

### 2.4 關鍵設計決策

| 決策 | 選擇 | 原因 |
|------|------|------|
| 整合方式 | 繼承 Hybrid_v3 | 不破壞現有 regime detection，可 A/B 對比 |
| 過濾方向 | MSI > 8.0 暫停 | 避免同步崩盤（高耦合 = 高度相關 = 一損俱損）|
| 過濾方向 | MSI < 6.5 啟用 | 分散環境下 BTC 個別行情更精準 |
| 缺失 MSI 預設 | 7.5 (中性) | 預設行為等於現有策略 |
| 計算時機 | populate_indicators 內 | 與其他特徵同時計算 |

### 2.5 驗證計畫

**前置條件**:
- [ ] 累積 ≥ 6 個月 bybit BTC 1h 資料（目前 2 月）
- [ ] 或下載 binance BTC 1h 28 月資料 + 其他 9 個 binance 1h 資料
- [ ] 重新跑 POC，期望 p-value < 0.05

**完整 backtest 計畫**:
- [ ] 在 Freqtrade 設定 `BTC/USDT:USDT` 為唯一交易對
- [ ] 同時下載其他 9 個幣種 1h 資料到 `user_data/data/bybit/`
- [ ] 跑 4 個月 OOS backtest (2026-02-01 ~ 2026-06-01)
- [ ] 對比基準:
  - Hybrid_v3 (現有): 利潤 -3.98%, WR 85.2%, Max DD 5.75%
  - Hybrid_v3_MSI (目標): 利潤 > -3.0%, WR > 86%, Max DD < 5%
- [ ] 至少 30 筆交易才能下結論

### 2.6 風險清單

1. ⚠️ **資料可用性**: 9 個幣種需 bybit 1h 資料全齊，當前僅 2 個月
2. ⚠️ **計算成本**: 10x10 eigendecomp × 每根 15m K 線 = 約 5-10% CPU overhead
3. ⚠️ **過擬合**: MSI threshold (6.5/8.0) 從 POC 推估，可能需 GA 優化
4. ⚠️ **Regime 失效**: MSI 是同步指標，regime 變化時 MSI 反應延遲

---

## 3. 替代方案

如果 POC 重跑後仍不顯著，可考慮：

### 3.1 不同 MSI threshold
- 用 rolling quantile 動態 threshold (POC 中用 6.5/8.0 是固定的)
- 例如：`msi_filter = (msi > msi.rolling(168).quantile(0.95))`

### 3.2 MSI 作為 XGBoost 特徵
- 把 MSI 加入 Path 3 XGBoost 訓練
- 用 Tree model 自動學習 MSI 與其他特徵的交互
- 重跑 `poc_p3_xgboost.py` 加 `msi` 特徵

### 3.3 不同 Entry Logic
- 嘗試 mean-reversion 而非 trend-following
- 嘗試更長 holding period (24h 而非 4h)
- 嘗試不同 RSI/ADX 參數

### 3.4 直接放棄
- 若所有路徑都無顯著 edge，回到 Hybrid_v3 基準優化 (trailing_stop, ROI 重新 GA)

---

## 4. 完整檔案清單

| 檔案 | 狀態 | 說明 |
|------|------|------|
| `poc_p2_msi_edge.py` | ✅ 完成 | POC 驗證腳本 (2 月資料) |
| `Hybrid_v3_MSI.py` | ⏸️ 待實施 | 完整策略骨架（本設計書） |
| `configs/backtest_btc_msi.json` | ⏸️ 待實施 | Freqtrade backtest config |
| `reports/msi_integration_poc_20260605.md` | ⏸️ 待實施 | Backtest 結果報告 |

---

*Generated: 2026-06-05 by MiniMax-M3*
*依 [multi_breakthrough_p2_p3_results_20260605.md](./multi_breakthrough_p2_p3_results_20260605.md) 中 Path 2 結論*
