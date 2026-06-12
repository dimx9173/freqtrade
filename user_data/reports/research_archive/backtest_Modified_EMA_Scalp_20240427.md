# Backtest Report: Modified_EMA_Scalp

## Configuration
- **Strategy**: Modified_EMA_Scalp
- **Timeframe**: 5m
- **Trading Mode**: Isolated Futures
- **Pairs**: BTC/USDT:USDT, ETH/USDT:USDT, BNB/USDT:USDT, SOL/USDT:USDT, XRP/USDT:USDT
- **Timerange**: 2025-01-01 00:00:00 → 2025-04-27 00:00:00
- **Starting Balance**: 1000 USDT
- **Stake Amount**: 100 USDT
- **Max Open Trades**: 5

> **Note**: Requested timerange was 20240101-20240427, but available data starts from 2025-01-01. Backtest ran on available data (2025-01-01 to 2025-04-27, 116 days).

---

## Summary Metrics

| Metric | Value |
|--------|-------|
| **Total Trades** | 1423 |
| **Daily Avg Trades** | 12.27 |
| **Final Balance** | 733.669 USDT |
| **Total Profit** | -266.331 USDT (-26.63%) |
| **CAGR** | -62.26% |
| **Sharpe Ratio** | -23.92 |
| **Sortino Ratio** | -132.85 |
| **Calmar Ratio** | -13.72 |
| **SQN** | -3.85 |
| **Profit Factor** | 0.79 |
| **Expectancy (Ratio)** | -0.19 (-0.06) |
| **Max Drawdown** | 321.353 USDT (31.98%) |
| **Max Consecutive Wins** | 29 |
| **Max Consecutive Losses** | 10 |

---

## Pair Breakdown

| Pair | Trades | Avg Profit % | Tot Profit USDT | Tot Profit % | Avg Duration | Win% |
|------|--------|--------------|----------------|--------------|--------------|------|
| BNB/USDT:USDT | 214 | -0.09 | -20.121 | -2.01 | 9:30:00 | 72.4% |
| XRP/USDT:USDT | 350 | -0.12 | -40.696 | -4.07 | 3:20:00 | 70.6% |
| BTC/USDT:USDT | 181 | -0.26 | -44.401 | -4.44 | 11:09:00 | 68.0% |
| SOL/USDT:USDT | 354 | -0.23 | -71.287 | -7.13 | 3:54:00 | 68.4% |
| ETH/USDT:USDT | 324 | -0.34 | -89.826 | -8.98 | 5:11:00 | 66.0% |
| **TOTAL** | **1423** | **-0.21** | **-266.331** | **-26.63%** | **5:49:00** | **68.9%** |

---

## Exit Reason Stats

| Exit Reason | Exits | Avg Profit % | Tot Profit USDT | Win% |
|-------------|-------|--------------|-----------------|------|
| roi | 980 | 1.09 | 1008.010 | 100% |
| stop_loss | 439 | -3.12 | -1273.636 | 0% |
| force_exit | 4 | -0.19 | -0.705 | 25% |

---

## Long/Short Analysis

| Direction | Trades | Profit USDT | Profit % |
|-----------|--------|-------------|----------|
| Long | 780 | -218.206 | -21.82% |
| Short | 643 | -48.125 | -4.81% |

---

## Drawdown Details

- **Max Balance**: 1004.87 USDT
- **Min Balance**: 683.517 USDT
- **Absolute Drawdown**: 321.353 USDT (31.98%)
- **Drawdown Duration**: 101 days 00:20:00
- **Drawdown Start**: 2025-01-01 14:00:00
- **Drawdown End**: 2025-04-12 14:20:00

---

## Assessment

The Modified_EMA_Scalp strategy produced **1423 trades** with a **68.9% win rate**, but the overall performance was **negative** with a **-26.63% total profit** and a **Sharpe ratio of -23.92**. The strategy suffered significant losses primarily from stop_loss exits (439 trades, -1273.636 USDT), which overwhelmed the profitable roi exits (980 trades, +1008.010 USDT). The strategy experienced a maximum drawdown of 31.98%, indicating high risk in the tested period.

**Key Issues**:
- High stop loss rate (439/1423 = 30.8%)
- Very negative Sharpe ratio (-23.92) indicates poor risk-adjusted returns
- Short positions performed better than long positions during this period
