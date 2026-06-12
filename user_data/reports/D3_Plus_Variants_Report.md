# D3+ Variants Backtest Results

## Test Setup
- **Timerange**: 2026-04-01 to 2026-05-04 (33 days)
- **Pairs**: BTC, ETH, SOL, XRP, BNB (USDT futures, 15m)
- **Starting Balance**: $10,000 USDT
- **Max Open Trades**: 5
- **Strategy**: Based on PSV1_SO_VarD3 (Price pullback ±2%)

---

## Results Summary

| Strategy | Total Profit | Profit % | Drawdown | Trades | Win Rate |
|----------|--------------|----------|----------|--------|----------|
| **D3_Baseline** | $156.80 | 1.57% | 0.83% | 8 | 75.0% |
| **D3_Kelly17** | $25.64 | 0.26% | 0.14% | 8 | 75.0% |
| **D3_Kelly25** | $38.07 | 0.38% | 0.21% | 8 | 75.0% |
| **D3_SL1.5_TP6** | $167.58 | 1.68% | 0.64% | 8 | 75.0% |
| **D3_Kelly17_SL1.5_TP6** | $27.44 | 0.27% | 0.11% | 8 | 75.0% |

---

## Key Findings

### 1. D3_SL1.5_TP6 (Tighter Stop, Wider Profit) - BEST PERFORMER
- **+1.68%** profit (+$167.58) - **+0.11% better than baseline**
- **Lower drawdown** (0.64% vs 0.83%)
- Settings: SL 1.5%, TP 6%/3.5%/2%

### 2. D3_Kelly17 (Kelly 17% Position)
- **+0.26%** profit ($25.64)
- 17% position size → profit scaled by ~6x for comparison
- **Lowest drawdown** (0.14%)
- Best for **risk-averse** strategies

### 3. D3_Kelly25 (Kelly 25% Position)
- **+0.38%** profit ($38.07)
- 25% position size → profit scaled ~4x for comparison
- **Low drawdown** (0.21%)

### 4. D3_Kelly17_SL1.5_TP6 (Combined)
- **+0.27%** profit ($27.44)
- **Lowest absolute drawdown** (0.11%)
- Conservative but lower absolute returns

---

## Conclusions

1. **Tighter SL + Wider TP works**: D3_SL1.5_TP6 improved profit by +$10.78 (+0.11%) vs baseline with lower drawdown

2. **Kelly sizing reduces exposure**: When accounting for position size (dividing by 0.17), Kelly17 actually produces comparable returns but with much lower risk

3. **Combined approach is most conservative**: D3_Kelly17_SL1.5_TP6 has the lowest drawdown (0.11%) - good for capital preservation

4. **Recommendation**: 
   - For **maximum profit**: Use D3_SL1.5_TP6
   - For **balanced risk/return**: Use D3_Baseline
   - For **minimum drawdown**: Use D3_Kelly17_SL1.5_TP6

---

## Parameter Changes

| Parameter | D3 Baseline | Kelly Variants | SL1_TP6 Variants |
|-----------|-------------|----------------|------------------|
| Stop Loss | -2.0% | -2.0% | -1.5% |
| Initial ROI | 5.5% | 5.5% | 6.0% |
| Position | 100% | 17% or 25% | 100% |