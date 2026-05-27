# 數學理論策略迭代記錄

## 策略目錄結構

```
math_based/
├── Adaptive_Scalp_v2.py          # 自適應市場狀態策略 (ADX + BB + RSI)
├── PSV1_SO_D3_Plus.py            # D3+ 回調策略
├── PSV1_SO_D3_Enhanced.py        # D3 增強版
├── PSV3_Regime_Adaptive.py       # 狀態自適應策略
├── PSV5_RegimeRouter.py          # 多策略路由
├── Pullback_Scalp_v1.py          # 回調剝頭皮基礎版
├── Pullback_Scalp_v1_ShortOnly.py    # 回調空單版
├── Pullback_Scalp_v1_SO_BiDir.py     # 回調雙向版
├── Pullback_Scalp_v1_SO_Dynamic.py   # 回調動態版
├── Pullback_Scalp_v1_SO_Final.py     # 回調最終版
├── RegimeAdaptive_B.py           # 狀態自適應 B
├── RegimeAware_Minimal.py        # 最小狀態感知
├── RegimeAware_v1.py             # 狀態感知 v1
├── RegimeAware_v2.py             # 狀態感知 v2
├── D3e_Strategy.py               # D3e 極端優化
│
├── risk_reward_ratio_design.md   # 風險報酬比設計理論
├── trend_detection_mechanisms.md # 趨勢識別機制
├── adaptive_scalp_v2_spec.md     # 自適應策略規格
├── pullback_strategy_research.md # 回調策略研究
├── strategy_failure_analysis.md  # 策略失敗分析
│
└── ITERATION_LOG.md              # 本檔案：迭代記錄
```

## 核心理論基礎

### 1. 凱利公式 (Kelly Criterion)
```
f* = (W × R - (1-W)) / R
W = 勝率, R = 盈虧比
```

### 2. 期望值公式
```
E = P_win × AvgWin - P_loss × AvgLoss
E > 0 ⟺ W > 1/(1+R)
```

### 3. 市場狀態分類
| Regime | ADX 範圍 | 策略 |
|--------|----------|------|
| 0 | < 20 | 均值回歸 |
| 1 | 20-25 | 觀望 |
| 2 | > 25 | 趨勢跟隨 |

## 迭代記錄

### v1.0 (2026-05-21)
- **建立**: 整理所有數學理論策略到統一目錄
- **來源**: test/, research/
- **策略數**: 15 個
- **狀態**: 待測試

### v1.1 (2026-05-21)
- **整合**: BB_RPB_TSL_BI + NSGAII 優化策略
- **來源**: strategies/test/nsgaii_bb_rpb_tsl_bi_test/
- **新位置**: `math_based/nsgaii_bb_rpb_tsl_bi/`
- **包含檔案**:
  - `BB_RPB_TSL_BI.py` — 策略主檔
  - `BB_RPB_TSL_BI.json` — NSGAII 優化參數
  - `config.json` — dry-run 測試設定 (port 13998)
  - `README.md` — 策略說明
  - `backtest_report.md` — 回測驗證報告
- **回測結果**: 83 trades, +6.80%, 95.2% win rate, 0.62% max drawdown
- **狀態**: 已驗證，待確認 +12.65% 數據來源

## 待測試項目

- [ ] Adaptive_Scalp_v2 回測
- [ ] D3+ 系列參數優化
- [ ] Regime 策略組合測試
- [ ] 凱利倉位管理整合
- [ ] 確認 NSGAII +12.65% 原始數據來源

## 最佳實踐

1. **每次迭代必須記錄**: 日期、版本、變更、結果
2. **參數變更需有理論依據**: 引用對應的 .md 文件
3. **回測結果需保存**: 輸出到 reports/ 目錄
4. **commit 前檢查**: 確保理論與實作一致
