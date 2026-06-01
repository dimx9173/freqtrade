# ⚠️ DEPRECATED — MultiTFPolyReg_v1

> **此策略已被棄用（deprecated），不應再使用。** 詳見 [`DEPRECATED.md`](./DEPRECATED.md)。
>
> **棄用日期**：2026-06-01
> **原因**：方向預測 SNR = 0.02（統計上不顯著，劣於隨機）
> **替代方案**：
> - `../multi_tf_regime_v1/MultiTF_RegimeDetector_v1.py`（regime 分類）
> - `../multi_tf_regime_v1/Hybrid_v1.py` ~ `Hybrid_v3.py`（regime + 信號混合策略）
>
> 本檔案與原始碼**僅保留供歷史研究與理論參考**，不應用於回測或實盤。

---

# MultiTFPolyReg_v1 — 多元多時間框架多項式回歸策略

## 策略資訊

- **策略名稱**: MultiTFPolyReg_v1
- **策略類型**: math_based（數學理論驅動）
- **版本**: v1
- **建立日期**: 2026-05-29
- **主時間框架**: 5m
- **資訊時間框架**: 15m, 1h, 4h
- **交易所**: Bybit (Spot)
- **交易幣種**: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT

## 檔案結構

```
multi_tf_polyreg_v1/
├── MultiTFPolyReg_v1.py          # 策略主檔
├── config.json                   # Dry-run 設定（port 13989）
├── README.md                     # 本檔案
└── backtest_report.md            # 回測報告模板
```

## 數學理論基礎

本策略基於以下嚴謹的數學框架設計：

### 1. Weierstrass / Stone-Weierstrass 逼近定理

> 任何連續函數 $f \in C([a,b])$ 皆可被多項式一致逼近。

- **推論**：金融價格函數（在有限區間內）可用多項式回歸建模
- **限制**：定理不保證收斂速率、係數穩定性

### 2. Nyquist-Shannon 取樣定理

> 若要從離散樣本完美重建信號，取樣頻率必須 ≥ 2× 信號最大頻率

- 金融市場 $f_{\max} \approx \text{tick-level}$ → 取樣永遠不足
- **實務推論**：金融 SNR ≈ 0.02 → **degree ≤ 2**（來源：THEORY_FRAMEWORK.md）
- degree=2 為硬約束，不可放寬

### 3. Wavelet MRA（多解析度分析）

> 不同時間框架的價格資訊經由正交小波分解後，屬於不同的 Wj 子空間，**互相獨立**。

- **推論**：多 TF 特徵提供的資訊是正交獨立的 → 多元回歸有效
- 5m / 15m / 1h / 4h 的價格+量特徵構成多元輸入向量

### 4. Ridge 正則化

> 低 SNR 環境下，$\ell_2$（Ridge）比 $\ell_1$（Lasso）更穩定。

- $\ell_1$ 傾向將係數收縮到 0，容易丟失微弱信號
- $\ell_2$ 保留所有維度，僅收縮係數 → 適合金融低 SNR
- Ridge $\alpha = 0.1$（預設值）

### 5. 連續值預測 → sign() 轉方向

- **直接預測方向**（+1/-1）的 sign 函數不連續 → 訓練時產生 Gibbs 現象
- **解法**：預測**連續收益率**，再以 `sign(pred_return)` 轉方向
- 進場門檻 `entry_threshold = 0.002`（預測收益率 > 0.2% 才進場）

### 6. BIC 模型選擇（未來迭代）

- BIC = $-2\ln(\hat{L}) + k\ln(n)$
- 低 SNR 下比 AIC 保守（懲罰項 $\ln(n) > 2$）
- v1 使用固定 max_features=20 + SelectKBest（f_regression）作特徵選擇

### 7. 滾動窗口訓練

> 金融市場為非平穩過程 → 全域擬合失效

- 滾動窗口大小 `window = 300`（約 25 小時的 5m bars）
- 每 `retrain_interval = 50` 根 bar 重新訓練一次模型
- Walk-forward 訓練 → 零 lookahead bias

## 策略參數

| 參數 | 預設值 | 範圍 | 說明 |
|------|--------|------|------|
| degree | 2（硬約束） | - | 多項式最高次數 ≤ 2 |
| window | 300 | 100–500 | 訓練窗口大小（5m bars） |
| forecast_horizon | 12 | 4–24 | 預測 N 根 bar 後的收益率 |
| ridge_alpha | 0.1 | 0.01–10 | Ridge 正則化強度 |
| entry_threshold | 0.002 | 0.001–0.015 | 進場門檻（預測收益率） |
| max_features | 20 | 10–40 | 最大特徵數（SelectKBest） |
| retrain_interval | 50 | 20–150 | 重新訓練間隔（bars） |
| stoploss | -0.05 | - | 固定止損 |
| minimal_roi | 0: 5%, 60: 3%, 120: 1% | - | 分段獲利了結 |

## 特徵工程

### 每 TF 擷取的特徵（~13 項）

每個時間框架獨立計算：

| 特徵 | 說明 |
|------|------|
| `ret_1` | 1 期收益率 |
| `ret_5` | 5 期收益率 |
| `ret_10` | 10 期收益率 |
| `vol_20` | 20 期滾動波動率 |
| `price_pos` | 價格在 20 期範圍內的相對位置 |
| `ma_dev_20` | 偏離 20 期均線程度 |
| `ma_dev_50` | 偏離 50 期均線程度 |
| `vol_ratio` | 成交量相對於 20 期均值 |
| `rsi_14` | RSI 正規化到 [0,1] |
| `macd` | MACD 線（正規化） |
| `macd_signal` | MACD 訊號線（正規化） |
| `macd_hist` | MACD 柱狀圖（正規化） |
| `adx` | ADX 趨勢強度（正規化） |

### 特徵處理 Pipeline

```
Raw Features (4 TF × ~13 = ~52)
    ↓
StandardScaler（標準化）
    ↓
PolynomialFeatures(degree=2) → ~1400 多項式特徵
    ↓
SelectKBest(f_regression, k=20) → 20 最佳特徵
    ↓
Ridge(alpha=0.1) → 預測對數收益率
```

## 進場 / 出場邏輯

### 進場
- `pred_return > entry_threshold` → `enter_long`
- 預測收益率（對數）超過門檻時做多

### 出場
- `pred_return < 0 且上一根 ≥ 0` → `exit_long`（預測轉向時出場）
- 搭配 `stoploss = -0.05` 與 `trailing_stop` 防禦

## 執行方式

```bash
# 回測
freqtrade backtesting \
  --config user_data/strategies/math_based/multi_tf_polyreg_v1/config.json \
  --strategy MultiTFPolyReg_v1 \
  --timerange 20251101-20260529

# Dry-run（即時模擬）
freqtrade trade \
  --config user_data/strategies/math_based/multi_tf_polyreg_v1/config.json \
  --strategy MultiTFPolyReg_v1
```

## 注意事項

- **sklearn 依賴**：需要 `scikit-learn` 套件（`pip install scikit-learn`）
- **獨立 port**：13989（Dry-run），不可與其他 Bot 衝突
- **獨立 sqlite**：`tradesv3_multi_tf_polyreg_v1.sqlite`（由 Freqtrade 依 config 自動產生）
- **lookahead 防範**：使用 `merge_asof(direction='backward')` 確保不使用未來資訊
- **首次啟動**：需要足夠歷史資料（≥ startup_candle_count = 400 根 bar）

## 參考文獻

- THEORY_FRAMEWORK.md — 數學理論框架文件
- Weierstrass Approximation Theorem (1885)
- Nyquist-Shannon Sampling Theorem (1949)
- Mallat, S. "A Wavelet Tour of Signal Processing" (1999)
- Hoerl & Kennard, "Ridge Regression" (1970)
- Schwarz, G. "Estimating the Dimension of a Model" (1978, BIC)
