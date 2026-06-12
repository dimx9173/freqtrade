# 剝頭皮策略變體設計文件

## 專案資訊
- **作者**：Brian (Speculari)
- **日期**：2026-04-27
- **目標**：設計適應空頭市場的剝頭皮策略變體
- **交易工具**：合約（多空雙向）
- **槓桿**：5x
- **交易對**：Top 5 幣種
- **最小時間框架**：1m

---

## 背景問題

原始策略（均值回歸 + EMA 濾網）在空頭市場出現：
- **0 筆交易**（EMA 濾網過濾掉所有機會）
- **15m 時間框架更慘**（-93.32%）

核心問題：**趨勢濾網在空頭市場會過濾掉所有進場機會**

---

## 變體 A：BinHV45-Contract

### 設計理念
基於 freqtrade 官方 BinHV45 策略，移除所有趨勢方向限制，增加空頭進場，專為合約多空雙向設計。

### 核心邏輯
- **無趨勢濾網**：不依賴 EMA 方向或趨勢確認
- **純 BB 觸及**：價格觸及 Bollinger Bands 極端即進場
- **多空對稱**：多頭觸及下軌，空頭觸及上軌

### 進場條件

#### 多頭進場（Long Entry）
```python
(
    dataframe['lower'].shift().gt(0) &
    dataframe['bbdelta'].gt(dataframe['close'] * buy_bbdelta / 1000) &
    dataframe['closedelta'].gt(dataframe['close'] * buy_closedelta / 1000) &
    dataframe['tail'].lt(dataframe['bbdelta'] * buy_tail / 1000) &
    dataframe['close'].lt(dataframe['lower'].shift()) &
    dataframe['close'].le(dataframe['close'].shift())
)
```

#### 空頭進場（Short Entry）
```python
(
    dataframe['upper'].shift().gt(0) &
    dataframe['bbdelta'].gt(dataframe['close'] * buy_bbdelta / 1000) &
    dataframe['closedelta'].gt(dataframe['close'] * buy_closedelta / 1000) &
    dataframe['tail'].lt(dataframe['bbdelta'] * buy_tail / 1000) &
    dataframe['close'].gt(dataframe['upper'].shift()) &
    dataframe['close'].ge(dataframe['close'].shift())
)
```

### 指標計算
```python
# Bollinger Bands (40期, 2標準差)
bollinger = qtpylib.bollinger_bands(dataframe['close'], window=40, stds=2)
dataframe['upper'] = bollinger['upper']
dataframe['mid'] = bollinger['mid']
dataframe['lower'] = bollinger['lower']

# BB Delta (帶寬)
dataframe['bbdelta'] = (dataframe['mid'] - dataframe['lower']).abs()

# Price Delta (價格變動)
dataframe['pricedelta'] = (dataframe['open'] - dataframe['close']).abs()

# Close Delta (收盤變動)
dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()

# Tail (下影線)
dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs()
```

### 參數設置
```python
# Hyperopt 參數
buy_bbdelta = IntParameter(low=1, high=15, default=7, space='buy')
buy_closedelta = IntParameter(low=15, high=20, default=17, space='buy')
buy_tail = IntParameter(low=20, high=30, default=25, space='buy')

# 固定參數
minimal_roi = {"0": 0.0125}  # 1.25%
stoploss = -0.05  # 5% 止損（5x槓桿 = 25% 本金）
timeframe = '1m'
```

### 風險管理
- **止損**：固定 5%（考慮 5x 槓桿，實際本金風險 25%）
- **ROI**：1.25% 即出場（剝頭皮邏輯）
- **無 trailing stop**：純 ROI 出場

---

## 變體 B：Modified-EMA-Scalp

### 設計理念
基於 Brian 原始策略，將 EMA 趨勢方向條件改為 ADX 趨勢強度條件，保留 BB + RSI 進場邏輯，增加空頭進場。

### 核心邏輯
- **ADX 替代 EMA**：不管趨勢方向，只要有足夠趨勢強度即可
- **保留 RSI 過濾**：避免極端超買/超賣
- **BB 觸及確認**：價格觸及極端軌道

### 進場條件

#### 多頭進場（Long Entry）
```python
(
    (dataframe['close'] < dataframe['bb_lowerband']) &
    (dataframe['rsi'] < 30) &
    (dataframe['adx'] > 20) &  # 只要有趨勢強度，不管方向
    (dataframe['volume'] > 0)
)
```

#### 空頭進場（Short Entry）
```python
(
    (dataframe['close'] > dataframe['bb_upperband']) &
    (dataframe['rsi'] > 70) &
    (dataframe['adx'] > 20) &  # 只要有趨勢強度，不管方向
    (dataframe['volume'] > 0)
)
```

### 指標計算
```python
# Bollinger Bands (20期, 2標準差)
bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
dataframe['bb_lowerband'] = bollinger['lower']
dataframe['bb_middleband'] = bollinger['mid']
dataframe['bb_upperband'] = bollinger['upper']

# RSI (14期)
dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

# ADX (14期)
dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
```

### 參數設置
```python
minimal_roi = {
    "0": 0.02,    # 2%
    "30": 0.01,   # 1% after 30 min
}
stoploss = -0.03  # 3% 止損（5x槓桿 = 15% 本金）
timeframe = '5m'
```

### 風險管理
- **止損**：3%（考慮 5x 槓桿，實際本金風險 15%）
- **ROI 分層**：2% 立即出場，1% 30分鐘後
- **ADX 過濾**：避免無趨勢市場的雜訊交易

---

## 變體 D：BiDirectional-BB-Scalp

### 設計理念
純 Bollinger Bands 均值回歸策略，完全對稱的多空雙向設計，動態止損基於 ATR。

### 核心邏輯
- **純 BB 策略**：不依賴任何趨勢指標
- **RSI 確認**：避免在極端趨勢中逆勢
- **ATR 動態止損**：根據波動率調整止損距離

### 進場條件

#### 多頭進場（Long Entry）
```python
(
    (dataframe['close'] < dataframe['bb_lowerband'] * 0.99) &  # 觸及下軌下方 1%
    (dataframe['rsi'] < 35) &  # 超賣
    (dataframe['volume'] > dataframe['volume'].rolling(20).mean())  # 放量
)
```

#### 空頭進場（Short Entry）
```python
(
    (dataframe['close'] > dataframe['bb_upperband'] * 1.01) &  # 觸及上軌上方 1%
    (dataframe['rsi'] > 65) &  # 超買
    (dataframe['volume'] > dataframe['volume'].rolling(20).mean())  # 放量
)
```

### 指標計算
```python
# Bollinger Bands (20期, 2標準差)
bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
dataframe['bb_lowerband'] = bollinger['lower']
dataframe['bb_middleband'] = bollinger['mid']
dataframe['bb_upperband'] = bollinger['upper']

# RSI (14期)
dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

# ATR (14期)
dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

# Volume MA
dataframe['volume_ma'] = dataframe['volume'].rolling(window=20).mean()
```

### 動態止損
```python
# 基於 ATR 的動態止損
def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
    dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    last_candle = dataframe.iloc[-1].squeeze()
    
    # 動態止損 = 2x ATR
    stoploss_distance = last_candle['atr'] * 2 / last_candle['close']
    return stoploss_distance
```

### 參數設置
```python
minimal_roi = {
    "0": 0.03,    # 3%
    "60": 0.02,   # 2% after 60 min
    "120": 0.01,  # 1% after 120 min
}
stoploss = -0.05  # 5% 最大止損（5x槓桿 = 25% 本金）
timeframe = '5m'
```

### 風險管理
- **動態止損**：2x ATR，根據波動率自動調整
- **ROI 分層**：3% / 2% / 1% 遞減
- **放量確認**：Volume > 20期均量，避免假突破

---

## 通用配置

### Freqtrade 合約配置
```json
{
  "trading_mode": "futures",
  "margin_mode": "isolated",
  "stoploss": -0.05,
  "max_open_trades": 10,
  "stake_amount": "unlimited",
  "stake_currency": "USDT",
  "dry_run_wallet": 1000,
  "cancel_open_orders_on_exit": true,
  "unfilledtimeout": {
    "entry": 10,
    "exit": 10
  }
}
```

### 槓桿配置
```python
# 在策略中設置槓桿
def leverage(self, pair: str, current_time: datetime, current_rate: float,
             proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
             side: str, **kwargs) -> float:
    return 5.0  # 固定 5x 槓桿
```

### 交易對配置
```python
# Top 5 幣種
pair_whitelist = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT"
]
```

---

## 回測計劃

### 回測參數
```
時間範圍：2024-01-01 至 2026-04-27（包含空頭市場）
時間框架：1m / 5m
交易對：Top 5 幣種
槓桿：5x
本金：1000 USDT
手續費：0.05%（合約 taker fee）
```

### 評估指標
1. **總利潤**（%）
2. **勝率**（%）
3. **最大回撤**（%）
4. **夏普比率**
5. **交易次數**
6. **平均持倉時間**
7. **連續虧損次數**

### 比較基準
- 原始策略（均值回歸 + EMA 濾網）
- 買入持有（Buy & Hold）
- 各變體之間的比較

---

## 風險提示

### 空頭市場特殊風險
1. **均值回歸策略在空頭市場勝率下降**：價格可能持續下跌，不回歸
2. **連續止損風險**：空頭市場波動大，可能連續觸發止損
3. **資金費率風險**：合約持倉可能產生資金費率成本

### 建議風險管理措施
1. **縮小倉位**：建議使用 1-2% 風險 per trade
2. **嚴格止損**：1-2% 止損（考慮 5x 槓桿）
3. **暫停機制**：連續 5 筆虧損後暫停 1 小時
4. **每日虧損上限**：日虧損達 10% 當日停止交易

---

## 實作計劃

### Phase 1：基礎實作
1. [ ] 實作變體 A（BinHV45-Contract）
2. [ ] 實作變體 B（Modified-EMA-Scalp）
3. [ ] 實作變體 D（BiDirectional-BB-Scalp）

### Phase 2：回測驗證
1. [ ] 執行 12 個月回測
2. [ ] 分析各變體表現
3. [ ] 比較空頭市場適應性

### Phase 3：優化迭代
1. [ ] Hyperopt 參數優化
2. [ ] 市場狀態識別整合
3. [ ] 動態策略切換

---

## 參考資料

1. Freqtrade 官方策略庫：https://github.com/freqtrade/freqtrade-strategies
2. BinHV45 原始策略：berlinguyinca/BinHV45.py
3. Market Regime Detection：Judy AI Lab, NexusFi Academy
4. Volatility Regime Detection：Volatility Box Research
