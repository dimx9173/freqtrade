# Backtest Results: Pullback_Scalp_v1_C (Variant C)

## Strategy Configuration
- **Strategy**: Pullback_Scalp_v1_C
- **Timeframe**: 15m
- **Period**: 2025-01-17 to 2025-04-27 (99 days)
- **Pairs**: BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT

## Risk Parameters
| Parameter | Value |
|-----------|-------|
| Stop Loss | -2% |
| Take Profit | 8% |
| Trailing Stop | Enabled |
| Trailing Stop Positive | 4% |
| Trailing Stop Positive Offset | 5% (activate at 5% profit) |
| Trailing Only Offset Reached | True |

## Backtest Results

### Summary Metrics
| Metric | Value |
|--------|-------|
| Total Trades | 20 |
| Win Rate | 55.0% (11 wins, 9 losses) |
| **Total Profit** | **-1.741 USDT (-0.17%)** |
| Starting Balance | 1000 USDT |
| Final Balance | 998.259 USDT |
| **Max Drawdown** | **6.47 USDT (0.65%)** |
| Avg Duration | 8:28:00 |
| Profit Factor | 0.82 |
| SQN | -0.35 |

### Per-Pair Results
| Pair | Trades | Avg Profit % | Total Profit USDT | Win Rate |
|------|--------|--------------|-------------------|----------|
| SOL/USDT | 2 | 0.57% | 1.024 | 100% |
| XRP/USDT | 3 | 0.30% | 0.914 | 66.7% |
| BTC/USDT | 6 | -0.05% | -0.113 | 66.7% |
| BNB/USDT | 4 | -0.27% | -1.056 | 25.0% |
| ETH/USDT | 5 | -0.57% | -2.511 | 40.0% |

### Exit Reason Stats
| Exit Reason | Count | Avg Profit % | Total Profit USDT |
|-------------|-------|--------------|-------------------|
| exit_signal | 16 | 0.39% | 5.905 |
| stop_loss | 4 | -2.12% | -7.646 |

### Long/Short Breakdown
| Direction | Trades | Profit % | Profit USDT |
|-----------|--------|----------|-------------|
| Long | 10 | 0.20% | 2.024 |
| Short | 10 | -0.38% | -3.765 |

## Analysis

### Key Findings
1. **Loss**: Strategy lost -1.741 USDT (-0.17%) over 99 days with 5 max open trades
2. **Drawdown**: Max drawdown 0.65% (6.47 USDT) - relatively contained
3. **Win Rate**: 55% win rate but individual winners are small while losers are larger
4. **Stop Loss Hits**: 4 trades hit stop loss averaging -2.12% loss per trade
5. **Best Pair**: SOL/USDT performed best with 100% win rate and +0.10% profit
6. **Worst Pair**: ETH/USDT performed worst with 40% win rate and -0.25% profit

### Comparison (1:4 RR Target)
- The 8% take profit target was rarely hit (only 16 exits via exit_signal, but average was only 0.39%)
- The 1:4 risk-reward ratio did not deliver expected results due to low hit rate on large moves
- The 2% stop loss was hit 4 times (20% of trades) resulting in significant losses

## Conclusion
Variant C (2% SL / 8% TP / trailing stop) with 1:4 RR ratio showed **negative returns** during the test period. The high take profit target was rarely reached, while stop losses were hit more frequently than expected. The trailing stop mechanism may have cut winning trades short. Consider:
- Lower take profit target (e.g., 5-6%)
- Tighter trailing stop activation
- Adjust entry conditions to improve win rate
