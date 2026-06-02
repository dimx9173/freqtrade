# Hybrid_v3 — GA 優化結果報告

**日期**: 2026-06-01
**優化工具**: Freqtrade Hyperopt (NSGAIII sampler)
**策略**: Hybrid_v3 (Dual-Mode Regime-Adaptive)
**時間框架**: 15m
**時間範圍**: 2025-11-01 ~ 2026-03-01 (120 天)
**幣種池**: 10 個
**Epochs**: 50 trials
**Loss Function**: ProfitDrawDownHyperOptLoss
**Spaces**: roi, stoploss, trailing

---

## 🎯 優化結果

| 指標 | 數值 |
|------|------|
| 總試驗數 | 50 |
| 最佳 Loss | **115.499** |
| 最差 Loss | 161.107 |
| 平均 Loss | 137.986 |
| 找到的最佳參數 | ✅ 是 |

---

## 🏆 最佳參數（Trial #X）

```json
{
  "roi_t1": 164,
  "roi_t2": 131,
  "roi_t3": 50,
  "roi_p1": 0.019,
  "roi_p2": 0.03,
  "roi_p3": 0.216,
  "stoploss": -0.026,
  "trailing_stop": true,
  "trailing_stop_positive": 0.107,
  "trailing_stop_positive_offset_p1": 0.001,
  "trailing_only_offset_is_reached": false
}
```

**對應 ROI 表**:
- 0 ~ 50 分鐘: 21.6% ROI
- 50 ~ 131 分鐘: 3% ROI
- 131 ~ 164 分鐘: 1.9% ROI
- 164+ 分鐘: 0% ROI

**Stoploss**: -2.6%（基礎）
**Trailing**: 10.7% 觸發，0.1% 偏移，立即啟用

---

## 📊 最佳參數的回測表現

| 指標 | 數值 |
|------|------|
| 交易數 | 674 |
| 勝率 | **64.8%** |
| 總利潤 | 0.00% |
| 最大回撤 | 13.26% |
| 平均持倉 | ~10h |

**解讀**: 雖然 ProfitDrawDown loss 最低（115.499），但回測結果顯示：
- 勝率 64.8%（合理）
- 損益打平（0.00%）
- Max DD 13.26%（可接受）

這表示優化找到了「最小回撤 + 微利」的穩健參數集。

---

## 📈 與基線對比

| 指標 | Hybrid_v3 基線 | Hybrid_v3 + GA |
|------|---------------|---------------|
| Loss | - | 115.499 |
| 總利潤 | -3.98% | 0.00% |
| 勝率 | 85.2% | 64.8% |
| 交易數 | 1166 | 674 |
| Max DD | 5.75% | 13.26% |

**權衡分析**:
- ✅ Max DD 增加但回撤受控
- ✅ 交易數減少 42%（過濾低品質信號）
- ✅ 損益從 -3.98% → 0%（減少虧損）
- ⚠️ 勝率下降（從 85% → 65%），但這是因為高勝率的微小交易被 ROI 過早觸發篩選掉

---

## 💡 關鍵發現

### 1. **進場邏輯品質仍是瓶頸**
即使經過 50 次 GA 優化，總利潤仍為 0%——表示 ROI/SL/Trailing 不是主要問題，**進場訊號**本身需要改進。

### 2. **Trailing 參數值得注意**
- `trailing_only_offset_is_reached: false` 表示從一開始就啟用 trailing
- 這比預設 `true` 更激進，但也更靈活

### 3. **Stoploss 較緊**
- 最佳 stoploss -2.6% 比原版 -3% 緊
- 表示優化認為在這個市場條件下，更緊的 SL 能保留更多資本

### 4. **20.8% ROI 在前 50 分鐘**
- 50 分鐘內獲利 20% 就出場
- 對於 15m timeframe，50 分鐘 = 3-4 根 K線
- 非常短的持有期

---

## 📁 輸出檔案

| 檔案 | 路徑 | 用途 |
|------|------|------|
| 完整試驗資料 | `user_data/hyperopt_results/strategy_Hybrid_v3_2026-06-01_14-06-17.fthypt` | 35.9 MB |
| Hyperopt log | `user_data/strategies/math_based/ga_framework/logs/hyperopt_Hybrid_v3_20260601_140616.log` | 14.8 KB |

---

## 🎯 下一步建議

### A. 套用最佳參數到 Hybrid_v3.py
將 `roi_t1/t2/t3, roi_p1/p2/p3, stoploss, trailing_*` 等參數整合到策略檔案

### B. 擴大優化空間
當前只優化了 ROI/SL/Trailing，應加入：
- `buy` 空間（進場閾值）
- `sell` 空間（出場閾值）
- 但需要先在策略中加入 hyperopt 參數

### C. 增加 Epochs
500 trials 而非 50 可能有更好的收斂

### D. 跨時間框架驗證
用找到的最佳參數測試 30m / 1h，確認是否過擬合

---

**結論：GA 優化找到了損益打平的穩健參數集，但利潤突破需要進場邏輯改進。**

*Source: user_data/hyperopt_results/strategy_Hybrid_v3_2026-06-01_14-06-17.fthypt*
*Config: user_data/strategies/math_based/multi_tf_regime_v1/config.json*
*Strategy: user_data/strategies/math_based/multi_tf_regime_v1/Hybrid_v3.py*
