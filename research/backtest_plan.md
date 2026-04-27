# 回測執行計劃

## 專案資訊
- **日期**：2026-04-27
- **策略變體**：A / B / D
- **交易模式**：合約（多空雙向）
- **槓桿**：5x
- **交易對**：Top 5 幣種

---

## 策略檔案位置

| 變體 | 檔案路徑 |
|------|---------|
| **A (BinHV45-Contract)** | `~/project/freqtrade_strategies/BinHV45_Contract.py` |
| **B (Modified-EMA-Scalp)** | `~/project/freqtrade_strategies/Modified_EMA_Scalp.py` |
| **D (BiDirectional-BB-Scalp)** | `~/project/freqtrade_strategies/BiDirectional_BB_Scalp.py` |
| **設計文件** | `~/project/design_scalping_variants.md` |

---

## 回測參數配置

### 時間範圍
```
開始：2024-01-01
結束：2026-04-27
總計：~28 個月（包含完整空頭市場週期）
```

### 交易對（Top 5）
```python
pair_whitelist = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT", 
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT"
]
```

### 本金與風險
```
本金（dry_run_wallet）：1000 USDT
單筆倉位：proposed_stake（由 freqtrade 自動計算）
最大持倉：10 筆
槓桿：5x
```

### 手續費
```
合約 taker fee：0.05%
合約 maker fee：0.02%
```

---

## 回測執行命令

### 變體 A：BinHV45_Contract
```bash
cd ~/project
freqtrade backtesting \
  --strategy BinHV45_Contract \
  --config config.json \
  --timerange 20240101-20260427 \
  --timeframe 1m \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT XRP/USDT:USDT DOGE/USDT:USDT \
  --dry-run-wallet 1000 \
  --max-open-trades 10
```

### 變體 B：Modified_EMA_Scalp
```bash
cd ~/project
freqtrade backtesting \
  --strategy Modified_EMA_Scalp \
  --config config.json \
  --timerange 20240101-20260427 \
  --timeframe 5m \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT XRP/USDT:USDT DOGE/USDT:USDT \
  --dry-run-wallet 1000 \
  --max-open-trades 10
```

### 變體 D：BiDirectional_BB_Scalp
```bash
cd ~/project
freqtrade backtesting \
  --strategy BiDirectional_BB_Scalp \
  --config config.json \
  --timerange 20240101-20260427 \
  --timeframe 5m \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT XRP/USDT:USDT DOGE/USDT:USDT \
  --dry-run-wallet 1000 \
  --max-open-trades 10
```

---

## 評估指標

### 核心指標
| 指標 | 說明 | 目標值 |
|------|------|--------|
| **總利潤** | 回測期間總報酬率 | > 0% |
| **勝率** | 盈利交易 / 總交易 | > 40% |
| **最大回撤** | 最大資金回落幅度 | < 30% |
| **夏普比率** | 風險調整後報酬 | > 1.0 |
| **交易次數** | 總交易筆數 | > 100 |
| **平均持倉時間** | 每筆交易平均持續時間 | < 2h |
| **連續虧損次數** | 最大連續虧損筆數 | < 10 |

### 空頭市場專項指標
| 指標 | 說明 |
|------|------|
| **空頭期間交易數** | 2024-2025 空頭期間的交易筆數 |
| **空頭期間勝率** | 空頭期間的盈利比例 |
| **空頭期間利潤** | 空頭期間的總利潤 |
| **多頭/空頭交易比例** | 做多 vs 做空的交易比例 |

---

## 比較基準

### 1. 原始策略（均值回歸 + EMA 濾網）
```bash
freqtrade backtesting \
  --strategy Original_EMA_Scalp \
  --config config.json \
  --timerange 20240101-20260427 \
  --timeframe 5m
```

### 2. 買入持有（Buy & Hold）
```bash
freqtrade backtesting \
  --strategy DoesNothingStrategy \
  --config config.json \
  --timerange 20240101-20260427
```

---

## 回測結果記錄表

### 變體 A：BinHV45_Contract
| 指標 | 數值 | 備註 |
|------|------|------|
| 總利潤 | ___% | |
| 勝率 | ___% | |
| 最大回撤 | ___% | |
| 夏普比率 | ___ | |
| 交易次數 | ___ | |
| 平均持倉時間 | ___ | |
| 連續虧損次數 | ___ | |
| 多頭交易數 | ___ | |
| 空頭交易數 | ___ | |

### 變體 B：Modified_EMA_Scalp
| 指標 | 數值 | 備註 |
|------|------|------|
| 總利潤 | ___% | |
| 勝率 | ___% | |
| 最大回撤 | ___% | |
| 夏普比率 | ___ | |
| 交易次數 | ___ | |
| 平均持倉時間 | ___ | |
| 連續虧損次數 | ___ | |
| 多頭交易數 | ___ | |
| 空頭交易數 | ___ | |

### 變體 D：BiDirectional_BB_Scalp
| 指標 | 數值 | 備註 |
|------|------|------|
| 總利潤 | ___% | |
| 勝率 | ___% | |
| 最大回撤 | ___% | |
| 夏普比率 | ___ | |
| 交易次數 | ___ | |
| 平均持倉時間 | ___ | |
| 連續虧損次數 | ___ | |
| 多頭交易數 | ___ | |
| 空頭交易數 | ___ | |

---

## 後續優化計劃

### Phase 1：參數優化（Hyperopt）
```bash
# 變體 A
freqtrade hyperopt \
  --strategy BinHV45_Contract \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces buy stoploss roi \
  -e 100

# 變體 B
freqtrade hyperopt \
  --strategy Modified_EMA_Scalp \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces buy sell stoploss roi \
  -e 100

# 變體 D
freqtrade hyperopt \
  --strategy BiDirectional_BB_Scalp \
  --hyperopt-loss SharpeHyperOptLoss \
  --spaces buy sell stoploss roi \
  -e 100
```

### Phase 2：市場狀態識別整合
- 整合 ADX + BB Width + EMA Slope 的市場狀態分類
- 根據市場狀態動態調整策略參數
- 盤整市場 → 均值回歸策略
- 趨勢市場 → 趨勢跟隨或暫停

### Phase 3：組合策略測試
- 測試多策略同時運行
- 評估策略間的相關性
- 優化資金分配

---

## 風險管理檢查清單

- [ ] 止損設置合理（考慮 5x 槓桿）
- [ ] 最大持倉限制已設定
- [ ] 資金費率已考慮
- [ ] 爆倉風險已評估
- [ ] 連續虧損暫停機制已設定
- [ ] 日虧損上限已設定

---

## 備註

### 已知限制
1. **1m 資料量龐大**：回測可能需要較長時間
2. **合約回測準確性**：freqtrade 合約回測可能與實際有差異
3. **資金費率未計入**：回測可能未完全模擬資金費率影響

### 建議
1. 先執行 1 個月的快速回測驗證策略邏輯
2. 確認策略能正常產生交易信號後，再執行完整回測
3. 回測結果僅供參考，實盤前需進行 paper trading
