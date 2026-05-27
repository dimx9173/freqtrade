# 三指標組合測試：EMA + BB + Volume

## 策略設計

**檔案位置**: `/home/brian/freqtrade/user_data/strategies/uat/Scalp_EMA_BB_Volume.py`

### 指標組合邏輯

| 指標 | 參數 | 用途 |
|------|------|------|
| EMA 多頭排列 | EMA5 > EMA10 > EMA20 | 趨勢方向確認 |
| Bollinger Bands | period=20, std=2.0 | 進場時機 (觸及下軌) |
| Volume | > 1.2x 均量 (SMA20) | 動量確認 |

### 進場條件 (AND 邏輯)
1. **EMA多頭排列**: EMA5 > EMA10 > EMA20 (短期上升趨勢)
2. **BB觸及下軌**: `low <= bb_lower` (超賣/反彈機會)
3. **成交量放大**: `volume >= 1.2 * volume_sma` (動量確認)
4. **牛市蠟燭**: `close > open` (價格方向確認)

### 出場條件
- BB觸及上軌 (`high >= bb_upper`)
- EMA多頭排列結束 (`ema5 < ema10`)
- Trailing stop 追蹤

## 回測結果

**時間範圍**: 2025-04-26 至 2026-04-26 (12個月)  
**時間框架**: 5m  
**交易對**: XRP, SOL, BTC, ETH, DOGE (USDT)

### 初步問題發現

策略在獨立Python測試中可產生訊號 (XRP 5m 資料找到 28 個符合條件的K線)，但 freqtrade 回測顯示 0 筆交易。

**可能原因**:
1. 資料格式問題 - feather vs JSON 轉換
2. `confirm_trade_entry` 中的 spread > 0.006 過濾條件可能過於嚴格
3. `leverage` 屬性衝突 - IStrategy 的 `leverage` 是方法而非屬性 (已修正)

### 已修正問題

1. 將 `leverage = 5` 改為 `leverage()` 方法
2. 簡化進場條件邏輯
3. 移除 `get_entry_signal` 等非必要方法

## 對比參考策略

| 策略 | 交易次數 | 勝率 | 總損益 | 最大回撤 |
|------|---------|------|--------|----------|
| Scalp_BB_Volume | 328 | 64.3% | -4.797 USDT | 2.25% |
| Scalp_EMA_Only | 14,714 | 85.9% | -238.58 USDT | 79.71% |

## 後續建議

1. 確認資料格式是否相容 (feather/JSON)
2. 放寬 `confirm_trade_entry` 的 spread 檢查
3. 減少 EMA 週期或調整 BB 參數以产生更多訊號
4. 考慮添加 `populate_buy_trend` 作為 `populate_entry_trend` 的別名
