# NASOSv5_mod3 Futures 1x 對照組實驗計畫

> 建立日期: 2026-05-28
> 實驗目的: 公平比較 Spot vs Futures 1x 的表現差異
> 參考方法論: `freqtrade-strategy-iteration` skill 中的 spot-vs-futures-comparison.md

---

## 1. 實驗設計原則

根據過往驗證（2026-05-26），公平比較必須控制以下變因：

| 變因 | 控制方式 |
|------|----------|
| **時間範圍** | 統一 `--timerange 20250824-20260524` (273天) |
| **策略檔案** | 同一個 `NASOSv5_mod3.py`，不改動 buy/sell params |
| **幣對清單** | 統一 23 幣對（排除 LEO、PYUSD 無 futures 資料者） |
| **stake_amount** | 統一 50 USDT |
| **max_open_trades** | 統一 10 |
| **timeframe** | 統一 5m |
| **leverage** | Futures 明確設為 1 |
| **fee** | Spot 0.1% / Futures 0.06%（Bybit 實際費率） |

---

## 2. 現有配置檔案對照

### Spot 對照組
- **Config**: `user_data/config/test/config_4.json`
- **Trading mode**: `spot`
- **Stoploss**: 策略預設 `-0.3` (-30%)
- **Fee**: 0.1%

### Futures 1x 實驗組
- **Base Config**: `user_data/config/test/config_futures_1x.json`
- **Trading mode**: `futures`
- **Margin mode**: `isolated`
- **Leverage**: `1`
- **Fee**: 0.06%

### 已建立的變體配置（供 stoploss 測試）
| 配置檔 | Stoploss 設定 | 用途 |
|--------|--------------|------|
| `config_futures_1x.json` | 策略預設 -0.3 | 基準對照 |
| `config_futures_1x_sl-0.05.json` | -0.05 (-5%) | 緊止損測試 |
| `config_futures_1x_sl-0.10.json` | -0.10 (-10%) | 中度止損測試 |

---

## 3. 策略參數確認

`NASOSv5_mod3` 的 **buy/sell params 在 Spot 和 Futures 實驗中保持一致**：

```python
# Buy params (v7 hyperopt 結果)
buy_params = {
    "base_nb_candles_buy": 20,
    "ewo_high": 4.299,
    "ewo_high_2": 8.492,
    "ewo_low": -8.476,
    "low_offset": 0.984,
    "low_offset_2": 0.901,
    "lookback_candles": 7,
    "profit_threshold": 1.036,
    "rsi_buy": 80,
    "rsi_fast_buy": 27,
}

# Sell params
sell_params = {
    "base_nb_candles_sell": 20,
    "high_offset": 1.01,
    "high_offset_2": 1.142,
}
```

> 注意：策略檔案已更新 deprecated 參數名稱（`sell_profit_only` → `exit_profit_only` 等）

---

## 4. 數據下載確認

### 已下載的幣對資料（2026-05-28 確認）

**Spot 資料**:
```bash
# 24 個幣對有 spot 5m 資料
# 注意：BTC/USDT, NEAR/USDT 等資料起始時間較晚
```

**Futures 資料**:
```bash
# 33 個幣對有 futures 5m 資料
# 注意：CC/USDT:USDT 起始於 2025-10-31
# 注意：NEAR/USDT:USDT 起始於 2025-11-25
```

### 資料完整性檢查命令
```bash
cd /home/brian/freqtrade && source .venv/bin/activate

# 檢查 spot 資料
freqtrade list-data --exchange bybit --trading-mode spot --data-format-ohlcv feather

# 檢查 futures 資料
freqtrade list-data --exchange bybit --trading-mode futures --data-format-ohlcv feather

# 下載缺失資料（如需更新）
freqtrade download-data --exchange bybit --trading-mode futures --timeframes 5m \
  --pairs BTC/USDT:USDT ETH/USDT:USDT ... \
  --timerange 20250824-20260524 --data-format-ohlcv feather
```

---

## 5. 回測命令

### 5.1 Spot 基準回測
```bash
cd /home/brian/freqtrade && source .venv/bin/activate
freqtrade backtesting \
  --strategy NASOSv5_mod3 \
  --config user_data/config/test/config_4.json \
  --timerange 20250824-20260524 \
  --cache=day
```

### 5.2 Futures 1x 基準回測（策略預設 stoploss -0.3）
```bash
freqtrade backtesting \
  --strategy NASOSv5_mod3 \
  --config user_data/config/test/config_futures_1x.json \
  --timerange 20250824-20260524 \
  --cache=day
```

### 5.3 Futures 1x + 緊止損 (-5%)
```bash
freqtrade backtesting \
  --strategy NASOSv5_mod3 \
  --config user_data/config/test/config_futures_1x.json \
  --config user_data/config/test/config_futures_1x_sl-0.05.json \
  --timerange 20250824-20260524 \
  --cache=day
```

### 5.4 Futures 1x + 中度止損 (-10%)
```bash
freqtrade backtesting \
  --strategy NASOSv5_mod3 \
  --config user_data/config/test/config_futures_1x.json \
  --config user_data/config/test/config_futures_1x_sl-0.10.json \
  --timerange 20250824-20260524 \
  --cache=day
```

---

## 6. 結果比較框架

### 6.1 核心指標對照表

| 指標 | Spot (config_4) | Futures 1x (基準) | Futures 1x (SL-5%) | Futures 1x (SL-10%) |
|------|----------------|-------------------|-------------------|---------------------|
| **總交易數** | 170 | 25 | 23 | 22 |
| **總獲利 %** | +1.46% | +10.43% | +15.49% | +14.32% |
| **絕對獲利 (USDT)** | +14.60 | +104.31 | +154.87 | +143.19 |
| **勝率** | 77.1% | 100% | 95.7% | 100% |
| **Sharpe** | 0.18 | 1.20 | 1.41 | 1.34 |
| **最大回撤** | 14.91% | 0.00% | 0.25% | 0.00% |
| **平均持倉時間** | 4:50 | 0:02 | 0:02 | 0:03 |
| **CAGR %** | 1.96% | 14.19% | 21.23% | 19.59% |
| **Profit Factor** | 1.07 | 0.00* | 61.86 | 0.00* |

> *Profit Factor 顯示 0.00 是因為無虧損交易，計算異常

### 6.2 關鍵觀察

1. **交易數量差異巨大**: Spot 170 筆 vs Futures 25 筆
   - 原因：Futures 資料對部分幣對（BTC, ETH, BNB, SOL, TRX, HYPE, ZEC, XMR, BCH, USD1, LTC, NEAR）在回測期間無訊號或資料不完整
   - 這導致 **樣本數不足**，統計顯著性存疑

2. **Futures 1x 表現較好但樣本偏少**: 
   - 100% 勝率可能是因為交易次數太少
   - 平均持倉時間僅 2-3 分鐘，策略可能在 futures 環境下過度敏感

3. **Stoploss 調整影響**:
   - SL-5%: 23 筆交易，1 筆止損，總獲利 +15.49%
   - SL-10%: 22 筆交易，0 筆止損，總獲利 +14.32%
   - 策略預設 -30%: 25 筆交易，0 筆止損，總獲利 +10.43%

### 6.3 退出原因分析

| 退出原因 | Spot | Futures 1x (基準) | Futures 1x (SL-5%) |
|----------|------|-------------------|-------------------|
| trailing_stop_loss | 100 (3.91% avg) | 22 (4.14% avg) | 18 (8.76% avg) |
| roi | 1 (40%) | 3 (40%) | 4 (40%) |
| exit_signal | 62 (-0.94% avg) | 0 | 0 |
| stop_loss | 7 (-49.08% avg) | 0 | 1 (-5.11%) |

---

## 7. 實驗結論與建議

### 7.1 當前發現

1. **Futures 1x 在現有資料下表現較好**，但樣本數嚴重不足（僅 22-25 筆 vs Spot 170 筆）
2. **資料完整性是最大問題**：許多幣對的 futures 資料在回測期間不完整或缺失
3. **策略在 futures 環境下交易頻率大幅降低**，可能與 pairlist 或資料品質有關

### 7.2 後續建議

1. **擴大資料範圍**：
   - 確認所有 23 個幣對的 futures 5m 資料完整性
   - 對缺失資料的幣對進行 `--prepend` 或 `--erase` 重新下載

2. **統一 Pairlist**：
   - 建立一個共同的 pairlist，只包含有完整 spot + futures 資料的幣對
   - 建議使用：TON, AVAX, ADA, SUI, DOGE, LINK, HBAR, XLM, XRP, CC, M（這些有交易訊號）

3. **增加回測期間**：
   - 若資料允許，延長回測期間以獲得更多樣本

4. **實際部署前驗證**：
   - 在 dry_run 模式下運行 Futures 1x bot 至少 1-2 週
   - 比較同期 Spot bot 的表現

### 7.3 風險提醒

- ⚠️ Futures 1x 的 100% 勝率僅基於 22-25 筆交易，**不可過度解讀**
- ⚠️ 部分幣對（BTC, ETH 等）在 futures 回測中完全無交易，需檢查原因
- ⚠️ Funding fee 在回測中可能未完全模擬，實際運行可能有差異

---

## 8. 檔案清單

| 檔案 | 用途 |
|------|------|
| `user_data/strategies/prod/NASOSv5_mod3.py` | 策略主檔（已更新 deprecated 參數） |
| `user_data/config/test/config_4.json` | Spot 對照組配置 |
| `user_data/config/test/config_futures_1x.json` | Futures 1x 基準配置 |
| `user_data/config/test/config_futures_1x_sl-0.05.json` | Futures 1x + 緊止損 |
| `user_data/config/test/config_futures_1x_sl-0.10.json` | Futures 1x + 中度止損 |
| `user_data/config/coinmarketcap-pairlist.json` | Spot pairlist |
| `user_data/config/futures-pairlist-full.json` | Futures pairlist |
| `user_data/reports/NASOSv5_mod3_spot_vs_futures_1x_experiment_plan.md` | 本實驗計畫 |
