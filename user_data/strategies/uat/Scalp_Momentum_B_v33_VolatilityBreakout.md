# Scalp_Momentum_B_v33 - Volatility Breakout Strategy
====================================================

## 1. 策略概念與核心理念

**核心理念放棄**: 均值回歸 (v32) / 順勢 EMA (v28)
**新方向**: 波動率突破 → 趨勢跟隨

### 為什麼做這個改變？
- v28 (EMA+RSI順勢): 牛市 +1.83%，熊市 -3.77% → 牛市有效，熊市失效
- v32 (BB均值回歸): 5m版本 -1.16% → 均值回歸在現有市場失效
- **洞察**: 突破比EMA信號更及時，趨勢跟隨在牛熊市場都能運作
- **目標**: 月化 5%，熊市也能運作

---

## 2. 指標計算

### 2.1 Donchian Channel（價格通道）
```python
# N 期最高價 / 低價
donchian_high = dataframe['high'].rolling(window=self.donchian_period).max()
donchian_low  = dataframe['low'].rolling(window=self.donchian_period).min()
donchian_mid  = (donchian_high + donchian_low) / 2
```

### 2.2 Keltner Channel（ATR通道）
```python
# 中軌 = EMA
keltner_mid = ta.EMA(dataframe, timeperiod=self.keltner_ema_period)
# 上下軌 = 中軌 ± ATR * 倍數
keltner_upper = keltner_mid + (dataframe['atr'] * self.keltner_multiplier)
keltner_lower = keltner_mid - (dataframe['atr'] * self.keltner_multiplier)
```

### 2.3 ATR（平均真實波幅）
```python
dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)
dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']  # ATR 百分比
```

### 2.4 波動率確認指標
```python
# 近期 ATR 均線（判斷波動率是否擴張）
dataframe['atr_sma'] = dataframe['atr'].rolling(window=10).mean()
dataframe['atr_expansion'] = dataframe['atr'] > dataframe['atr_sma']  # 波動擴張

# 布林帶寬度（另一種波動率度量）
bb_upper, bb_middle, bb_lower = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
dataframe['bb_width'] = (bb_upper - bb_lower) / bb_middle
```

### 2.5 成交量指標
```python
dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
```

---

## 3. 進場邏輯

### 3.1 多頭進場（Long Entry）
**觸發條件**（全部滿足）：
1. **價格突破**: `close > donchian_high`（突破 N 期高點）
2. **波動確認**: `atr_expansion == True`（ATR高於均線，波動正在擴張）
3. **成交量確認**: `volume_ratio >= 1.5`（成交量 > 1.5x 均量）
4. **不是在盤整**: `bb_width > 0.05`（布林帶寬度 > 5%，市場有趨勢）

### 3.2 空頭進場（Short Entry）
**觸發條件**（全部滿足）：
1. **價格突破**: `close < donchian_low`（突破 N 期低點）
2. **波動確認**: `atr_expansion == True`
3. **成交量確認**: `volume_ratio >= 1.5`
4. **不是在盤整**: `bb_width > 0.05`

### 3.3 進場濾鏡（Filters）
```python
# ATR 太大或太小都不交易（避開極端波動）
cond_atr_range = (dataframe['atr_pct'] >= 0.003) & (dataframe['atr_pct'] <= 0.015)

# 價差過大不交易（滑價保護）
spread = (dataframe['high'] - dataframe['low']) / dataframe['close']
cond_spread = spread < 0.008

# 冷卻時間（同一標的 60 秒內不重複進場）
```

---

## 4. 出場邏輯

### 4.1 追蹤止損（Trailing Stop ATR-Based）
```python
# ATR 倍數作為止損距離
trail_dist = dataframe['atr'] * self.trail_multiplier  # e.g., 2.0 ATR

# 進場後高点更新
dataframe['trail_high'] = dataframe['high'].cummax()  # 做多用 high
dataframe['trail_low']  = dataframe['low'].cummin()   # 做空用 low

# 當前 profit = (current - entry) / entry
# 止損觸發：profit < -trail_dist_pct
```

### 4.2 反向突破止損
```python
# 做多時：價格跌破 Donchian 中軌 → 止損
# 做空時：價格漲過 Donchian 中軌 → 止損
cond_reverse_long  = close < donchian_mid   # 多頭止損
cond_reverse_short = close > donchian_mid   # 空頭止損
```

### 4.3 時間退出（可選，防止長期持有）
```python
# 最大持有時間 15 分鐘（5m 圖 3 根K線）
max_holding_seconds = 900
```

---

## 5. 參數建議

### 5.1 主要參數
| 參數 | 建議值 | 說明 |
|------|--------|------|
| `donchian_period` | 12（5m）/ 8（15m） | 突破週期 |
| `atr_period` | 14 | ATR 計算週期 |
| `keltner_ema_period` | 20 | Keltner 中軌 EMA |
| `keltner_multiplier` | 2.0 | Keltner 通道寬度 |
| `trail_multiplier` | 2.0 | 止損 ATR 倍數 |
| `volume_ratio_min` | 1.5 | 成交量倍數門檻 |
| `bb_width_min` | 0.05 | 波動率最低門檻 |

### 5.2 時間框架建議
- **5 分鐘**: 適合日內交易，波動較快，donchian_period=12
- **15 分鐘**: 過濾雜訊能力強，donchian_period=8

### 5.3 ROI / Stoploss 建議
```python
stoploss = -0.02                    # -2% 硬止損
minimal_roi = {
    "0": 0.003,    # 即時 0.3%
    "5": 0.006,    # 5 分鐘 0.6%
    "10": 0.010,   # 10 分鐘 1.0%
    "15": 0.015,   # 15 分鐘 1.5%
}
trailing_stop_positive = 0.004      # +0.4% 後啟動
trailing_stop_offset = 0.006         # 回調 0.6% 觸發
```

---

## 6. 與 v28 的差異分析

| 維度 | v28 | v33（新品） |
|------|-----|-------------|
| **核心理念** | EMA 順勢 + RSI 拉回 | 波動率突破 |
| **進場觸發** | EMA 多頭排列 + RSI 回調 | 價格突破 N 期高/低點 |
| **進場時機** | 等拉回（吉爾丁漢逆勢） | 突破當下（追趨勢） |
| **RSI 角色** | 進場過濾（35-72） | 無 |
| **布林帶** | 無 | 波動率確認 |
| **趨勢判斷** | EMA 多空排列 | Donchian 通道突破 |
| **多空對稱** | 只做多 | 雙向（突破高做多，突破低做空）|
| **止損類型** | 固定 -2% | ATR 追蹤止損 |
| **波動過濾** | ATR < 1% | ATR expansion + BB width |

### 關鍵差異解釋

**1. 為什麼不用 EMA？**
- EMA 是落後指標，價格已經走了很遠才出現信號
- 突破信號比 EMA 交叉更及時

**2. 為什麼加入 BB width 過濾？**
- 盤整時突破信號過多，會產生假信號
- BB width > 5% 表示市場有明確趨勢

**3. 為什麼雙向交易？**
- v28 只做多，牛市有效但熊市失效
- 熊市也能做空，增加盈利機會

**4. ATR 追蹤止損的優點？**
- 適應市場波動環境
- 大波動時放寬止損，小波動時收紧止損

---

## 7. 策略代碼結構

```python
class Scalp_Momentum_B_v33(IStrategy):
    
    # ========== 核心參數 ==========
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.004
    trailing_stop_positive_offset = 0.006
    trailing_only_offset_is_reached = True
    leverage = 5
    timeframe = "5m"
    
    # ========== 波動率突破參數 ==========
    donchian_period = 12      # 12 期高/低點突破
    atr_period = 14
    keltner_ema_period = 20
    keltner_multiplier = 2.0
    trail_multiplier = 2.0    # 止損 ATR 倍數
    volume_ratio_min = 1.5
    bb_width_min = 0.05
    max_atr_pct = 0.015       # ATR 上限
    min_atr_pct = 0.003       # ATR 下限
    max_spread_pct = 0.008
    
    # ========== Indicators ==========
    def populate_indicators(self, dataframe, metadata):
        # Donchian Channel
        dataframe['dc_high'] = dataframe['high'].rolling(self.donchian_period).max()
        dataframe['dc_low']  = dataframe['low'].rolling(self.donchian_period).min()
        dataframe['dc_mid'] = (dataframe['dc_high'] + dataframe['dc_low']) / 2
        
        # Keltner Channel
        dataframe['keltner_ema'] = ta.EMA(dataframe, timeperiod=self.keltner_ema_period)
        dataframe['keltner_upper'] = dataframe['keltner_ema'] + dataframe['atr'] * self.keltner_multiplier
        dataframe['keltner_lower'] = dataframe['keltner_ema'] - dataframe['atr'] * self.keltner_multiplier
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        dataframe['atr_sma'] = dataframe['atr'].rolling(10).mean()
        dataframe['atr_expansion'] = dataframe['atr'] > dataframe['atr_sma']
        
        # Bollinger Bands width (volatility filter)
        bb_upper, bb_middle, bb_lower = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_width'] = (bb_upper - bb_lower) / bb_middle
        
        # Volume
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # Spread
        dataframe['spread'] = (dataframe['high'] - dataframe['low']) / dataframe['close']
        
        return dataframe
    
    # ========== Entry ==========
    def populate_entry_trend(self, dataframe, metadata):
        # Filters
        cond_atr_range = (dataframe['atr_pct'] >= self.min_atr_pct) & (dataframe['atr_pct'] <= self.max_atr_pct)
        cond_spread = dataframe['spread'] < self.max_spread_pct
        cond_volatility = dataframe['bb_width'] > self.bb_width_min
        cond_vol_expansion = dataframe['atr_expansion'] == True
        cond_volume = dataframe['volume_ratio'] >= self.volume_ratio_min
        
        # Long: Price breaks above Donchian high + all filters
        cond_breakout_up = dataframe['close'] > dataframe['dc_high']
        dataframe['enter_long'] = (
            cond_breakout_up &
            cond_atr_range &
            cond_spread &
            cond_volatility &
            cond_vol_expansion &
            cond_volume
        ).astype(int)
        
        # Short: Price breaks below Donchian low + all filters
        cond_breakout_down = dataframe['close'] < dataframe['dc_low']
        dataframe['enter_short'] = (
            cond_breakout_down &
            cond_atr_range &
            cond_spread &
            cond_volatility &
            cond_vol_expansion &
            cond_volume
        ).astype(int)
        
        return dataframe
    
    # ========== Exit ==========
    def populate_exit_trend(self, dataframe, metadata):
        # Reverse breakout exit logic
        cond_reverse_long  = dataframe['close'] < dataframe['dc_mid']
        cond_reverse_short = dataframe['close'] > dataframe['dc_mid']
        
        dataframe['exit_long']  = cond_reverse_long.astype(int)
        dataframe['exit_short'] = cond_reverse_short.astype(int)
        
        return dataframe
```

---

## 8. 風險管理

| 參數 | 值 | 說明 |
|------|------|------|
| `max_open_trades` | 2 | 最多 2 筆同時持倉 |
| `trade_cooldown` | 60 | 同標的 60 秒冷卻 |
| `daily_max_loss` | 1.5% | 單日最大虧損 |
| `max_drawdown` | 2% | 最大回撤斷路器 |
| `confirm_trade_entry_timeout` | 60 | 訂單超時 60 秒 |

---

## 9. 預期表現

### 優點
- **信號及時**: 突破比 EMA 交叉更早
- **雙向交易**: 牛熊市場都能獲利
- **趨勢明確**: 只有高波動時段交易，過濾盤整
- **適應性強**: ATR 止損適應不同波動環境

### 風險
- **假突破**: 突破後很快回落
- **震盪市場**: 即使有 BB 過濾，仍可能受傷
- **滑價**: 突破時點差可能擴大

---

## 10. 下一步行動

1. **Backtest**: 在 5m 和 15m 圖上回測
2. **參數優化**: 調整 donchian_period、ATR 倍數
3. **加入 Keltner 確認**: 價格同時突破 Keltner 上軌
4. **測試其他市場**: BTC、ETH、SOL、XRP
