# Hybrid_v3 SL Local Hyperopt (9 epochs) — Regime Overfit Confirmed

**日期**: 2026-06-06 01:33 (新 run)
**Source**: `user_data/hyperopt_results/strategy_Hybrid_v3_2026-06-06_01-33-14.fthypt`
**對比**: `user_data/hyperopt_results/strategy_Hybrid_v3_2026-06-01_14-06-17.fthypt` (上次)

---

## 🎯 關鍵發現

### 🔴 9 個 trials **全部 loss=3.268, 全部 16 trades**
- Stoploss 從 -6.8% 到 -34.8% 變化，**loss 完全沒差**
- 全部 16 trades 都用 ROI 出場，**stoploss 完全沒被觸發**
- 6 月 BTC 從 ~$92k 漲到 ~$108k，持倉永遠浮盈，stoploss redundant

### 上次 vs 本次 對比

| 項目 | 上次 (2025-11~2026-03) | 本次 (2025-12~2026-05) |
|------|----------------------|----------------------|
| Timerange | 4 月（含熊市） | 6 月（含 4-5 月反彈） |
| BTC 趨勢 | $108k → $82k → $95k | $92k → $108k |
| Best SL | **-2.6%** (緊) | -28.8% (寬鬆, 但 redundant) |
| Best Loss | 115.499 | 3.268 |
| Trades | 674 | 16 |
| Regime | 熊市+震盪 | 純牛市 |

**結論**: 上次 SL=-2.6% 是「在 4 月熊市保護資本」的緊 SL；本次 SL=-28.8% 是「6 月牛市無需 SL」的空集合。**兩個 best 都無法 cross-validate**。

---

## 🛑 不要套用本次 Best

### 為何不套用 SL=-28.8%？
- **Regime overfit**: 6 月牛市太短，無法驗證熊市表現
- 4 月 (上次 GA 區間) BTC 跌 20%，**-28.8% SL 在 4 月會一次虧 28.8%**（vs -2.6% 只虧 2.6%）
- 4 月熊市 -3.98% profit + max DD 5.75% 是「現狀 -2.6% SL」撐住的
- 套用 -28.8% 會讓 4 月 DD 暴增到 28%+，可能爆倉

### 為何 ProfitDrawDown Loss 對 SL 不敏感？
- Loss 公式：`profit - max_drawdown * weight`
- 若 **所有 trades 都用 ROI 出場（無 SL 觸發）** → SL 完全不影響 profit 或 drawdown
- freqtrade hyperopt 內部不重複計算 trades 細節，只看 metrics summary
- → SL hyperopt 在無 SL 觸發的 regime 必然無差

---

## 📊 9 Trials 詳細

| # | SL | Loss | Trades |
|---|-----|------|--------|
| 1 | -28.8% | 3.268 | 16 |
| 2 | -25.8% | 3.268 | 16 |
| 3 | -22.2% | 3.268 | 16 |
| 4 | -7.2% | 3.268 | 16 |
| 5 | -29.0% | 3.268 | 16 |
| 6 | -34.8% | 3.268 | 16 |
| 7 | -26.4% | 3.268 | 16 |
| 8 | -26.6% | 3.268 | 16 |
| 9 | -6.8% | 3.268 | 16 |

**SL 範圍**: -34.8% to -6.8% (mean -23.1%)
**Loss 範圍**: 3.268 (全相同)

---

## ✅ 真正可執行的下一步

### 1. 維持現狀 (推薦)
- **SL -2.6%** 保留（上上次 GA 4 月熊市找的）
- **ROI 21.6/3/1.9%** 保留
- **Trail 10.7%** 保留
- → 部署 dry-run，累積 live data

### 2. 跨時段 Walk-Forward 驗證 (研究性, 非立即)
- 需 1+ 年 10 幣種 15m 資料（目前不齊全）
- 拆 6-month train + 1-month test，滾動
- 目標：確認 SL -2.6% 在 4 月和 6 月都 work

### 3. 修進場邏輯 (根本)
- Hybrid_v3.py 的 populate_entry_trend 有 9 種 NFI next gen 條件
- 真正的瓶頸是「**進場太少**」(6 月才 16 trades)
- 應研究如何放寬條件換更多 trade 機會

### 4. 部署 Hybrid_v3_MSI v1 + 觀察
- 之前 commit `fd827380b` 的 MSI gate
- 雖然 2 月 backtest 4 trades 不顯著，但**進 dry-run live 觀察 regime=2 進場的 WR**
- 3-6 月後可統計 30+ trades 的 MSI gate 效果

---

## 📁 產出

- 本報告（regime overfit 警示）
- `user_data/hyperopt_results/strategy_Hybrid_v3_2026-06-06_01-33-14.fthypt` (9 trials)
- 維持現狀 (SL -2.6%, ROI 21.6/3/1.9%)

## 🎯 我的強烈推薦

**選項 4：部署 Hybrid_v3_MSI v1 到 dry-run**。理由：
1. 現狀已收斂（GA 證明）
2. SL 在 6 月 redundant, 短期無需再優化
3. MSI gate 是新 alpha 來源，需要 live data 驗證
4. 3-6 月後可累積 30+ regime=2 trades 做 MSI 統計

**執行步驟**：
```bash
# 部署 dry-run
freqtrade trade --config user_data/strategies/math_based/multi_tf_regime_v1/config.json \
  --strategy Hybrid_v3_MSI --strategy-path user_data/strategies/math_based/multi_tf_regime_v1
```

**或**選項 1：保持 Hybrid_v3 (不帶 MSI) dry-run，純粹部署驗證。
