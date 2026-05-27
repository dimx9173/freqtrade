# Freqtrade 策略管理規範

## 目錄結構

| 目錄 | 用途 | 狀態 |
|------|------|------|
| `prod/` | 當前運行的 5 個 Bot 策略 | 5 策略 / 11 檔 |
| `uat/` | 備選策略（UAT / Stage）| 1 策略 / 2 檔 |
| `test/` | 實驗性策略（年化報酬 > 20% 可晉升 uat/）| 93 檔 |

## 晋升規則

```
test/ ──年化報酬 > 20%──→ uat/
uat/  ──確認穩定──→ prod/
```

**test → uat 晉升門檻：**
- 年化報酬 **> 20%**
- 夏普比率 **> 1.0**
- 最大回撤 **< 15%**
- 回測數據 **≥ 6 個月**

**uat → prod 晉升條件：**
- 類同 Bot 實盤觀察表現穩定
- 通過每月策略評估會議

## 降級規則

```
prod/ ──表現不佳──→ test/
uat/  ──報酬 < 20%──→ test/
```

## 當前 Bot Slot 對照

| Slot | 策略 | 目錄 | 狀態 |
|------|------|------|------|
| 1 | NASOSv4 | `prod/` | 🟢 運行 |
| 3 | BB_RPB_TSL_BI | `prod/` | 🟢 運行 |
| 4 | NASOSv5_mod3 | `prod/` | 🟢 運行 |
| 5 | SMAOffsetProtectOptV1 | `prod/` | 🟢 運行 |
| 6 | ElliotV5_SMA_ninja | `prod/` | 🟢 運行 |

## 策略命名規範

- `.py` — 策略程式碼
- `.json` — Hyperopt 優化參數
- `*.bak` — 實驗性備份
- `*.disabled` — 已停用

## 啟動腳本

```bash
# 一鍵啟動全部 Bot
bash user_data/scripts/start_all_bots.sh

# 指定 Slot
bash user_data/scripts/start_all_bots.sh 3

# 查看
tmux attach -t freqtrade_main
```
