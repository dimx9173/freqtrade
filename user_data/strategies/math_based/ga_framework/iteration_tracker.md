# 數學策略 GA 迭代追蹤

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

### MathCombo_Adaptive_v1

#### Iteration #1
- **日期**: 2026-05-21
- **Session ID**: 20260521_013359
- **結果**: 129 trades, -0.55%, 55.8% win rate
- **狀態**: ❌ 已封存

#### Iteration #2 (GA 優化 - Sortino)
- **日期**: 2026-05-21
- **Session ID**: 20260521_111110
- **Epochs**: 500
- **Loss Function**: SortinoHyperOptLoss
- **Spaces**: buy
- **結果**:
  - 交易數: 19
  - 總利潤: -0.72% (-7.151 USDT)
  - 勝率: 42.1%
  - 最大回撤: 0.91%
  - Objective: 0.97827
- **最佳參數**:
  - window: 243.106
  - dev_mult: 1.849
  - zscore_threshold: 2.325
  - adx_min: 29.779
  - adx_max: 25.937
- **Hyperopt檔**: `archive/math_based/strategy_MathCombo_Adaptive_v1_2026-05-21_11-11-10.fthypt`
- **狀態**: ❌ 已封存

---

### PolyReg_Adaptive_v1

#### Iteration #1
- **日期**: 2026-05-21
- **Session ID**: 20260521_013009
- **結果**: 215 trades, -24.61%, 47.9% win rate
- **狀態**: ❌ 需重新優化

#### Iteration #2 (v2 修復)
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

## 待執行迭代

- [x] MathCombo_Adaptive_v1 - ~~調整參數重新優化~~ → **已封存**
- [ ] PolyReg_Adaptive_v2 - backtest 驗證
- [ ] Adaptive_Scalp_v2 - 首次優化
- [ ] 確認 NSGAII +12.65% 原始數據來源
