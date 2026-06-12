# Adaptive_Scalp_v2 策略規格文件

**版本**: v2.0  
**創建日期**: 2026-04-27  
**策略類型**: 自適應市場狀態剝头皮策略  
**時間框架**: 5m 進場 / 15m 確認趨勢  
**交易模式**: Futures (can_short = True)  
**槓桿**: 5x  

---

## 1. 策略概述

### 1.1 核心概念

Adaptive_Scalp_v2 是一款自適應市場狀態的智能剝头皮策略，根據實時市場條件自動切換三種交易模式：

| Regime | ADX 範圍 | 市場狀態 | 交易模式 | 風險報酬比 |
|--------|----------|----------|----------|------------|
| **Regime 0** | ADX < 20 | 盤整/低波動 | 均值回歸 (BB + RSI) | 1:1.5 |
| **Regime 1** | ADX 20-25 | 過渡/觀望 | 輕倉觀望或不做單 | N/A |
| **Regime 2** | ADX > 25 | 強趨勢 | 趨勢跟隨 (EMA + ADX) | 1:3 |

### 1.2 策略架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    Adaptive_Scalp_v2 架構                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────┐                     │
│   │   5m Timeframe  │    │   15m Timeframe │ (informative)     │
│   │   進場信號       │    │   趨勢確認       │                     │
│   └────────┬────────┘    └────────┬────────┘                   │
│            │                       │                             │
│            └───────────┬───────────┘                             │
│                        ▼                                         │
│            ┌─────────────────────┐                               │
│            │   Market Regime      │                               │
│            │   Detector (ADX)      │                               │
│            └──────────┬────────────┘                               │
│                       │                                            │
│          ┌────────────┼────────────┐                              │
│          │            │            │                              │
│          ▼            ▼            ▼                              │
│   ┌───────────┐ ┌───────────┐ ┌───────────┐                     │
│   │ Regime 0   │ │ Regime 1  │ │ Regime 2  │                     │
│   │ 均值回歸   │ │  過渡觀望  │ │ 趨勢跟隨   │                     │
│   │ BB + RSI  │ │ 輕倉/不做 │ │ EMA + ADX │                     │
│   └───────────┘ └───────────┘ └───────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 進場條件 (Entry Conditions)

### 2.1 Regime 0 - 均值回歸進場 (ADX < 20)

**邏輯**: 價格觸及布林帶外軌後反彈，RSI 顯示超買/超賣

| 方向 | 條件 |
|------|------|
| **多頭進場** | 1. `close < bb_lower` (觸及下軌) <br> 2. `rsi < 35` (RSI 超賣) <br> 3. `volume > volume_ma * 0.8` (成交量確認) <br> 4. `close > open` (陽燭確認) |
| **空頭進場** | 1. `close > bb_upper` (觸及上軌) <br> 2. `rsi > 65` (RSI 超買) <br> 3. `volume > volume_ma * 0.8` (成交量確認) <br> 4. `close < open` (陰燭確認) |

**15m 確認條件** (可選):
- 多頭: `close_15m > ema_200_15m` (價格在 200 均線上方)
- 空頭: `close_15m < ema_200_15m` (價格在 200 均線下方)

### 2.2 Regime 1 - 過渡觀望 (ADX 20-25)

**原則**: 減少交易頻率，僅執行高質量信號

| 方向 | 條件 |
|------|------|
| **多頭進場** | 1. `adx > 22` (ADX 在上升) <br> 2. `plus_di > minus_di` <br> 3. `ema_fast > ema_slow` <br> 4. `volume > volume_ma * 1.2` (更嚴格成交量要求) |
| **空頭進場** | 1. `adx > 22` <br> 2. `minus_di > plus_di` <br> 3. `ema_fast < ema_slow` <br> 4. `volume > volume_ma * 1.2` |

**持倉限制**: Regime 1 只允許 0.5x 槓桿或半倉

### 2.3 Regime 2 - 趨勢跟隨進場 (ADX > 25)

**邏輯**: 順勢而為，等待 EMA 黃金交叉/死亡交叉配合 ADX 確認

| 方向 | 條件 |
|------|------|
| **多頭進場** | 1. `adx > 25` (趨勢強度足夠) <br> 2. `plus_di > minus_di` (多頭方向) <br> 3. `ema_fast > ema_slow` (EMA 多頭排列) <br> 4. `adx_rising = True` (ADX 正在上升) <br> 5. `close > bb_middle` (價格在 BB 中軌上方) |
| **空頭進場** | 1. `adx > 25` <br> 2. `minus_di > plus_di` (空頭方向) <br> 3. `ema_fast < ema_slow` (EMA 空頭排列) <br> 4. `adx_rising = True` <br> 5. `close < bb_middle` (價格在 BB 中軌下方) |

**15m 確認條件** (必要):
- 多頭: `ema_50_15m > ema_200_15m` AND `close_15m > ema_200_15m`
- 空頭: `ema_50_15m < ema_200_15m` AND `close_15m < ema_200_15m`

### 2.4 進場條件速查表

| 條件 | Regime 0 (盤整) | Regime 1 (過渡) | Regime 2 (趨勢) |
|------|----------------|----------------|----------------|
| ADX | < 20 | 20-25 | > 25 |
| ADX 方向 | 任意 | 上升優先 | 上升 |
| EMA 排列 | 任意 | 任意 | 必須对齐 |
| +DI vs -DI | 任意 | 方向確認 | 方向確認 |
| RSI | < 35 或 > 65 | 任意 | 任意 |
| BB 位置 | 觸及外軌 | 任意 | 中軌以上/以下 |
| 成交量 | > 0.8x MA | > 1.2x MA | > 1.0x MA |
| 15m 確認 | 建議 | 建議 | **必要** |
| 槓桿 | 5x | 2.5x (半倉) | 5x |

---

## 3. 出場條件 (Exit Conditions)

### 3.1 止損 (Stop Loss)

**使用 ATR 動態止損**，根據市場狀態調整：

| Regime | ATR 倍數 | 最小止損 | 最大止損 |
|--------|----------|----------|----------|
| Regime 0 (盤整) | 1.5x ATR | 1.0% | 2.5% |
| Regime 1 (過渡) | 1.75x ATR | 1.25% | 2.75% |
| Regime 2 (趨勢) | 2.0x ATR | 1.5% | 4.0% |

**公式**:
```
stoploss_pct = (ATR × multiplier) / current_price
stoploss_pct = max(min_stoploss, min(stoploss_pct, max_stoploss))
```

### 3.2 止盈 (Take Profit) - 分層 ROI

**基礎 ROI 表格**:

| 時間 (分鐘) | Regime 0 止盈 | Regime 2 止盈 |
|-------------|---------------|---------------|
| 0 (立即) | 1.5% | 4.5% |
| 15 | 1.25% | 3.5% |
| 30 | 1.0% | 2.5% |
| 60 | 0.75% | 2.0% |

**動態止盈調整**:
- ATR 止盈 = `(ATR × profit_multiplier) / current_price`
- `profit_multiplier`: Regime 0 = 3.0x, Regime 2 = 5.0x
- 確保 `止盈 >= 2 × 止損` (最小 R/R = 1:2)

### 3.3 追蹤止損 (Trailing Stop)

| 市場狀態 | trailing_stop_positive | trailing_stop_positive_offset | trailing_only_offset_is_reached |
|----------|------------------------|-------------------------------|--------------------------------|
| 趨勢強 (Regime 2) | 0.3% | 1.0% | True |
| 盤整 (Regime 0) | 禁用 | - | - |

### 3.4 出場條件速查表

| 出場觸發 | 條件 |
|----------|------|
| 止損 | ATR 動態止損觸發 |
| 止盈 (Regime 0) | ROI 達到 1.5% 或 ATR 止盈 |
| 止盈 (Regime 2) | ROI 達到 4.5% 或 ATR 止盈 |
| 追蹤止損 | 利潤 > 1% 後，0.3% trailing |
| 時間止損 | 最大持倉 45 分鐘 (5m  timeframe) |
| 趨勢反轉 | ADX < 20 且反向信號出現 |

---

## 4. 風險管理規則

### 4.1 倉位大小

| 帳戶餘額 | 每筆風險 | 最大單筆損失 |
|----------|----------|--------------|
| $1,000 | 2% ($20) | $20 |
| $5,000 | 1.5% ($75) | $75 |
| $10,000+ | 1% ($100) | $100 |

### 4.2 每日交易限制

| 限制項目 | 數量/值 |
|----------|---------|
| 每日最大交易次數 | 20 筆 |
| 每日最大損失 | 5% 帳戶 |
| 每日最大連續虧損 | 3 筆 |

### 4.3 市場狀態風險調整

| Regime | 倉位大小 | 槓桿 | 備註 |
|--------|----------|------|------|
| Regime 0 (盤整) | 100% | 5x | 嚴格止損 |
| Regime 1 (過渡) | 50% | 2.5x | 謹慎交易 |
| Regime 2 (趨勢) | 100% | 5x | 允許利潤奔跑 |

### 4.4 風險報酬比目標

| Regime | 目標 R/R | 最低止盈 | 止損 | 盈虧平衡勝率 |
|--------|----------|----------|------|--------------|
| Regime 0 | 1:1.5 | 1.5% | 1.0% | 40% |
| Regime 1 | 1:2 | 2.5% | 1.25% | 33% |
| Regime 2 | 1:3 | 4.5% | 1.5% | 25% |

**公式驗證**:
```
期望值 = Win% × avg_win - Loss% × avg_loss
期望值 > 0 才執行交易
```

---

## 5. 參數表 (Parameters)

### 5.1 策略基本參數

| 參數名 | 數值 | 說明 |
|--------|------|------|
| `timeframe` | "5m" | 進場時間框架 |
| `informative_timeframe` | "15m" | 趨勢確認時間框架 |
| `can_short` | True | 開啟空頭交易 |
| `leverage` | 5 | 期貨槓桿倍數 |
| `stoploss` | -0.02 | 基礎止損 -2% |

### 5.2 指標參數

| 參數名 | 數值 | 說明 |
|--------|------|------|
| `ema_fast_period` | 12 | EMA 快速週期 |
| `ema_slow_period` | 26 | EMA 慢速週期 |
| `adx_period` | 14 | ADX 計算週期 |
| `adx_threshold_strong` | 25 | 強趨勢閾值 |
| `adx_threshold_weak` | 20 | 盤整閾值 |
| `atr_period` | 14 | ATR 計算週期 |
| `bb_period` | 20 | 布林帶週期 |
| `bb_std` | 2 | 布林帶標準差倍數 |
| `rsi_period` | 14 | RSI 計算週期 |
| `rsi_oversold` | 35 | RSI 超賣閾值 |
| `rsi_overbought` | 65 | RSI 超買閾值 |

### 5.3 止損/止盈參數

| 參數名 | 數值 | 說明 |
|--------|------|------|
| `atr_stop_multiplier_r0` | 1.5 | Regime 0 ATR 止損倍數 |
| `atr_stop_multiplier_r1` | 1.75 | Regime 1 ATR 止損倍數 |
| `atr_stop_multiplier_r2` | 2.0 | Regime 2 ATR 止損倍數 |
| `atr_profit_multiplier_r0` | 3.0 | Regime 0 ATR 止盈倍數 |
| `atr_profit_multiplier_r2` | 5.0 | Regime 2 ATR 止盈倍數 |
| `trailing_stop_positive` | 0.003 | 追蹤止損 0.3% |
| `trailing_stop_offset` | 0.01 | 追蹤止損激活偏移 1% |

### 5.4 ROI 參數

```python
minimal_roi = {
    "0": 0.045,      # 立即 4.5% (Regime 2)
    "15": 0.035,     # 15分鐘 3.5%
    "30": 0.025,     # 30分鐘 2.5%
    "45": 0.015,     # 45分鐘 1.5%
}
```

### 5.5 交易限制參數

| 參數名 | 數值 | 說明 |
|--------|------|------|
| `max_trades_per_day` | 20 | 每日最大交易次數 |
| `max_daily_loss_pct` | 0.05 | 每日最大損失 5% |
| `max_consecutive_losses` | 3 | 最大連續虧損次數 |
| `max_hold_minutes` | 45 | 最大持倉時間 |

---

## 6. Freqtrade 程式碼結構

### 6.1 完整策略程式碼

```python
# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F501

from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
from typing import Optional


class Adaptive_Scalp_v2(IStrategy):
    """
    Adaptive_Scalp_v2 - 自適應市場狀態剝头皮策略
    =======================
    
    核心邏輯:
    - Regime 0 (ADX < 20): 均值回歸，BB 觸及 + RSI 極端
    - Regime 1 (ADX 20-25): 過渡觀望，輕倉交易
    - Regime 2 (ADX > 25): 趨勢跟隨，EMA 交叉 + 動量確認
    
    風險報酬比:
    - Regime 0: R/R = 1:1.5
    - Regime 2: R/R = 1:3
    
    Author: Research Team
    Version: 2.0
    """

    # ============================
    # 基本參數
    # ============================
    timeframe = "5m"
    informative_timeframe = "15m"
    
    can_short = True
    leverage = 5
    
    # 止損
    stoploss = -0.02
    
    # 追蹤止損
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True
    
    # ROI - 分層止盈
    minimal_roi = {
        "0": 0.045,
        "15": 0.035,
        "30": 0.025,
        "45": 0.015,
    }

    # ============================
    # 指標參數
    # ============================
    ema_fast_period = 12
    ema_slow_period = 26
    adx_period = 14
    adx_threshold_strong = 25
    adx_threshold_weak = 20
    atr_period = 14
    bb_period = 20
    bb_std = 2
    rsi_period = 14
    rsi_oversold = 35
    rsi_overbought = 65

    # ============================
    # ATR 倍數參數
    # ============================
    atr_stop_multiplier_r0 = 1.5
    atr_stop_multiplier_r1 = 1.75
    atr_stop_multiplier_r2 = 2.0
    atr_profit_multiplier_r0 = 3.0
    atr_profit_multiplier_r2 = 5.0

    # ============================
    # 多時間框架指標
    # ============================
    @informative("15m")
    def populate_indicators_15m(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """15m 時間框架趨勢確認指標"""
        dataframe["ema_50_15m"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200_15m"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx_15m"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["close_15m"] = dataframe["close"]
        return dataframe

    # ============================
    # 指標計算
    # ============================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === EMA ===
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_period)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_period)
        dataframe["ema_bullish"] = dataframe["ema_fast"] > dataframe["ema_slow"]
        dataframe["ema_bearish"] = dataframe["ema_fast"] < dataframe["ema_slow"]
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # === ADX + DI ===
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_period)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.adx_period)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.adx_period)
        dataframe["adx_rising"] = dataframe["adx"] > dataframe["adx"].shift(2)

        # === ATR ===
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # === Bollinger Bands ===
        bb = ta.BBANDS(dataframe["close"], timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std)
        dataframe["bb_upper"] = bb["upper"]
        dataframe["bb_middle"] = bb["mid"]
        dataframe["bb_lower"] = bb["lower"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]

        # === RSI ===
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # === 成交量 ===
        dataframe["volume_ma"] = dataframe["volume"].rolling(20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma"]

        # === Regime 分類 ===
        dataframe["regime"] = np.where(
            dataframe["adx"] > self.adx_threshold_strong, 2,  # Regime 2: 強趨勢
            np.where(dataframe["adx"] < self.adx_threshold_weak, 0, 1)  # Regime 0: 盤整, 否則 1
        )
        dataframe["regime_name"] = np.where(
            dataframe["regime"] == 2, "strong_trend",
            np.where(dataframe["regime"] == 0, "choppy", "transition")
        )

        # === 進場方向 ===
        dataframe["bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        return dataframe

    # ============================
    # 進場信號
    # ============================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        # === Regime 0: 均值回歸 (ADX < 20) ===
        cond_mr_long = (
            (dataframe["regime"] == 0) &
            (dataframe["close"] < dataframe["bb_lower"]) &
            (dataframe["rsi"] < self.rsi_oversold) &
            (dataframe["volume_ratio"] > 0.8) &
            (dataframe["close"] > dataframe["open"])
        )

        cond_mr_short = (
            (dataframe["regime"] == 0) &
            (dataframe["close"] > dataframe["bb_upper"]) &
            (dataframe["rsi"] > self.rsi_overbought) &
            (dataframe["volume_ratio"] > 0.8) &
            (dataframe["close"] < dataframe["open"])
        )

        # === Regime 1: 過渡觀望 (ADX 20-25) ===
        cond_trans_long = (
            (dataframe["regime"] == 1) &
            (dataframe["adx"] > 22) &
            dataframe["bullish"] &
            dataframe["ema_bullish"] &
            (dataframe["volume_ratio"] > 1.2)
        )

        cond_trans_short = (
            (dataframe["regime"] == 1) &
            (dataframe["adx"] > 22) &
            dataframe["bearish"] &
            dataframe["ema_bearish"] &
            (dataframe["volume_ratio"] > 1.2)
        )

        # === Regime 2: 趨勢跟隨 (ADX > 25) ===
        # 15m 確認條件
        cond_15m_bullish = (
            (dataframe["close_15m"] > dataframe["ema_200_15m"]) &
            (dataframe["ema_50_15m"] > dataframe["ema_200_15m"])
        )
        cond_15m_bearish = (
            (dataframe["close_15m"] < dataframe["ema_200_15m"]) &
            (dataframe["ema_50_15m"] < dataframe["ema_200_15m"])
        )

        cond_tf_long = (
            (dataframe["regime"] == 2) &
            dataframe["bullish"] &
            dataframe["ema_bullish"] &
            dataframe["adx_rising"] &
            (dataframe["close"] > dataframe["bb_middle"]) &
            cond_15m_bullish
        )

        cond_tf_short = (
            (dataframe["regime"] == 2) &
            dataframe["bearish"] &
            dataframe["ema_bearish"] &
            dataframe["adx_rising"] &
            (dataframe["close"] < dataframe["bb_middle"]) &
            cond_15m_bearish
        )

        # === 合併信號 ===
        dataframe.loc[cond_mr_long | cond_trans_long | cond_tf_long, "enter_long"] = 1
        dataframe.loc[cond_mr_short | cond_trans_short | cond_tf_short, "enter_short"] = 1

        return dataframe

    # ============================
    # 出場信號
    # ============================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # === ADX 下降表示趨勢減弱 ===
        exit_long_cond = dataframe["adx"] < self.adx_threshold_weak
        exit_short_cond = dataframe["adx"] < self.adx_threshold_weak

        dataframe.loc[exit_long_cond, "exit_long"] = 1
        dataframe.loc[exit_short_cond, "exit_short"] = 1

        return dataframe

    # ============================
    # 動態止損
    # ============================
    def custom_stoploss(self, pair: str, trade: Trade, current_time,
                        current_rate: float, current_profit: float,
                        **kwargs) -> float:
        dataframe, _ = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)

        if dataframe is None or len(dataframe) < self.adx_period:
            return -0.02

        atr_value = dataframe.iloc[-1]["atr"]
        adx = dataframe.iloc[-1]["adx"]
        regime = dataframe.iloc[-1]["regime"]

        if atr_value is None or np.isnan(atr_value):
            return -0.02

        # 根據 Regime 選擇 ATR 倍數
        if regime == 0:
            stop_mult = self.atr_stop_multiplier_r0
        elif regime == 1:
            stop_mult = self.atr_stop_multiplier_r1
        else:
            stop_mult = self.atr_stop_multiplier_r2

        # 計算 ATR 止損百分比
        atr_stop_pct = (atr_value * stop_mult) / current_rate

        # 限制範圍
        min_stop = 0.01 if regime == 0 else (0.0125 if regime == 1 else 0.015)
        max_stop = 0.025 if regime == 0 else (0.0275 if regime == 1 else 0.04)

        return -max(min_stop, min(atr_stop_pct, max_stop))

    # ============================
    # 槓桿調整
    # ============================
    def adjust_trade_position(self, pair: str, trade: Trade, current_time,
                             current_rate: float, current_vol: float,
                             min_stake: Optional[float], max_stake: float,
                             current_entry_rate: float, current_exit_rate: float,
                             current_profit: float, **kwargs) -> Optional[float]:
        """根據 Regime 動態調整倉位"""
        dataframe, _ = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)

        if dataframe is None:
            return None

        regime = dataframe.iloc[-1]["regime"]

        # Regime 1 (過渡) 減少倉位
        if regime == 1:
            return None  # 不追加倉位

        return None  # 其他 Regime 正常處理

    # ============================
    # 策略informative timeframes
    # ============================
    @property
    def protections(self):
        return [
            {
                "method": "MaxDrawdown",
                "lookback_period": 60,
                "trade_limit": 10,
                "stop_duration": 60,
                "lock_duration": 30,
            },
            {
                "method": "StoplossGuard",
                "lookback_period": 60,
                "trade_limit": 5,
                "stop_duration": 20,
                "lock_duration": 30,
            },
        ]
```

---

## 7. 回測驗證要點

### 7.1 回測參數建議

| 項目 | 建議值 |
|------|--------|
| 時間範圍 | 2024-01-01 至 2026-04-27 |
| 交易所 | Binance Futures |
| 交易對 | BTC/USDT:USDT, ETH/USDT:USDT |
| 資金管理 | Fixed, 100 USDT per trade |
| 起始資金 | 10,000 USDT |

### 7.2 成功標準

| 指標 | 目標值 |
|------|--------|
| 總收益率 | > 50% |
| 最大回撤 | < 20% |
| Sharpe Ratio | > 1.5 |
| 勝率 | > 40% |
| 平均 R/R | > 1:2 |
| 盈虧交易比 | > 1.2 |

### 7.3 需要監控的關鍵指標

1. **Regime 分佈**: 確認策略在不同市場狀態下都有交易
2. **R/R 實際值**: 定期檢查實際 R/R 是否符合設計
3. **連續虧損**: 監控 Regime 0 到 Regime 2 的轉換是否順暢
4. **15m 確認效果**: 檢查過濾是否過多或過少

---

## 8. 風險警告

1. **並非無風險**: 任何交易策略都存在虧損可能
2. **市場狀態變化**: Regime 判定可能延遲，導致錯誤進場
3. **流動性風險**: 高波動市場中止損可能執行在較差價格
4. **槓桿風險**: 5x 槓桿會放大虧損，請確保風險承受能力
5. **過去表現不代表未來**: 回測結果不代表實盤表現

---

## 9. 版本歷史

| 版本 | 日期 | 更新內容 |
|------|------|----------|
| v1.0 | 2026-04-27 | 初始版本基於三份研究文件 |
| v2.0 | 2026-04-27 | 整合完整規格文件 |

---

## 10. 參考資料

- `~/freqtrade/research/trend_detection_mechanisms.md` - 趨勢識別機制研究
- `~/freqtrade/research/risk_reward_ratio_design.md` - 風險報酬比設計研究
- `~/freqtrade/research/trend_following_alternative.md` - 趨勢跟隨替代方案研究
- Freqtrade 官方文檔: Custom Stoploss & ROI
