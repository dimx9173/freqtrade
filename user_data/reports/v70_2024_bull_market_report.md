# V70 2024 Bull Market Backtest Report

**Date:** May 5, 2026  
**Period Tested:** 2024-01-01 to 2024-12-31 (Full year 2024 - Bull market)  
**Asset:** BTC/USDT on Binance (15m timeframe)  
**Strategy:** FreqAI_ML_Strategy_v70

---

## Executive Summary

**Result: V70 NOT PROFITABLE in 2024 Bull Market**

| Metric | Value |
|--------|-------|
| Initial Capital | $10,000.00 |
| Final Capital | $3,354.64 |
| **Total Return** | **-66.45%** |
| Total Trades | 1,535 |
| Win Rate | 38.4% |

---

## Regime Distribution in 2024

The 2024 BTC market was overwhelmingly bullish with price rising from ~$42,000 to ~$93,000 (+120%):

| Regime | Candles | % of Time | Price Change |
|--------|---------|-----------|-------------|
| SIDEWAYS | 18,216 | 52.0% | +119.12% |
| VOLATILE | 8,822 | 25.2% | +116.55% |
| UPTREND | 4,516 | 12.9% | +120.06% |
| DOWNTREND | 3,486 | 9.9% | +106.10% |

**Note:** Despite being a bull market, regime detection showed only 12.9% was classified as "uptrend" by V70's strict criteria (ADX≥25, DI+>DI-, price>EMA).

---

## Performance by Regime

| Regime | Trades | Wins | Losses | Win% | Profit |
|--------|---------|------|--------|------|--------|
| UPTREND | 345 | 132 | 213 | 38.3% | -$1,821.94 |
| DOWNTREND | 253 | 85 | 168 | 33.6% | -$1,874.09 |
| SIDEWAYS | 938 | 372 | 566 | 39.7% | -$2,949.34 |
| VOLATILE | 0 | 0 | 0 | N/A | $0.00 |
| **TOTAL** | **1,535** | **589** | **946** | **38.4%** | **-$6,645.36** |

---

## Key Findings

1. **V70 Strategy Loses Money in 2024 Bull Market** - Despite BTC price increasing 120%, the strategy lost 66% of capital

2. **Low Win Rate (38.4%)** - Strategy wins less than 40% of trades, requiring high avg win size to break even

3. **Uptrend Regime Underperformance** - Even in the "uptrend" regime (supposedly ideal for V70), strategy lost money ($-1,821)

4. **Regime Detection Issues** - Only 12.9% of 2024 was classified as "uptrend" despite BTC going from $42k to $93k

5. **High Trade Frequency** - 1,535 trades in one year leads to significant fee drag

---

## Why V70 Lost Money in 2024

1. **Misclassification of Bull Market** - V70's regime detection is too strict; requires ADX≥25 AND DI+>DI- AND price>EMA simultaneously

2. **Fee Drag** - High frequency trading (1,535 trades × 0.2% fees) = significant capital erosion

3. **Mean Reversion Bias** - V70 exits positions quickly (2-8% profit targets) missing large trend moves

4. **Shorting During Bull Pullbacks** - DOWNTREND regime trades were predominantly shorts that lost money as dips were bought

---

## Files Created

- `user_data/reports/v70_2024_bull_market_results.json` - Raw results data
- `user_data/scripts/v70_2024_backtest.py` - Backtest script

---

## Conclusion

**V70 is NOT suitable for 2024-style bull market conditions.** The strategy's strict regime detection and aggressive profit-taking caused it to miss the major rally while still incurring heavy trading fees.

**Recommendation:** Consider modifications for bull markets:
- Relax uptrend detection criteria
- Hold positions longer during strong trends
- Reduce trade frequency with wider profit targets
- Reduce shorting activity during bull markets