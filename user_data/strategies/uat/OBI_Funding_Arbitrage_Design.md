# Order Book Imbalance + Funding Rate Arbitrage Strategy
## Strategy Design Document v1.0

---

## 1. Core Concept

### 1.1 Market Microstructure Theory

**Order Book Imbalance (OBI)** 是衡量市場買賣壓力的核心指標：
- `OBI = (Bid_Volume - Ask_Volume) / (Bid_Volume + Ask_Volume)`
- 範圍：-1 (完全賣壓) 到 +1 (完全買壓)
- 假設：Order Book 反映真實供需，失衡預示價格移動方向

**資金費率 (Funding Rate)** 是交易所平衡多空倉位的機制：
- 正資金費率 → 多頭支付空頭 → 市場偏多情緒
- 負資金費率 → 空頭支付多頭 → 市場偏空情緒
- 資金費率有均值回歸特性，可預測短期方向

### 1.2 策略邏輯

```
策略核心：利用「短期 Order Book 失衡 + 資金費率方向」做均值回歸

假設：
1. Order Book 失衡不會永遠持續
2. 資金費率偏離均值後會回歸
3. 兩者共振 = 高概率反轉點
```

---

## 2. 可行性分析

### 2.1 Freqtrade 回測限制

| 限制項目 | 說明 | 影響 |
|---------|------|------|
| 無法取得實時 Order Book | Freqtrade 只提供 OHLCV 數據 | 需用替代指標 |
| 無法模擬撮合引擎 | 無法計算掛單簿深度 | 需用成交量 proxy |
| 資金費率更新頻率 | 通常 8 小時一次 | 只能作為濾網，不能作為進場觸發 |

### 2.2 替代指標方案

**替代 Order Book Imbalance 的指標：**

| 指標 | 計算方式 | 優點 | 缺點 |
|------|---------|------|------|
| **Volume Delta** | 成交量的主動買方 - 主動賣方 | 可從 OHLCV 推估 | 需 tick 數據或細粒度數據 |
| **Trend Pressure Index (TPI)** | `(close - open) / (high - low)` 的標準化 | 簡單可用 | 只能反映價格移動方向 |
| **VWAP Deviation** | 價格偏離 VWAP 的程度 | 反映公允價值 | 需額外計算 |
| **Volume Profile Imbalance** | 成交量的價格分佈集中度 | 反映支撐/阻力 | 需自定義計算 |
| **Bid-Ask Volume Proxy** | 用 `(close-low) / (high-low)` 推估買賣壓 | 可從 OHLCV 計算 | 準確度較低 |

### 2.3 推薦替代方案

**首選：Volume Delta + Trend Pressure Index 組合**

```
Volume Delta (VD) = 
  if close > open: +volume
  elif close < open: -volume
  else: 0

VD_SMA = SMA(VD, period=20)
VD_Std = StdDev(VD, period=20)
VD_ZScore = (VD - VD_SMA) / VD_Std

# Z-score > 0 表示買壓 dominant
# Z-score < 0 表示賣壓 dominant
```

**Trend Pressure Index (TPI) =**
```
TPI = (close - open) / (high - low + epsilon)
範圍：-1 到 +1
> 0.7 = 極強買盤
< -0.7 = 極強賣盤
```

---

## 3. 進場邏輯

### 3.1 Long Entry 條件

```
進場時間框架：1分鐘或5分鐘（極短持倉）
槓桿：3-5x
目標盈利：0.3-0.8%

必須滿足 ALL條件：

[Order Book Proxy 條件]
1. TPI < -0.7 (極強賣壓，即將反轉)
2. VD_ZScore < -1.5 (成交量偏空)
3. 價格貼近近期低點 (bb_position < 0.15)

[資金費率濾網]
4. funding_rate > 0 (偏多市場，多頭有保護)
5. funding_rate 在歷史分位数 > 30% (避免在資金費率極端負值進場)

[價格壓縮確認]
6. ATR < 過去20日ATR的50%分位 (波動率壓縮)
7. 最近3根K線範圍 < 過去10根K線平均範圍的60%

[時機觸發]
8. 價格刺穿近期支撐後快速收回 (假突破)
9. TPI 在連續3根K線內由負轉正
```

### 3.2 Short Entry 條件

```
Short Entry：Long 的鏡像

1. TPI > +0.7 (極強買壓，即將反轉)
2. VD_ZScore > +1.5 (成交量偏多)
3. 價格貼近近期高點 (bb_position > 0.85)
4. funding_rate < 0 (偏空市場，空頭有保護)
5. funding_rate 在歷史分位数 < 70%
6. ATR < 過去20日ATR的50%分位
7. 最近3根K線範圍 < 過去10根K線平均範圍的60%
8. 價格突破近期阻力後快速回落 (假突破)
9. TPI 在連續3根K線內由正轉負
```

### 3.3 進場時機範例

```
Long 進場時機：
┌─────────────────────────────────────┐
│  假設：TPI=-0.8, VD_ZScore=-1.8      │
│  funding_rate=0.01% (正，多頭保護)   │
│  價格在 BB Lower 附近                │
│  波動率收縮                          │
│  → 進場做多，目標 0.5%               │
└─────────────────────────────────────┘
```

---

## 4. 出場邏輯

### 4.1 Exit Conditions

```
持倉時間：1-3分鐘（硬性上限）

[LONG Exit]
1. 時間止損：持倉 > 180秒 (3分鐘) → 強制退出
2. 盈利目標：profit >= 0.5% → 部分止盈
3. TPI 回歸：TPI > +0.3 (賣壓消失) → 平倉
4. VD_ZScore 回正：VD_ZScore > 0 → 平倉
5. 止損：profit <= -0.4% → 止損

[SHORT Exit]
1. 時間止損：持倉 > 180秒 → 強制退出
2. 盈利目標：profit >= 0.5% → 部分止盈
3. TPI 回歸：TPI < -0.3 (買壓消失) → 平倉
4. VD_ZScore 回負：VD_ZScore < 0 → 平倉
5. 止損：profit <= -0.4% → 止損
```

### 4.2 Trailing Stop 機制

```
Trailing Stop (for 5min timeframe):
- 激活條件：profit >= 0.3%
- 移動距離：0.2%
- 只允許盈利方向移動

Example:
Entry: 100.0
After 1min: 100.4 (0.4% profit) → trailing 激活，stop = 100.1
Price moves to 100.6 → stop 移動到 100.3
Price retraces to 100.3 → 被踢出，profit = 0.3%
```

---

## 5. 風險管理

### 5.1 風險參數

```
每筆交易風險：帳戶的 0.5-1%
每日最大虧損：帳戶的 2%
最大同倉交易數：2筆
交易間隔：同一交易對 60秒冷卻

止損設定：
- Long: entry - 0.4%
- Short: entry + 0.4%
- 緊急止損: -0.6% (觸發後立即平倉)
```

### 5.2 每日虧損上限邏輯

```python
class DailyLossCircuitBreaker:
    def __init__(self, max_daily_loss=0.02):
        self.max_daily_loss = max_daily_loss
        self.daily_pnl = 0.0
        self.last_reset = datetime.date.today()
    
    def check(self, current_pnl):
        today = datetime.date.today()
        if today != self.last_reset:
            self.daily_pnl = 0.0
            self.last_reset = today
        
        self.daily_pnl = current_pnl
        
        if self.daily_pnl <= -self.max_daily_loss:
            # 觸發每日虧損上限，停止所有交易
            return False  # 阻止新交易
        return True
```

### 5.3 資金費率風險

```
資金費率並非進場觸發信號，僅作為市場環境濾網：
- 正資金費率 > 0.05%：市場偏多，避免做空
- 負資金費率 < -0.05%：市場偏空，避免做多
- 資金費率接近 0：中性市場，兩邊都可操作
```

---

## 6. 指標計算詳細說明

### 6.1 Trend Pressure Index (TPI)

```python
def calculate_tpi(dataframe, period=1):
    """
    TPI = (close - open) / (high - low)
    衡量價格移動的方向和力度
    
    範圍：-1 到 +1
    """
    range_ = dataframe['high'] - dataframe['low']
    range_ = range_.replace(0, np.nan)  # 避免除零
    
    tpi = (dataframe['close'] - dataframe['open']) / range_
    return tpi

# 使用：
# TPI > 0.7  = 極強買盤
# TPI < -0.7 = 極強賣盤
```

### 6.2 Volume Delta (VD)

```python
def calculate_volume_delta(dataframe):
    """
    Volume Delta 推算主動買賣方向
    
    上漲時的成交量視為買方成交量
    下跌時的成交量視為賣方成交量
    """
    delta = np.where(
        dataframe['close'] > dataframe['open'],
        dataframe['volume'],      # 漲 = 買盤
        -dataframe['volume']      # 跌 = 賣盤
    )
    # 十字星 = 0
    delta = np.where(
        dataframe['close'] == dataframe['open'],
        0,
        delta
    )
    return delta

def calculate_vd_zscore(dataframe, period=20):
    """計算 Volume Delta 的 Z-Score"""
    delta = calculate_volume_delta(dataframe)
    sma = delta.rolling(period).mean()
    std = delta.rolling(period).std()
    zscore = (delta - sma) / std.replace(0, np.nan)
    return zscore
```

### 6.3 波動率壓縮識別

```python
def calculate_compression_ratio(dataframe, lookback_short=3, lookback_long=10):
    """
    識別價格波動率收縮
    compression_ratio < 0.6 表示波動率壓縮，可能突破
    """
    short_range = dataframe['high'].rolling(lookback_short).max() - \
                   dataframe['low'].rolling(lookback_short).min()
    long_range = dataframe['high'].rolling(lookback_long).max() - \
                 dataframe['low'].rolling(lookback_long).min()
    
    compression = short_range / long_range.replace(0, np.nan)
    return compression

# 使用：
# compression < 0.6 且 TPI 極端 → 進場信號
```

---

## 7. 策略實現架構

### 7.1 偽代碼結構

```python
class OBI_Funding_Arbitrage(IStrategy):
    # ========== 參數 ==========
    timeframe = "1m"  # 1分鐘（極短持倉）
    leverage = 5
    
    stoploss = -0.004  # -0.4%
    max_holding_seconds = 180  # 3分鐘
    
    # TPI 參數
    tpi_long_threshold = -0.7
    tpi_short_threshold = 0.7
    tpi_entry_confirm = 0.3
    
    # Volume Delta 參數
    vd_zscore_threshold = 1.5
    
    # 波動率參數
    compression_threshold = 0.6
    
    # 風險參數
    max_daily_loss = 0.02
    max_open_trades = 2
    
    # ========== 指標計算 ==========
    def populate_indicators(self, dataframe, metadata):
        # TPI
        dataframe['tpi'] = calculate_tpi(dataframe)
        
        # Volume Delta Z-Score
        dataframe['vd_zscore'] = calculate_vd_zscore(dataframe)
        
        # 波動率壓縮
        dataframe['compression'] = calculate_compression_ratio(dataframe)
        
        # 資金費率（從外部加載）
        # funding_rate = self.get_funding_rate(metadata['pair'])
        # dataframe['funding_rate'] = funding_rate
        
        # BB 用於識別高低位置
        bbands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_position'] = (dataframe['close'] - bbands['lowerband']) / \
                                   (bbands['upperband'] - bbands['lowerband'])
        
        return dataframe
    
    # ========== 進場信號 ==========
    def populate_entry_trend(self, dataframe, metadata):
        # LONG: 賣壓極致 + 即將反轉
        long_signal = (
            (dataframe['tpi'] < self.tpi_long_threshold) &   # 極強賣壓
            (dataframe['bb_position'] < 0.15) &               # 價格低位
            (dataframe['vd_zscore'] < -self.vd_zscore_threshold) &  # 成交確認
            (dataframe['compression'] < self.compression_threshold)  # 波動率壓縮
        )
        
        # SHORT: 買壓極致 + 即將反轉
        short_signal = (
            (dataframe['tpi'] > self.tpi_short_threshold) &  # 極強買壓
            (dataframe['bb_position'] > 0.85) &              # 價格高位
            (dataframe['vd_zscore'] > self.vd_zscore_threshold) &   # 成交確認
            (dataframe['compression'] < self.compression_threshold)  # 波動率壓縮
        )
        
        dataframe['enter_long'] = long_signal.astype(int)
        dataframe['enter_short'] = short_signal.astype(int)
        
        return dataframe
    
    # ========== 出場信號 ==========
    def custom_exit(self, pair, trade, current_time, current_rate, 
                    current_profit, **kwargs):
        # 時間止損
        if trade and hasattr(trade, 'open_date'):
            holding = (current_time - trade.open_date).total_seconds()
            if holding >= self.max_holding_seconds:
                return "time_exit"
        
        # TPI 回歸
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is not None and len(dataframe) > 0:
            current_tpi = dataframe['tpi'].iloc[-1]
            
            if trade.enter_side == 'long' and current_tpi > self.tpi_entry_confirm:
                return "tpi_reversal"
            if trade.enter_side == 'short' and current_tpi < -self.tpi_entry_confirm:
                return "tpi_reversal"
        
        return None
```

---

## 8. 回測替代方案

### 8.1 Freqtrade 無法模擬的項目

| 無法模擬 | 替代方案 |
|---------|---------|
| 實時 Order Book | 用 TPI + Volume Delta Z-Score |
| 掛單簿深度 | 用 BB Position 替代 |
| 撮合延遲 | 用較寬止損 (0.4%) 吸收 |
| 滑點 | 加入 0.1% 滑點假設 |

### 8.2 回測注意事項

```
1. 資金費率數據頻率
   - 資金費率每8小時更新一次
   - 回測時假設在兩個資金結算之間的方向不變
   - 用前一個結算週期的資金費率

2. 進場時機
   - 回測假設信號產生的下一根K線開盤進場
   - 實際可能需要等K線收盤確認

3. 交易成本
   - Maker fee: ~0.02%
   - Taker fee: ~0.05%
   - 進出场各算一次
```

### 8.3 建議的回測配置

```python
# 回測配置
backtest:
  start_date: "2024-01-01"
  end_date: "2026-04-01"
  timeframe: "1m"
  max_open_trades: 2
  stake_amount: 1000
  fee_maker: 0.0002
  fee_taker: 0.0005
  slippage: 0.001  # 0.1% 滑點
```

---

## 9. 預期績效

### 9.1 理論月化收益

```
假設：
- 勝率：55-60%
- 平均盈利：0.4%
- 平均虧損：0.35%
- 每日交易次數：4-6筆（1分鐘K線）

月化計算：
- 交易天數：22天
- 日均交易：5筆
- 月總交易：110筆
- 預期勝率：55%
- 月盈餘交易：60.5筆
- 月虧損交易：49.5筆

月化 = (60.5 * 0.4% - 49.5 * 0.35%) / 2 (槓桿) 
     ≈ (24.2% - 17.3%) / 2 
     ≈ 3.45% (5x槓桿)
```

### 9.2 風險提示

```
⚠️ 本策略為高頻均值回歸策略：
1. 適合盤整市場，趨勢市場可能虧損
2. 需要穩定的低延遲交易所連接
3. 滑點和費用會顯著影響績效
4. 過去績效不代表未來表現
```

---

## 10. 實盤部署檢查清單

### 10.1 上線前必須確認

- [ ] 交易所有提供 1m 級別的 OHLCV 數據
- [ ] 資金費率數據可以實時獲取
- [ ] 網路延遲 < 100ms
- [ ] 交易費用 < 0.05%
- [ ] 槓桿設定正確（3-5x）
- [ ] 每日虧損上限邏輯已實現
- [ ] 止損訂單已掛好
- [ ] 監控系統已設定

### 10.2 監控指標

```
1. 訂單成交率 > 95%
2. 平均滑點 < 0.1%
3. 每日交易次數在預期範圍
4. 資金費率異常時報警
```

---

## 11. 版本歷史

| 版本 | 日期 | 說明 |
|-----|------|------|
| 1.0 | 2026-04-26 | 初始版本 |

---

## 12. 參考文獻

1. Order Book Imbalance - CMU CS Paper
2. Market Making and Mean Reversion - OPTIMIZATION OF TRADING STRATEGIES
3. Funding Rate Arbitrage - Binance Futures Education
4. Volume Weighted Average Price (VWAP) - Technical Analysis
