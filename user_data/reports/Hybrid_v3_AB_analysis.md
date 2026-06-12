# Hybrid_v3 A/B Backtest 深度分析報告

**日期**: 2026-05-31  
**回測期間**: 2026-05-01 ~ 2026-05-25  
**交易對**: BTC/USDT:USDT  
**時間框架**: 15m  
**市場變化**: +1.64%

---

## 一、核心數據總結

| 指標 | Hybrid_v3 | Hybrid_v3_OF | BB_RPB_TSL_BI (基線) |
|------|-----------|--------------|----------------------|
| 總利潤 | **-0.92%** | **-0.93%** | **+6.22%** |
| 勝率 | 33.3% | 35.1% | ~60% |
| Profit Factor | 0.45 | 0.45 | >1.5 |
| Max Drawdown | 1.03% | 1.04% | ~3% |
| 交易數 | 72 | 74 | ~200+ |

**關鍵發現**: 兩個版本都虧損，且訂單流版本幾乎沒有差異。市場上漲 +1.64% 但策略完全沒跟上。

---

## 二、Exit Reason 深度拆解

### 2.1 exit_signal — 最大虧損來源 (40-42 筆, avg -0.40%, 勝率 27-31%)

這是 **最嚴重的問題**。exit_signal 佔總交易數的 55% 以上，且平均虧損 -0.40%。

**根本原因分析**:

1. **CROSS logic 過於敏感** (populate_exit_trend 第 577-653 行):
   ```python
   trending_exit = (
       (dataframe["regime"] == 2)
       & (
           # EMA CROSS down: 只在一根 K 線上觸發
           ((dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"]))
           # RSI CROSS above 65: 只在一根 K 線上觸發
           | ((dataframe["rsi"] > self.RSI_TREND_EXIT)
              & (dataframe["rsi"].shift(1) <= self.RSI_TREND_EXIT))
       )
   )
   ```
   - **問題 1**: RSI cross above 65 在 15m 時間框架上極度敏感。BTC 在盤整時 RSI 經常在 60-70 之間波動，導致頻繁觸發假出場。
   - **問題 2**: EMA12/26 cross down 在震盪市會反覆交叉，每次交叉都觸發出場，但趨勢可能根本沒結束。
   - **問題 3**: CROSS logic 雖然解決了連續出場的問題，但變成了「只要指標一閃過就立即出場」，完全沒有確認機制。

2. **RSI 閾值過低**:
   - RSI_TREND_EXIT = 65: 在強趨勢中，RSI 可以持續在 70-80 運行。65 的閾值會在趨勢剛開始加速時就出場。
   - RSI_MEAN_REV_EXIT = 60: 均值回歸的目標應該是 RSI 50（中線），而不是 60。60 只完成了 2/3 的回歸就提前出場。

3. **缺少多條件確認**:
   - BB_RPB_TSL_BI 的 custom_exit 使用了 **多指標組合**（RSI + CMF + CTI + max_profit 回撤），而 Hybrid_v3 只用單一指標。

### 2.2 stoploss — 12 筆全虧, avg -0.79%

**根本原因分析**:

1. **custom_stoploss 過於嚴格** (第 658-696 行):
   ```python
   def custom_stoploss(...):
       if current_profit < 0:
           return -0.03  # 虧損時硬止損 -3%
   ```
   - **問題**: 在 15m 時間框架上，BTC 的正常波動經常超過 3%。-3% 的硬止損在正常回調中就會被觸發。
   - **對比**: BB_RPB_TSL_BI 使用 stoploss = -0.05 (-5%)，且 custom_stoploss 在虧損時 **不返回負數**，而是讓虧損浮動直到 custom_exit 或 ROI 出場。

2. **沒有學習 BB_RPB_TSL_BI 的「虧損浮動」設計**:
   - BB_RPB_TSL_BI 的 custom_stoploss 只在 **盈利時** 返回正數鎖定利潤。
   - 虧損時，BB_RPB_TSL_BI 依靠 custom_exit 的複雜條件（RSI + CMF + EMA200 + 回撤幅度）來判斷是否真該止損。
   - Hybrid_v3 則在虧損時直接 -3% 硬止損，沒有給價格任何回調空間。

### 2.3 roi — 15 筆全贏, avg +0.55%

**這是唯一穩定盈利的渠道，但數量太少**。

**根本原因分析**:

1. **ROI 目標過高**:
   ```python
   minimal_roi = {
       "0": 0.03,    # 3% 立即目標
       "120": 0.015, # 1.5% 在 30 小時後
       "240": 0.005, # 0.5% 在 60 小時後
   }
   ```
   - 3% 的即時目標在 15m 時間框架上很難達到。BTC 在 15m 上的典型波動是 1-2%。
   - 對比 BB_RPB_TSL_BI: `minimal_roi = {"0": 0.205}` — 20.5% 的單一目標，但這是 5m 時間框架，且交易頻率更高。

2. **ROI 與 exit_signal 的時間競爭**:
   - 大部分交易在達到 ROI 之前就被 exit_signal 或 stoploss 出場了。
   - 只有 15/72 = 20.8% 的交易能撐到 ROI 出場。

---

## 三、與 BB_RPB_TSL_BI 的結構性差異

### 3.1 Entry 設計對比

| 維度 | Hybrid_v3 | BB_RPB_TSL_BI |
|------|-----------|---------------|
| Entry 條件數 | 3 (trend/mean_rev/weak_trend) | **12+** (dip/break/uptrend/ewo/clucHA/cofi/nfi 等) |
| Entry 確認 | 單一指標 | **多指標組合** + 1h informative |
| 時間框架 | 15m + 30m/1h/4h informative | **5m** + 1h informative |
| Entry 頻率 | 72 筆/25天 (2.9筆/天) | ~200+ 筆/25天 (8+筆/天) |

**BB_RPB_TSL_BI 的 Entry 優勢**:
- 12 種不同的 entry 條件覆蓋了更多市場狀態。
- 每種條件都經過 hyperopt 優化，參數精確到小數點後 3 位。
- 使用 Heikin Ashi 蠟燭過濾噪音。
- 大量保護條件（CTI, CRSI, Williams %R, volume ratio）防止假突破。

### 3.2 Exit 設計對比

| 維度 | Hybrid_v3 | BB_RPB_TSL_BI |
|------|-----------|---------------|
| populate_exit_trend | 有 (CROSS logic) | **無** (exit_long = 0) |
| custom_exit | 簡單 (RSI>75, time, drawdown) | **極其複雜** (~500 行條件) |
| custom_stoploss | 分級利潤保護 + 虧損硬止損 | **純利潤保護** (虧損不干预) |
| Trailing stop | DISABLED | **隱含在 custom_stoploss** |

**BB_RPB_TSL_BI 的 Exit 優勢**:
- **沒有 populate_exit_trend**，完全依靠 custom_exit + custom_stoploss + ROI。
- custom_exit 有 **~500 行條件**，根據 current_profit 區間、RSI、CMF、CTI、max_profit 回撤等多維度判斷。
- custom_stoploss 只在 **盈利時** 返回正數鎖定利潤，虧損時讓價格浮動。
- 這種設計讓盈利交易能 **充分奔跑**，虧損交易有機會 **自然回調**。

### 3.3 核心哲學差異

| Hybrid_v3 | BB_RPB_TSL_BI |
|-----------|---------------|
| 「讓策略決定何時出場」 | 「讓利潤決定何時出場」 |
| 技術指標驅動出場 | **利潤區間驅動出場** |
| 頻繁出場 (72 筆) | 精選出場 (200+ 筆但條件複雜) |
| 虧損硬止損保護本金 | 虧損浮動等待反轉 |

---

## 四、訂單流版本的實際價值評估

### 4.1 為什麼 Hybrid_v3_OF 幾乎沒有差異？

1. **Bybit 不支援 --dl-trades**: backtest 中 `self.dp.trades()` 返回空數據。
2. **Order Flow 指標全部為 0** (Hybrid_v3_OF.py 第 142-146 行):
   ```python
   dataframe["vi"] = 0.0
   dataframe["spread_pct"] = 0.0
   dataframe["cvd"] = 0.0
   dataframe["cvd_slope"] = 0.0
   ```
3. **of_confirm 條件** `(vi > -0.2) & (spread_pct < 0.008)` 在 vi=0 時總是為 True，所以不會過濾任何交易。

### 4.2 訂單流的正確使用方式

**建議**: 
- **Backtest 中完全放棄訂單流**，專注改善基礎策略。
- **Live/Dry-run 中啟用訂單流** 作為額外過濾層，但期望值不要太高。
- 如果要在 backtest 中驗證訂單流，需要下載歷史 trades 數據（Binance 提供，Bybit 不提供）。

---

## 五、具體改進建議（按優先級排序）

### 🔴 P0: 緊急修復（預期改善: -0.92% → +2~4%）

#### 1. 修復 exit_signal — 改用 LEVEL logic + 延遲確認

**問題**: CROSS logic 過於敏感，RSI 一閃過 65 就立即出場。

**方案 A（推薦）: 改用 LEVEL logic + 連續確認**:
```python
def populate_exit_trend(self, dataframe, metadata):
    dataframe["exit_long"] = 0

    # ── Trending Exit: EMA cross down OR RSI 連續 3 根 > 65 ──
    trending_exit = (
        (dataframe["regime"] == 2)
        & (
            # EMA CROSS down
            ((dataframe["ema_fast"] < dataframe["ema_slow"])
             & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"]))
            # RSI LEVEL above 65 with confirmation (連續 2 根確認)
            | ((dataframe["rsi"] > self.RSI_TREND_EXIT)
               & (dataframe["rsi"].shift(1) > self.RSI_TREND_EXIT)
               & (dataframe["rsi"].shift(2) <= self.RSI_TREND_EXIT))
        )
    )

    # ── Ranging Exit: RSI 連續 2 根 > 60 ──
    ranging_exit = (
        (dataframe["regime"] == 0)
        & (
            ((dataframe["rsi"] > self.RSI_MEAN_REV_EXIT)
             & (dataframe["rsi"].shift(1) > self.RSI_MEAN_REV_EXIT))
            | ((dataframe["close"] > dataframe["bb_upper"])
               & (dataframe["close"].shift(1) > dataframe["bb_upper"]))
        )
    )
    ...
```

**方案 B: 提高 RSI 閾值**:
- RSI_TREND_EXIT: 65 → **75**
- RSI_MEAN_REV_EXIT: 60 → **70**

**方案 C: 增加多條件確認**:
```python
trending_exit = (
    (dataframe["regime"] == 2)
    & (
        # 條件 1: EMA cross down + MACD hist < 0 (動量確認)
        ((dataframe["ema_fast"] < dataframe["ema_slow"])
         & (dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"])
         & (dataframe["macd_hist"] < 0))
        # 條件 2: RSI > 65 + close < EMA fast (價格確認)
        | ((dataframe["rsi"] > self.RSI_TREND_EXIT)
           & (dataframe["rsi"].shift(1) <= self.RSI_TREND_EXIT)
           & (dataframe["close"] < dataframe["ema_fast"]))
    )
)
```

#### 2. 放寬 stoploss — 學習 BB_RPB_TSL_BI 的「虧損浮動」設計

**問題**: -3% 硬止損在正常回調中被頻繁觸發。

**方案**:
```python
def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
    # 關鍵改變: 虧損時不硬止損，讓 custom_exit 處理
    if current_profit < -0.05:  # 只有虧損超過 5% 才硬止損
        return -0.05
    
    # 盈利時的利潤保護保持不變
    if current_profit >= 0.05:
        return +0.02
    if current_profit >= 0.03:
        return +0.01
    if current_profit >= 0.015:
        return -0.015
    
    return -0.99  # 讓價格自由浮動
```

#### 3. 降低 ROI 目標 — 讓更多交易能盈利出場

**問題**: 3% 目標太難達到，大部分交易被 exit_signal/stoploss 截殺。

**方案**:
```python
minimal_roi = {
    "0": 0.015,     # 1.5% 立即目標 (was 3%)
    "60": 0.008,    # 0.8% 在 15 小時後
    "120": 0.005,   # 0.5% 在 30 小時後
    "240": 0.003,   # 0.3% 在 60 小時後
}
```

### 🟡 P1: 重要優化（預期改善: +2~4% → +4~6%）

#### 4. 豐富 custom_exit — 學習 BB_RPB_TSL_BI 的多維度出場

**方案**: 根據 profit 區間設計分級出場條件:
```python
def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
    dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    if dataframe is None or dataframe.empty:
        return None
    
    last_candle = dataframe.iloc[-1]
    previous_candle = dataframe.iloc[-2]
    
    # ── 微利區間 (0~1%): 嚴格保護 ──
    if 0.01 > current_profit >= 0:
        if (last_candle["rsi"] < 35) and (last_candle["macd_hist"] < 0):
            return "profit_t_0_1"
    
    # ── 中利區間 (1~3%): 動量確認 ──
    elif 0.03 > current_profit >= 0.01:
        max_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
        if (max_profit > (current_profit + 0.02)) and (last_candle["rsi"] < 40):
            return "profit_t_1_1"
    
    # ── 高利區間 (>3%): 利潤鎖定 ──
    elif current_profit >= 0.03:
        max_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
        if (max_profit > (current_profit + 0.03)) and (last_candle["rsi"] < 45):
            return "profit_t_3_1"
    
    # ── 虧損區間: 只在極端條件出場 ──
    if current_profit < -0.03:
        if (last_candle["rsi"] > previous_candle["rsi"]) and (last_candle["close"] < last_candle["ema_slow"]):
            return "stoploss_u_e_1"
    
    # 時間出場保持不變
    holding_minutes = (current_time - trade.open_date).total_seconds() / 60
    if holding_minutes > 2880:
        return "time_exit"
    
    return None
```

#### 5. 優化 Entry 條件 — 減少假突破

**問題**: 
- trending_entry 的 volume 條件太寬鬆 (`volume > volume.rolling(20).mean()`)。
- ranging_entry 的 RSI < 40 在震盪市中經常觸發，但震盪市可能繼續下跌。

**方案**:
```python
# Trending entry: 增加 1h EMA 確認
trending_entry = (
    (dataframe["regime"] == 2)
    & (dataframe["ema_fast"] > dataframe["ema_slow"])
    & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
    & (dataframe["plus_di"] > dataframe["minus_di"])
    & (dataframe["macd_hist"] > 0)
    & (dataframe["volume"] > 1.5 * dataframe["volume"].rolling(20).mean())  # 1.5x volume
    & (dataframe["close"] > dataframe["ema_slow"])  # 價格在 EMA slow 之上
)

# Ranging entry: 增加底背離確認
ranging_entry = (
    (dataframe["regime"] == 0)
    & (dataframe["close"] < dataframe["bb_lower"])
    & (dataframe["rsi"] < self.RSI_MEAN_REV_ENTRY)
    & (dataframe["rsi"] > dataframe["rsi"].shift(1))  # RSI 開始回升 (底背離)
    & (dataframe["volume"] > 1.2 * dataframe["volume"].rolling(20).mean())
)
```

#### 6. 啟用 Trailing Stop（與 custom_stoploss 協調）

**問題**: trailing_stop = False 錯過了趨勢中的利潤奔跑。

**方案**: 
```python
trailing_stop: bool = True
trailing_stop_positive: float = 0.015  # 1.5%
trailing_stop_positive_offset: float = 0.03  # 3%
trailing_only_offset_is_reached: bool = True
```

注意: 啟用 trailing_stop 時需要調整 custom_stoploss，避免衝突。

### 🟢 P2: 長期改進

#### 7. 引入 Heikin Ashi 蠟燭

BB_RPB_TSL_BI 使用 Heikin Ashi 過濾噪音，這是 Hybrid_v3 缺少的。

```python
heikinashi = qtpylib.heikinashi(dataframe)
dataframe["ha_close"] = heikinashi["close"]
dataframe["ha_open"] = heikinashi["open"]

# Entry 使用 HA 蠟燭
trending_entry = (
    ...
    & (dataframe["ha_close"] > dataframe["ha_open"])  # HA 蠟燭為陽線
)
```

#### 8. 增加更多 Entry 條件類型

學習 BB_RPB_TSL_BI 的多條件設計:
- `is_dip`: RSI + CCI + SRSI 組合
- `is_break`: BB 突破 + 成交量確認
- `is_local_uptrend`: EMA 差值 + BB 觸碰
- `is_clucHA`: Heikin Ashi + BB 40 週期

#### 9. 訂單流的正確定位

- **Backtest**: 完全移除訂單流相關代碼，簡化策略。
- **Live/Dry-run**: 保留訂單流作為可選增強層，但設計 A/B 測試機制驗證實際效果。

---

## 六、改進路線圖

```
Phase 1 (立即執行, 預期 1-2 天):
  1. 修復 exit_signal: RSI 閾值 65→75, 增加連續確認
  2. 放寬 stoploss: -3% → -5% 硬止損, 虧損 <5% 時浮動
  3. 降低 ROI: 3% → 1.5%
  → 預期結果: -0.92% → +2~4%

Phase 2 (1 週內):
  4. 豐富 custom_exit: 分級 profit 區間出場條件
  5. 優化 entry: volume 1.5x, 增加 EMA 確認
  6. 啟用 trailing_stop
  → 預期結果: +2~4% → +4~6%

Phase 3 (1-2 週):
  7. 引入 Heikin Ashi
  8. 增加 entry 條件類型
  9. 簡化/移除訂單流代碼
  → 預期結果: +4~6% → +6~8% (接近 BB_RPB_TSL_BI)
```

---

## 七、結論

Hybrid_v3 的虧損 **不是因為策略概念錯誤**（regime detection + dual-mode 是正確的方向），而是因為:

1. **Exit 過於敏感**: CROSS logic + 低 RSI 閾值導致頻繁假出場。
2. **Stoploss 過緊**: -3% 硬止損在正常回調中頻繁觸發。
3. **ROI 過高**: 3% 目標讓大部分交易無法盈利出場。
4. **缺少利潤區間驅動的出場**: 沒有學習 BB_RPB_TSL_BI 的核心優勢。

**最關鍵的改變**: 從「指標驅動出場」轉向「利潤區間驅動出場」，讓盈利交易充分奔跑，虧損交易有回調空間。
