# Pullback Scalping Strategy Design

## Overview

- **Strategy Name**: PullbackScalp
- **Type**: Trend-following + Mean-reversion pullback
- **Timeframe**: Multi-timeframe (1h trend confirmation, 15m entry)
- **Markets**: Spot/Long only (configurable for short)
- **Premise**: Enter during pullbacks in confirmed trends, avoiding chasing.

---

## 1. Trend Confirmation (1h)

| Condition | Long | Short |
|-----------|------|-------|
| Price vs EMA | `close > EMA(50)` | `close < EMA(50)` |
| ADX | `ADX(14) > 25` | `ADX(14) > 25` |
| Trend Label | `trend == 1` | `trend == -1` |

- Use `@informative` decorator to load 1h data.
- ADX > 25 confirms trend strength (not just direction).
- Side note: ADX does not indicate direction — use price vs EMA for direction.

---

## 2. Pullback Identification (15m)

### Long Pullback (trend == 1)
- Price touches EMA(21) on 15m, **OR**
- RSI(14) drops from above `60` back into `40–50` zone

### Short Pullback (trend == -1)
- Price touches EMA(21) on 15m, **OR**
- RSI(14) rises from below `40` back into `50–60` zone

| Pullback Type | Condition A | Condition B |
|---------------|-------------|-------------|
| Long | `15m close ≤ EMA(21)` | `RSI(14) in [40, 50]` after being > 60 |
| Short | `15m close ≥ EMA(21)` | `RSI(14) in [50, 60]` after being < 40 |

---

## 3. Entry Confirmation (15m)

Requires **both**:
1. **Candlestick pattern** on 15m:
   - Long: `hammer`, `inverse_hammer`, `bullish_engulfing`
   - Short: `shooting_star`, `bearish_engulfing`, `hangman`
2. **Volume spike**: `volume > SMA(volume, 20) * 1.5`

Signal label: `enter_long` / `enter_short`

---

## 4. Exit Logic

### Stop Loss
- Long: SL = pullback low − 1 × ATR(14)
- Short: SL = pullback high + 1 × ATR(14)

### Take Profit
- TP option A (preferred): previous swing high/low on 15m
- TP option B: 2 × ATR from entry
- Use whichever is smaller distance (more conservative).

### Exit Signal
- `exit_long` when price crosses TP or SL hit
- `exit_short` analogously

---

## 5. Complete Strategy Structure

```python
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

import talib.abstract as ta
from technical import qtpylib


class PullbackScalp(IStrategy):
    """
    Pullback Scalping strategy.
    - 1h: confirm trend with EMA50 + ADX > 25
    - 15m: wait for pullback to EMA21 or RSI zone
    - 15m: enter on candlestick pattern + volume confirmation
    - Exit: ATR-based SL/TP
    """

    INTERFACE_VERSION = 3

    # Can go short if configured
    can_short: bool = True

    # --- Timeframe settings ---
    timeframe = '15m'
    inf_timeframe = '1h'

    # --- Exit settings (override via config if needed) ---
    stoploss = -0.03           # -3% from entry
    minimal_roi = {
        "0": 0.015,           # 1.5% at break-even
        "30": 0.01,           # 1% after 30 min
        "60": 0.02,           # 2% after 60 min
    }

    # Trailing (optional, can enable)
    trailing_stop = False
    trailing_only_offset_is_reached = True
    trailing_start = 0.01
    trailing_stop_positive = 0.015

    # --- ATR period ---
    atr_period = 14

    # ============================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1h informative (trend confirmation)
        inf = self.informative_1h(dataframe, metadata)
        dataframe['trend'] = 0
        dataframe.loc[
            (inf['close'] > inf['ema_50']) & (inf['adx'] > 25),
            'trend'
        ] = 1
        dataframe.loc[
            (inf['close'] < inf['ema_50']) & (inf['adx'] > 25),
            'trend'
        ] = -1

        # EMA 21 (15m pullback reference)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)

        # EMA 50 (used alongside ADX for extra confirmation)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)

        # ADX on 15m (optional local confirmation)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # ATR for SL/TP
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # Volume SMA
        dataframe['vol_sma'] = dataframe['volume'].rolling(20).mean()

        # Candlestick pattern detection
        dataframe['pattern_hammer'] = ta.CDLHAMMER(dataframe)
        dataframe['pattern_engulfing'] = ta.CDLENGULFING(dataframe)
        dataframe['pattern_shooting_star'] = ta.CDLSHOOTINGSTAR(dataframe)
        dataframe['pattern_hangman'] = ta.CDLHANGMAN(dataframe)
        dataframe['pattern_inverse_hammer'] = ta.CDLINVERSEHAMMER(dataframe)

        return dataframe

    # ============================================================
    @informative('1h')
    def informative_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe.copy()
        df['ema_50'] = ta.EMA(df, timeperiod=50)
        df['adx'] = ta.ADX(df, timeperiod=14)
        # Keep only necessary columns
        return df[['date', 'close', 'ema_50', 'adx']]

    # ============================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        trend = dataframe['trend']
        rsi = dataframe['rsi']
        ema21 = dataframe['ema_21']
        close = dataframe['close']
        vol = dataframe['volume']
        vol_sma = dataframe['vol_sma']
        atr = dataframe['atr']

        # --- Long entry conditions ---
        long_pullback = (
            # Condition A: price touches EMA21
            (close <= ema21) &
            (trend == 1)
        ) | (
            # Condition B: RSI pulled back to 40-50 zone
            (rsi >= 40) & (rsi <= 50) &
            (trend == 1)
        )

        long_pattern = (
            (dataframe['pattern_hammer'] > 0) |
            (dataframe['pattern_inverse_hammer'] > 0) |
            (dataframe['pattern_engulfing'] > 0)
        )
        long_vol = vol > vol_sma * 1.5

        dataframe.loc[
            long_pullback & long_pattern & long_vol,
            'enter_long'
        ] = 1

        # --- Short entry conditions ---
        short_pullback = (
            # Condition A: price touches EMA21
            (close >= ema21) &
            (trend == -1)
        ) | (
            # Condition B: RSI pulled back to 50-60 zone
            (rsi >= 50) & (rsi <= 60) &
            (trend == -1)
        )

        short_pattern = (
            (dataframe['pattern_shooting_star'] > 0) |
            (dataframe['pattern_hangman'] > 0) |
            (dataframe['pattern_engulfing'] < 0)
        )
        short_vol = vol > vol_sma * 1.5

        dataframe.loc[
            short_pullback & short_pattern & short_vol,
            'enter_short'
        ] = 1

        return dataframe

    # ============================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        # Exit on opposite signal (reversal) — simple approach
        # Alternatively rely on stoploss/trailing entirely
        return dataframe

    # ============================================================
    def custom_stoploss(self, trade: Trade, current_time: datetime,
                        current_rate: float, current profit: float,
                        **kwargs) -> float:
        """
        Dynamic SL based on pullback low/high + ATR.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss

        last_candle = dataframe.iloc[-1]

        # Get entry price
        entry_rate = trade.open_rate

        # Pullback reference: EMA21 or RSI zone — use current candle's EMA21 as reference
        ema21 = last_candle['ema_21']
        atr = last_candle['atr']

        if trade.direction == 'long':
            # SL = pullback low - ATR
            # Use min of EMA21 and recent low as pullback reference
            pullback_ref = min(ema21, last_candle['low'])
            sl = stoploss_from_absolute(pullback_ref - atr, entry_rate, trade)
        else:
            # SL = pullback high + ATR
            pullback_ref = max(ema21, last_candle['high'])
            sl = stoploss_from_absolute(pullback_ref + atr, entry_rate, trade)

        return sl

    # ============================================================
    def confirm_trade_exit(self, trade: Trade, order: Order,
                           current_time: datetime, **kwargs) -> bool:
        """
        Optional: add extra exit confirmation logic.
        """
        return True
```

---

## 6. Parameter Recommendations

| Parameter | Recommended Value | Range | Notes |
|-----------|-------------------|-------|-------|
| `timeframe` | `15m` | — | Entry timeframe |
| `inf_timeframe` | `1h` | — | Trend confirmation |
| `atr_period` | `14` | 10–20 | For SL/TP sizing |
| `RSI period` | `14` | 7–21 | Standard |
| `EMA 21` | `21` | 15–30 | Pullback reference |
| `EMA 50` | `50` | 40–60 | Trend filter |
| `ADX threshold` | `25` | 20–30 | Trend strength |
| `Volume SMA` | `20` | 15–30` | Volume filter |
| `Volume multiplier` | `1.5` | 1.2–2.0 | Confirmation |
| `stoploss` | `-0.03` | -0.02 to -0.05 | ATR-based preferred |
| `minimal_roi` | see above | — | Adjust per asset |
| `Trailing` | disabled initially | — | Test before enabling |

---

## 7. Pair Selection & Filtering

- Prefer liquid pairs: `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, etc.
- Exclude stablecoin pairs and low-volume altcoins.
- Add `VolumeFilter` or `QuoteConcentrationFilter` if needed.

---

## 8. Backtesting Notes

```bash
# Download 1h + 15m data
freqtrade download-data --timeframe 1h --timerange 20230101- -t 5m
freqtrade download-data --timeframe 15m --timerange 20230101- -t 5m
# Then resample to 15m with informative 1h

# Run backtest
freqtrade backtest --strategy PullbackScalp \
  --timeframe 15m \
  --timerange 20230101-20230701 \
  --strategy-path user_data/strategies \
  --min-trades 50
```

> **Note**: Since the strategy uses informative 1h data, ensure your backtest data includes both timeframes.

---

## 9. Risk Management Summary

| Element | Value |
|---------|-------|
| Max loss per trade | 1× ATR from pullback point |
| Target reward | 2× ATR or prior swing |
| Risk:Reward | ~1:2 |
| Max daily trades | Set via `max_trades` in config |
| Max open trades | `2–3` simultaneous |

---

## 10. Potential Enhancements

1. **HTF confirmation**: Add 4h trend alignment to avoid counter-trend trades.
2. **Momentum confirmation**: Require RSI(14) > 50 on 1h for long entries.
3. **Tighten entry**: Only enter when RSI exits the 40–50 zone upward (not just sitting in it).
4. **Dynamic TP**: Use recent 15m swing high/low instead of fixed ATR.
5. **Filter volatile pairs**: Exclude pairs where ATR% > 5% to avoid choppy behavior.
6. **Trailing stop**: Enable after 1% profit, trail by 0.75%.
