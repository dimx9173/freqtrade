# Freqtrade User Data — Agent Instructions

## 版本控制規範

### 必須 Commit 的檔案
以下檔案變更**必須**自動 commit + push：
- `user_data/strategies/prod/*.json` — 策略參數
- `user_data/strategies/prod/*.py` — 策略程式碼
- `user_data/config/*.json` — 設定檔
- `user_data/scripts/utilities/*.sh` — 工具腳本
- `user_data/scripts/*.sh` — 啟動/停止腳本

### 禁止 Commit 的檔案
以下檔案**絕對不**進入 git：
- `user_data/hyperopt_results/*.fthypt`
- `user_data/hyperopt_results/summary_results_*.log`
- `user_data/logs/*.log`
- `user_data/data/` — K線資料
- `user_data/sqlite/*.sqlite` — 交易資料庫
- 任何臨時檔案、備份檔（`*.bak`, `*.tmp`, `*backup*`）

### Commit 訊息格式
```
auto(hyperopt): {strategy_name} params @ {timestamp}
auto(config): update {config_file} @ {timestamp}
auto(strategy): modify {strategy_name}.py @ {timestamp}
auto(script): update {script_name} @ {timestamp}
```

## 檔案整理規範

### 禁止行為
- ❌ 在 `~/` 根目錄建立散亂檔案
- ❌ 重複建立備份檔（`*.bak.2026*`, `*backup*`）
- ❌ 建立無意義的臨時檔案
- ❌ 在 `user_data/strategies/test/` 累積過期策略

### 必須行為
- ✅ 新檔案歸類到正確目錄
- ✅ 定期清理 `test/` 目錄過期策略
- ✅ 備份統一放到 `user_data/backups/`
- ✅ 報告統一放到 `user_data/reports/`

## 目錄結構

```
user_data/
├── config/              # 設定檔（必須 commit）
├── strategies/
│   ├── prod/            # 生產策略（必須 commit）
│   ├── test/            # 測試策略（定期清理）
│   └── archive/         # 封存策略（不再用的）
├── scripts/
│   ├── utilities/       # 工具腳本（必須 commit）
│   └── *.sh             # 啟動/停止腳本（必須 commit）
├── hyperopt_results/    # 優化結果（不 commit）
├── logs/                # 日誌（不 commit）
├── data/                # K線資料（不 commit）
├── sqlite/              # 資料庫（不 commit）
├── backups/             # 備份檔案（選擇性 commit）
└── reports/             # 報告（選擇性 commit）
```

## 自動化流程

### Hyperopt 完成後
1. 匯出參數到 `strategies/prod/{name}.json`
2. `git add strategies/prod/*.json config/*.json`
3. `git commit -m "auto(hyperopt): ..."`
4. `git push`

### Config 修改後
1. `git add config/*.json`
2. `git commit -m "auto(config): ..."`
3. `git push`

### 策略程式碼修改後
1. `git add strategies/prod/*.py`
2. `git commit -m "auto(strategy): ..."`
3. `git push`
