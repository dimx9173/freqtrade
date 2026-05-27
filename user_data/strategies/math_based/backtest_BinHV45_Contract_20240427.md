# Backtest Report: BinHV45_Contract

## Configuration
- **Strategy**: BinHV45_Contract
- **Timeframe**: 1m
- **Trading Mode**: Futures
- **Pairs**: BTC/USDT:USDT, ETH/USDT:USDT, BNB/USDT:USDT, SOL/USDT:USDT, XRP/USDT:USDT
- **Time Range**: 2024-04-01 to 2024-04-27 (26 days)
- **Starting Balance**: 1000 USDT
- **Stake Amount**: 100 USDT
- **Max Open Trades**: 5
- **Exchange**: Bybit

## Strategy Parameters
- **Minimal ROI**: 1.25% (0.0125)
- **Stop Loss**: 5%
- **Leverage**: 5x
- **BB Window**: 40, BB StdDev: 2
- **Buy BB Delta Threshold**: 0.0007
- **Buy CloseDelta Threshold**: 0.0017
- **Buy Tail Threshold**: 0.25

## Backtest Results

### Summary
| Metric | Value |
|--------|-------|
| **Total Trades** | 0 |
| **Total Profit (USDT)** | 0.000 |
| **Total Profit (%)** | 0.00% |
| **Win Rate** | N/A (no trades) |
| **Max Drawdown** | 0 USDT (0.00%) |
| **Avg Duration** | N/A |
| **Sharpe Ratio** | N/A |

### Per-Pair Results
| Pair | Trades | Avg Profit % | Tot Profit USDT | Tot Profit % | Avg Duration | Win | Draw | Loss | Win% |
|------|--------|--------------|-----------------|--------------|--------------|-----|------|------|------|
| BTC/USDT:USDT | 0 | 0.0 | 0.000 | 0.0 | 0:00 | 0 | 0 | 0 | 0 |
| ETH/USDT:USDT | 0 | 0.0 | 0.000 | 0.0 | 0:00 | 0 | 0 | 0 | 0 |
| BNB/USDT:USDT | 0 | 0.0 | 0.000 | 0.0 | 0:00 | 0 | 0 | 0 | 0 |
| SOL/USDT:USDT | 0 | 0.0 | 0.000 | 0.0 | 0:00 | 0 | 0 | 0 | 0 |
| XRP/USDT:USDT | 0 | 0.0 | 0.000 | 0.0 | 0:00 | 0 | 0 | 0 | 0 |

### Enter Tag Stats
No entries recorded.

### Exit Reason Stats
No exits recorded.

## Analysis
The backtest produced **0 trades** during the period 2024-04-01 to 2024-04-27. This could be due to:

1. **Bollinger Bands conditions not met**: The strategy requires price to cross BB lower/upper bands with specific delta conditions that may not have occurred during this period.

2. **Market conditions**: The April 2024 period may not have had sufficient volatility for the BB mean-reversion signals to trigger.

3. **BB Window size**: The 40-period BB with 1m timeframe requires significant trend continuation before a mean-reversion setup forms.

## Data Information
- **Data Source**: Bybit futures
- **Downloaded Data Length**: 37,999 candles per pair (1m)
- **Data Start**: 2024-04-01 00:00:00
- **Data End**: 2024-04-27 00:00:00

## Notes
- Backtest completed successfully with no errors
- All pairs had sufficient historical data for the specified time range
- The strategy did not generate any entry signals during this period

---
*Report generated: 2026-04-27*
