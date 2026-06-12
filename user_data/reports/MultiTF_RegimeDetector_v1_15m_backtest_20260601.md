# MultiTF_RegimeDetector_v1 — 15m Backtest Report

**日期**: 2026-06-01
**策略**: MultiTF_RegimeDetector_v1
**時間框架**: 15m
**交易模式**: futures (USDT perpetual, isolated)
**回測區間**: 2025-11-01 ~ 2026-05-31
**幣種池**: 10 個（BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, TON, SUI）
**槓桿**: 1x（預設 futures）
**初始資金**: 1000 USDT
**單筆下注**: 50 USDT
**最大同時持倉**: 3

---

## 結果總覽

| 指標 | 數值 | 評估 |
|------|------|------|
| 交易數 | 5185 | ⚠️ 過高（多幣種×7個月） |
| 總利潤 | -94.96% | 💀 帳戶幾乎歸零 |
| 總利潤 USDT | -949.625 | 從 1000 → 50.375 |
| 勝率 | 12.2% | 💀 極低 |
| 平均持倉 | 0:42:00 | 短線 |
| 最大回撤 | 94.97% | 💀 幾乎全毀 |
| 連勝/連敗 | 10 / 65 | 連虧 65 次 |
| 市場表現 | -42.48% | 跑輸市場 52.48% |

---

## 與基線對比

| 指標 | 30m 基線（單幣BTC）| 15m 多幣（10 個）| 變化 |
|------|---------------------|------------------|------|
| 交易數 | 234 | 5185 | +22x |
| 總利潤 | -3.11% | -94.96% | 惡化 30 倍 |
| 勝率 | 39.7% | 12.2% | -27.5pp |
| 最大回撤 | 3.45% | 94.97% | +91.52pp |

**結論**：從 30m 切到 15m 並擴展到 10 個幣種，表現**全面崩潰**。

---

## 失敗原因分析

### 1. 多幣種擴展的副作用
- **過擬合風險**：策略參數為 BTC 優化，套用於 10 個幣種時不適用
- **流動性差異**：DOGE/AVAX/TON/SUI 在 15m 級別的雜訊更大
- **Regime 跨市場不一致**：BTC 在 trending 時，其他幣種可能 ranging

### 2. 15m 進場頻率過高
- 5185 trades / 7 個月 / 10 幣種 = 平均每幣每天 2.5 次交易
- 過度交易導致手續費累積 + 雜訊暴露

### 3. 進場訊號品質差
- 12.2% 勝率表示進場後價格方向幾乎隨機
- 與之前結論一致：**純 Regime + 波動率 + BB/EMA 進場邏輯不夠**

---

## 退出原因分析

（需從 trades.json 進一步分析；目前觀察到 65 連敗，估計主要為 stop_loss 觸發）

---

## 教訓

1. **不要盲目擴展幣種**：策略為 BTC 優化時，不應直接套用到 10 個幣種
2. **時間框架選擇很重要**：15m 在多幣種下雜訊過大
3. **進場邏輯需強化**：Regime + 波動率只決定倉位大小，不該獨自決定進場時機

---

## 下一步建議

### A. 回歸單幣種（BTC）測試 15m
```bash
freqtrade backtesting --strategy-path user_data/strategies/math_based/multi_tf_regime_v1 \
  --config user_data/strategies/math_based/multi_tf_regime_v1/config_btc.json \
  --strategy MultiTF_RegimeDetector_v1 --timerange 20251101-20260601
```

### B. 套用 Hybrid_v3（BB_RPB 進場邏輯）
直接整合 BB_RPB 進場訊號（+6.22% 基線），不依賴 Regime 進場

### C. 暫停 15m 實驗，回到 30m + 單幣 BTC
目前 30m 單幣 BTC 雖然虧 -3.11%，但表現穩定，是更好的起點

---

**結論：MultiTF_RegimeDetector_v1 在 15m × 10 幣種配置下完全失敗，需重新設計。**

*報告生成時間: 2026-06-01*
*Source: user_data/strategies/math_based/multi_tf_regime_v1/MultiTF_RegimeDetector_v1.py*
*Config: user_data/strategies/math_based/multi_tf_regime_v1/config.json*
