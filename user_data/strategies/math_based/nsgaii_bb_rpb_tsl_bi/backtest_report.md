# BB_RPB_TSL_BI + NSGAII 回測驗證報告

## 測試環境

- **工作目錄**: `/home/brian/freqtrade/user_data/`
- **策略路徑**: `strategies/math_based/nsgaii_bb_rpb_tsl_bi/BB_RPB_TSL_BI.py`
- **Config**: `strategies/math_based/nsgaii_bb_rpb_tsl_bi/config.json`
- **Timerange**: 2025-11-19 至 2026-05-19 (182天)
- **Timeframe**: 5m
- **Exchange**: Bybit (Spot)
- **起始資金**: 1000 USDT
- **Stake**: 50 USDT
- **Max Open Trades**: 5

## 回測結果 (2026-05-21 10:30)

| 指標 | 數值 |
|------|------|
| 總交易數 | 83 |
| 總利潤 | +6.80% (+67.968 USDT) |
| 勝率 | 95.2% (79勝 / 4敗) |
| 平均獲利 | 1.64% |
| 最大回撤 | 0.62% (6.311 USDT) |
| Sharpe Ratio | 5.77 |
| Sortino Ratio | 4.11 |
| Profit Factor | 4.96 |
| 市場變化 | -19.18% |

## 幣種表現

| 幣種 | 交易數 | 利潤 |
|------|--------|------|
| SOL/USDT | 7 | +0.62% |
| ETH/USDT | 5 | +0.43% |
| TOTAL | 83 | +6.80% |

## 主要出場原因

| 原因 | 次數 |
|------|------|
| signal_profit_q_momdiv_coh | 25 |
| trailing_stop_loss | 24 |
| signal_profit_q_momdiv | 12 |
| sell_stoploss_u_e_1 | 4 (虧損) |

## 與原始基線比較

| 指標 | 基線 (5/20) | NSGAII 優化後 | 改善 |
|------|------------|--------------|------|
| 交易數 | 9 | 83 | +74 |
| 總利潤 | +6.22% | +6.80% | +0.58% |
| 勝率 | 66.7% | 95.2% | +28.5% |
| 平均獲利 | 0.69% | 1.64% | +0.95% |

## 待確認數據

用戶提供但未找到檔案來源的數據：
- +12.65% 總利潤
- 28 交易數
- 96.4% 勝率
- SOL +8.50%
- ETH +4.15%

**狀態**: 待用戶提供原始截圖或檔案路徑

## 結論

NSGAII 優化顯著提升勝率 (66.7% → 95.2%) 和平均獲利 (0.69% → 1.64%)，但總利潤提升有限 (+6.22% → +6.80%)。最大回撤僅 0.62%，風險控制優秀。
