# Pullback Entry Strategies for Freqtrade - Research Report

**Date**: 2026-04-27  
**Focus**: Cryptocurrency Futures Pullback Entry Strategies

---

## 1. EMA Pullback Entry Strategy

### Pullback Identification Method
- **Trend Detection**: EMA9 > EMA21 > EMA50 (bullish alignment)
- **Pullback Detection**: Price retraces to test EMA support zone
- **Confirmation**: RSI bouncing from oversold territory (30-50 zone)
- **ADX Filter**: ADX > 25 to confirm strong trend before pullback entry

### Entry Confirmation Conditions
```
1. EMA200 rising (minimum 10 periods)
2. EMA9 > EMA21 (short-term momentum restored)
3. ADX > 25 (trend strength sufficient)
4. +DI > -DI (directional bias aligned)
5. RSI 30-40 zone (deep pullback, not extreme oversold)
```

### Stop Loss / Take Profit Settings
- **Stop Loss**: 1-2% below entry
- **Take Profit**: 1% (quick scalp) or trailing stop with 0.5% offset
- **Timeframe**: 15m or 1h for swing pullbacks

### Win Rate & Risk-Reward
- Expected win rate: 60-70% in trending markets
- Risk-reward ratio: 1:1 to 1:1.5
- Best performance: Strong trending assets (BTC, ETH in clear trends)

### Freqtrade Implementation
```python
class EMAPullbackStrategy(IStrategy):
    timeframe = '15m'
    stoploss = -0.015
    minimal_roi = {"0": 0.01}
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe)
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_conditions = (
            (dataframe['ema200'] > dataframe['ema200'].shift(10)) &
            (dataframe['ema9'] > dataframe['ema21']) &
            (dataframe['adx'] > 25) &
            (dataframe['plus_di'] > dataframe['minus_di']) &
            (dataframe['rsi'] > 30) &
            (dataframe['rsi'] < 40)
        )
        dataframe.loc[long_conditions, 'enter_long'] = 1
        return dataframe
```

---

## 2. RSI Pullback Strategy

### Pullback Identification Method
- **Classic RSI Oversold**: RSI < 30 indicates deep pullback
- **RSI Pullback Zone**: RSI 35-50 in uptrend = healthy retracement
- **RSI Cross Up**: RSI crossing UP through 50 (momentum shift)
- **Divergence**: Price makes lower low but RSI makes higher low (bullish div)

### Entry Confirmation Conditions
```
LONG Entry (RSI Oversold):
1. Close < BB lower band
2. RSI < 30
3. ADX > 20 (trend exists)

OR (RSI Pullback in Uptrend):
1. RSI crosses UP through 50
2. EMA9 > EMA21 (trend intact)
3. Volume confirmation (ratio > 1.0)
```

### Stop Loss / Take Profit Settings
- **Stop Loss**: 2-3% below entry
- **Take Profit**: 2% immediate / 1% after 30 min
- **Trailing Stop**: 2% positive with 4% offset

### Win Rate & Risk-Reward
- RSI oversold (RSI < 30): 55-65% win rate, strong when ADX high
- RSI cross at 50: 60-70% win rate in trending markets
- Best environment: Trending markets with clear pullbacks

### Freqtrade Implementation
```python
class RSIPullbackStrategy(IStrategy):
    timeframe = '5m'
    stoploss = -0.03
    minimal_roi = {"0": 0.02, "30": 0.01}
    can_short = True
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, num_std=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = (
            (dataframe['close'] < dataframe['bb_lowerband']) &
            (dataframe['rsi'] < 30) &
            (dataframe['adx'] > 20)
        )
        return dataframe
```

---

## 3. Buy the Dip (Trend Pullback) Strategy

### Pullback Identification Method
- **Higher Highs, Higher Lows**: Upward trend structure intact
- **Dip Detection**: Price pulls back to previous support level
- **Volume Confirmation**: Volume spike on bounce (institutional accumulation)
- **Candlestick Patterns**: Hammer, engulfing bullish patterns at support

### Entry Confirmation Conditions
```
1. EMA alignment (9 > 21 > 50)
2. Price retests EMA50 or previous swing low
3. RSI < 50 (not oversold, pullback not exhaustion)
4. Volume on bounce > volume on decline
5. Bullish candlestick confirmation
```

### Stop Loss / Take Profit Settings
- **Stop Loss**: Below recent swing low or 2%
- **Take Profit**: Previous high or 3:1 risk-reward target
- **Timeframe**: 1h for swing, 5m for intraday

### Win Rate & Risk-Reward
- Win rate: 55-65% in strong trends
- Risk-reward: 1:2 to 1:3 (larger R:R for swing plays)
- Key: Wait for confirmation, don't preemptively buy

---

## 4. Fibonacci Retracement Entry Strategy

### Pullback Identification Method
- **Fib Levels**: 0.382, 0.5, 0.618 retracement zones
- **Golden Zone**: 0.618 - best probability reversal area
- **Structure**: Identify swing high/low with pivot detection
- **Confluence**: Fib level + EMA + support/resistance = high probability entry

### Entry Confirmation Conditions
```
1. Clear impulse wave (swing high to low)
2. Price retraces to 0.382, 0.5, or 0.618 level
3. RSI bounce from oversold OR RSI divergence at Fib level
4. EMA50/200 support at Fib zone
5. Volume contraction at Fib level (accumulation)
```

### Stop Loss / Take Profit Settings
- **Stop Loss**: Below 0.618 level (wider stop for reliability)
- **Take Profit**: Previous swing high or 1.272 extension
- **Timeframe**: 1h/4h for swing, 15m for intraday

### Win Rate & Risk-Reward
- Win rate: 50-60% (fewer but higher quality trades)
- Risk-reward: 1:2 to 1:3
- Best for: Swing trading on higher timeframes

---

## 5. Support/Resistance Bounce Strategy

### Pullback Identification Method
- **Horizontal Levels**: Price repeatedly bounces from support/resistance
- **Zone Detection**: Not single price, but range (1-2% width)
- **Order Block**: Institutional order zones (previous big candles)
- **Liquidity Sweep**: Price sweeps below support then reverses

### Entry Confirmation Conditions
```
1. Price approaches support zone (within 1%)
2. RSI oversold or bouncing from low
3. Bullish price action (hammer, engulfing, pin bar)
4. Volume confirmation on bounce
5. No major news/event risk
```

### Stop Loss / Take Profit Settings
- **Stop Loss**: Below support zone or recent low (1.5-2%)
- **Take Profit**: Near resistance or 2:1 R:R
- **Timeframe**: 15m-1h for clearest zones

### Win Rate & Risk-Reward
- Win rate: 55-65% at key levels
- Risk-reward: 1:1.5 to 1:2
- Key: Identify "fresh" levels vs. stale levels

---

## 6. Advanced Hybrid Strategy (From Existing Strategies)

### Combined Pullback Entry Logic
Based on `Hybrid_v1` and `Scalp_Momentum_B` strategies:

```python
class HybridPullbackStrategy(IStrategy):
    """
    EMA Trend + RSI Pullback + Volume Confirmation
    Key insight: In uptrend, RSI pulls back to 45-50 then bounces.
    We catch this bounce rather than waiting for RSI < 30.
    """
    
    timeframe = '1h'
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    
    minimal_roi = {"0": 0.03, "60": 0.015, "180": 0.01}
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_fast'] = ta.EMA(dataframe['close'], timeperiod=9)
        dataframe['ema_slow'] = ta.EMA(dataframe['close'], timeperiod=21)
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=8)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['volume_ma'] = dataframe['volume'].rolling(20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        prev = dataframe['rsi'].shift(1)
        curr = dataframe['rsi']
        
        # Long: RSI crosses UP through 50 + EMA bullish + Volume
        long_cond = (
            (prev < 50) & (curr >= 50) &  # RSI cross up through 50
            (dataframe['ema_fast'] > dataframe['ema_slow']) &  # EMA bullish
            (dataframe['volume_ratio'] > 1.0)  # Volume confirmation
        )
        dataframe.loc[long_cond, 'enter_long'] = 1
        return dataframe
```

### Scalp Momentum Pullback (1m/5m)
```python
class ScalpPullbackStrategy(IStrategy):
    """
    Bidirectional scalp with pullback detection + pin bar confirmation
    """
    
    stoploss = -0.015
    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.004
    timeframe = "1m"
    
    # Pullback parameters
    pullback_min = 0.001  # 0.1% pullback
    rsi_min_long = 35
    rsi_max_long = 72
    volume_mult = 0.75
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=5)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=7)
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=10)
        
        # Pullback detection
        dataframe["recent_high"] = dataframe["high"].rolling(window=4).max()
        dataframe["pullback_pct"] = (dataframe["recent_high"] - dataframe["close"]) / dataframe["recent_high"]
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cond_trend_long = dataframe["ema_fast"] > dataframe["ema_slow"]
        cond_trend2_long = dataframe["ema_slow"] > dataframe["ema_trend"]
        cond_pullback = dataframe["pullback_pct"] >= self.pullback_min
        cond_rsi_long = (dataframe["rsi"] >= self.rsi_min_long) & (dataframe["rsi"] <= self.rsi_max_long)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * self.volume_mult)
        
        dataframe["enter_long"] = (
            cond_trend_long &
            cond_trend2_long &
            dataframe["ema_rising"] &
            cond_pullback &
            cond_rsi_long &
            cond_volume &
            (dataframe["close"] > dataframe["open"])
        ).astype(int)
        return dataframe
```

---

## Summary: Best Pullback Entry Methods

### By Timeframe

| Timeframe | Best Strategy | Key Indicators |
|-----------|--------------|----------------|
| 1m | Scalp Momentum | EMA 5/12/20, RSI 35-72, Pullback %, Volume |
| 5m | RSI + BB | BB lower band, RSI < 30, ADX > 20 |
| 15m | EMA Pullback | EMA 9/21/200, RSI 30-40, ADX > 25 |
| 1h | Hybrid RSI Cross | EMA 9/21, RSI cross 50, Volume |
| 4h | Fib + Support | Fibonacci 0.618, Support zones |

### By Market Condition

| Market Condition | Recommended Strategy |
|------------------|---------------------|
| Strong Uptrend | EMA Pullback, RSI Cross at 50 |
| Strong Downtrend | Short at RSI > 70 + BB upper band |
| Ranging | Support/Resistance bounce |
| High Volatility | Tighter stops, smaller size |

### Key Success Factors

1. **Trend Confirmation First**: Always confirm trend before pullback entry
2. **ADX > 25**: Only trade pullbacks in trending markets
3. **RSI Zone 30-50**: Don't wait for extreme oversold
4. **Volume Confirmation**: Institutional accumulation/suppression
5. **Tight Stops**: 1-2% maximum for scalp, 2-3% for swing

---

## Recommended Freqtrade Implementation Order

1. **Start with**: `EMAPullbackStrategy` (15m) - solid foundation
2. **Add**: `RSIPullbackStrategy` (5m) - for faster entries
3. **Combine**: `HybridPullbackStrategy` (1h) - for swing trades
4. **Enhance**: Add volume confirmation, pin bar filters

### Common Parameters

```python
# Universal pullback parameters
stoploss = -0.015 to -0.03
minimal_roi = {"0": 0.01 to 0.03}
trailing_stop = True
trailing_stop_positive = 0.01 to 0.02
timeframe = "5m" to "1h"
can_short = True (for futures)
```

---

## Risk Management Notes

- **Never trade against strong trend without confirmation**
- **Stop loss is mandatory** - pullback trades can become traps
- **Position sizing**: Reduce size on lower timeframes
- **Max spread check**: Reject entries when spread > 0.4%
- **Max ATR check**: Reject entries when volatility > 0.8%
