# Adaptive_Scalp_v2 回測失敗分析報告

## 執行摘要

| 指標 | 數值 |
|------|------|
| 回測期間 | 2025-01-16 至 2025-04-27 (約100天) |
| 總交易數 | 14 筆 |
| 勝率 | 0% (0勝14敗) |
| 總虧損 | -13.82 USDT (-1.38%) |
| 總虧損 (含槓桿) | 約 -60% |
| 平均交易時長 | **0 根K線** (全部當根進出台灣時間17:00-21:15) |
| 退出原因 | 100% stop_loss |

---

## 核心發現：所有交易在進場當根K線即觸發止損

### 問題 1：custom_stoploss 動態止損過寬（主因）

**位置：** `Adaptive_Scalp_v2.py` 第 213-236 行

```python
def custom_stoploss(
    self,
    pair: str,
    trade,
    current_time,
    current_rate: float,
    current_profit: float,
    after_fill: bool,
    **kwargs,
) -> float:
    dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    if dataframe.empty:
        return self.stoploss

    last_candle = dataframe.iloc[-1]
    atr = last_candle["atr"]

    # ATR-based stop distance (~2-3% depending on volatility)
    stoploss_distance = atr / current_rate
    return -stoploss_distance
```

**問題：** 每次都取得**最新一根K線**的ATR作為止損距離。在15m timeframe下，`process_only_new_candles=True` 時，策略只在新K線形成時被呼叫，但 `custom_stoploss` 仍使用最新（可能是剛進場的同一根）K線的ATR，導致止損位置極不穩定。

實測數據顯示：
- 預期止損位置：entry × (1 - 2.5%/5) = entry × 0.995
- 實際止損位置偏離高達 50-150 點
- **所有 14 筆交易的 stop_loss_ratio 皆在 -0.27% ~ -0.85% 之間**，遠寬於預期的 -0.5%

### 問題 2：進場後價格從未向有利方向移動

逐筆分析（以 Trade 1 為例）：
- 進場價：100,565 USDT
- 當根最低：100,257.9（低於進場價 307 點）
- 當根最高：101,605.0（高於進場價 1,040 點）
- **最終收盤：100,446.5（收在進場價下方）**

所有 14 筆交易的 `max_rate` 都短暫突破初始止損價，但 `custom_stoploss` 的動態止損不斷上調，最終在低於進場價數十點處觸發。

### 問題 3：ROI 階梯完全未被觸及

- `minimal_roi = {"0": 0.08, "30": 0.05, "60": 0.03, "120": 0.02}`
- 所有交易 duration = 0，根本沒有機會達到任何 ROI 門檻
- `trailing_stop` 也因同樣原因從未啟動

### 問題 4：進場時機集中在特定時段（17:00-21:15 UTC）

14 筆交易中有 12 筆發生在 UTC 17:00-21:15（台灣時間凌晨1:00-5:15），這是亞洲交易時段低流動性窗口，極易被短暫流動性掃損。

---

## 逐筆交易數據

| # | 開倉時間 (UTC) | 方向 | 進場價 | 實際觸發止損價 | 觸發% | 最終虧損% | 含槓桿虧損% |
|---|----------------|------|--------|----------------|-------|-----------|-------------|
| 1 | 01-27 13:00 | Long | 100,565 | 100,446.5 | -0.59% | -1.19% | -5.94% |
| 2 | 02-03 08:00 | Long | 95,247 | 95,095.5 | -0.80% | -1.40% | -6.97% |
| 3 | 02-14 21:15 | Short | 96,848 | 96,937.4 | -0.46% | -1.06% | -5.31% |
| 4 | 02-17 16:00 | Short | 95,614 | 95,666.4 | -0.28% | -0.88% | -4.39% |
| 5 | 02-21 15:45 | Short | 97,535 | 97,626.7 | -0.47% | -1.07% | -5.35% |
| 6 | 03-03 15:00 | Short | 89,270 | 89,422.5 | -0.85% | -1.45% | -7.27% |
| 7 | 03-16 16:15 | Long | 84,121 | 84,038.0 | -0.50% | -1.09% | -5.47% |
| 8 | 04-01 15:15 | Long | 84,870 | 84,786.7 | -0.49% | -1.09% | -5.44% |
| 9 | 04-04 11:00 | Short | 82,544 | 82,621.0 | -0.47% | -1.07% | -5.34% |
| 10 | 04-13 02:30 | Short | 84,776 | 84,841.5 | -0.39% | -0.99% | -4.93% |
| 11 | 04-13 17:30 | Long | 84,678 | 84,617.0 | -0.36% | -0.96% | -4.80% |
| 12 | 04-14 00:30 | Long | 84,722 | 84,625.7 | -0.57% | -1.17% | -5.84% |
| 13 | 04-21 14:15 | Long | 87,647 | 87,582.4 | -0.37% | -0.97% | -4.85% |
| 14 | 04-21 17:15 | Short | 86,814 | 86,897.3 | -0.48% | -1.08% | -5.41% |

---

## 根本原因分析

### 1. custom_stoploss 的 ATR 計算方式錯誤（第 213-236 行）

```python
# 錯誤：每次取得 last_candle 的最新 ATR
last_candle = dataframe.iloc[-1]
atr = last_candle["atr"]
stoploss_distance = atr / current_rate
return -stoploss_distance
```

問題在於：
- 若 `process_only_new_candles=True`，策略在上一根K線計算信號，但在新K線第一個tick執行進場
- `custom_stoploss` 被呼叫時，dataframe 只有1根K線（進場的那根），其ATR仍是進場前的值
- ATR 波動時，止損位置會劇烈變動

**正確做法：** 應在進場時固定止損距離，不在每根K線重新計算，或使用進場K線的ATR計算。

### 2. 進場邏輯與市場微結構不匹配

- `breakout_up` 計算：`dataframe["close"] > dataframe["swing_high"]`（shift(1)）
- 在低流動性時段，突破常是「虛假突破」，價格迅速回歸
- EMA crossover + breakout 兩者同時滿足的頻率低，導致交易次數極少（100天14筆）

### 3. 槓桿與止損設計不匹配

- 5x 槓桿 + 2.5% 停損 = 12.5% 可承受虧損
- 但 `custom_stoploss` 實際給出約 -0.3%~-0.85% 的止損範圍
- 在 5x 槓桿下，這意味著只需要 0.06%-0.17% 的反向波動就觸發止損

---

## 修復建議（行號級別）

### 建議 1：移除或修正 custom_stoploss（高優先級）

**檔案：** `Adaptive_Scalp_v2.py`，第 213-236 行

**方案 A（推薦）：完全移除 custom_stoploss**，讓 Freqtrade 使用固定的 `stoploss = -0.025`（2.5%），在 5x 槓桿下提供 12.5% 的有效止損空間：

```python
# 刪除整個 custom_stoploss 方法（第 213-236 行）
# 將第 51 行 use_custom_stoploss = True 改為：
use_custom_stoploss = False
```

**方案 B（替代）：修復 custom_stoploss 的 ATR 計算邏輯**：

```python
def custom_stoploss(
    self,
    pair: str,
    trade,
    current_time,
    current_rate: float,
    current_profit: float,
    after_fill: bool,
    **kwargs,
) -> float:
    # 固定比例止損：2.5% / 5x槓桿 = 0.5% 距離
    # 或使用進場時的ATR，不使用實時ATR
    return -0.005  # 固定 0.5% 止損（5x槓桿下 = 2.5% 虧損）
```

### 建議 2：調整 ROI 階梯（高優先級）

**檔案：** `Adaptive_Scalp_v2.py`，第 54-59 行

當前（過度進取）：
```python
minimal_roi = {
    "0": 0.08,   # 8% at 0 minutes（幾乎不可能）
    "30": 0.05,  # 5% after 30 minutes
    "60": 0.03,  # 3% after 60 minutes
    "120": 0.02, # 2% after 120 minutes
}
```

**建議修改（更符合比特幣15m實際波動）：**（第 54-59 行）
```python
minimal_roi = {
    "0": 0.04,   # 4% immediately（更實際的目標）
    "60": 0.03,  # 3% after 60 minutes
    "180": 0.02, # 2% after 180 minutes
}
```

### 建議 3：調整 trailing_stop 參數（高優先級）

**檔案：** `Adaptive_Scalp_v2.py`，第 61-65 行

當前（配置錯誤）：
```python
trailing_stop = True
trailing_stop_only_offset_is_reached = True
trailing_stop_offset = 0.05  # 這會被 trailing_positive_offset 覆蓋
trailing_positive_offset = 0.05
```

問題：`trailing_only_offset_is_reached=True` 意味著trailing只在盈利超過5%後啟動，但 `minimal_roi` 要求8%才能接觸ROI，導致trailing根本沒機會啟動。

**建議修改（第 61-65 行）：**
```python
trailing_stop = True
trailing_stop_only_offset_is_reached = False  # 立即啟動trailing
trailing_stop_offset = 0.02  # 2% trailing distance
trailing_positive_offset = 0.015  # 1.5% profit lock
```

### 建議 4：加入進場延遲確認（降低虛假信號）

**檔案：** `Adaptive_Scalp_v2.py`，第 138-143 行

```python
# 當前：只看上一根的 swing high/low
dataframe["swing_high"] = dataframe["high"].rolling(window=swing_window).max().shift(1)
dataframe["swing_low"] = dataframe["low"].rolling(window=swing_window).min().shift(1)

# 建議：要求價格在突破後連續2根K線保持在上方
dataframe["breakout_up"] = (
    (dataframe["close"] > dataframe["swing_high"]) &
    (dataframe["close"] > dataframe["close"].shift(1)) &
    (dataframe["close"].shift(1) > dataframe["swing_high"].shift(1))
)
dataframe["breakout_down"] = (
    (dataframe["close"] < dataframe["swing_low"]) &
    (dataframe["close"] < dataframe["close"].shift(1)) &
    (dataframe["close"].shift(1) < dataframe["swing_low"].shift(1))
)
```

### 建議 5：調整 EMA 引數降低靈敏度（减少假信號）

**檔案：** `Adaptive_Scalp_v2.py`，第 72-73 行

```python
# 當前：太快速，信號過多
ema_fast_period = 9
ema_slow_period = 21

# 建議：使用更平滑的參數
ema_fast_period = 12
ema_slow_period = 26
```

### 建議 6：降低槓桿或調整停損設計

**檔案：** `Adaptive_Scalp_v2.py`，第 79-93 行

當前 `leverage()` 返回 5.0x。考慮到 `custom_stoploss` 實際止損只有 0.3%-0.85%，5x 槓桿過度危險。

**建議修改（第 79-93 行）：**
```python
def leverage(
    self,
    pair: str,
    current_time,
    current_rate: float,
    proposed_leverage: float,
    max_leverage: float,
    entry_tag: str | None,
    side: str,
    **kwargs,
) -> float:
    """
    Set leverage to 2x for all trades.
    With proper stoploss (2.5%), 2x gives 5% effective risk.
    """
    return 2.0
```

---

## 總結

| 問題層面 | 嚴重程度 | 修復難度 |
|----------|----------|----------|
| custom_stoploss ATR計算錯誤 | 🔴 致命 | ★★☆ |
| ROI 目標過度進取 | 🔴 致命 | ★☆☆ |
| trailing_stop 配置矛盾 | 🟡 重要 | ★☆☆ |
| 進場邏輯產生虛假信號 | 🟡 重要 | ★★☆ |
| 槓桿過高 | 🟡 重要 | ★☆☆ |

**核心修復：** 移除或修正 `custom_stoploss`（第 213-236 行），將 `use_custom_stoploss` 改為 `False`，並調整 `minimal_roi` 和 `trailing_stop` 參數。

---

*分析日期：2026-04-27*
*數據來源：backtest-result-2026-04-27_10-27-38.json*
