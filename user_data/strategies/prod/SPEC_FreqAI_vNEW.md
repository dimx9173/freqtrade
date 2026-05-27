# FreqAI_ML_Strategy_v80 - Strategy Specification

## Overview

**Strategy Name:** FreqAI_ML_Strategy_v80  
**Type:** FreqAI ML-powered crypto trading strategy  
**Goal:** Maximum -3% loss in bear market conditions  
**Pair:** BTC/USDT:USDT (futures)  
**Timeframe:** 1h  
**Backtest Timerange:** 20251101-20260501  

### Core Philosophy

This strategy addresses the corruption issues discovered in V70 (performance degraded from -1.88% to -5.22%) by implementing:

1. **Stricter Entry Thresholds** - Raise thresholds to reduce false signals and improve signal quality
2. **Regime-Aware Position Sizing** - Dynamic sizing based on market conditions
3. **Enhanced Risk Management** - Kelly Criterion with conservative drawdown protection
4. **ML + Technical Confirmation** - Dual-layer validation to filter unreliable predictions

The strategy prioritizes capital preservation in adverse conditions while maintaining growth potential in favorable trends.

---

## 1. Regime Detection

### ADX Thresholds (Lowered from 28)

| Regime | ADX Threshold | Notes |
|--------|---------------|-------|
| **Uptrend** | >= 22 | Long entries only |
| **Downtrend** | >= 22 | Short entries only |
| **Sideways** | < 22 | Reduced position, range-bound |
| **Volatile** | ADX 15-25 + High Vol Override | Maximum caution |

### High Volatility Override

High Vol Override is **only** triggered when ADX is marginal (15-25):
- ADX 15-25 indicates uncertain trend direction
- Combined with elevated ATR percentile + BB width → Volatile regime
- Position size reduced to 0.3x multiplier

### Composite Volatility Indicators

```python
# ATR Percentile + Bollinger Band Width composite
atr_percentile = calculate_percentile(df['atr'], window=20)
bb_width_percentile = calculate_percentile(df['bb_width'], window=20)
volatility_composite = (atr_percentile + bb_width_percentile) / 2

# High Vol Override triggers when:
# - ADX in marginal zone (15-25) AND
# - volatility_composite > 0.75
```

---

## 2. Entry Signals

### Threshold Changes (Raised from V70)

| Regime | Prediction Threshold | Confidence Threshold | Change |
|--------|---------------------|---------------------|--------|
| **Uptrend** | 0.65 | 0.70 | Raised from 0.55 |
| **Downtrend** | 0.72 | 0.75 | Raised from 0.65 |
| **Sideways** | 0.70 | 0.75 | Maintained |
| **Volatile** | 0.72 | 0.75 | Maintained |

### Entry Conditions

**Uptrend Long Entry:**
```python
uptrend_entry = (
    (regime == 'uptrend') &
    (ml_prediction > 0.65) &
    (ml_confidence > 0.70) &
    (DataFrame['adx'] >= 22) &
    (DataFrame['plus_di'] > DataFrame['minus_di']) &  # DI+ confirmation
    (DataFrame['ema_12'] > DataFrame['ema_26']) &      # EMA confirmation
    (DataFrame['volume_ratio'] > 1.2) &
    (DataFrame['smc_score'] >= 0.50) &
    price_above_vwap
)
```

**Downtrend Short Entry:**
```python
downtrend_entry = (
    (regime == 'downtrend') &
    (ml_prediction < 0.35) &  # Inverted for short
    (ml_confidence > 0.75) &
    (DataFrame['adx'] >= 22) &
    (DataFrame['minus_di'] > DataFrame['plus_di']) &  # DI- confirmation
    (DataFrame['ema_12'] < DataFrame['ema_26']) &      # EMA confirmation
    (DataFrame['volume_ratio'] > 1.2)
)
```

### DI+/DI- Confirmation

Directional Indicator (DI) confirmation is used to validate trend direction:
- Uptrend: `plus_di > minus_di` confirms bullish momentum
- Downtrend: `minus_di > plus_di` confirms bearish momentum

### EMA Confirmation

- Uptrend: `ema_12 > ema_26` (12-period EMA above 26-period EMA)
- Downtrend: `ema_12 < ema_26` (12-period EMA below 26-period EMA)

### No Trade Zone

When prediction is in the neutral zone (0.40-0.60) AND confidence < 0.70, the trade is rejected:
```python
in_no_trade_zone = (
    (ml_prediction > 0.40) & (ml_prediction < 0.60) &
    (ml_confidence < 0.70)
)
```

---

## 3. Exit Signals

### Regime-Specific Profit Targets

| Regime | Target Profit | Time Limit |
|--------|--------------|-------------|
| **Uptrend** | 8% | 360 min (6h) |
| **Downtrend** | 4% | 120 min (2h) |
| **Sideways** | 2% | 90 min |
| **Volatile** | 3% | 60 min |

### Stop Loss (Regime-Specific)

| Regime | Stop Loss | Notes |
|--------|-----------|-------|
| **Uptrend** | -3% | Tighter to protect gains |
| **Downtrend** | -5% | Wider due to volatility |
| **Sideways** | -2% | Tight range trading |
| **Volatile** | -10% | Wide stop, reduced position |

### Trailing Stop Configuration

```python
trailing_stop = True
trailing_stop_positive = 0.005     # 0.5% base
trailing_stop_positive_offset = 0.015  # 1.5% offset
trailing_only_offset_is_reached = True

# Regime-specific offsets:
# Uptrend:    0.025 (2.5%) - allow profits to run
# Downtrend:  0.012 (1.2%) - quick profit taking
# Sideways:   0.008 (0.8%) - scalping
# Volatile:   0.015 (1.5%) - defensive
```

### Custom Exit Triggers

1. **ML Reversal Exit** - When ML prediction reverses with high confidence:
   ```python
   if (ml_pred < 0.35 and ml_conf > 0.70) or (ml_pred > 0.65 and ml_conf > 0.70):
       return "ML_REVERSAL"
   ```

2. **Regime Change Exit** - Exit when market regime shifts unexpectedly:
   ```python
   if new_regime == 'volatile' and not trade_tag.startswith('VOLATILE'):
       return "REGIME_VOLATILE_EXIT"
   ```

3. **Trend Reversal Exit** - Exit on trend direction change:
   ```python
   if prev_regime == 'uptrend' and current_regime == 'downtrend':
       return "TREND_REVERSAL"
   ```

---

## 4. Risk Management

### Kelly Criterion Dynamic Position Sizing

```python
def calculate_kelly_fraction(win_rate, avg_win, avg_loss, safety_factor=0.5):
    """
    Kelly with Half-Kelly safety factor
    """
    if avg_loss == 0:
        return 0
    
    kelly_ratio = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    
    # Original Kelly
    kelly = (kelly_ratio * p - q) / kelly_ratio
    
    # Half-Kelly (0.5x safety factor)
    return max(0, kelly * safety_factor)
```

**Constraints:**
- Kelly fraction capped between 0.05 (5%) and 0.20 (20%)
- Only applied when `dynamic_position_sizing` is enabled
- Recalculated based on 30-day rolling window

### Max Drawdown Protection

| Drawdown Level | Action |
|----------------|--------|
| **10%** | Warning - monitor closely |
| **15%** | Reduce positions by 50% |
| **20%** | Reduce positions by 75% |
| **25%** | Stop all trades, review strategy |

### Volatile Regime Position Size

In volatile market conditions (High Vol Override triggered):
- **Position size: 0.3x** (70% reduction)
- Only enter with highest confidence signals
- Stop loss widened to -10%

### Dynamic Stake Amount

```python
def custom_stake_amount(self, pair, current_time, current_rate, ...):
    # Base stake
    base = self.base_risk_factor.value  # 5% of wallet
    
    # Regime multiplier
    regime_mult = {
        'uptrend': 1.3,
        'downtrend': 0.35,  # Reduced from 0.5
        'sideways': 0.7,
        'volatile': 0.3
    }.get(regime, 0.5)
    
    # ML confidence adjustment (0.5 to 1.5)
    conf_mult = 0.5 + ml_confidence * 1.0
    
    # DI protection (reduce if DI anomaly)
    di_mult = 1.0 if di_value < 0.85 else 0.7
    
    final_stake = proposed_stake * base * regime_mult * conf_mult * di_mult
    return max(min_stake, min(max_stake, final_stake))
```

### Consecutive Loss Protection

| Consecutive Losses | Position Reduction | Cooldown |
|--------------------|-------------------|----------|
| **3 losses** | 50% | None |
| **5 losses** | 75% | 30 min |
| **7 losses** | 100% | 60 min |

---

## 5. Implementation Plan

### Phase 1: Core Infrastructure
1. Create `FreqAI_ML_Strategy_v80.py` with Freqtrade base class
2. Implement `populate_indicators()` with all required indicators:
   - ADX, Plus_DI, Minus_DI
   - EMA 12 and 26
   - ATR, Bollinger Bands
   - Volume ratio, SMC score
3. Implement regime detection logic

### Phase 2: Entry/Exit Logic
4. Implement `populate_entry_trend()` with regime-aware thresholds
5. Implement `populate_exit_trend()` with trailing stop
6. Add `custom_exit()` method for advanced exit logic
7. Implement No Trade Zone filtering

### Phase 3: Risk Management
8. Implement `custom_stake_amount()` with Kelly sizing
9. Add max drawdown protection
10. Implement consecutive loss protection

### Phase 4: Configuration
11. Create `FreqAI_ML_Strategy_v80.json` config
12. Define all hyperparameters as DecimalParameters
13. Set backtest timerange: 20251101-20260501

### Key Files

| File | Path |
|------|------|
| Strategy | `~/freqtrade/user_data/strategies/prod/FreqAI_ML_Strategy_v80.py` |
| Config | `~/freqtrade/user_data/strategies/prod/FreqAI_ML_Strategy_v80.json` |
| Spec | `~/freqtrade/user_data/strategies/prod/SPEC_FreqAI_vNEW.md` |

---

## 6. Parameter Summary

### Entry Thresholds

| Parameter | Default | Range | Regime |
|-----------|---------|-------|--------|
| `uptrend_prediction_threshold` | 0.65 | 0.55-0.80 | Uptrend |
| `uptrend_confidence_threshold` | 0.70 | 0.55-0.85 | Uptrend |
| `downtrend_prediction_threshold` | 0.72 | 0.55-0.80 | Downtrend |
| `downtrend_confidence_threshold` | 0.75 | 0.55-0.90 | Downtrend |
| `sideways_prediction_threshold` | 0.70 | 0.60-0.85 | Sideways |
| `volatile_prediction_threshold` | 0.72 | 0.65-0.85 | Volatile |

### Position Multipliers

| Parameter | Default | Range | Regime |
|-----------|---------|-------|--------|
| `uptrend_position_mult` | 1.3 | 0.8-1.5 | Uptrend |
| `downtrend_position_mult` | 0.35 | 0.2-0.6 | Downtrend |
| `sideways_position_mult` | 0.7 | 0.4-0.9 | Sideways |
| `volatile_position_mult` | 0.3 | 0.2-0.5 | Volatile |

### Trailing Stop Offsets

| Parameter | Default | Range | Regime |
|-----------|---------|-------|--------|
| `uptrend_trailing_offset` | 0.025 | 0.015-0.04 | Uptrend |
| `downtrend_trailing_offset` | 0.012 | 0.008-0.02 | Downtrend |
| `sideways_trailing_offset` | 0.008 | 0.005-0.015 | Sideways |
| `volatile_trailing_offset` | 0.015 | 0.01-0.025 | Volatile |

---

## References

- Entry/Exit Signals: `~/Brian_Notes/Research/FreqAI/03_Entry_Exit_Signals.md`
- Risk Management: `~/Brian_Notes/Research/FreqAI/04_Risk_Management.md`
- Regime Detection: `~/Brian_Notes/Research/FreqAI/02_Regime_Detection.md`
- V70 Strategy: `~/freqtrade/user_data/strategies/prod/FreqAI_ML_Strategy_v70.py`
