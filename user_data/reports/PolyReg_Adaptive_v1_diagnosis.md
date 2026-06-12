# PolyReg_Adaptive_v1 診斷報告

## 策略概述

**PolyReg_Adaptive_v1** 是一個基於多項式迴歸的均值回歸/趨勢跟隨混合策略。

## 失敗症狀

- **Iteration #1**: 215 trades, **-24.61%**, 47.9% WR
- **Hyperopt**: 0 trades, 100% waste (所有 epoch loss=100000)

---

## 根因分析

### 1. **Timeframe 不匹配 (CRITICAL)**
- 策略設定 `timeframe = '1h'`
- 但 hyperopt config (`config_polyreg_hyperopt.json`) 也設為 `1h`
- **問題**: 如果 backtest 資料只有 15m，freqtrade 會自動重採樣，但這會導致：
  - `startup_candle_count = 300` 在 1h 下需要 300 小時 (12.5 天) 的 warm-up
  - 若資料不足，策略無法產生訊號
  - 指標計算在重採樣後行為不同

### 2. **進場條件過於嚴格 (CRITICAL)**
```python
# 原始條件
long_condition = (
    dataframe['atr_ok'] &                          # ATR 必須在中間 40% 範圍
    (dataframe['adx'] < self.adx_threshold.value) & # ADX < threshold
    (dataframe['low'].shift(1) < dataframe['poly_lower'].shift(1)) &  # 前一根觸及下軌
    (dataframe['close'] > dataframe['poly_lower'])                    # 當前收於下軌之上
)
```

問題：
- `atr_ok` 要求 ATR 在 30%-70% 分位數之間，這本身就過濾掉了 60% 的市場狀態
- `adx < threshold` 同時要求盤整市場
- 兩個條件疊加後，符合條件的時間點極少
- 在 1h timeframe 下，這種條件組合可能幾乎不會觸發

### 3. **Hyperopt 參數空間問題**
- `degree = DecimalParameter(1, 4, default=2)` → 但後續轉為 `int(self.degree.value)`
- 當 degree=1.899 時，int() 變成 1，與預期不同
- 應使用 `IntParameter` 而非 `DecimalParameter`

### 4. **Exit 條件過於敏感**
```python
exit_long = (
    (dataframe['close'] > dataframe['poly_pred']) &
    (dataframe['close'].shift(1) <= dataframe['poly_pred'].shift(1))
)
```
- 這是 cross 條件，但當價格在迴歸線附近震盪時，會連續觸發 exit
- 導致過早出場，無法獲取完整利潤

### 5. **趨勢跟隨條件被註解掉**
```python
# 趨勢跟隨進場 (可選)
# dataframe.loc[dataframe['trend_long'], 'enter_long'] = 1
```
- 只啟用了均值回歸，但均值回歸在趨勢市場中會持續虧損
- 這解釋了為何 Iteration #1 有 215 筆交易但 -24.61%

### 6. **can_short = False 但 short 條件存在**
- 策略設定了 `can_short = False`
- 但計算了 `short_condition` 和 `trend_short`
- 雖然不會實際進場，但浪費計算資源

---

## 修復方案 (v2)

### 修正 1: Timeframe 統一
```python
timeframe = '15m'  # 與資料一致
```

### 修正 2: 放寬進場條件
- 移除 `atr_ok` 強制要求 (改為可選)
- 放寬 ADX 範圍 (20-40 → 10-50)
- 加入 volume 過濾作為替代

### 修正 3: 啟用雙模式
- 同時啟用 mean-reversion 和 trend-following
- 使用參數開關控制

### 修正 4: 修正參數類型
```python
# 錯誤
degree = DecimalParameter(1, 4, default=2)
# 正確
degree = IntParameter(1, 4, default=2)
```

### 修正 5: 降低 startup_candle_count
```python
startup_candle_count = 100  # 從 300 降低
```

### 修正 6: 優化 Exit 邏輯
- 保持 cross 條件但確保不會連續觸發
- 考慮加入最小持倉時間

---

## 建議測試步驟

1. **先執行一次 backtest** 確認有交易產生
2. **Hyperopt 使用較少 epochs** (100-200) 快速驗證
3. **觀察參數分佈**: 若 still 0 trades，進一步放寬條件
4. **考慮加入 informative timeframe** (1h) 做趨勢確認

---

## 檔案

- 原始: `strategies/math_based/PolyReg_Adaptive_v1.py`
- 修復: `strategies/math_based/PolyReg_Adaptive_v2.py`
- 報告: `reports/PolyReg_Adaptive_v1_diagnosis.md`
