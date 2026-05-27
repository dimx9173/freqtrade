# Backtest: Pullback_Scalp_v1_B (1:4 Risk/Reward)

## Strategy Configuration
| Parameter | Value |
|-----------|-------|
| stoploss | -0.015 (1.5%) |
| minimal_roi | {"0": 0.06} (6%) |
| trailing_stop_positive | 0.03 |
| trailing_stop_positive_offset | 0.04 |
| Risk:Reward Ratio | 1:4 |

## Backtest Summary

| Metric | Value |
|--------|-------|
| **Total Trades** | 20 |
| **Win Rate** | 50% (10W / 10L) |
| **Total Profit** | -6.483 USDT (-0.65%) |
| **Max Drawdown** | 7.302 USDT (0.73%) |
| **Starting Balance** | 1000 USDT |
| **Final Balance** | 993.517 USDT |
| **Avg Duration** | 5:44:00 |
| **Profit Factor** | 0.52 |
| **SQN** | -1.27 |

## Per-Pair Results

| Pair | Trades | Win% | Avg Profit% | Total USDT |
|------|--------|------|-------------|------------|
| XRP/USDT | 3 | 66.7% | 0.47% | +1.415 |
| SOL/USDT | 2 | 100% | 0.57% | +1.024 |
| BTC/USDT | 6 | 66.7% | -0.16% | -0.788 |
| BNB/USDT | 4 | 25.0% | -0.81% | -3.118 |
| ETH/USDT | 5 | 20.0% | -1.15% | -5.015 |

## Exit Reason Analysis

| Exit Reason | Count | Avg Profit% | Win Rate |
|-------------|-------|-------------|----------|
| exit_signal | 11 | 0.66% | 90.9% (10/11) |
| stop_loss | 9 | -1.62% | 0% (0/9) |

## Key Observations

1. **High stop-loss hit rate**: 9 out of 20 trades (45%) hit stop loss, indicating the 1.5% stop may be too tight for this strategy's entry timing
2. **Long/Short imbalance**: Long trades averaged -0.07% vs Short trades at -0.58%
3. **Strong exit signal performance**: When trades exited via exit_signal (RSI overbought/oversold or BB), win rate was 90.9%
4. **Limited drawdown**: Max drawdown only 0.73% due to tight stop loss, but this came at cost of frequent stops
5. **Market context**: BTC dropped ~25% during test period; strategy not optimized for bear markets

## Conclusion

The 1:4 R/R variant (1.5% stop / 6% target) performed poorly with **-0.65% total return** and **-6.483 USDT loss** over 99 days. While the drawdown was controlled at 0.73%, the high stop-loss hit rate (45%) suggests the strategy's pullback entries don't hold well with tight stops. This variant is not recommended without further optimization.
