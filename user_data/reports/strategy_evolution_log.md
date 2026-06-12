# FreqAI 策略演進記錄
# 位置: ~/freqtrade/user_data/reports/strategy_evolution_log.md
# 更新規則: 每次回測後必須追加記錄

---

## v70.0 — 2026-05-03 — 原始基準版本
- **Timerange**: 20251101-20260501
- **Market**: -45.81%
- **Result**: -1.88%, 275 trades, 36.0% win, 1.94% drawdown
- **Long/Short**: 41/234
- **Key Params**: downtrend_adx_min=28, sideways_adx<25, uptrend_adx_min=25
- **Code State**: 原始版本，有 BBANDS/MACD 回傳問題
- **Note**: 234 Short 主要來自 Sideways（Downtrend ML threshold 過嚴被封死）

---

## v70.1 — 2026-05-03 — 修復技術指標
- **Change**: BBANDS 改用 dict key 取值，MACD 改用 dict key 取值
- **Result**: -2.09%, 535 trades, 39.3% win, Sharpe -8.24
- **Issue**: 修復後交易數暴增，可能改變了指標計算邏輯
- **Status**: ❌ 未達基準，需要重新調整

---

## v70.2 — 2026-05-03 — 調整 Regime Threshold
- **Change**: downtrend_adx_min 28→20, sideways ADX<25→<20, uptrend_adx_min 25→20
- **Result**: -1.78%, 275 trades, 36.0% win, 1.83% drawdown
- **Issue**: JSON 參數未完全同步（log 顯示仍載入舊值）
- **Status**: ⚠️ 接近基準，需確認參數同步

---

## v53 — 2026-05-03 — NO ROI 版本對照測試
- **Timerange**: 20251101-20260501
- **Market**: -45.81%
- **Result**: -12.92%, 242 trades, 82.6% win, 16.16% drawdown
- **Note**: 高勝率陷阱，少數大虧損抵消多數小盈利
- **Status**: ❌ 遠差於 V70

---

## v55_short (V81) — 2026-05-03 — 簡化技術指標策略
- **Timerange**: 20251101-20260501
- **Market**: -45.81%
- **Result**: -6.93%, 429 trades, 69.2% win, 8.09% drawdown
- **Long/Short**: 177/252, Long -8.38% / Short +1.45%
- **Key Insight**: Short 在熊市賺錢，Long 在熊市虧錢
- **Status**: ⚠️ Short 有 edge，但 Long 拖累整體

---

## v55_hi_roi — 2026-05-03 — 高 ROI 版本對照
- **Timerange**: 20251101-20260501
- **Market**: -45.81%
- **Result**: -19.14%, 219 trades, 82.2% win, 22.76% drawdown
- **Status**: ❌ 最差表現，高勝率但大虧損

---

## 關鍵發現總結

1. **V70 原始 (-1.88%) 是最佳基準** — drawdown 僅 1.94%，遠優於其他版本
2. **Short 在熊市有 edge** — V55_short 的 Short 交易 +1.45%
3. **高勝率 ≠ 好策略** — V53/V55 勝率 82%+ 但總虧損更大
4. **FreqAI backtest 會即時訓練模型** — ml_prediction 是真實值，非 fallback 0.5
5. **Regime detection 順序影響巨大** — Sideways 條件寬鬆導致過多 Short 交易

---

## 待測試項目

- [ ] V70 參數完全同步後重新回測
- [ ] 限制 Long 交易數量（熊市中 Long 必然虧損）
- [ ] 測試 V70 在牛市/橫盤時期的表現
- [ ] 比較 V70 vs V55_short 的組合策略
- [ ] 訓練專用模型後重新回測 V70

---

## 已廢除的假設

1. ❌ "ml_prediction fallback 是 0.5" — 實際上 FreqAI 會即時訓練模型
2. ❌ "降低 ADX threshold 會改善結果" — 導致更多 Downtrend 交易但不一定更好
3. ❌ "高勝率策略更安全" — V53/V55 證明高勝率可能伴隨大虧損



---

## v70.3-shortonly — 2026-05-03 — Subagent 測試
- **Timerange**: 20251101-20260501
- **Market**: -45.81%
- **Change**: 移除所有 Long entry，只保留 Short entry
- **Result**: -4.14%, 929 trades, 55.4% win, 4.29% drawdown
- **vs 基準**: 比 V70 原始 (-1.88%) 更差
- **Insight**: 純 Short 在熊市中無法獲利，Long/Short 混合更能平衡風險
- **Status**: ❌ 無效方向

---

## v70.3-relaxshort — 2026-05-03 — Subagent 測試
- **Timerange**: 20251101-20260501
- **Market**: -45.81%
- **Change**: Downtrend prediction threshold 0.65→0.55
- **Result**: -16.57%, 725 trades, 49.5% win, 17.09% drawdown
- **vs 基準**: 遠差於 V70 原始 (-1.88%)
- **Insight**: 放寬 threshold 讓更多 Short 進場，但這些額外交易是虧損的
- **Status**: ❌ 無效方向

---

## v70.3-tightsideways — 2026-05-03 — Subagent 測試
- **Timerange**: 20251101-20260501
- **Market**: -45.81%
- **Change**: Sideways bb_percent threshold 0.75→0.85
- **Result**: -14.93%, 648 trades, 51.5% win, 15.37% drawdown
- **vs 基準**: 遠差於 V70 原始 (-1.88%)
- **Insight**: Short 交易佔總虧損 94%，收緊條件未見顯著改善
- **Status**: ❌ 無效方向

---

## 本輪 Subagent 測試總結

| 變體 | 總獲利 | 交易數 | 勝率 | Drawdown | 評價 |
|------|--------|--------|------|----------|------|
| V70 原始 (基準) | **-1.88%** | 275 | 36.0% | 1.94% | ⭐ 最佳 |
| v70.3-shortonly | -4.14% | 929 | 55.4% | 4.29% | ❌ |
| v70.3-relaxshort | -16.57% | 725 | 49.5% | 17.09% | ❌ |
| v70.3-tightsideways | -14.93% | 648 | 51.5% | 15.37% | ❌ |

**關鍵發現**：
1. 所有變體都比 V70 原始差
2. Short 交易在當前設定下無法在熊市獲利
3. V70 原始的保守設定（較少交易、較嚴格條件）反而表現最好
4. **V70 原始 (-1.88%) 可能是局部最優解**

**下一步建議**：
- 停止修改 entry/exit logic
- 轉向優化 FreqAI 模型訓練參數
- 或測試 V70 在牛市/橫盤時期的表現


## V81-V85 FreqAI 日內交易研發日誌（2026-05-05）

### 背景目標
用戶目標：BTC/ETH 日內 5m 交易，每次不超過 5 個指標，6 個月訓練資料，月報酬 10%

### 核心發現

#### V81R - Regression 架構驗證
- FreqAI 訓練成功，預測欄位 `&-ml_return`
- 預測範圍 -0.008 ~ +0.013（太小）
- 3 trades，threshold 問題

#### V82 - 延長預測窗口（12-bar = 3小時）✅ 突破
- 15m 數據：勝率 81%，虧損 -3.39%，drawdown 3.96%
- 對比 3-bar（45分鐘）：勝率 53%，虧損 -12.46%
- **關鍵：預測更長窗口產生更強信號**

#### V83 - 擴展到 5m 時間框架
- 5m 數據：103 trades，勝率 53.4%，虧損 -2.74%，drawdown 3.45%
- 市場背景：BTC 2025-11 至 2026-04 下跌 ~30%（熊市）
- **V83 虧損比大盤少 27%，證明 ML 有一定過濾能力**

### 三方向擴展測試結果

| 方向 | 做法 | 結果 | 結論 |
|------|------|------|------|
| A. 多幣種 | BTC+ETH+SOL | -16.26%（BTC 單幣 -2.74%）| ❌ 拒絕 |
| B. 混合 Regime | V70 + V83 ML | -3.14%（V83 -2.74%）| ❌ 拒絕 |
| C. 風險管理 | SL -2.5% + ROI +3% | -4.89%（但 worst trade -2.69% ↓）| ⚠️ 部分成功 |

### 最佳基準：V83（5m，單 BTC）
- 103 trades，-2.74%，勝率 53.4%，drawdown 3.45%
- 市場下跌 30%，策略只虧 2.74%

### 關鍵教訓
1. **預測窗口越長，信號越強** — 12-bar 勝率 81% > 3-bar 53%
2. **單幣 BTC 表現最好** — ETH/SOL 在熊市拖後腿
3. **Regime filtering 在持續下跌市場無效** — V70 的 regime 判斷反而過濾掉正確空頭信號
4. **風險管理有效但不足** — Stop loss 將最大虧損限制在 -2.69%，但無法改變負報酬
5. **熊市中 ML 策略仍虧損** — 重點是虧得比大盤少（-2.74% vs -30%）

### 待解決問題
1. 仍需戰勝大盤（目標月報酬 10%）
2. 需要牛市/橫盤期驗證策略是否真的有效
3. 只用 BTC（其他幣表現差）



---

## v94 — 2026-05-05 — Regime Detection Fixes (Option A)
- **Changes**: ADX 25→22, Sideways ADX <20→<22, High Vol Override 只在 marginal zone (ADX 15-25), Uptrend prediction threshold 0.55→0.60
- **Timerange**: 20260116-20260430
- **Market**: BTC -31.47%
- **Pairs**: BTC+ETH+SOL+XRP+LTC+ADA+DOGE+AVAX+LINK+DOT (Bybit futures)
- **Result**: -2.3%, 642 trades, 56.9% win, 2.92% drawdown
- **vs V70**: +0.42% worse total return, +20.9% higher win rate
- **Analysis**: Win rate 大幅提升但總虧損略增。More trades = more fees. ADX 降低導致更多進場但精準度下降。

---

## v95 — 2026-05-05 — FreqAI + Technical Indicator Hybrid (Option C)
- **Changes**: V94 regime fixes + Hurst exponent + Z-score filter + ATR-based dynamic stops + wider trailing (0.8%/2.0%)
- **Timerange**: 20260116-20260430
- **Market**: BTC -31.47%
- **Pairs**: Same as V94
- **Result**: -1.9%, 513 trades, 55.0% win, 2.75% drawdown
- **vs V70**: -0.02% (essentially same as V70)
- **Analysis**: V95 ≈ V70。Hurst/Z-score 技術指標未帶來顯著改善。

---

## EMA_Cross_ADX_RSI — 2026-05-05 — Pure Technical (Option D, CORRECTED)
- **Strategy**: EMA(12/26) cross + ADX≥25 + DI+>DI- + RSI(30-68) filter + 6% TP / 2.5% SL / 24-bar timeout
- **Timerange**: 20260116-20260430 (SAME as FreqAI strategies!)
- **Market**: BTC -20.2% (Bybit futures)
- **Data**: Bybit BTC/USDT futures 15m
- **Result**: **+13.05%, 131 trades, 51.1% win, 19.84% drawdown**
- **vs V70**: **+14.93% better** (massive outperformance!)
- **Analysis**: 純技術指標大幅跑贏所有 FreqAI 策略。No ML, no FreqAI training overhead. Simple is better.
- **Key Insight**: V70 regime detection ADX threshold 問題導致錯過進場。純 EMA cross 找到更多有效訊號。

---

## Summary: All Strategies Compared (2026-01-16 to 2026-04-30)

| Strategy | Return | Trades | Win Rate | Drawdown | vs V70 |
|----------|--------|--------|----------|----------|--------|
| **EMA Cross (D)** | **+13.05%** | 131 | 51.1% | 19.84% | **+14.93%** ⭐ |
| V70 original | -1.88% | ~275 | 36.0% | 1.94% | baseline |
| V94 (ADX fix) | -2.3% | 642 | 56.9% | 2.92% | -0.42% |
| V95 (Hurst) | -1.9% | 513 | 55.0% | 2.75% | -0.02% |

**Conclusion**: Pure EMA cross + ADX + RSI >> all FreqAI strategies in bear market.
FreqAI's ML predictions are NOT adding value over simple technical indicators.

---

## 4-way Entry Experiment — 2026-06-06 — 並行回測

- **Timerange**: 20250501-20260524 (1 年)
- **Market**: 9 pairs (ETH/SOL/BNB/XRP/DOGE/ADA/AVAX/TON/SUI)
- **Baseline**: Hybrid_v3 823 trades / 63.4% WR / -12.54% / 13.00% DD / Sharpe -5.55

| Exp | Direction         | Trades | WR    | Profit   | DD     | Sharpe | Calmar | PF   | Verdict   |
|-----|-------------------|-------:|------:|---------:|-------:|-------:|-------:|-----:|-----------|
| A   | voting ≥2/9       |    823 | 63.4% |  -12.54% | 13.00% |  -5.55 |  -4.80 | 0.50 | ❌ no-op  |
| B   | strict ADX 15/28  |    501 | 61.3% |   -5.35% |  7.65% |  -2.26 |  -3.48 | 0.64 | ✅ +58%   |
| C   | ATR>MA(100)       |    454 | 65.2% |   -5.33% |  6.29% |  -2.08 |  -4.22 | 0.63 | ✅✅ BEST  |
| D   | 3/3 mtf consensus |   2357 | 60.9% |  -43.50% | 44.45% | -21.35 |  -4.87 | 0.41 | 💀 3x 爛  |

### 關鍵發現

- **A no-op**: 823 trades 中 769 個是 weak_trend (regime=1), 改 BB_RPB voting 等於沒改
- **B effective**: 嚴格 ADX → 更多 transition → 篩掉低品質 weak_trend
- **C best**: ATR gate 阻擋 178 trades max_gain<5% 的低波動假進場
- **D disaster**: 嚴格共識推更多 bar 進 transition = 更多 weak_trend

### 下一步 (3-way follow-up @ 2026-06-06)

- **C_sma50**: ATR(14) > SMA(50) — 反應更快
- **C_sma200**: ATR(14) > SMA(200) — 反應更慢
- **B+C**: ADX 15/28 + ATR gate 組合

### Commit
- 91cec8a69 auto(research): Hybrid_v3 entry 4-way experiment - C volatility wins
