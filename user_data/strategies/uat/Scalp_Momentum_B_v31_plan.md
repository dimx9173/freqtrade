# Scalp_Momentum_B v31 迭代計畫
## 雙向剝头皮 + 1m/3m 快速進出

---

## 一、版本回測失敗分析 (v28)

| 指標 | 數值 |
|------|------|
| 回測期間 | 6個月 |
| 總交易筆數 | 4103 |
| 勝率 | 87.6% |
| 淨損益 | **-3.77%** |
| 最大回撤 | 9.1% |
| 止損筆數 | **507筆** |
| 市場變化 | -48.39% (熊市) |

### 失敗根因
1. **只做多頭**：熊市環境中逆勢交易，6個月大部分時間趨勢向下
2. **時間框架太慢**：5m框架在快速變化的市場中信號滯後
3. **無空頭對沖**：無法利用下跌趨勢獲利
4. **固定倉位**：507筆止損顯示風險管理不足，無動態調整
5. **無反轉識別**：插針形態未被利用，被當作假突破止損

---

## 二、v31 核心改進架構

### 2.1 時間框架
- **主要**：3m（平衡速度與穩定性）
- **快速模式**：1m（高波動市場專用）
- 動態切換：根據市場波動率自動選擇

### 2.2 雙向交易機制

```
         ┌─────────────────────────────┐
         │      趨勢判斷層              │
         │  EMA_GT_1m / EMA_GT_3m      │
         └──────────┬──────────────────┘
                    │
         ┌──────────▼──────────┐
         │   趨�勢方向          │
         ├──────────┬───────────┤
         │  多頭    │   空頭    │
         │ (long)  │  (short) │
         └──────────┴───────────┘
```

---

## 三、進場邏輯

### 3.1 多頭進場 (Long Entry)

| 條件 | 參數 | 說明 |
|------|------|------|
| 趨勢確認 | EMA_fast > EMA_slow > EMA_trend | 上漲趨勢 |
| 回調深度 | pullback ≥ 0.15% 且 ≤ 0.8% | 逢低買入 |
| RSI 範圍 | 35 ≤ RSI ≤ 65 | 超賣回升 |
| 成交量 | ≥ SMA20 × 0.8 | 有力上漲 |
| K線形態 | 收盤 > 開盤 (陽線) | 看漲確認 |
| 插針形態 | 下影線 ≥ K線長度 60% | 快速反轉信號 |

**進場觸發（多頭）**：
```
cond_trend_long = EMA_fast > EMA_slow > EMA_trend
cond_pullback = 0.0015 ≤ pullback ≤ 0.008
cond_rsi = 35 ≤ RSI ≤ 65
cond_volume = volume ≥ SMA20 × 0.8
cond_bullish = close > open
cond_pinbar = (low - min(open,close)) / (high - low + 0.0001) ≥ 0.6

enter_long = cond_trend_long & cond_pullback & cond_rsi & cond_volume & (cond_bullish OR cond_pinbar)
```

### 3.2 空頭進場 (Short Entry)

| 條件 | 參數 | 說明 |
|------|------|------|
| 趨勢確認 | EMA_fast < EMA_slow < EMA_trend | 下跌趨勢 |
| 反彈高度 | pullback ≥ 0.15% 且 ≤ 0.8% | 反彈做空 |
| RSI 過高 | RSI ≥ 50 (反彈至中部/高部) | 上漲乏力 |
| 成交量 | ≥ SMA20 × 0.8 | 有力下跌 |
| K線形態 | 收盤 < 開盤 (陰線) | 看跌確認 |
| 插針形態 | 上影線 ≥ K線長度 60% | 快速反轉信號 |

**進場觸發（空頭）**：
```
cond_trend_short = EMA_fast < EMA_slow < EMA_trend
cond_pullback_short = 0.0015 ≤ pullback ≤ 0.008  (价格反彈後)
cond_rsi_overbought = RSI ≥ 50  # 反彈後的高位
cond_volume = volume ≥ SMA20 × 0.8
cond_bearish = close < open
cond_pinbar_top = (max(open,close) - high) / (high - low + 0.0001) ≥ 0.6

enter_short = cond_trend_short & cond_pullback_short & cond_rsi_overbought & cond_volume & (cond_bearish OR cond_pinbar_top)
```

---

## 四、插針形態識別 (Pin Bar Detection)

### 4.1 插針定義
```
K線長度 = high - low
上影線長度 = high - max(open, close)
下影線長度 = min(open, close) - low

下影線插針 (Bull Pinbar) = 下影線 / K線長度 ≥ 60%
上影線插針 (Bear Pinbar) = 上影線 / K線長度 ≥ 60%
```

### 4.2 插針強度分級
| 等級 | 影線比例 | 交易置信度 |
|------|----------|------------|
| 強 | ≥ 70% | 高，可直接進場 |
| 中 | 60%~70% | 中，需其他條件確認 |
| 弱 | < 60% | 不採用 |

---

## 五、出場邏輯

### 5.1 多頭出場
- **止盈1**：+0.4% → 50%倉位
- **止盈2**：+0.7% → 30%倉位
- **移動止損**：從+0.4%開始，隨價格上漲追蹤
- **硬止損**：-2%

### 5.2 空頭出場
- **止盈1**：+0.4% → 50%倉位
- **止盈2**：+0.7% → 30%倉位
- **移動止損**：從+0.4%開始，隨價格下跌追蹤
- **硬止損**：-2%

### 5.3 快速止損條件
滿足以下任一條件立即止損：
- 進場後 2根K線內未觸發止盈且RSI背離
- 插針形態失敗（再次插針反方向）
- 突發成交量放大但方向不利

---

## 六、趨勢過濾機制

### 6.1 趨勢判斷
```
         ┌─────────────────────────────────┐
         │     多時間框架 EMA 趨勢          │
         │  1m EMA_fast vs 3m EMA_fast     │
         └─────────────────────────────────┘
         
         明確多頭：1m↑ & 3m↑ → 允許做多
         明確空頭：1m↓ & 3m↓ → 允許做空
         震盪區間：方向矛盾 → 暫停交易
```

### 6.2 震盪區間識別
```python
# 震盪區間條件：兩個方向都能滿足進場條件
cond_choppy = (RSI在40-60來回震盪) AND (無明確方向)
if cond_choppy:
    停止交易，等待突破確認
```

### 6.3 趨勢強度過濾
```
強趨勢：|EMA_fast - EMA_slow| / EMA_slow ≥ 0.5% → 正常交易
弱趨勢：|EMA_fast - EMA_slow| / EMA_slow < 0.5% → 降低倉位50%
震盪：方向不明 → 停止交易
```

---

## 七、動態倉位管理

### 7.1 連續止損追蹤
```python
consecutive_stops = 0  # 全域計數器

def on_trade_stop(trade):
    global consecutive_stops
    consecutive_stops += 1
```

### 7.2 倉位調整規則
| 連續止損次數 | 倉位調整 | 備註 |
|-------------|----------|------|
| 0-2 | 100% (正常) | - |
| 3-4 | 50% | 警告 |
| 5-6 | 25% | 高度警戒 |
| ≥7 | 0% (停止交易) | 需人工審查 |

### 7.3 獲利後重置
```python
# 連續止損計數在以下情況重置
if 單筆交易獲利 > 0.5%:
    consecutive_stops = 0  # 重置
```

---

## 八、風險控制參數建議

### 8.1 核心參數
```python
# 止損
stoploss = -0.02          # -2% 硬止損
trailing_stop = True
trailing_stop_positive = 0.003
trailing_stop_positive_offset = 0.005
trailing_only_offset_is_reached = True

# 倉位
leverage = 3              # 降低槓桿（熊市環境）
max_stake_per_trade = 0.15  # 每筆最多15%資金
max_daily_loss = 0.05     # 單日最大虧損5%停止

# 進場確認
max_spread_pct = 0.003    # 0.3% 最大價差
max_atr_pct = 0.008       # 0.8% 最大ATR波動
```

### 8.2 進場間隔
```python
cooldown = 10  # 最小10根K線間隔
max_trades_per_day = 10  # 單日最多10筆
```

---

## 九、參數對照表

### 9.1 v28 vs v31 參數變化
| 參數 | v28 | v31 | 變化原因 |
|------|-----|-----|----------|
| timeframe | 5m | 1m/3m | 加快信號速度 |
| stoploss | -2% | -2% | 保持 |
| leverage | 5 | 3 | 降低風險 |
| rsi_min | 35 | 35 | 多頭保持 |
| rsi_max | 72 | 65 | 多頭更保守 |
| rsi_short_min | - | 50 | 空頭RSI門檻 |
| volume_mult | 0.75 | 0.8 | 略提高量能要求 |
| pullback_min | 0.15% | 0.15% | 保持 |
| pullback_max | - | 0.8% | 新增上限防假突破 |
| max_stake | - | 15% | 新增單筆限制 |
| max_daily_loss | - | 5% | 新增日虧損限制 |

---

## 十、1m vs 3m 自動切換邏輯

```python
def select_timeframe(self, dataframe) -> str:
    """
    根據市場波動率自動選擇時間框架
    """
    atr_pct = dataframe['atr'].iloc[-1] / dataframe['close'].iloc[-1]
    
    if atr_pct > 0.015:  # 高波動
        return "1m"   # 更快反應
    elif atr_pct > 0.008:  # 中波動
        return "3m"   # 平衡選擇
    else:  # 低波動
        return "3m"  # 穩定市場用3m
```

---

## 十一、回測目標

### 11.1 v31 預期目標
| 指標 | 目標值 | v28對比 |
|------|--------|---------|
| 月化收益率 | ≥5% | - |
| 勝率 | ≥75% | 87.6% (參考) |
| 最大回撤 | ≤5% | 9.1% |
| 日交易筆數 | 3-8筆 | - |
| 月止損筆數 | ≤50筆 | 507/6≈84筆/月 |
| Sharpe Ratio | ≥1.5 | - |

### 11.2 關鍵KPI追蹤
- [ ] 插針形態識別率
- [ ] 空頭交易佔比（目標30-40%）
- [ ] 平均持倉時間
- [ ] 連續止損觸發頻率
- [ ] 動態倉位調整效果

---

## 十二、實施主序

```
Phase 1: 基礎架構
├── 雙向進場邏輯實作
├── 1m/3m時間框架適配
└── 插針形態識別函數

Phase 2: 風險系統
├── 動態倉位管理
├── 趨勢過濾機制
└── 每日虧損限制

Phase 3: 優化
├── 回測參數調優
├── 空頭邏輯單獨測試
└── 1m vs 3m 表現對比

Phase 4: 上線
├── 模擬盤驗證1週
├── 小資金實盤
└── 全量上線
```

---

## 十三、代碼結構預覽

```python
class Scalp_Momentum_B_v31(IStrategy):
    
    # ========================
    # 參數定義
    # ========================
    timeframe_1m = "1m"
    timeframe_3m = "3m"
    
    # 止損
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.005
    
    # 倉位
    leverage = 3
    consecutive_stops = 0
    max_stake_per_trade = 0.15
    max_daily_loss = 0.05
    
    # ========================
    # 核心指標
    # ========================
    def populate_indicators(self, dataframe, metadata):
        # EMA系列
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=5)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_trend'] = ta.EMA(dataframe, timeperiod=20)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=7)
        
        # 成交量
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=10)
        
        # 插針形態
        dataframe['pinbar_ratio'] = self.calc_pinbar(dataframe)
        dataframe['pinbar_type'] = self.detect_pinbar_type(dataframe)
        
        return dataframe
    
    # ========================
    # 進場信號
    # ========================
    def populate_entry_trend(self, dataframe, metadata):
        # 多頭進場
        dataframe['enter_long'] = self.calc_long_signal(dataframe).astype(int)
        
        # 空頭進場
        dataframe['enter_short'] = self.calc_short_signal(dataframe).astype(int)
        
        return dataframe
    
    # ========================
    # 插針形態計算
    # ========================
    def calc_pinbar(self, dataframe):
        body = abs(dataframe['close'] - dataframe['open'])
        upper_wick = dataframe['high'] - dataframe[['open', 'close']].max(axis=1)
        lower_wick = dataframe[['open', 'close']].min(axis=1) - dataframe['low']
        total = dataframe['high'] - dataframe['low']
        
        return np.where(
            total > 0,
            np.maximum(upper_wick, lower_wick) / total,
            0
        )
    
    def detect_pinbar_type(self, dataframe):
        """返回: 1=下影線(多頭信號), 2=上影線(空頭信號), 0=無"""
        body = abs(dataframe['close'] - dataframe['open'])
        upper_wick = dataframe['high'] - dataframe[['open', 'close']].max(axis=1)
        lower_wick = dataframe[['open', 'close']].min(axis=1) - dataframe['low']
        
        return np.where(
            lower_wick > body * 1.2, 1,  # 下影線
            np.where(upper_wick > body * 1.2, 2, 0)  # 上影線
        )
```

---

## 十四、風險預警機制

```python
# 風險預警觸發條件
def check_risk_limits(self, pairs: list) -> bool:
    daily_loss = self.get_daily_loss()
    consecutive_stops = self.get_consecutive_stops()
    
    # 紅色警戒：單日虧損>5% 或 連續止損≥7次
    if daily_loss > 0.05 or consecutive_stops >= 7:
        self.notify("#alert", "⚠️ 風險警戒：停止交易檢查")
        return False
    
    # 黃色警戒：單日虧損>3% 或 連續止損≥5次
    if daily_loss > 0.03 or consecutive_stops >= 5:
        self.reduce_position_size(50)  # 倉位減半
        self.notify("#warning", "⚡ 倉位減半")
    
    return True
```

---

## 十五、總結

v31 的核心改進：
1. **雙向交易**：牛市做多、熊市做空，擴大盈利機會
2. **1m/3m 框架**：縮短持倉時間，提高資金效率
3. **插針形態**：識別快速反轉點，捕捉逆勢利潤
4. **動態倉位**：根據連續止損自動調整，降低風險
5. **趨勢過濾**：只在明確趨勢中交易，減少被掃

---

*生成時間：2026-04-26*
*基於版本：Scalp_Momentum_B_v28*
*目標版本：Scalp_Momentum_B_v31*
