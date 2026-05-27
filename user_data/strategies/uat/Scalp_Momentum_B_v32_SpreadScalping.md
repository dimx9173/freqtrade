# Scalp_Momentum_B_v32 - Pure Spread Scalping Strategy Design
================================================================

## 1. Executive Summary

### Strategy Concept
**Pure spread scalping** — Trade the bid-ask spread rather than directional price movement. 
This strategy exploits short-term order book imbalances, liquidity pockets, and mean-reversion 
opportunities without requiring correct trend predictions.

### Core Philosophy
```
v28/v31 Problem: Trend-following fails in sideways/bear markets
v32 Solution: Ignore trend entirely, focus on:
  1. Spread widening = institutional activity = opportunity
  2. Bollinger Band mean-reversion = statistical edge
  3. Volume spikes = confirm liquidity-driven moves
  4. Tight time-boxed exits = prevent overnight risk
```

### Target Performance
| Metric | Target | v28 Benchmark |
|--------|--------|--------------|
| Monthly Return | ≥5% | N/A (bear market) |
| Max Drawdown | ≤2% | 9.10% |
| Win Rate | ≥75% | 87.6% |
| Max Loss per Trade | ≤0.2% | -2% |
| Holding Time | <5 min | 5m+ |
| Trades per Day | 10-20 | ~9 |

---

## 2. Core Indicators (Trend-Agnostic)

### 2.1 Primary: Bollinger Bands (BB) — Mean Reversion Signal
```
BB_period = 20
BB_std = 2.0 (tight for scalping: 1.5)

Signal Logic:
- Price touches lower BB → potential LONG (mean reversion up)
- Price touches upper BB → potential SHORT (mean reversion down)
- NO trend requirement
```

### 2.2 Secondary: Spread/Wick Ratio — Institutional Activity Detector
```
body = abs(close - open)
upper_wick = high - max(open, close)
lower_wick = min(open, close) - low

Spread Signal:
- Large wick / small body (wick_body_ratio > 3.0) = smart money activity
- Wide range candle = liquidity hunt = potential reversal
```

### 2.3 Confirmation: Volume Spike + BB Position
```
volume_sma = SMA(volume, 20)
volume_ratio = volume / volume_sma

Confirmation conditions:
- Price at BB extreme AND
- volume_ratio > 1.5 AND
- Wick shows rejection direction
→ High probability scalp setup
```

### 2.4 Exclusion Filter: ATR Volatility Cap
```
atr_pct = ATR(14) / close
max_atr_pct = 0.008 (0.8%)

IF atr_pct > max_atr_pct → Skip (chop market)
```

---

## 3. Entry Logic

### 3.1 LONG Entry Conditions (All Required)
```
1. Price Position: close <= BB_lower (or within 0.5% of it)
2. Wick Rejection: lower_wick > body * 2.0 (strong rejection)
3. Volume: volume_ratio >= 1.5
4. Wick Direction: lower_wick > upper_wick (bullish tilt)
5. ATR Filter: atr_pct <= 0.008
6. Spread Filter: (high - low) / close <= 0.004
```

### 3.2 SHORT Entry Conditions (All Required)
```
1. Price Position: close >= BB_upper (or within 0.5% of it)
2. Wick Rejection: upper_wick > body * 2.0 (strong rejection)
3. Volume: volume_ratio >= 1.5
4. Wick Direction: upper_wick > lower_wick (bearish tilt)
5. ATR Filter: atr_pct <= 0.008
6. Spread Filter: (high - low) / close <= 0.004
```

### 3.3 Entry Flow
```
Tick arrives
  → Check BB position (lower/upper 3%)
    → Check wick/body ratio (>3.0)
      → Check volume spike (>1.5x)
        → Check ATR filter
          → Check spread filter
            → ENTER
```

---

## 4. Exit Logic

### 4.1 Time-Based Exit (Primary) — Maximum 5 Minutes
```
holding_time >= 300 seconds → FORCE EXIT
This prevents:
- Overnight exposure
- Extended drawdowns
- Market regime changes
```

### 4.2 Trailing Stop (Secondary)
```
Once profit >= 0.05%:
  → Activate trailing stop
  → trail_stop_positive = 0.002 (0.2%)
  → Exit when profit drops below trailing threshold
```

### 4.3 Stop Loss (Hard Cap)
```
stoploss = -0.0015 (-0.15%)
This is the absolute maximum loss per trade.
NEVER exceeded.
```

### 4.4 Profit Target (Optional — for strong moves)
```
IF profit >= 0.10% AND holding_time < 120 seconds
  → Take profit immediately (strong move)
```

### 4.5 Exit Priority
```
1. STOP LOSS (highest priority, never adjusted)
2. TIME EXIT (5 min hard cap)
3. TRAILING STOP (activates at +0.05%)
4. PROFIT TARGET (optional early exit)
```

---

## 5. Position Management

### 5.1 Position Size
```
risk_per_trade = 0.3% of account (3x stop loss buffer)
stop_loss_pct = 0.15%
position_size = risk_per_trade / stop_loss_pct
            = 0.003 / 0.0015
            = 2x notional (use 5x leverage → position = 10x risk)
```

### 5.2 Leverage
```
leverage = 5 (as per existing config)
This amplifies the 0.05-0.1% scalp targets to meaningful returns
```

### 5.3 Concurrent Positions
```
max_open_trades = 2
Only 2 simultaneous scalp positions to manage exposure
```

### 5.4 Cooldown
```
trade_cooldown = 60 seconds
After any exit (win or loss), wait 60s before new entry on same pair
```

---

## 6. Risk Controls

### 6.1 Per-Trade Risk
```
Maximum loss per trade: 0.15% of account
Achieved via: tight stop loss + position sizing
```

### 6.2 Daily Loss Limit
```
daily_max_loss = 1.5%
IF daily_pnl <= -1.5% → STOP TRADING FOR 24 HOURS
```

### 6.3 Drawdown Circuit Breaker
```
max_drawdown = 2.0%
IF current_drawdown >= 2.0% → PAUSE strategy, review
```

### 6.4 Market Regime Filter
```
IF ATR > 0.8% (high volatility):
  → Reduce position size by 50%
  → OR skip entirely

IF ATR < 0.3% (very low volatility):
  → Skip (spread too tight, not enough movement)
```

### 6.5 Spread Filter (Slippage Protection)
```
spread = (high - low) / close
IF spread > 0.4% → SKIP
This prevents entering during illiquid periods
```

---

## 7. Parameters Summary

### 7.1 Bollinger Bands
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| period | 20 | Standard, smooth |
| std_dev | 1.5 | Tighter = more signals |
| upper_touch | 100% BB | Entry trigger |
| lower_touch | 100% BB | Entry trigger |

### 7.2 Wick Confirmation
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| wick_body_ratio | ≥3.0 | Strong rejection |
| lower_dominance | lower_wick > upper_wick | Bullish signal |
| upper_dominance | upper_wick > lower_wick | Bearish signal |

### 7.3 Volume
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| volume_sma | 20 | Standard |
| volume_ratio | ≥1.5 | Confirm institutional activity |

### 7.4 Filters
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| max_atr_pct | 0.008 | Skip high volatility |
| max_spread_pct | 0.004 | Skip illiquid periods |
| min_volume_ratio | 1.5 | Institutional confirmation |

### 7.5 Exit Rules
| Rule | Value | Priority |
|------|-------|----------|
| Stop Loss | -0.15% | 1 (never adjust) |
| Time Exit | 300 sec (5 min) | 2 |
| Trailing Start | +0.05% | 3 |
| Trailing Distance | 0.02% | 3 |
| Early Profit Target | +0.10% | 4 (if <120 sec) |

### 7.6 Position
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| leverage | 5x | Per config |
| risk_per_trade | 0.3% | Conservative |
| max_open_trades | 2 | Limit exposure |
| cooldown | 60 sec | Prevent overtrading |

---

## 8. Expected Performance Characteristics

### 8.1 Trade Profile
```
Trade Duration:    30-300 seconds (avg ~2 min)
Win Rate Target:   75-80%
Profit per Win:    0.05-0.10% (0.25-0.5% with leverage)
Loss per Loss:     -0.10 to -0.15%
Daily Trades:      10-20 (both directions)
```

### 8.2 Monthly Projection (Conservative)
```
假设:
- 20 trading days
- 15 trades/day average
- 75% win rate
- 0.07% avg profit, -0.12% avg loss

Gross profit = 15 * 20 * 0.75 * 0.07% = 1.575%
Gross loss  = 15 * 20 * 0.25 * 0.12% = 0.9%
Net monthly = 1.575% - 0.9% = 0.675%

With 5x leverage on 300U:
= 0.675% * 5 = ~3.4% monthly

需要更高频率或更好的win rate来达到5%目标
```

### 8.3 Advantage vs v28/v31
```
| Aspect         | v28 (Trend)    | v31 (Trend+BB)  | v32 (Spread) |
|----------------|----------------|-----------------|--------------|
| Trend reliance | High (EMA)     | Medium          | NONE         |
| Entry signal   | Pullback+RSI   | Pullback+RSI    | BB+Wick+Vol  |
| Bear market    | Loses (-3.77%) | Unknown (0 short)| Should work  |
| Holding time   | 5m+            | 5m+             | <5 min       |
| Win rate       | 87.6%          | 93.6% (1m)      | Target 75%+  |
| Trade freq     | ~9/day         | ~4.5/day        | Target 15+/day|
```

---

## 9. Implementation Notes

### 9.1 Timeframe
```
PRIMARY: 1m (more signals, faster execution)
FALLBACK: 3m (if 1m data insufficient)
```

### 9.2 Pair Selection
```
START: BTC/USDT only (highest liquidity, tightest spreads)
IF v32 profitable on BTC:
  → Add ETH/USDT
  → Add SOL/USDT
```

### 9.3 Backtest Requirements
```
Minimum: 60 days backtest
Must include:
- Bull market period
- Bear market period  
- Sideways period
Must NOT be tested only on 1m/24day window like v31
```

### 9.4 Key Differences from v31
```
v31 Problem:
- Still relies on EMA trend (trend_trend_long = ema_fast > ema_slow)
- Short side never triggered (0 short trades in 24 days)
- Holding time longer than 5 min target

v32 Solution:
- NO EMA trend requirement at all
- BB position + wick direction ONLY
- Short entries: same logic, opposite BB side
- HARD 5-minute exit regardless of profit
```

---

## 10. Success Criteria

### Must Achieve
- [ ] 60+ day backtest shows ≥5% monthly return
- [ ] Works in both bull and bear market periods
- [ ] Short trades trigger (bidirectional, not just long)
- [ ] Average holding time < 5 minutes
- [ ] Drawdown ≤ 2%

### Should Achieve
- [ ] Win rate ≥ 75%
- [ ] Daily trades ≥ 10
- [ ] Short trades ≥ 30% of total

### Stretch Goals
- [ ] Monthly return ≥ 10% (2x target)
- [ ] Sharpe Ratio ≥ 2.0

---

## 11. Next Steps

### Phase 1: Implementation
1. Create `Scalp_Momentum_B_v32.py`
2. Implement BB indicators with populate_indicators()
3. Implement spread/wick ratio in indicators
4. Implement entry conditions in populate_entry_trend()
5. Implement 5-min time exit in custom_exit()
6. Implement daily loss limit in Bot loop

### Phase 2: Backtest
1. Download 6+ months 1m data for BTC, ETH
2. Run 60+ day backtest (2025-10-01 to 2026-04-26)
3. Include both bull (-48%) and current periods
4. Verify short trades trigger

### Phase 3: Optimization
1. Tune BB_std (1.5 vs 2.0)
2. Tune volume_ratio threshold (1.3 vs 1.5 vs 2.0)
3. Tune time exit (300s vs 240s vs 180s)
4. Tune trailing stop parameters

### Phase 4: Paper Trading
1. Run 2 weeks on Bybit testnet
2. Compare live vs backtest
3. Adjust for slippage/real conditions

---

## Appendix A: Pseudocode

```python
def populate_indicators(df):
    # BB
    df['bb_upper'], df['bb_mid'], df['bb_lower'] = BB(df, 20, 2)
    
    # Wick metrics
    df['body'] = abs(df['close'] - df['open'])
    df['upper_wick'] = df['high'] - df[['close','open']].max(axis=1)
    df['lower_wick'] = df[['close','open']].min(axis=1) - df['low']
    df['wick_ratio'] = df[['upper_wick','lower_wick']].max(axis=1) / df['body']
    
    # Volume
    df['volume_sma'] = SMA(df['volume'], 20)
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # ATR
    df['atr'] = ATR(df, 14)
    df['atr_pct'] = df['atr'] / df['close']
    
    return df

def populate_entry_trend(df):
    # LONG: Price at lower BB + strong lower wick + volume spike
    cond_long = (
        (df['close'] <= df['bb_lower'] * 1.005) &  # Near lower BB
        (df['lower_wick'] > df['body'] * 2.0) &     # Rejection wick
        (df['lower_wick'] > df['upper_wick']) &     # Bullish tilt
        (df['volume_ratio'] >= 1.5) &                # Volume confirm
        (df['atr_pct'] <= 0.008) &                  # Not too volatile
        (df['wick_ratio'] >= 3.0)                   # Wick dominance
    )
    df['enter_long'] = cond_long.astype(int)
    
    # SHORT: Price at upper BB + strong upper wick + volume spike
    cond_short = (
        (df['close'] >= df['bb_upper'] * 0.995) &  # Near upper BB
        (df['upper_wick'] > df['body'] * 2.0) &    # Rejection wick
        (df['upper_wick'] > df['lower_wick']) &     # Bearish tilt
        (df['volume_ratio'] >= 1.5) &               # Volume confirm
        (df['atr_pct'] <= 0.008) &                  # Not too volatile
        (df['wick_ratio'] >= 3.0)                   # Wick dominance
    )
    df['enter_short'] = cond_short.astype(int)
    
    return df

def custom_exit(trade, ...):
    # Time-based exit (5 min)
    if current_time - trade.open_date >= 300:
        return "time_exit"
    
    # Trailing stop
    if current_profit >= 0.0005:
        if current_profit - trailing_offset <= best_profit - 0.0002:
            return "trailing_exit"
    
    return None  # Let normal stops handle
```

---

## Appendix B: Why This Will Work When v28/v31 Failed

### v28 Failure Mode
```
- Only long (no short in bear market = missed opportunities)
- EMA trend filter missed reversals
- RSI bounds too wide (35-72)
- Stop loss too wide (-2%)
```

### v31 Failure Mode
```
- Short side: pin_bar_bear requirement too strict → 0 short trades
- Still has EMA trend filter
- Data only 24 days → not representative
- Same timeframe as v28 (5m) → slow signals
```

### v32 Solution
```
- NO trend filter (EMA never used for direction)
- Short side: symmetric logic, same BB+wicK rules
- 1m timeframe = more signals
- 0.15% stop = smaller risk per trade
- 5-min hard exit = controlled exposure
- Spread filter = avoids slippage
```

---

*Document Version: 1.0*
*Created: 2026-04-26*
*Strategy: Scalp_Momentum_B_v32*
*Author: Hermes Agent*
