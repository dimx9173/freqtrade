# Backtest Report: Pullback_Scalp_v1_A

## Strategy Configuration

| Parameter | Value |
|-----------|-------|
| Strategy | Pullback_Scalp_v1_A |
| Timeframe | 15m |
| Timerange | 2025-01-01 - 2025-04-27 |
| Pairs | BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT |
| Stoploss | -1% (1% risk) |
| Takeprofit | 4% (minimal_roi) |
| Trailing Stop | Disabled |
| Risk:Reward Ratio | 1:4 |
| Max Open Trades | 5 |
| Dry Run Wallet | 1000 USDT |
| Stake Amount | 100 USDT |

## Results Summary

| Metric | Value |
|--------|-------|
| **Total Trades** | 20 |
| **Win Rate** | 50.0% (10W / 10L) |
| **Total Profit** | -2.384 USDT (-0.24%) |
| **Max Drawdown** | 3.862 USDT (0.39%) |
| **Avg Duration** | 4h 53m |
| **Profit Factor** | 0.75 |
| **SQN** | -0.57 |

## Per-Pair Performance

| Pair | Trades | Avg Profit % | Tot Profit USDT | Win% |
|------|--------|--------------|-----------------|------|
| XRP/USDT | 3 | 0.64 | 1.915 | 66.7% |
| SOL/USDT | 2 | 0.57 | 1.024 | 100% |
| BTC/USDT | 6 | 0.01 | 0.099 | 66.7% |
| BNB/USDT | 4 | -0.56 | -2.155 | 25.0% |
| ETH/USDT | 5 | -0.75 | -3.267 | 20.0% |

## Exit Reason Stats

| Exit Reason | Exits | Avg Profit % | Win Rate |
|-------------|-------|--------------|----------|
| exit_signal | 11 | 0.66% | 90.9% |
| stop_loss | 9 | -1.12% | 0% |

## Risk Assessment

- **Absolute Drawdown**: 3.862 USDT (0.39%)
- **Drawdown Duration**: 39 days 20 hours
- **Market Change**: -25.32% (bear market period)

## Conclusion

Pullback_Scalp_v1_A with 1:4 Risk:Reward ratio underperformed during the Jan-Apr 2025 period:
- **Negative absolute return** (-2.384 USDT)
- **High stop loss hit rate** (45% of trades hit stop loss)
- **Only 50% win rate** required to break even with 1:4 RR, but actual win rate was exactly 50%
- **Strong market headwind** (-25.32% market change)

The tight 1% stoploss with 4% target appears too aggressive for this strategy's entry signals in the current market conditions.

---
*Generated: 2026-04-27*
