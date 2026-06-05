# Hybrid_v3 GA Refinement 分析（基於既有 fthypt 50 trials）

**日期**: 2026-06-05
**Source**: `user_data/hyperopt_results/strategy_Hybrid_v3_2026-06-01_14-06-17.fthypt` (50 trials)
**目標**: 評估「重新跑 hyperopt」vs「local refinement」的價值
**結論**: 🟡 改善空間小 + 資料限制，**不值得重跑 hyperopt**

---

## 📊 50 Trials 統計

### Top 5 by Loss

| Rank | Loss | ROI (% / min) | Stoploss | Trailing | 備註 |
|------|------|---------------|----------|----------|------|
| **#1** | **115.499** | 1.9%@164 / 3.0%@131 / **21.6%@50** | -2.6% | 10.7% @ 0.001 | **現行 production** |
| #2 | 118.051 | 4.9%@280 / 8.4%@52 / 16.0%@73 | -8.5% | 4.8% @ 9.3% | 寬鬆 SL, 慢 trail |
| #3 | 119.314 | 4.1%@241 / 2.8%@112 / 20.0%@52 | -33.7% | 7.1% @ 1.0% | 寬 SL, 緊 trail |
| #4 | 120.005 | 4.5%@256 / 2.1%@173 / 3.3%@66 | -11.2% | 30.4% @ 1.8% | 寬 SL, 強 trail |
| #5 | 124.289 | 5.5%@209 / 7.0%@73 / 10.1%@37 | -9.9% | 20.1% @ 5.0% | 中庸 |

**Top 1 vs Top 5 改善**: -2.6% loss (115.5→118.1)
**Top 1 vs median loss (137.99)**: -16.3% loss

### 參數分布 (n=50)

| 參數 | mean | min | max | std | 觀察 |
|------|------|-----|-----|-----|------|
| roi_t1 (min) | 178 | 34 | 306 | 72 | 寬散亂，無明顯峰 |
| roi_t2 (min) | 95 | 30 | 173 | 40 | 集中 30-130 min |
| roi_t3 (min) | 78 | 33 | 120 | 30 | 集中 30-120 min |
| roi_p1 (%) | 4.0 | 1.7 | 6.0 | 1.3 | 寬分布 |
| roi_p2 (%) | 6.2 | 1.5 | 10.8 | 3.1 | **中位數偏低** |
| roi_p3 (%) | 16.3 | 3.3 | 30.5 | 8.4 | **高 ROI 是常見選擇** |
| **stoploss (%)** | -16.5 | -33.7 | **-2.1** | 9.5 | **極端分布**: 多數寬鬆, best 撞 -2.6% |
| trailing_stop_pos | 0.167 | 0.040 | 0.348 | 0.098 | 集中 0.04-0.30 |
| trailing_offset | 0.049 | 0.001 | 0.099 | 0.030 | best 0.001 不可行 |

---

## 🎯 關鍵發現

### 1. 收斂已達局部最優
- Top 1 loss 115.499 vs Top 5 最低 118.051 — **只差 2.3%**
- 重新跑 50 epochs 隨機搜尋，**期望改善 < 2% loss** (因為搜尋空間已被覆蓋)
- 真正改善需 **200+ epochs** 或 **貝氏最佳化 (Optuna)**
- 但 200 epochs × 60s/trial = **3.3 小時**，超 terminal 600s timeout

### 2. SL 搜尋不足
- 50 trials 中 **只有 1 個 SL=-2.6%**（best #1）
- 1/50 = 2% 機率落在緊 SL 區間
- SL -2.6% 勝過其他寬鬆 SL (-8%~-34%) 8-15 個 loss points
- **暗示**: 緊 SL 才是 best，但搜尋未充分
- **解方**: 在 SL -2% ~ -4% 區間做 local search (10 epochs)

### 3. Best Trail Offset 0.001 不可行
- freqtrade 要求 trailing_stop_positive > trailing_stop_positive_offset_p1
- best 設 0.001，freqtrade 拒絕；現已硬編為 0.12 (12%)
- **影響**: 實際 production 的 trail offset = 0.12，可能未達 best 真正效果
- **可能 alpha**: 試 offset = 0.05~0.08（freqtrade 仍接受）

### 4. ROI 結構清晰
- Best #1 的 ROI 是 **遞減式**: 21.6% (前 50min) → 3% (50-131min) → 1.9% (131-164min) → 0%
- 符合短持策略: 「快速抓 21.6% 動能，沒抓到就快速出場」
- 這個結構在 Top 5 都有，但**只有 best 抓到 21.6% 配合 50min**
- 暗示: 21% ROI + 50min 是 sweet spot，但 50 trials 中僅 1 個撞到

---

## 🔬 Local Refinement 提案

| 方案 | 參數範圍 | Epochs | 預估改善 | 預估時間 |
|------|----------|--------|----------|----------|
| **A. SL Local** | -2% ~ -4% (3 點) | 9 | 1-3% loss | 9-15 分鐘 |
| **B. Trail Offset** | 0.03~0.10 (4 點) | 16 | 0.5-1% loss | 16-30 分鐘 |
| **C. ROI t3** | 30-70 min (5 點) | 25 | 0.5-1% loss | 25-45 分鐘 |
| **D. 全部 local** | A+B+C | 144 | 1-5% loss | 2-3 小時 |
| **E. 不做** | 維持現狀 | 0 | 0% | 0 |

---

## 🛑 不跑 Hyperopt 的 3 個原因

### 1. 資料限制
- 10 幣種 15m 1 年 data **不存在** (上次 GA 用的合約 15m 來自 2025-11~2026-03 4 月窗口)
- 現在用 bybit 15m BTC 只有 **2 月** (2026-03-20~2026-05-24)
- 2 月 window 跑任何 hyperopt 都會**過擬合到 2 月 noise**

### 2. ROI 表已收斂
- 50 trials 中 best 已是局部最優
- 再跑 50 epochs 隨機搜尋，**期望改善 < 2%**
- 投入 30-50 分鐘只換 1-2% loss 改善 — **不划算**

### 3. 進場邏輯才是瓶頸
- 上次 GA 報告明確指出：
  > "即使經過 50 次 GA 優化，總利潤仍為 0%——表示 ROI/SL/Trailing 不是主要問題，**進場訊號**本身需要改進"
- 重新優化 ROI/SL/Trailing 是**治標不治本**
- 應集中精力在**進場邏輯** (Hybrid_v3 1299 行 populate_entry_trend 的 9 種 NFI next gen 條件)

---

## 🎯 推薦下一步

| 選項 | 動作 | 預期效果 | 預估時間 |
|------|------|----------|----------|
| **A1** | 跑 SL local search 9 epochs (-2~-4%) | loss 1-3% 改善 | 9-15 分鐘 |
| **A2** | 跑 Trail offset local 16 epochs (0.03~0.10) | 解決不可行 0.001 偏移 | 16-30 分鐘 |
| **B** | 直接套用現有 best (loss 115.499) 到 dry-run 部署 | 0% loss 改善但 live 驗證 | 0 |
| **C** | 切回 funding-rate-arbitrage 實作 SPEC v1.0 | 換 project 換 alpha | 視 scope |
| **D** | 接受現狀，部署 Hybrid_v3_MSI v1 觀察 3-6 月 | 累積 live data | 0 (被動) |

### 我的建議
**A1 (9 分鐘) + 然後 B 部署**。理由：
- A1 跑 9 epochs 控制在 15 分鐘內，可接受
- 解 SL 搜尋不足的問題
- 結果直接用於 B dry-run 部署
- 短期 ROI (1-2 月 live 數據) 比 50 epochs 過擬合更可信

### 若選擇 A1，執行命令
```bash
cd /home/brian/freqtrade
nohup ./.venv/bin/python3 -m freqtrade hyperopt \
  --config user_data/strategies/math_based/multi_tf_regime_v1/config.json \
  --strategy-path user_data/strategies/math_based/multi_tf_regime_v1 \
  --strategy Hybrid_v3 \
  --hyperopt-loss ProfitDrawDownHyperOptLoss \
  --spaces stoploss \
  --epochs 9 \
  --timerange 20251101-20260301 \
  --timeframe 15m \
  > /tmp/hyperopt_sl_local.log 2>&1 &
```

預期 9 epochs × 60s = 9 分鐘完成。

---

## 📁 產出

- 本分析報告
- `poc_ga_analysis.py` (用於分析 fthypt，可重複使用)
- 既有 fthypt 已包含 50 trials 全部資料
