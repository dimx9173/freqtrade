# 數學策略 GA 迭代追蹤

> 最後更新: 2026-06-03（補 2026-06-01 session 4 個 task）

## 迭代記錄格式

每個策略的 GA 迭代應記錄：

```markdown
### [策略名稱] - Iteration #[N]
- **日期**: YYYY-MM-DD
- **Session ID**: YYYYMMDD_HHMMSS
- **Epochs**: N
- **Loss Function**: XXX
- **結果**:
  - 總利潤: X%
  - 交易數: N
  - 勝率: X%
  - 最大回撤: X%
- **參數檔**: [連結]
- **報告**: [連結]
- **狀態**: ✅ 完成 / ⚠️ 待驗證 / ❌ 失敗
```

---

## 當前迭代記錄

### nsgaii_bb_rpb_tsl_bi

#### Iteration #1 (基線)
- **日期**: 2026-05-20
- **來源**: 原始 BB_RPB_TSL_BI backtest
- **結果**: 9 trades, +6.22%, 66.7% win rate
- **狀態**: ✅ 基線已建立

#### Iteration #2 (NSGAII 優化)
- **日期**: 2026-05-21
- **Session ID**: 20260521_103038
- **Epochs**: 500
- **Loss Function**: ProfitDrawDownHyperOptLoss
- **結果**: 83 trades, +6.80%, 95.2% win rate, 0.62% max drawdown
- **參數檔**: `strategies/math_based/nsgaii_bb_rpb_tsl_bi/BB_RPB_TSL_BI.json`
- **報告**: `strategies/math_based/nsgaii_bb_rpb_tsl_bi/backtest_report.md`
- **狀態**: ✅ 已驗證

#### Iteration #3 (邏輯修復)
- **日期**: 2026-05-21
- **問題**: GA 優化輸出 adx_max (25.937) < adx_min (29.779)，邏輯矛盾
- **修復**: 交換 adx_max 和 adx_min 值，使 adx_min (25.937) < adx_max (29.779)
- **驗證**: 使用修正後參數重新 backtest
  - 交易數: 19
  - 總利潤: -0.72% (-7.151 USDT)
  - 勝率: 42.1%
  - 最大回撤: 0.91%
- **結論**: 邏輯修復完成，但策略本身收益為負，建議重新優化或檢視策略邏輯
- **狀態**: ✅ 邏輯矛盾已修復，策略需進一步優化

---

### PolyReg_Adaptive（活躍）

#### v1 Iteration #1
- **日期**: 2026-05-21
- **Session ID**: 20260521_013009
- **結果**: 215 trades, -24.61%, 47.9% win rate
- **狀態**: ❌ v1 已廢棄 — 由 v2 取代

#### v2 修復
- **日期**: 2026-05-24
- **問題**: timeframe 1h 與 15m backtest 不匹配；entry 條件過嚴 (ADX + ATR + channel break)；僅 mean-reversion 無 trend-following；degree 參數型別錯誤
- **修復**: v2 版本
  - timeframe 改為 15m
  - DecimalParameter → IntParameter
  - ATR filter 改為可選，加入 volume filter
  - ADX 範圍放寬 (10-50)
  - 啟用 mean-reversion + trend-following 雙模式
  - startup_candle_count 從 300 降至 100
- **策略檔**: `strategies/math_based/PolyReg_Adaptive_v2.py`
- **診斷報告**: `user_data/reports/PolyReg_Adaptive_v1_diagnosis.md`
- **狀態**: ⚠️ 待 backtest 驗證

---

### Hybrid_v3（活躍）— 2026-06-01 session 重大突破

#### Iteration #1 (Regime-guided 雙模式架構驗證)
- **日期**: 2026-06-01
- **Session ID**: 20260601_140616
- **目標**: 驗證 regime-guided 雙模式進場（trending: EMA+MACD / ranging: RSI+BB）vs 原版 ADX 單模式
- **結果**:
  - 1166 trades
  - 勝率 **85.2%** (原版 12.2%)
  - Max DD 5.75% (原版 94.97%)
  - **總利潤 -3.98%** (原版 -94.96%) — **架構勝 30×**
- **核心洞察**: 純 Regime + TA 進場是災難；Regime + 雙模式進場接近獲利
- **報告**: `user_data/reports/Hybrid_v3_15m_backtest_20260601.md`
- **狀態**: ✅ 架構突破驗證完成

#### Iteration #2 (GA 50 trials, 優化 ROI/SL/Trailing)
- **日期**: 2026-06-01
- **Loss Function**: ProfitDrawDownHyperOptLoss
- **Spaces**: roi stoploss trailing
- **Epochs**: 50
- **結果**:
  - 674 trades, WR 64.8%, 利潤 0.00%, Max DD 13.26%
  - 最佳 Loss: 115.499
  - 找到「不賠」參數集，但**打平非獲利**
- **最佳參數**:
  - ROI: 50min 21.6% / 131min 3% / 164min 1.9%
  - Stoploss: -2.6%
  - Trailing: 10.7% 觸發, 0.1% 偏移, 立即啟用
- **報告**: `user_data/strategies/math_based/ga_framework/reports/Hybrid_v3_GA_results_20260601.md`
- **狀態**: ⚠️ 進場邏輯是下一個瓶頸（架構 > 參數）

---

### MultiTF_RegimeDetector_v1 (15m × 10 幣種) — ❌ 失敗教訓

#### Iteration #C (多幣種擴展實驗)
- **日期**: 2026-06-01
- **嘗試**: 將 BTC-only 優化的策略擴展到 10 幣種
- **結果**:
  - 5185 trades
  - **總利潤 -94.96%** (帳戶歸零)
  - 勝率 12.2%
  - Max DD 94.97%
  - 連虧 65 次
- **報告**: `user_data/reports/MultiTF_RegimeDetector_v1_15m_backtest_20260601.md`
- **結論**: ❌ **不要盲目擴展幣種** — 單幣種優化策略不能套用多幣種
- **狀態**: 維持 BTC-only 限制

---

### Adaptive_Scalp_v2
- **狀態**: ⚠️ 待建立
- **描述**: ADX + BB + RSI 自適應 Trend-Following Scalping (15m, 5x leverage)
- **待辦**: 首次 GA 優化

---

### MultiTFPolyReg_v1

- **狀態**: 📋 規劃中
- **描述**: 多 TF 多項式回歸策略 (基於 Wavelet MRA 數學理論)
- **數學基礎**: degree≤2, Ridge, BIC, 滾動窗口, 4×TF
- **待辦**: 建立策略模板

---

## 已封存策略

### MathCombo_Adaptive_v1 ❌
- **封存日期**: 2026-05-21
- **原因**: Iteration #1: 129 trades, -0.55%, 55.8% win rate — 負收益且過度交易
- **Iteration #2 (GA, Sortino)**: 19 trades, -0.72%, 42.1% win rate — 同樣負收益
  - 最佳參數: window=243.106, dev_mult=1.849, zscore_threshold=2.325
  - Objective: 0.97827
- **結論**: 策略設計有根本缺陷，不適合當前市場條件，永久封存

---

## 待執行迭代
## 待執行迭代
- [ ] **Hybrid_v3 套用 GA 參數 + 整合 BB_RPB 進場邏輯**（基線 +6.22% 已驗證）— 🔴 高優先
- [ ] Hybrid_v3 GA 50→500 epochs 進階收斂
- [ ] Hybrid_v3 buy/sell space 擴展（自定義 IntParameter/DecimalParameter）
- [ ] PolyReg_Adaptive_v2 — backtest 驗證後進行 GA 優化
- [ ] Adaptive_Scalp_v2 — 首次 GA 優化
- [ ] MultiTFPolyReg_v1 — 建立策略模板
- [x] ~~MathCombo_Adaptive_v1 重新優化~~ → 已封存
- [x] ~~MultiTF_RegimeDetector_v1 多幣種擴展~~ → 維持 BTC-only
- [ ] 確認 NSGAII +12.65% 原始數據來源
