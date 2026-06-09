# PROJECT_INDEX — Freqtrade

> 給 AI agent / 新 session 用的專案導覽。涵蓋專案代碼、路徑、live bots、cron jobs、常用指令。
> 對齊慣例：`aero:~/project/dpdk_cex` 的 `host:path` 格式。

---

## 1. 專案代碼 (Project Code)

```
freqtrade:~/freqtrade
```

或完整格式（host-scoped）：

```
ubuntu-32gb-nbg1-2:~/freqtrade
```

## 2. 路徑 (Path)

| 用途 | 路徑 |
|---|---|
| Project root (git) | `/home/brian/freqtrade` |
| Workdir (預設) | `/home/brian/freqtrade` |
| Venv python (有 pandas/pyarrow) | `/home/brian/freqtrade/.venv/bin/python3` |
| Freqtrade binary | `/home/brian/freqtrade/.venv/bin/freqtrade` |
| User data | `/home/brian/freqtrade/user_data/` |
| 設定檔 | `/home/brian/freqtrade/user_data/config/config_*.json` |
| 生產策略 | `/home/brian/freqtrade/user_data/strategies/prod/*.py` |
| K 線資料 | `/home/brian/freqtrade/user_data/data/bybit/futures/` |
| 交易日誌 | `/home/brian/freqtrade/user_data/logs/freqtrade_*.log` |
| 交易 DB | `/home/brian/freqtrade/user_data/sqlite/tradesv3_*.sqlite` |
| AGENTS.md (commit/clean 規則) | `/home/brian/freqtrade/user_data/AGENTS.md` |

## 3. Git

- **Repo:** `brian/freqtrade` (本地，未 push)
- **Branch:** `phase1/pre-flight-smoke-test`
- **Commit 規範:** `<type>(<scope>): <subject>` (見 user_data/AGENTS.md)

## 4. Live Bots (6 個，tmux session `freqtrade_main`)

| # | config | Strategy | Timeframe | tmux window | DB |
|---|---|---|---|---|---|
| 1 | `config_1.json` | NASOSv4 | 5m | base | `tradesv3_91.sqlite` |
| 2 | `config_2.json` | PSV5_Hybrid | 15m | PSV5_Hybrid | `tradesv3_92.sqlite` |
| 3 | `config_3.json` | BB_RPB_TSL_BI | 5m | BB_RPB_TSL_BI | `tradesv3_93.sqlite` |
| 4 | `config_4.json` | NASOSv5_mod3 | 5m | NASOSv5_mod3 | `tradesv3_94.sqlite` |
| 5 | `config_5.json` | SMAOffsetProtectOptV1 | 15m | SMAOffsetProtectOptV1 | `tradesv3_95.sqlite` |
| 6 | `config_6.json` | ElliotV5_SMA_ninja | 5m | ElliotV5_SMA_ninja | `tradesv3_96.sqlite` |

啟動模式：每個 bot 走 `zsh user_data/scripts/utilities/monitor_run.sh 'freqtrade trade --config ...'`。**必須用絕對路徑**，否則 tmux window 預設 cwd 是 `~`，相對路徑會炸（lesson learned 2026-06-09）。

## 5. Cron Jobs (Hermes)

| Job ID | Name | Schedule | 跑的腳本 |
|---|---|---|---|
| `6534ca1089e4` | futures-daily-download | `0 2 * * *` 每天 02:00 | `~/.hermes/scripts/download_futures_daily.sh` |
| `714cc6261ca0` | futures-history-download | `0 2 * * 0` 每週日 02:00 | `~/.hermes/scripts/download_futures_history.sh` |
| `e7e995e05c2a` | CEO 每日自我反思 | `0 0 * * *` 每天 00:00 | (LLM agent) |
| `d8d6aa6e99ca` | Freqtrade 每5小時健康檢查 | `0 */5 * * *` | (Python script) |

⚠️ **Hermes cron 跑的是 `~/.hermes/scripts/` 副本，不是 repo 檔**。修 cron script 必須兩處同步 + md5sum 驗證（lesson 2026-06-09：曾連 2 次 commit 只改 repo，導致 10+ 天 5/5 假「讀取失敗」）。

## 6. 常用指令

```bash
# 進入工作目錄
cd /home/brian/freqtrade

# 啟動所有 6 個 bots (重啟後)
tmux new-session -d -s freqtrade_main -n base
# 在每個 window 跑 (絕對路徑！)：
zsh /home/brian/freqtrade/user_data/scripts/utilities/monitor_run.sh \
  'freqtrade trade --config /home/brian/freqtrade/user_data/config/config_N.json \
   --db-url sqlite:////home/brian/freqtrade/user_data/sqlite/tradesv3_9N.sqlite \
   --logfile /home/brian/freqtrade/user_data/logs/freqtrade_<STRATEGY>.log \
   --strategy-path /home/brian/freqtrade/user_data/strategies/prod \
   --strategy <STRATEGY>'

# 健康檢查 (6 個 bots heartbeat)
for n in 1 2 3 4 5 6; do
  ps -ef | grep "config_${n}.json" | grep -v grep | head -1
done

# 觸發 daily download (驗證 verify 區塊)
hermes cron run 6534ca1089e4

# 用 venv python 驗證 feather 資料
/home/brian/freqtrade/.venv/bin/python3 -c "
import pandas as pd
df = pd.read_feather('/home/brian/freqtrade/user_data/data/bybit/futures/BTC_USDT_USDT-5m-futures.feather')
print(f'{len(df)} rows, {df.iloc[0][\"date\"]} ~ {df.iloc[-1][\"date\"]}')"
```

## 7. 已知坑 (Lessons Learned)

- **`set -e` + `2>/dev/null` + `python3 -c "..."` 雙引號 = 沉默失敗**：bash 會展開 f-string 內的 `$variable` 變 Python `NameError`，被 `2>/dev/null` 吞掉。改用 `<<'PYEOF'` 單引號 heredoc + 寫到 `/tmp/verify.py` 再 exec。 (incident 2026-06-09)
- **機器重啟 → bots 全部死**：目前沒有 systemd / @reboot cron 自動啟動。`uptime` 顯示 `< 60 min` 通常代表剛重啟，第一件事檢查 6 個 bots 是否還在。 (incident 2026-06-09)
- **bybit API 連環 `ExchangeNotAvailable`**：多 pair 同時炸 warning 會拖死 freqtrade。重啟 bots 前先 `curl https://api.bybit.com/v5/market/kline?symbol=BTCUSDT&interval=60&limit=2&category=spot` 確認 API 回 OK。 (incident 2026-06-09)
- **Hermes cron 環境的 `python3` 是 `/usr/bin/python3`，沒有 pandas**：所有 cron 跑的腳本都必須明確指定 `$FREQTRADE_DIR/.venv/bin/python3`，不可用 `python3` 裸呼叫。

## 8. 維護

- 新增 live bot → 更新第 4 節表格
- 新增/移除 cron → 更新第 5 節表格
- 重大事件 / 坑 → 加第 7 節
- 改路徑 → 更新第 2 節
