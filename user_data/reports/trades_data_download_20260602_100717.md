# BTC/USDT:USDT 15m 期貨 Trades 資料下載驗證報告

**任務時間**: 2026-06-02 10:07 UTC
**執行者**: Subagent (delegated task)
**工作目錄**: `/home/brian/freqtrade`
**結論**: ❌ **下載失敗 — Bybit 公開 API 不提供歷史 trades 資料**

---

## 1. 下載指令（已執行）

### 1.1 原始指令（orchestrator 提供）
```bash
freqtrade download-data --exchange bybit --trading-mode futures \
  --pairs BTC/USDT:USDT --timeframes 15m --trades \
  --timerange 20251101-20260601 \
  --data-format-ohlcv feather --data-format-trades feather
```
**首次執行結果**: `freqtrade: error: unrecognized arguments: --trades`
- 原因: CLI 旗標名稱錯誤，正確名稱為 `--dl-trades`

### 1.2 修正後指令（已執行第二次）
```bash
freqtrade download-data --exchange bybit --trading-mode futures \
  --pairs BTC/USDT:USDT --timeframes 15m --dl-trades \
  --timerange 20251101-20260601 \
  --data-format-ohlcv feather --data-format-trades feather
```
**第二次執行結果**: 失敗（見下節）

---

## 2. 失敗根因

### 2.1 freqtrade 拒絕原因
```
2026-06-02 10:05:24,020 - freqtrade - ERROR - Trade history not available for Bybit.
You cannot use --dl-trades for this exchange.
```

**源碼位置**: `freqtrade/data/history/history_utils.py:759-763`
```python
if not exchange.get_option("trades_has_history", True):
    raise OperationalException(
        f"Trade history not available for {exchange.name}. "
        "You cannot use --dl-trades for this exchange."
    )
```

**設定位置**: `freqtrade/exchange/bybit.py:30`
```python
"trades_has_history": False,  # Endpoint doesn't support pagination
```

### 2.2 直接 API 驗證（CCXT 繞過 freqtrade 限制）
用 CCXT 對 Bybit v5 公開 endpoint 進行直接測試，確認 `since` 參數被忽略：

| 測試 | 結果 |
|---|---|
| `fetch_trades('BTC/USDT:USDT')` (無 since) | ✅ 成功，回傳最新 trades |
| `fetch_trades('BTC/USDT:USDT', since=2025-11-01)` | ❌ 忽略 since 參數，只回傳 2026-06-02 最新 trades |
| `publicGetV5MarketRecentTrade` 直接呼叫 | ❌ 端點 `category=linear, symbol=BTCUSDT, limit=5` 只回傳當下最新 trades，無歷史分頁 |

**樣本回傳**:
```json
{"execId": "45780d95-...", "symbol": "BTCUSDT", "price": "69490.30",
 "size": "0.002", "side": "Sell", "time": "1780394790875"}
```

**判定**: Bybit v5 公開 endpoint `/v5/market/recent-trade` **不支援時間分頁**（no `cursor`/`startTime`/`endTime` 過濾），是 freqtrade 將 `trades_has_history` 設為 `False` 的根因。

### 2.3 Bybit 端點限制
Bybit 對歷史 trades 的政策：
- 公開 REST 端點 `/v5/market/recent-trade` 最多回傳最近 ~1000 筆
- 完整歷史 trades **僅提供給**：
  - Bybit 企業級 API 客戶（需商業合作）
  - 第三方資料商轉售（Kaiko、Tardis、Amberdata、CoinAPI、Coinalyze 等）
- 不像 Binance/OKX 對免費用戶開放

---

## 3. 現有資料覆蓋

### 3.1 BTC/USDT:USDT 既有資料（已驗證）
| 檔案 | 大小 | K線根數 | 時間範圍 |
|---|---|---|---|
| `BTC_USDT_USDT-15m-futures.feather` | 480,554 B | 17,383 | 2025-12-01 00:00 → 2026-05-31 01:30 UTC |
| `BTC_USDT_USDT-5m-futures.feather` | 60,626 B | — | — |
| `BTC_USDT_USDT-1h-futures.feather` | 340,618 B | — | — |
| `BTC_USDT_USDT-1h-funding_rate.feather` | 35,466 B | — | — |
| `BTC_USDT_USDT-1h-mark.feather` | 529,282 B | — | — |

### 3.2 目標缺失檔案
- ❌ `BTC_USDT_USDT-trades.feather` （不存在）
- ❌ 任何 `*trades*.feather` （全 bybit/futures 資料夾皆無）

### 3.3 策略 Hybrid_v3_OF.py 對 trades 的依賴
從 `user_data/strategies/math_based/multi_tf_regime_v1/Hybrid_v3_OF.py:160-188` 確認：
- 策略在 **backtest 模式** 走 `self.dp.trades(pair, timeframe=self.timeframe)` 取得歷史 trades
- 用 trades 計算三個特徵：`vi`（Volume Imbalance）、`cvd`（Cumulative Volume Delta）、`cvd_slope`
- 程式碼已有 `try/except` 防護：若 trades 不可用，會在 `logger.debug` 層級記錄，**不會** 讓 backtest 崩潰，只是不寫入 `vi`/`cvd` 欄位

---

## 4. 替代方案（按優先級）

### 方案 A：付費第三方資料商（**最完整**）
| 服務 | 費用 | 涵蓋 | 整合方式 |
|---|---|---|---|
| **Tardis.dev** | ~$50/月 起 | Bybit 全歷史 trades | CSV/Parquet 直接下載，可轉 feather |
| **Kaiko** | 企業級 | Bybit/Binance/OKX 全歷史 | API 或 S3 |
| **Amberdata** | 訂閱制 | Bybit 衍生品歷史 trades | REST API |
| **CoinAPI** | $79/月 起 | 50+ 交易所 | REST API |

**操作步驟**（以 Tardis 為例）:
1. 註冊並取得 API key
2. 下載對應日期範圍的 BTCUSDT 永續 trades（CSV.gz）
3. 用 `freqtrade convert-trade-data` 或自寫腳本轉成 feather
4. 放到 `user_data/data/bybit/futures/BTC_USDT_USDT-trades.feather`

### 方案 B：改用支援歷史 trades 的交易所（**最便宜**）
部分交易所免費提供歷史 trades：

| 交易所 | 支援 | freqtrade 支援 |
|---|---|---|
| **Binance** | ✅ 完整歷史 | ✅ |
| **OKX** | ✅ 完整歷史 | ✅ |
| **Kraken** | ✅（無 OHLCV，僅 trades） | ✅ |
| **Bybit** | ❌（見 §2） | ❌ |

**操作**:
1. 註冊 Binance/OKX API key
2. 重新跑下載指令（僅改 `--exchange binance`）
3. 注意：會切換策略執行的目標市場，**需先驗證 Hybrid_v3_OF 在新交易所仍能運作**

### 方案 C：略過 OF 模式（**最快，零成本**）
策略已內建防護，**沒有 trades 資料時仍能跑 backtest**，只是 `vi`/`cvd` 為 NaN：
- 進場規則 `OF_VI_ENTRY_MIN = -0.2` 會變成恆 True（NaN 比較會被 pandas 警告）
- 退出規則 `OF_CVD_EXIT_DIVERGENCE` 會失效
- 策略行為退化成「無 OF 過濾器版本」

**建議**:
- 若策略核心邏輯不嚴重依賴 OF features，可先關閉 OF 過濾
- 修改 `Hybrid_v3_OF.py` 的 `populate_entry_trend` 把 OF 條件移除或用 fallback

### 方案 D：從現有 K線 + 公開 tick 估計（**近似解**）
- 用 5m K線的 (open, high, low, close) 構造 tick 代理變數
- 例如用 close > open 推估買賣方向
- 統計意義弱，但能讓 backtest 跑起來
- **不建議用於實盤決策**

---

## 5. 推薦下一步

| 優先級 | 動作 | 預估時間 |
|---|---|---|
| 1️⃣ | 決定 Hybrid_v3_OF 對 OF 特徵的依賴程度 | 10 分鐘 |
| 2️⃣ | 若強依賴：申請 Tardis 試用（free tier 1 month）並下載 2025-12~2026-05 區間 | 30 分鐘 |
| 3️⃣ | 若弱依賴：直接跳過 OF，跑無 OF 的 backtest 結果 | 5 分鐘 |
| 4️⃣ | 若需快速驗證：改用 binance 拉 BTCUSDT 永續 trades 跑一輪 | 1-2 小時 |

---

## 6. 附錄：完整命令記錄

### 6.1 CLI 修正歷程
```bash
# 第一次（旗標錯誤）
freqtrade download-data --exchange bybit --trading-mode futures \
  --pairs BTC/USDT:USDT --timeframes 15m --trades \
  --timerange 20251101-20260601 \
  --data-format-ohlcv feather --data-format-trades feather
# → error: unrecognized arguments: --trades

# 第二次（修正為 --dl-trades）
freqtrade download-data --exchange bybit --trading-mode futures \
  --pairs BTC/USDT:USDT --timeframes 15m --dl-trades \
  --timerange 20251101-20260601 \
  --data-format-ohlcv feather --data-format-trades feather
# → ERROR - Trade history not available for Bybit. You cannot use --dl-trades for this exchange.
```

### 6.2 資料夾狀態
```bash
$ ls /home/brian/freqtrade/user_data/data/bybit/futures/BTC_USDT_USDT*
BTC_USDT_USDT-12h-futures.feather
BTC_USDT_USDT-15m-futures.feather
BTC_USDT_USDT-1d-futures.feather
BTC_USDT_USDT-1h-funding_rate.feather
BTC_USDT_USDT-1h-futures.feather
BTC_USDT_USDT-1h-mark.feather
BTC_USDT_USDT-1m-futures.feather
BTC_USDT_USDT-1w-futures.feather
BTC_USDT_USDT-2h-futures.feather
BTC_USDT_USDT-30m-futures.feather
BTC_USDT_USDT-3m-futures.feather
BTC_USDT_USDT-4h-futures.feather
BTC_USDT_USDT-5m-futures.feather
# ❌ 無任何 *trades*.feather 檔案
```

### 6.3 環境資訊
- freqtrade 版本: `2026.3`（INFO log 顯示）
- CCXT 版本: `4.5.31`
- 虛擬環境: `/home/brian/freqtrade/.venv`（已啟用）

---

## 7. 給 Orchestrator 的摘要

1. **無法完成**原始任務（trades 下載），原因為 Bybit 公開 API 不支援歷史 trades 分頁
2. **策略已有 graceful degradation**，可選擇：
   - 接受降級（無 OF 特徵）
   - 改用其他交易所或付費資料商
3. **未產生任何 trades 檔案**，無需清理
4. **未 commit 任何變更**（依指示）
5. 完整失敗診斷與替代方案詳見 §2-§4
