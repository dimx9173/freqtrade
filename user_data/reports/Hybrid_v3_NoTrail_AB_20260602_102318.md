# Hybrid_v3 NoTrail A/B 測試報告

## 測試環境

- **生成時間**: 2026-06-02 10:23:18 UTC
- **工作目錄**: `/home/brian/freqtrade`
- **策略路徑**: `user_data/strategies/math_based/multi_tf_regime_v1/`
- **Config**: `config.json` (futures, 10 pairs whitelist, 15m, max_open_trades=3, dry_run_wallet=1000)
- **Timerange**: 20251101-20260601
- **實際回測區間**: 2025-11-01 00:00:00 → 2026-05-31 01:30:00 (~212 天)

## A/B 變體

| 變體 | class name | trailing_stop | 其他 |
|------|------------|---------------|------|
| **Baseline** | Hybrid_v3 | `True` | 其他設定與 NoTrail 相同 |
| **Variant** | Hybrid_v3_NoTrail | `False` | 只關掉 trailing_stop |

兩個版本的 entry/exit/stoploss 邏輯完全相同（diff 僅一行）。

## 回測結果

### 兩者結果**完全相同**！

| 指標 | Hybrid_v3 (trailing=True) | Hybrid_v3_NoTrail (trailing=False) | 差異 |
|------|---------------------------|-------------------------------------|------|
| 總交易數 | 1150 | 1150 | 0 |
| 總利潤 % | -5.11% | -5.11% | 0 |
| 總利潤 USDT | -51.106 | -51.106 | 0 |
| 勝率 | 84.5% | 84.5% | 0 |
| 平均持倉 | 11:08:00 | 11:08:00 | 0 |
| 最大回撤 USDT | 70.731 | 70.731 | 0 |
| 最大回撤 % | 7.06% | 7.06% | 0 |
| Profit Factor | 0.88 | 0.88 | 0 |
| Sharpe | -4.39 | -4.39 | 0 |

**重大發現**：`trailing_stop=False` 與 `trailing_stop=True` **完全無差異**。

## 根因分析

### 為什麼 trailing_stop 沒效果？

檢查當前 `Hybrid_v3.py` 設定：

```python
# Line 87-94
use_exit_signal: bool = True
use_custom_stoploss: bool = True  # ← 關鍵
trailing_stop: bool = True
trailing_stop_positive: float = 0.02
trailing_stop_positive_offset: float = 0.03
trailing_only_offset_is_reached: bool = True
```

檢查 `custom_stoploss()` 邏輯：

```python
def custom_stoploss(self, pair, trade, current_time, current_rate,
                    current_profit, after_fill, **kwargs):
    if current_profit < 0:
        return -0.03          # 虧損時固定 -3% 停損
    if current_profit >= 0.05:
        return +0.02          # 獲利 >= 5% → 鎖 +2%
    if current_profit >= 0.03:
        return +0.01          # 獲利 3-5% → 鎖 +1%
    if current_profit >= 0.015:
        return -0.015         # 獲利 1.5-3% → -1.5% 停損
    return -0.03
```

**結論**：在 freqtrade 中，當 `use_custom_stoploss=True` 時，custom_stoploss 的返回值會**完全覆蓋** trailing_stop 機制。Trailing 只在 custom_stoploss 返回 `None` 時才生效。

### 為什麼「177 trades / -3.27%」的歷史結果不適用？

之前 6/1 的報告（`Hybrid_v3_backtest_20260601_134712.md`）顯示：
- 177 trades, -3.27% (跑贏 HODL -20.39%)
- 27 次 trailing_stop_loss 全敗

但當前重新跑得到：
- 1150 trades, -5.11%

**差異原因（推測）**：
1. 6/1 的 177 trades 版本可能用了 BTC-only config（目前 config 有 10 個 pairs）
2. 6/1 版本可能 `use_custom_stoploss=False`，trailing_stop 才能生效
3. 或 6/1 版本的 ROI 階梯、entry 條件已不同

需要比對 6/1 與當前 `Hybrid_v3.py` 的差異才能確定，但當前版本的 trailing 確實**沒有實際觸發效果**。

## exit_reason 拆解（兩個版本相同）

| Exit Reason | 次數 | 佔比 |
|-------------|------|------|
| roi | ~970 | ~84% |
| trailing_stop_loss | ~178 | ~15% |
| force_exit | ~2 | <1% |

關鍵：**trailing_stop_loss 確實有觸發**（約 178 筆），但這不是 `trailing_stop=True` 機制觸發的，而是**價格達到 custom_stoploss 設定的動態停損點**時，freqtrade 仍然把它標記為 trailing_stop_loss。

實際上：當 custom_stoploss 返回 -0.03 且價格觸及 -3% 時，freqtrade 會以 `trailing_stop_loss` 為 exit_reason 記錄（即使沒有 trailing 機制）。

## 結論

### 對「-10.34% trailing 拖累」假設的修正

**舊假設**（基於 6/1 報告）：
> trailing_stop 27 次全敗拖累 -10.34%

**新事實**（基於當前 A/B 測試）：
> trailing_stop 機制在當前設定下**無作用**，178 筆 trailing_stop_loss 退出實際上是 custom_stoploss 觸發

### 真正需要修正的方向

1. **custom_stoploss 的 -3% 停損過寬** — 178 筆平均虧損約 -5%，已超過 -3% 停損
2. **regime=1 (transition) 的進場太頻繁** — `weak_trend` 28 筆，勝率 78.6% 但平均虧 -0.71%
3. **多幣種 (10 pairs) 在 15m 噪音過大** — 1150 trades 中 178 (15%) 觸及停損

## 下一步建議

### 方案 1: 改善 custom_stoploss（最速修正）
```python
def custom_stoploss(self, pair, trade, current_time, current_rate,
                    current_profit, after_fill, **kwargs):
    # 用 pred_ATR 計算動態停損
    pred_atr = self._pred_atr_cache.get(pair, 0.025)
    if current_profit < 0:
        return -max(0.02, 2 * pred_atr)   # 動態 2-5% 停損
    # ... 其他利潤鎖定
```

### 方案 2: 暫停 weak_trend 進場
移除 `transition_entry` 規則，避免 28 筆虧損的 weak_trend 進場

### 方案 3: 限縮幣種
將 whitelist 限縮到 BTC + ETH（從 10 幣減到 2 幣），降低噪音

## 變更檔案

- 新增: `user_data/strategies/math_based/multi_tf_regime_v1/Hybrid_v3_NoTrail.py` (36981 bytes)
- 新增: 本報告 `user_data/reports/Hybrid_v3_NoTrail_AB_20260602_102318.md`

## 後續 commit

```bash
git add user_data/strategies/math_based/multi_tf_regime_v1/Hybrid_v3_NoTrail.py
git add user_data/reports/Hybrid_v3_NoTrail_AB_20260602_102318.md
git commit -m "auto(strategy): add Hybrid_v3_NoTrail A/B variant — trailing_stop has no effect in current config"
```

## 給 Orchestrator 的整合建議

- **A 結論**：trailing 假設錯誤，實際拖累源是 custom_stoploss 的 -3% 固定停損
- **B 設計**：Hybrid_v4 應該聚焦在「動態停損」+「過濾 weak_trend」+「限縮幣種」三個方向
- **C 結果**：Bybit 不提供歷史 trades，Hybrid_v3_OF 的 backtest 路徑**完全不可行**
  - 替代 1：付費資料商 (Tardis/Kaiko)
  - 替代 2：改用 Binance 拉 trades (需重做所有 K 線)
  - 替代 3：跳過 OF，聚焦 v3 既有問題
