# MultiTF_RegimeDetector_v1 — Regime Detection + Volatility Prediction + Pure TA Entry

## Strategy Information

- **Strategy Name**: MultiTF_RegimeDetector_v1
- **Strategy Type**: math_based
- **Version**: v1
- **Created**: 2026-05-29
- **Main Timeframe**: 15m
- **Informative Timeframes**: 30m, 1h, 4h
- **Exchange**: Bybit (Futures, USDT Perpetual)
- **Trading Pair**: BTC/USDT:USDT
- **Position**: Long-only (v1), can_short=True for future expansion

## File Structure

```
multi_tf_regime_v1/
├── MultiTF_RegimeDetector_v1.py   # Strategy main file (~430 lines)
├── config.json                     # Dry-run config (futures, port 13990)
└── README.md                       # This file
```

## Architecture

```
MultiTF_RegimeDetector_v1
├── Main TF: 15m
├── Informative: 30m, 1h, 4h
│
├── 1. Regime Detection (ADX multi-TF consensus)
│   └── ranging (ADX<20) | transition (20-25) | trending (>25)
│       Majority vote across 15m/1h/4h ADX
│       Validated: 99.8% accuracy with linear model
│
├── 2. Volatility Prediction (Ridge, R²=0.67)
│   └── PolynomialFeatures(degree=2) + Ridge(α=0.1) → pred_ATR
│       Predicts ATR 12 bars (3h) ahead
│       Used for: dynamic stops + position sizing
│
├── 3. Entry Logic (Pure TA, switched by Regime)
│   ├── Ranging (regime=0): BB mean-reversion
│   │   └── close < bb_lower(20, 2σ) & RSI(14) < 35
│   ├── Trending (regime=2): EMA trend-following
│   │   └── EMA12 > EMA26 & ADX(15m) > 25 & +DI > -DI
│   └── Transition (regime=1): no trades
│
├── 4. Exit Logic
│   ├── Exit Signals:
│   │   ├── Ranging: RSI recovers > 60
│   │   └── Trending: EMA crossover bearish or ADX < 20
│   ├── Dynamic Stop Loss (custom_stoploss):
│   │   ├── Base: -3%
│   │   ├── Normal: max(-3%, -2×pred_ATR)
│   │   ├── In 1.5% profit: trail at -1.5×pred_ATR
│   │   └── In 3% profit: trail at -1×pred_ATR
│   ├── ROI: 5% at 0m, 3% at 120m, 1% at 240m
│   └── Time Exit: 48h max hold
│
└── 5. Position Sizing (inverse volatility)
    └── stake = base × (2.5% / pred_ATR), clamped [50%, 100%]
```

## Key Design Decisions

| Decision | Rationale | Source |
|----------|-----------|--------|
| Regime = ADX consensus | 99.8% accuracy, linear model sufficient | `/tmp/debug_regime.py` |
| Volatility = Ridge(deg=2, α=0.1) | R²=0.67, best among tested | `/tmp/debug_regime.py` |
| No direction prediction | 47.8-49.1% accuracy = coin flip | `/tmp/debug_regime.py` |
| Entry = Pure TA only | Avoid ML overfitting on noisy direction signal | Design choice |
| Shorts disabled (v1) | Simplify initial validation | Version scope |

## Validated Results (from `/tmp/debug_regime.py`)

### Regime Detection
- **Linear model**: 99.8% accuracy
- **Poly deg=2**: 99.8% accuracy
- **Conclusion**: Linear ADX classification is sufficient; no ML needed

### Volatility (ATR) Prediction (R² scores)
- Linear: R²=0.5787
- Ridge α=0.1: R²=0.5761
- Ridge α=0.01: R²=0.5794
- **Linear + poly2: R²=0.6705** ← Selected
- Ridge α=0.1 + poly2: R²=0.6705

### Direction Prediction
- **47.8–49.1% accuracy** (statistically insignificant)
- **Verdict**: Abandoned — direction is unpredictable at 15m scale

## Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `timeframe` | 15m | Main trading timeframe |
| `can_short` | True | Futures mode (shorts disabled for v1) |
| `stoploss` | -0.03 | Base fallback stop loss |
| `ADX_RANGING_MAX` | 20 | ADX below = ranging |
| `ADX_TRENDING_MIN` | 25 | ADX above = trending |
| `BB_PERIOD` | 20 | Bollinger Band period |
| `BB_STD` | 2.0 | Bollinger Band standard deviations |
| `RSI_OVERSOLD` | 35 | RSI threshold for ranging entry |
| `EMA_FAST` | 12 | Fast EMA for trend entry |
| `EMA_SLOW` | 26 | Slow EMA for trend entry |
| `VOL_FORECAST_HORIZON` | 12 | Predict ATR N bars ahead (3h) |
| `VOL_WINDOW` | 300 | Training window (bars) |
| `VOL_RIDGE_ALPHA` | 0.1 | Ridge regularization |
| `VOL_RETRAIN_INTERVAL` | 50 | Retrain every N bars |
| `VOL_POLY_DEGREE` | 2 | Polynomial feature degree |

## How to Run

```bash
# Backtest
freqtrade backtesting \
  --config user_data/strategies/math_based/multi_tf_regime_v1/config.json \
  --strategy MultiTF_RegimeDetector_v1 \
  --timerange 20251101-20260529

# Dry-run (live simulation)
freqtrade trade \
  --config user_data/strategies/math_based/multi_tf_regime_v1/config.json \
  --strategy MultiTF_RegimeDetector_v1
```

## Dependencies

- `scikit-learn` — for Ridge regression volatility prediction
- `talib` (or `ta-lib`) — for technical indicators
- `pandas`, `numpy` — data processing

## Notes

- **API Keys**: Left empty in config — fill in for live trading
- **Port**: 13990 (dedicated, no conflict with other bots)
- **sklearn**: Lazy import — won't crash if sklearn not installed (volatility prediction disabled gracefully)
- **Lookahead**: `merge_asof(direction='backward')` ensures zero future data leakage
- **First Run**: Needs ≥400 bars of history for full indicator calculation
