
# Futures 1x 優化計畫

## 目標
將 Futures 1x 策略從目前表現優化到超越 Spot 基準

## 優化策略

### 1. ElliotV5_SMA_ninja (目前最佳: +6.89%)
- **目標**: +15%+
- **方法**:
  - Hyperopt 買入/賣出參數
  - 調整 stoploss (-0.03 → -0.05)
  - 測試不同時間框架 (5m, 15m, 1h)
  - 優化 leverage (1x → 2x)

### 2. BB_RPB_TSL_BI (目前: -4.50%)
- **目標**: 轉虧為盈 > +5%
- **方法**:
  - 重新設計買入邏輯
  - 調整 trailing stop 參數
  - 減少交易頻率 (提高品質)
  - 測試不同幣對權重

### 3. PSV5_Hybrid (目前: -17.07%)
- **目標**: 減少虧損至 -5% 以內
- **方法**:
  - 完全重新設計 (策略本身問題較大)
  - 或考慮淘汰此策略
  - 減少 max_open_trades
  - 提高 entry 門檻

## 執行步驟

### Phase 1: ElliotV5 優化 (1-2 天)
1. Hyperopt 買入參數 (1000 epochs)
2. Hyperopt 賣出參數 (1000 epochs)
3. 測試不同 stoploss
4. 回測驗證

### Phase 2: BB_RPB_TSL_BI 優化 (2-3 天)
1. 分析虧損原因
2. Hyperopt 關鍵參數
3. 調整 trailing stop
4. 回測驗證

### Phase 3: PSV5_Hybrid 決策 (1 天)
1. 快速 hyperopt 測試
2. 若無改善則淘汰
3. 尋找替代策略

## 預期結果
- ElliotV5: +6.89% → +15%
- BB_RPB_TSL_BI: -4.50% → +5%
- PSV5_Hybrid: -17.07% → -5% 或淘汰

## 總合預期
- 綜合獲利: +15% to +20%
- 勝率: > 60%
- Sharpe: > 1.5
