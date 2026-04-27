# Freqtrade 策略 Commit 規則

## 基本原則

1. **每個策略變體獨立 commit**
2. **commit message 清楚標示策略狀態**
3. **未通過回測的策略標記為 [WIP] 或 [TEST]**
4. **通過回測的策略標記為 [READY]**

---

## Commit Message 格式

```
[<狀態>] <策略名稱>: <簡短描述>

- 時間框架: <timeframe>
- 核心邏輯: <簡述>
- 止損: <stoploss>
- ROI: <minimal_roi>
- 風險提示: <如果有>
```

---

## 狀態標記

| 標記 | 說明 | 使用時機 |
|------|------|---------|
| **[WIP]** | Work In Progress | 剛建立，尚未回測 |
| **[TEST]** | 測試中 | 正在回測驗證 |
| **[READY]** | 已驗證 | 回測通過，可進入 UAT |
| **[HOTFIX]** | 緊急修復 | 修復生產問題 |
| **[ARCHIVE]** | 封存 | 策略廢棄，保留記錄 |

---

## 目錄對應規則

| 目錄 | 狀態 | Commit 標記 |
|------|------|------------|
| `strategies/test/` | 開發/測試中 | [WIP] / [TEST] |
| `strategies/uat/` | 用戶驗收測試 | [TEST] / [READY] |
| `strategies/prod/` | 生產環境 | [READY] |
| `research/` | 研究文件 | [DOCS] |

---

## 本次 Commit 建議

### Commit 1: 研究文件
```
[DOCS] scalping_variants_research: 空頭市場剝頭皮策略變體研究

- 分析 8 種策略變體
- 確認核心問題: EMA 趨勢濾網在空頭市場過濾所有交易
- 提出 3 個改進方案
```

### Commit 2: 變體 A
```
[WIP] BinHV45_Contract: 無趨勢濾網多空雙向剝頭皮

- 時間框架: 1m
- 核心邏輯: 純 BB 觸及進場，無趨勢方向限制
- 止損: 5%
- ROI: 1.25% 立即出場
- 風險提示: 空頭市場可能頻繁止損
```

### Commit 3: 變體 B
```
[WIP] Modified_EMA_Scalp: ADX 強度替代 EMA 方向濾網

- 時間框架: 5m
- 核心邏輯: ADX>20 替代 EMA 趨勢方向，保留 BB+RSI
- 止損: 3%
- ROI: 2% (0min) / 1% (30min)
- 改進點: 解決空頭市場 0 交易問題
```

### Commit 4: 變體 D
```
[WIP] BiDirectional_BB_Scalp: 純 BB 對稱多空 + ATR 動態止損

- 時間框架: 5m
- 核心邏輯: 純 BB 均值回歸，RSI 確認，放量過濾
- 止損: ATR 動態 2x
- ROI: 3% / 2% / 1% 分層
- 特色: Hyperopt 參數優化空間
```

---

## Commit 命令

```bash
cd ~/freqtrade

# 1. 添加研究文件
git add research/
git commit -m "[DOCS] scalping_variants_research: 空頭市場剝頭皮策略變體研究

- 分析 8 種策略變體
- 確認核心問題: EMA 趨勢濾網在空頭市場過濾所有交易
- 提出 3 個改進方案"

# 2. 添加變體 A
git add user_data/strategies/test/BinHV45_Contract.py
git commit -m "[WIP] BinHV45_Contract: 無趨勢濾網多空雙向剝頭皮

- 時間框架: 1m
- 核心邏輯: 純 BB 觸及進場，無趨勢方向限制
- 止損: 5%
- ROI: 1.25% 立即出場
- 風險提示: 空頭市場可能頻繁止損"

# 3. 添加變體 B
git add user_data/strategies/test/Modified_EMA_Scalp.py
git commit -m "[WIP] Modified_EMA_Scalp: ADX 強度替代 EMA 方向濾網

- 時間框架: 5m
- 核心邏輯: ADX>20 替代 EMA 趨勢方向，保留 BB+RSI
- 止損: 3%
- ROI: 2% (0min) / 1% (30min)
- 改進點: 解決空頭市場 0 交易問題"

# 4. 添加變體 D
git add user_data/strategies/test/BiDirectional_BB_Scalp.py
git commit -m "[WIP] BiDirectional_BB_Scalp: 純 BB 對稱多空 + ATR 動態止損

- 時間框架: 5m
- 核心邏輯: 純 BB 均值回歸，RSI 確認，放量過濾
- 止損: ATR 動態 2x
- ROI: 3% / 2% / 1% 分層
- 特色: Hyperopt 參數優化空間"
```

---

## 狀態轉換流程

```
[WIP] → [TEST] → [READY]
  ↓        ↓         ↓
建立    回測驗證   進入 UAT/PROD
```

### 轉換條件
- **[WIP] → [TEST]**: 策略語法正確，可載入 freqtrade
- **[TEST] → [READY]**: 回測通過（勝率>40%，最大回撤<30%，總利潤>0%）
- **[READY] → [HOTFIX]**: 生產發現問題，緊急修復
- **任何狀態 → [ARCHIVE]**: 策略廢棄，不再維護

---

## 注意事項

1. **不要一次 commit 多個策略**：每個策略獨立 commit，方便追蹤
2. **commit message 要具體**：不要寫「更新策略」，要寫「[WIP] BinHV45_Contract: 新增空頭進場條件」
3. **研究文件也要 commit**：`research/` 目錄的變更用 [DOCS] 標記
4. **config 變更要獨立 commit**：不要和策略混在一起

---

## Brian 的鐵律應用

> **更改任何設定前必須先備份**

- commit 前確認 `git status`
- 重要變更前先 `git stash` 或分支
- 生產策略修改前備份到 `strategies/backup/`
