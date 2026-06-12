# NASOSv5_mod3 擴展優化實驗計畫：ROI + Sell 聯合優化

> 版本: v1.0  
> 日期: 2026-05-28  
> 目標: 在現有 buy+sell hyperopt 基礎上，擴展納入 ROI 參數聯合優化，提升 5m 剝頭皮策略的出場效率  
> 原則: 性價比優先，避免維度災難，所有結果需獨立 backtest 驗證

---

## 1. 現狀分析（基線）

### 1.1 當前最佳參數（May 27, 2026 Hyperopt）

```python
# Buy parameters:
buy_params = {
    "base_nb_candles_buy": 15,
    "ewo_high": 2.461,
    "ewo_high_2": -5.211,
    "ewo_low": -8.257,
    "lookback_candles": 33,
    "low_offset": 0.982,
    "low_offset_2": 0.971,
    "profit_threshold": 0.993,
    "rsi_buy": 62,
    "rsi_fast_buy": 27,
}

# Sell parameters:
sell_params = {
    "base_nb_candles_sell": 24,
    "high_offset": 0.999,
    "high_offset_2": 1.378,
}
```

### 1.2 基線績效（In-Sample: 2025-11-26 → 2026-05-26, 180 days）

| 指標 | 數值 |
|------|------|
| 交易筆數 | 144 |
| 勝率 | 75.0% |
| 總收益 | +7.56% |
| 平均每筆 | +1.05% |
| 平均持倉 | 7:13 |
| Max Drawdown | ~0.92% |
| Objective | -74.92 |

### 1.3 關鍵問題：ROI 過於寬鬆

- 當前 `minimal_roi = {"0": 0.4}`（40%）
- 對 5m 剝頭皮策略而言，40% ROI 幾乎永遠不會觸發
- 實際出場幾乎全靠 `sell_signal`、`trailing_stop`、或 `stoploss`
- **機會成本**：許多獲利交易本可透過更積極的 ROI 及時鎖定利潤，卻因等待 sell signal 而回吐

---

## 2. 實驗設計

### 2.1 納入優化的 ROI 參數

採用 freqtrade 內建 `roi` space，建立**三階梯式 ROI table**：

```
{"0": roi_0, "120": roi_1, "300": roi_2}
```

| 參數 | 意義 | 預設值 | 搜索範圍 | 說明 |
|------|------|--------|---------|------|
| `roi_t1` | 第一階梯時間 | 120 | 固定 | 120 分鐘 = 24 根 5m K線 |
| `roi_t2` | 第二階梯時間 | 300 | 固定 | 300 分鐘 = 60 根 5m K線 |
| `roi_roi_1` | 長持利潤目標 | 0.05 | 0.01 ~ 0.15 | 持倉 >120min 後的降級目標 |
| `roi_roi_2` | 中持利潤目標 | 0.10 | 0.02 ~ 0.25 | 持倉 >300min 後的進一步降級 |
| `roi_roi_3` | 即時利潤目標 | 0.20 | 0.05 ~ 0.50 | 進場後立即目標（對應 time=0）|

**為何固定時間點？**
- 減少 2 個維度（`roi_t1`, `roi_t2`），避免維度災難
- 120min/300min 對 5m 策略是合理的持倉分界（參考基線平均持倉 7:13）
- 時間點的經濟意義明確：2h 內為短線剝頭皮，2-5h 為中線，>5h 為長線套牢

### 2.2 Search Space 維度控制

| Space | 參數數量 | 說明 |
|-------|---------|------|
| buy | 10 | 與現行完全一致 |
| sell | 3 | 與現行完全一致 |
| roi | 3 | 僅優化利潤值，時間固定 |
| **總計** | **16** | 可控範圍 |

**維度災難防護措施：**
1. **不優化 stoploss / trailing**：保持靜態，避免 SKILL.md 提到的 KeyError 衝突
2. **不優化時間點**：固定 120min / 300min，減少無效搜索
3. **延續已收斂範圍**：buy/sell 參數範圍不擴大，沿用現行設定

### 2.3 Epochs 建議

| 階段 | Epochs | Loss Function | 目的 | 預估時間 |
|------|--------|---------------|------|---------|
| Phase 1 | 300 | `ProfitDrawDownHyperOptLoss` | 快速探索 ROI 空間 | ~10 min |
| Phase 2 | 500 | `ProfitDrawDownHyperOptLoss` | 精煉聯合參數 | ~15 min |
| **或單階段** | **800** | `ProfitDrawDownHyperOptLoss` | 一次性完整搜索 | **~25 min** |

**推薦：單階段 800 epochs**（性價比最佳，總時間 <30min）

若計算資源極度敏感，可改為：
- **500 epochs 單階段**（~15min，參考上次 500 epochs 耗時）

### 2.4 Loss Function 選擇

| 選項 | 優點 | 缺點 | 建議 |
|------|------|------|------|
| `ProfitDrawDownHyperOptLoss` | 與基線一致，直接優化利潤-回撤 | 可能過度擬合利潤 | **✅ 首選（一致性）** |
| `SharpeHyperOptLossDaily` | 優化風險調整後收益 | 對 5m 策略的日頻 Sharpe 可能不敏感 | 可選第二輪對比 |
| `SortinoHyperOptLossDaily` | 只懲罰下行波動 | 與 ProfitDrawDown 類似 | 備選 |

**決定：使用 `ProfitDrawDownHyperOptLoss`**（與基線 hyperopt 完全一致，確保公平比較）

---

## 3. 與 v7 基線的公平比較方法

### 3.1 基線定義

「v7 基線」= NASOSv5_mod3 當前最佳配置（May 27 hyperopt 結果）：
- `buy` + `sell` 參數如上
- 靜態 `minimal_roi = {"0": 0.4}`
- 靜態 `stoploss = -0.3`
- 靜態 trailing stop

### 3.2 比較流程

```
Step 1: 基線 Backtest（必做）
  └─ 使用現行 prod/NASOSv5_mod3.py + NASOSv5_mod3.json
  └─ Timerange: 20251126-20260526
  └─ 記錄完整指標

Step 2: ROI 擴展 Hyperopt（必做）
  └─ 使用 test/NASOSv5_mod3_roi_exp.py（已移除 static minimal_roi）
  └─ Spaces: buy sell roi
  └─ Epochs: 800
  └─ 記錄最佳 epoch 參數

Step 3: 實驗組 Backtest（必做）
  └─ 使用最佳參數執行獨立 backtest
  └─ 同樣 timerange、同樣 config
  └─ 記錄完整指標

Step 4: 指標對比（必做）
  └─ 並列比較表格
  └─ 重點關注 exit reason 分佈變化
```

### 3.3 必須對比的指標

| 指標 | 基線 | 實驗組 | 改善方向 |
|------|------|--------|---------|
| Total Profit % | ? | ? | ↑ 越高越好 |
| Win Rate % | 75.0% | ? | ↑ 或 ↓（需結合 R:R 看） |
| Avg Profit % | 1.05% | ? | ↑ 越高越好 |
| Max Drawdown % | ~0.92% | ? | ↓ 越低越好 |
| Profit Factor | ? | ? | ↑ >1.5 為佳 |
| SQN | ? | ? | ↑ >1.0 為佳 |
| 交易筆數 | 144 | ? | 適中為佳（過多=過度交易） |
| 平均持倉時間 | 7:13 | ? | ↓ 可能改善（ROI 更快出場） |
| **Exit: ROI %** | ~0% | ? | **↑ 核心指標** |
| **Exit: Sell Signal %** | ? | ? | ↓ 可能減少 |
| **Exit: Stoploss %** | ? | ? | ↓ 越低越好 |
| **Exit: Trailing Stop %** | ? | ? | 觀察變化 |

### 3.4 統計顯著性注意事項

- 基線 144 筆交易，實驗組預期類似數量級
- 若交易數 <50，結論可信度下降
- 若 Profit 差異 <1%，可能屬於隨機波動
- **決策閾值**：實驗組 Profit 需比基線高 **>1%** 且 Drawdown 不惡化 **>2%** 才算有效改善

---

## 4. 執行命令

### 4.1 Step 1: 基線 Backtest

```bash
cd ~/freqtrade
freqtrade backtesting \
  -c user_data/config/config_4.json \
  -s NASOSv5_mod3 \
  --strategy-path user_data/strategies/prod/ \
  -i 5m \
  --timerange 20251126-20260526 \
  --export trades \
  --export-filename user_data/reports/NASOSv5_mod3_baseline_backtest.json
```

### 4.2 Step 2: ROI 擴展 Hyperopt

```bash
cd ~/freqtrade
freqtrade hyperopt \
  -c user_data/config/config_4.json \
  -s NASOSv5_mod3_roi_exp \
  --strategy-path user_data/strategies/test/ \
  -i 5m \
  --timerange 20251126-20260526 \
  -e 800 \
  --spaces buy sell roi \
  -j 6 \
  --hyperopt-loss ProfitDrawDownHyperOptLoss \
  --enable-protections \
  --dry-run-wallet 1000
```

### 4.3 Step 3: 實驗組 Backtest

```bash
cd ~/freqtrade
# 先匯出最佳參數到 json
freqtrade hyperopt-show \
  --hyperopt-file user_data/hyperopt_results/strategy_NASOSv5_mod3_roi_exp_*.fthypt \
  --best \
  --print-json > user_data/strategies/test/NASOSv5_mod3_roi_exp.json

# 再執行獨立 backtest
freqtrade backtesting \
  -c user_data/config/config_4.json \
  -s NASOSv5_mod3_roi_exp \
  --strategy-path user_data/strategies/test/ \
  -i 5m \
  --timerange 20251126-20260526 \
  --export trades \
  --export-filename user_data/reports/NASOSv5_mod3_roi_exp_backtest.json
```

---

## 5. 風險與注意事項

### 5.1 已知風險

| 風險 | 機率 | 影響 | 對策 |
|------|------|------|------|
| `minimal_roi` 靜態衝突導致 KeyError | 高 | Hyperopt 崩潰 | **已處理**：實驗策略已移除 static `minimal_roi` |
| Hyperopt 過度擬合 | 中 | 參數在 OOS 失效 | 限制 epochs 800，不擴大參數範圍 |
| ROI 過緊導致頻繁小額止盈 | 中 | 錯過大行情 | 搜索範圍下限設為 5%，避免過度積極 |
| 交易數銳減 | 低 | 樣本不足 | 監控交易數，若 <80 則放寬 ROI 範圍 |

### 5.2 關鍵原則（引用 SKILL.md）

1. **「永遠不要設 `minimal_roi = {}` 並用 `custom_exit`」** — 本實驗不涉及 custom_exit，安全
2. **「Hyperopt 結果必須獨立 backtest 驗證」** — 已納入 Step 3
3. **「靜態定義與 Hyperoptable 參數衝突」** — 已移除 static `minimal_roi`
4. **「ROI exits >> custom_exit for BB mean-reversion strategies」** — 對 NASOS 同樣適用，ROI 是核心出場機制

---

## 6. 預期結果與決策樹

### 6.1 預期結果

- **樂觀**：ROI 優化後，交易更快止盈，Avg Duration 下降，Profit 提升至 9-12%，Win Rate 維持或微升
- **中性**：Profit 微增 1-2%，但 Exit 分佈更健康（更多 ROI exit，更少 stoploss）
- **悲觀**：ROI 過緊導致頻繁小額止盈，錯過大行情，Profit 下降或 Win Rate 崩潰

### 6.2 決策樹

```
實驗組 Backtest 結果
│
├─ Profit > 基線 +1% 且 Drawdown < 基線 +2%
│   └─ ✅ 採用：更新 prod/NASOSv5_mod3.py 移除 static ROI，部署新參數
│
├─ Profit 與基線差異 < 1%
│   └─ ⚠️ 觀察 Exit 分佈：若 ROI exit 比例顯著提升（>30%）
│       ├─ 是 → 採用（出場機制更健康）
│       └─ 否 → 維持基線，ROI 優化無效
│
└─ Profit < 基線 或 Drawdown 惡化 > 2%
    └─ ❌ 放棄：維持基線，記錄失敗原因
```

---

## 7. 檔案清單

| 檔案 | 路徑 | 說明 |
|------|------|------|
| 實驗計畫 | `user_data/reports/NASOSv5_mod3_roi_experiment_plan.md` | 本文件 |
| 實驗策略 | `user_data/strategies/test/NASOSv5_mod3_roi_exp.py` | 移除 static ROI 的測試版策略 |
| 基線回測報告 | `user_data/reports/NASOSv5_mod3_baseline_backtest.json` | Step 1 產出 |
| 實驗回測報告 | `user_data/reports/NASOSv5_mod3_roi_exp_backtest.json` | Step 3 產出 |
| 對比分析 | `user_data/reports/NASOSv5_mod3_roi_comparison.md` | 手動或自動產出 |

---

## 8. 下一步行動

1. [ ] 審閱本計畫
2. [ ] 確認 `NASOSv5_mod3_roi_exp.py` 策略檔無誤
3. [ ] 執行 Step 1 基線 Backtest
4. [ ] 執行 Step 2 ROI 擴展 Hyperopt（800 epochs）
5. [ ] 執行 Step 3 實驗組 Backtest
6. [ ] 填寫對比表格，依決策樹決定是否採用
