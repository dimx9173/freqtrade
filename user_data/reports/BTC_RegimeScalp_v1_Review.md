# BTC_RegimeScalp_v1 策略設計審查報告

**審查日期**: 2026-05-31  
**審查對象**: Hybrid_v3 (BTC_RegimeScalp_v1)  
**基線比較**: BB_RPB_TSL_BI (+6.22%)  
**審查者**: 量化交易程式碼審查系統

---

## 1. 策略邏輯合理性審查

### 1.1 核心架構評估

| 組件 | 設計 | 評級 | 說明 |
|------|------|------|------|
| 體制偵測 | ADX 多 TF 共識 (15m/1h/4h) | ✅ 合理 | 與用戶已驗證的 99.8% 準確度一致 |
| 波動率預測 | Ridge + poly degree=2 預測 ATR | ✅ 合理 | R²=0.67 已驗證，用於倉位管理正確 |
| 進場邏輯 | 雙模式 (trend-following + mean-reversion) | ⚠️ 高風險 | 學術論文支持但實作複雜度高 |
| 出場邏輯 | Dual-mode exit + custom_stoploss | ⚠️ 需修復 | 多個已知 bug 未完全解決 |
| 倉位管理 | 反向波動率加權 | ✅ 合理 | 數學框架正確用法 |

### 1.2 明顯漏洞

**🔴 CRITICAL: trailing_stop = True 與 use_exit_signal = False 矛盾**

```python
# 第 105-116 行：
trailing_stop: bool = True              # ← 啟用 trailing_stop
trailing_stop_positive = 0.02
trailing_stop_positive_offset = 0.03
# ...
use_exit_signal: bool = False           # ← 但禁用 exit_signal
```

- **問題**: trailing_stop 與 custom_stoploss 同時啟用會產生衝突
- **歷史教訓**: Hybrid_v3 完全失敗時，trailing_stop_loss 出場平均虧損 -4.44%
- **修復**: `trailing_stop = False`（註解說要禁用，但程式碼仍設為 True）

**🔴 CRITICAL: populate_exit_trend 雖有 CROSS 邏輯，但 use_exit_signal=False 使其無效**

- 第 587-660 行精心設計的 2-bar RSI confirmation + EMA cross exit
- 但 `use_exit_signal = False` 讓這段程式碼永遠不會被執行
- 這是「殭屍程式碼」—— 存在但無作用，造成維護混淆

**🟡 WARNING: transition_entry (regime=1) 缺乏獨立驗證**

- 用戶的歷史數據顯示：「多空雙向自動切換」是無效方向
- transition_entry 本質是弱化版的 trending_entry，但 regime=1 時市場方向不明確
- 建議：完全禁用 transition_entry，或至少獨立驗證其 WR

**🟡 WARNING: custom_stoploss 回傳正數值會顯示為 trailing_stop_loss**

- 第 697-698 行：`return +0.02` 和 `return +0.01`
- freqtrade 內部將正數值視為「利潤保護 trailing stop」
- 回測報告會出現 `trailing_stop_loss` exit reason，造成分析混淆
- 這不是 bug 而是 freqtrade 的正常行為，但需要文件說明

---

## 2. 參數設置適合性審查

### 2.1 時間框架

| 參數 | 當前值 | 建議 | 理由 |
|------|--------|------|------|
| timeframe | 15m | ✅ 保持 | 用戶已驗證 15m 是最佳 TF |
| startup_candle_count | 350 | ⚠️ 過高 | VOL_WINDOW=300 已足夠，350 造成回測浪費 |
| informative TF | 30m/1h/4h | ⚠️ 30m 多餘 | 1h+4h 已足夠，30m 增加複雜度無顯著增益 |

### 2.2 Regime 閾值

| 參數 | 當前值 | 建議 | 理由 |
|------|--------|------|------|
| ADX_RANGING_MAX | 20.0 | ✅ 合理 | 與用戶歷史驗證一致 |
| ADX_TRENDING_MIN | 22.0 | ⚠️ 過低 | 原 25，降到 22 會增加 false positive |
| ADX_TREND_MIN (entry) | 18.0 | ⚠️ 過低 | 進場確認比 regime 分類還寬鬆，邏輯矛盾 |

**矛盾分析**:
- regime 分類：ADX > 22 才算 trending
- 進場條件：ADX > 18 就可以進場
- 這意味著 regime=1 (transition, ADX 20-22) 時，如果 ADX=19 仍可能進場
- 但 transition_entry 的條件又要求 ADX > 18
- → 實際上 regime=1 和 regime=2 的進場條件幾乎相同

### 2.3 RSI 閾值

| 參數 | 當前值 | 建議 | 理由 |
|------|--------|------|------|
| RSI_MEAN_REV_ENTRY | 40.0 | ⚠️ 過寬 | 原 30，放寬到 40 會增加 false entry |
| RSI_MEAN_REV_EXIT | 70.0 | ✅ 合理 | 2-bar confirmation 減少噪音 |
| RSI_TREND_EXIT | 75.0 | ✅ 合理 | 足夠寬鬆讓趨勢持續 |

**歷史教訓**: 用戶的 Hybrid_v3 測試顯示 RSI < 44 是破壞性過濾器（0 trades → 65% WR）
- RSI_MEAN_REV_ENTRY=40 雖然比 44 寬鬆，但在 ranging market 中仍可能過濾過多
- 建議：先測試 RSI < 30，若交易數不足再逐步放寬

### 2.4 波動率預測參數

| 參數 | 當前值 | 評估 |
|------|--------|------|
| VOL_FORECAST_HORIZON | 12 (3h) | ✅ 合理 |
| VOL_WINDOW | 300 | ✅ 合理 |
| VOL_RIDGE_ALPHA | 0.1 | ✅ 合理 |
| VOL_RETRAIN_INTERVAL | 50 | ⚠️ 過頻繁 | 每 50 根 K 線 (12.5h) 重訓練，計算成本高 |
| VOL_POLY_DEGREE | 2 | ✅ 已驗證 |
| pred_atr clip | [0.005, 0.15] | ✅ 正確（0.5% floor 已修復）|

### 2.5 ROI 設置

```python
minimal_roi = {
    "0": 0.015,    # 1.5% 立即目標
    "60": 0.01,    # 1% after 15h
    "120": 0.005,  # 0.5% after 30h
}
```

| 評估項 | 結論 |
|--------|------|
| 與 BB_RPB_TSL_BI 對比 | BB_RPB 用單一 ROI 20.5%，此策略用遞減 ROI |
| 適合性 | ⚠️ 過於保守 | 1.5% 目標在 BTC 15m 可能過快出場 |
| 建議 | 測試 `{"0": 0.03, "120": 0.015, "240": 0.005}` |

---

## 3. 進場條件審查

### 3.1 Trending Entry (regime=2)

```python
trending_entry = (
    (dataframe["regime"] == 2)
    & (dataframe["ema_fast"] > dataframe["ema_slow"])
    & (dataframe["adx_15m"] > self.ADX_TREND_MIN)       # ADX > 18
    & (dataframe["plus_di"] > dataframe["minus_di"])    # +DI > -DI
    & (dataframe["macd_hist"] > 0)                       # MACD > 0
    & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())
)
```

**評估**:
- ✅ EMA cross + ADX + DI + MACD 是多層確認，理論上 robust
- ⚠️ 但條件過多 → 交易數過少 → 統計顯著性不足
- ⚠️ `macd_hist > 0` 與 `ema_fast > ema_slow` 高度相關（冗餘條件）
- ⚠️ volume > MA 在 BTC 幾乎永遠為真（流動性充足）

**建議簡化**:
```python
trending_entry = (
    (dataframe["regime"] == 2)
    & (dataframe["ema_fast"] > dataframe["ema_slow"])
    & (dataframe["adx_15m"] > 20)  # 提高 ADX 閾值，減少 false positive
    & (dataframe["plus_di"] > dataframe["minus_di"])
)
```

### 3.2 Ranging Entry (regime=0)

```python
ranging_entry = (
    (dataframe["regime"] == 0)
    & (dataframe["close"] < dataframe["bb_lower"])
    & (dataframe["rsi"] < self.RSI_MEAN_REV_ENTRY)    # RSI < 40
    & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())
)
```

**評估**:
- ⚠️ `close < bb_lower` 在 ranging market 中頻繁發生（BB 設計就是包含 95% 價格）
- ⚠️ RSI < 40 在 ranging market 中不算極度超賣（RSI 30 才是標準超賣）
- ⚠️ 組合條件可能仍過於寬鬆，導致過多進場

**歷史教訓**: 用戶的 Pullback_Scalp_v1 在 ranging market 表現極差（多幣種 WR 28-38%）
- ranging entry 的 mean-reversion 在 crypto 中容易被趨勢延續打臉
- 建議：ranging entry 需要額外過濾，例如要求 RSI 從下方回升（RSI > RSI.shift(1)）

### 3.3 Transition Entry (regime=1)

```python
transition_entry = (
    (dataframe["regime"] == 1)
    & (dataframe["ema_fast"] > dataframe["ema_slow"])
    & (dataframe["adx_15m"] > self.ADX_TREND_MIN)
    & (dataframe["plus_di"] > dataframe["minus_di"])
    & (dataframe["volume"] > 1.2 * dataframe["volume"].rolling(20).mean())
)
```

**評估**:
- 🔴 **強烈建議移除** — regime=1 的定義就是「方向不明確」，此時進場等於賭方向
- 條件與 trending_entry 幾乎相同，只有 volume 閾值稍高
- 用戶的歷史數據顯示「多空雙向自動切換」是無效方向
- transition entry 本質就是在方向不明時賭方向

---

## 4. 止損設置審查

### 4.1 custom_stoploss 設計

```python
def custom_stoploss(self, ...):
    if current_profit < -0.05:
        return -0.05           # 5% hard stop
    elif current_profit < 0:
        return -0.99           # 讓價格在 -5%~0% 浮動

    if current_profit >= 0.05:
        return +0.02           # 鎖定 2% 利潤
    if current_profit >= 0.03:
        return +0.01           # 鎖定 1% 利潤
    if current_profit >= 0.015:
        return -0.015          # 保護一半利潤

    return -0.05               # 預設允許 -5%
```

**評估**:

| 層級 | 設計 | 評級 | 說明 |
|------|------|------|------|
| 虧損 < -5% | hard stop -5% | ✅ 合理 | 比 -3% 寬鬆，減少噪音止損 |
| -5% ~ 0% | 無止損 (return -0.99) | ⚠️ 過寬 | 可能讓小虧損變大虧損 |
| 0% ~ 1.5% | 允許 -5% | ⚠️ 過寬 | 盈利後又虧損 -5% 不合理 |
| 1.5% ~ 3% | 保護一半利潤 | ✅ 合理 |
| 3% ~ 5% | 鎖定 1% | ✅ 合理 |
| > 5% | 鎖定 2% | ⚠️ 過緊 | BTC 趨勢可能持續更久 |

**與 BB_RPB_TSL_BI 對比**:

BB_RPB_TSL_BI 的 custom_stoploss:
```python
if current_profit > 0.2: return 0.05    # >20% 利潤 → 鎖定 5%
elif current_profit > 0.1: return 0.03  # >10% 利潤 → 鎖定 3%
elif current_profit > 0.06: return 0.02 # >6% 利潤 → 鎖定 2%
elif current_profit > 0.03: return 0.015 # >3% 利潤 → 鎖定 1.5%
```

- BB_RPB 的利潤保護層級更寬鬆（3% 才開始保護）
- RegimeScalp 在 1.5% 就開始保護，可能過早出場
- **建議**: 將第一層利潤保護從 1.5% 提高到 3%

### 4.2 時間出場

```python
if holding_minutes > 2880:  # 48 hours
    return "time_exit"
```

- 48 小時在 15m TF 下過長
- 用戶的歷史數據顯示持倉時間長（7-9 天）是問題來源
- **建議**: 縮短到 24 小時（1440 分鐘）

---

## 5. 空頭邏輯審查

### 5.1 當前設計

```python
can_short: bool = False  # Long only
```

### 5.2 BTC 當前狀態分析

- 價格 $76,838，空頭趨勢
- RSI 50.44 中性
- MACD histogram 翻多
- 當前回撤 -39%
- 日線夏普 -0.31

### 5.3 評估

- 🔴 **在空頭趨勢中只做 long 是重大劣勢**
- 用戶的歷史數據顯示：「ShortOnly 在熊市有 edge」
- BB_RPB_TSL_BI 是 long-only，在熊市中表現會受影響
- 但 RegimeScalp 若也只能 long，則無法利用空頭趨勢

**建議**:
1. **短期**: 在空頭趨勢中暫停使用此策略，或切換到 ShortOnly 策略
2. **中期**: 添加 can_short=True，實作對稱的 short entry/exit 邏輯
3. **長期**: 考慮 regime-aware 多空切換（但需獨立驗證）

---

## 6. 與 BB_RPB_TSL_BI 比較

### 6.1 架構對比

| 特性 | BB_RPB_TSL_BI | RegimeScalp_v1 | 評估 |
|------|--------------|----------------|------|
| 時間框架 | 5m | 15m | BB_RPB 更頻繁交易 |
| 進場邏輯 | 多條件組合 (EWO/BB/RSI/EMA) | 雙模式 (trend/mean-rev) | BB_RPB 更成熟 |
| 出場邏輯 | custom_stoploss + custom_exit | custom_stoploss + ROI | BB_RPB 更複雜但更穩定 |
| 體制偵測 | 無 | ADX 多 TF 共識 | RegimeScalp 有優勢 |
| 波動率預測 | 無 | Ridge ATR 預測 | RegimeScalp 有優勢 |
| 倉位管理 | 固定 | 反向波動率加權 | RegimeScalp 更先進 |
| 參數數量 | ~40 個 hyperopt 參數 | ~15 個硬編碼參數 | RegimeScalp 更簡潔 |
| 回測表現 | +6.22% (基線) | 未驗證 | 待測試 |

### 6.2 BB_RPB_TSL_BI 的優勢

1. **經過大量 hyperopt 優化**: 40+ 參數經過數據驅動校準
2. **多進場條件**: 不依賴單一 regime，各種市場狀態都有對應進場邏輯
3. **成熟的出場機制**: custom_exit 包含 10+ 種出場條件（sell trail, deadfish, etc.）
4. **生產驗證**: 已實盤運行，表現穩定

### 6.3 RegimeScalp_v1 的優勢

1. **體制適應性**: 能區分 trending/ranging，理論上更靈活
2. **波動率預測**: ATR 預測用於動態倉位管理，風險控制更精細
3. **數學嚴謹性**: 基於已驗證的數學框架，可解釋性強
4. **參數簡潔**: 較少參數，過擬合風險較低

### 6.4 關鍵差距

- BB_RPB_TSL_BI 的 ROI 是單一 20.5%，RegimeScalp 是遞減 ROI（最高 1.5%）
- 這意味著 RegimeScalp 需要更高的勝率和交易頻率才能達到相同報酬
- RegimeScalp 尚未經過 hyperopt 優化，參數可能不是最佳

---

## 7. 改進建議（優先級排序）

### 🔴 P0 — 必須立即修復

1. **修復 trailing_stop 矛盾**
   ```python
   trailing_stop: bool = False  # 目前為 True，與 custom_stoploss 衝突
   ```

2. **移除或禁用 transition_entry**
   ```python
   # 刪除 regime=1 的進場邏輯，或設為條件編譯
   ```

3. **清理殭屍程式碼**
   - `populate_exit_trend` 在 `use_exit_signal=False` 時永遠不執行
   - 要么啟用 `use_exit_signal=True` 並驗證 exit 邏輯
   - 要么刪除 `populate_exit_trend` 減少混淆

### 🟡 P1 — 高優先級改進

4. **統一 ADX 閾值邏輯**
   ```python
   ADX_TRENDING_MIN = 25  # 恢復原值
   ADX_TREND_MIN = 22     # 進場確認高於 regime 分類閾值
   ```

5. **放寬 ROI 目標**
   ```python
   minimal_roi = {
       "0": 0.03,     # 3% 立即目標（原 1.5%）
       "120": 0.015,  # 1.5% after 30h
       "240": 0.005,  # 0.5% after 60h
   }
   ```

6. **收緊 ranging_entry 條件**
   ```python
   ranging_entry = (
       (dataframe["regime"] == 0)
       & (dataframe["close"] < dataframe["bb_lower"])
       & (dataframe["rsi"] < 30)  # 從 40 收緊到 30
       & (dataframe["rsi"] > dataframe["rsi"].shift(1))  # RSI 回升確認
       & (dataframe["volume"] > dataframe["volume"].rolling(20).mean())
   )
   ```

7. **簡化 trending_entry**
   ```python
   trending_entry = (
       (dataframe["regime"] == 2)
       & (dataframe["ema_fast"] > dataframe["ema_slow"])
       & (dataframe["adx_15m"] > 22)  # 提高閾值
       & (dataframe["plus_di"] > dataframe["minus_di"])
   )
   ```

### 🟢 P2 — 中優先級改進

8. **調整 custom_stoploss 層級**
   ```python
   if current_profit < -0.05:
       return -0.05
   elif current_profit < -0.03:
       return -0.03  # 新增 -3%~-5% 層級
   elif current_profit < 0:
       return -0.99

   if current_profit >= 0.05:
       return +0.02
   if current_profit >= 0.03:
       return +0.01
   # 移除 1.5% 層級，讓 ROI 處理小利潤
   ```

9. **縮短 time_exit**
   ```python
   if holding_minutes > 1440:  # 24h instead of 48h
       return "time_exit"
   ```

10. **減少 VOL_RETRAIN_INTERVAL**
    ```python
    VOL_RETRAIN_INTERVAL = 100  # 從 50 提高到 100，減少計算成本
    ```

11. **移除多餘 informative TF**
    ```python
    def informative_pairs(self):
        # 移除 30m，只保留 1h 和 4h
        return [(pair, "1h"), (pair, "4h")]
    ```

### 🔵 P3 — 長期改進

12. **添加 Short 邏輯**
    - 在空頭趨勢中，`can_short = True`
    - 對稱設計：trending short = EMA cross down + ADX > 25 + -DI > +DI
    - 獨立驗證 short 邏輯的 WR

13. **Hyperopt 參數化**
    - 將硬編碼參數轉為 `IntParameter` / `DecimalParameter`
    - 特別是 ADX 閾值、RSI 閾值、ROI 目標

14. **獨立驗證每個組件**
    - 只跑 trending_entry，禁用 ranging_entry
    - 只跑 ranging_entry，禁用 trending_entry
    - 比較兩者的單獨表現

15. **添加 Order Flow 增強**
    - 參考 Hybrid_v3_OF.py 的設計
    - Volume Imbalance + CVD + Spread 作為進場確認
    - 注意 backtest fallback 邏輯

---

## 8. 風險評估矩陣

| 風險 | 可能性 | 影響 | 緩解措施 |
|------|--------|------|----------|
| trailing_stop 衝突 | 高 | 高 | P0: 設 trailing_stop=False |
| transition_entry 虧損 | 高 | 中 | P0: 移除 transition_entry |
| ranging_entry false positive | 中 | 中 | P1: 收緊 RSI < 30 |
| 空頭趨勢中 long-only 虧損 | 高 | 高 | P3: 添加 short 邏輯 |
| 參數未經 hyperopt | 中 | 中 | P3: 參數化並 hyperopt |
| 交易數過少統計不足 | 中 | 中 | P1: 放寬 ROI + 簡化條件 |
| pred_atr 預測失準 | 低 | 中 | 已設 clip [0.005, 0.15] |

---

## 9. 結論

### 總體評分: 6.5/10

**優點**:
- 體制偵測和波動率預測組件設計正確，基於已驗證的數學框架
- 雙模式進場邏輯有學術支持（Generating Alpha 論文）
- 倉位管理設計合理

**缺點**:
- 存在明顯的程式碼矛盾（trailing_stop=True vs 註解說要禁用）
- transition_entry 未經驗證，可能成為虧損來源
- 參數設置過於保守（ROI 1.5%、ADX 18）
- 空頭趨勢中只能 long，無法對沖
- 殭屍程式碼（populate_exit_trend）造成維護混淆

**建議行動**:
1. **立即**: 修復 P0 問題（trailing_stop, transition_entry, 殭屍程式碼）
2. **短期**: 實施 P1 改進（統一閾值、放寬 ROI、收緊 ranging entry）
3. **中期**: 獨立驗證 trending vs ranging entry，只保留表現好的
4. **長期**: 添加 short 邏輯，進行完整 hyperopt

**預期效果**:
- 修復 P0 後，預計能避免 -4.44% 的 trailing_stop_loss 虧損
- 實施 P1 後，預計交易數增加 30-50%，勝率提升 5-10%
- 完整優化後，目標是達到或超越 BB_RPB_TSL_BI 的 +6.22% 基線
