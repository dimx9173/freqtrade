# BB_RPB_TSL_BI + NSGAII 優化整合

## 策略資訊

- **策略名稱**: BB_RPB_TSL_BI
- **優化方法**: NSGAII (Non-dominated Sorting Genetic Algorithm II)
- **整合日期**: 2026-05-21
- **所屬框架**: 數學策略整合研發 (math_based)

## 檔案結構

```
nsgaii_bb_rpb_tsl_bi/
├── BB_RPB_TSL_BI.py          # 策略主檔
├── BB_RPB_TSL_BI.json        # NSGAII 優化後參數
├── config.json               # Freqtrade 設定檔 (dry-run, port 13998)
├── README.md                 # 本檔案
└── backtest_report.md        # 回測驗證報告
```

## NSGAII 優化參數

參見 `BB_RPB_TSL_BI.json`

## 回測結果

參見 `backtest_report.md`

## 注意事項

- 本策略為 **dry-run 測試環境**，port 13998
- 獨立 sqlite db: `tradesv3_nsgaii_test.sqlite`
- 請勿與生產環境 (Bot3, port 13993) 混淆
