# FreqAI_ML_Strategy_v30.py 優化方案

**基於研究維度和分析維度的輸出制定**  
**日期: 2026-04-30**

---

## 1. FreqAI 最佳實踐（基於 FreqAI 最新文件 v2026.3）

### 1.1 FreqAI 核心配置建議

| 參數 | 建議值 | 說明 |
|------|--------|------|
| `freqai_enabled` | `true` | 啟用 ML 引擎 |
| `train_period_days` | 15-30 天 | 訓練數據窗口 |
| `backtest_period_days` | 7 天 | 回測窗口 |
| `purge_old_models` | 2 | 保留最近 2 個模型 |
| `live_retrain_hours` | 0 或根據需求 | 即時訓練設定 |

### 1.2 Feature Parameters 最佳化

```json
{
    "include_timeframes": ["5m", "15m", "1h"],
    "include_shifted_candles": 2-3,
    "label_period_candles": 20-24,
    "weight_factor": 0.9,
    "use_SVM_to_remove_outliers": true,
    "principal_component_analysis": false,
    "DI_threshold": 0.9,
    "indicator_periods_candles": [10, 20, 50]
}
```

### 1.3 Model Training 建議

| 模型 | 建議參數 |
|------|----------|
| **LightGBM** | `n_estimators`: 800, `learning_rate`: 0.03, `max_depth`: 8 |
| **XGBoost** | `n_estimators`: 800, `learning_rate`: 0.03, `max_depth`: 8 |
| **PyTorch** | 支援 early_stopping_patience (2026.3 新功能) |

### 1.4 FreqAI 限制與注意事項

- ⚠️ **不能**與動態 VolumePairlists 合併使用
- ✅ 使用 ShufflePairlist 或靜態 VolumePairlist
- ⚠️ CatBoost 不支援低功耗 ARM 設備
- ✅ 支援 Kraken Futures、Hyperliquid (2026.3)

---

## 2. 目前策略分析摘要

### 2.1 策略現況 (FreqAI_ML_Strategy_v30.py)

**優點:**
- ✅ `freqai_enabled = True` 正確啟用 ML
- ✅ 15m timeframe（已驗證最佳）
- ✅ EMA 多頭市場制度過濾
- ✅ 微觀結構特徵（已放寬閾值）
- ✅ Trailing Stop 風控參數
- ✅ 動態倉位管理

**需改進:**
- ⚠️ ML信心閾值固定 (ml_confidence_threshold, ml_prediction_threshold)
- ⚠️ 市場制度適應為 BooleanParameter，無法針對不同制度優化參數
- ⚠️ Feature engineering 可能過度複雜
- ⚠️ 入場邏輯有兩層（high_confidence_entry + standard_entry）

### 2.2 已驗證的績效目標

| 指標 | 已實現 | 目標 |
|------|--------|------|
| 15m timeframe | ✅ 12.84% (vs 5m: 4.27%) | ✅ 已確認 |
| 勝率 | 62-65% | ≥55% ✅ |
| 最大回撤 | 1.22-1.55% | ≤12% ✅ |
| SQN | 2.26-2.86 | >2 ✅ |
| OOS/IS ratio | 64% | >70% ⚠️ |

---

## 3. 具體改進方向

### 方向 A：Model 替換（LightGBM → XGBoost）

**目標:** 提升模型預測準確度和穩定性

#### 具體修改內容

1. **修改 config_freqai.json:**
```json
{
    "freqai": {
        "identifier": "FreqAI_XGBoost_v30",
        "model_training_parameters": {
            "n_estimators": 800,
            "learning_rate": 0.03,
            "max_depth": 8,
            "colsample_bytree": 0.9,
            "subsample": 0.9,
            "reg_alpha": 0.3,
            "reg_lambda": 0.3
        }
    }
}
```

2. **策略中替換 model name:**
```python
# 啟動時使用 --freqaimodel XGBoostRegressor
```

#### 預期效果

| 效果 | 說明 |
|------|------|
| ✅ 提升預測穩定性 | XGBoost的正則化通常更強 |
| ✅ 改善OOS/IS ratio | 目標從 64% 提升至 70%+ |
| ✅ 更好的特徵重要性分析 | XGBoost 的特徵重要性更直觀 |

#### 風險/缺點

| 風險 | 說明 |
|------|------|
| ⚠️ 訓練時間增加 | XGBoost 通常比 LightGBM 慢 10-20% |
| ⚠️ 記憶體使用增加 | 可能影響低記憶體設備 |
| ⚠️ 需要重新驗證 | 不同模型可能需要調整閾值 |

---

### 方向 B：ML 信心閾值動態化

**目標:** 根據市場制度調整 ML 進場門檻

#### 具體修改內容

1. **新增制度特定閾值參數:**
```python
# ML 信心閾值（制度適應）
ml_confidence_threshold_trend = DecimalParameter(0.55, 0.85, default=0.60, decimals=2, space="buy")
ml_confidence_threshold_volatile = DecimalParameter(0.65, 0.90, default=0.75, decimals=2, space="buy")
ml_prediction_threshold_trend = DecimalParameter(0.55, 0.80, default=0.60, decimals=2, space="buy")
ml_prediction_threshold_volatile = DecimalParameter(0.65, 0.85, default=0.70, decimals=2, space="buy")
```

2. **修改 populate_entry_trend:**
```python
# 根據市場制度選擇閾值
regime = DataFrame['market_regime']
ml_confidence = np.where(
    regime == 'strong_trend',
    self.ml_confidence_threshold_trend.value,
    np.where(regime == 'high_volatility',
             self.ml_confidence_threshold_volatile.value,
             self.ml_confidence_threshold.value)
)
ml_prediction = np.where(
    regime == 'strong_trend',
    self.ml_prediction_threshold_trend.value,
    np.where(regime == 'high_volatility',
             self.ml_prediction_threshold_volatile.value,
             self.ml_prediction_threshold.value)
)
```

#### 預期效果

| 效果 | 說明 |
|------|------|
| ✅ 減少震盪市錯誤信號 | 提高 volatile 市場的閾值 |
| ✅ 捕捉趨勢市的機會 | 降低 trend 市場的閾值 |
| ✅ 減少過擬合 | 制度適應降低 OOS 性能下降 |

#### 風險/缺點

| 風險 | 說明 |
|------|------|
| ⚠️ 參數數量增加 | 從 2 個閾值變成 4 個 |
| ⚠️ 優化複雜度提升 | 需要更多 hyperopt 時間 |
| ⚠️ 可能過度適應 | 需要 walk-forward 驗證 |

---

### 方向 C：Feature Engineering 簡化與強化

**目標:** 移除冗餘特徵，增加高價值特徵

#### 具體修改內容

1. **簡化微觀結構特徵:**
```python
# 移除低價值特徵（保留核心）
def add_microstructure_features(self, dataframe: DataFrame) -> DataFrame:
    # 保留: pressure_ratio, volume_ratio, liquidity_proxy
    # 簡化: 移除 price_momentum, price_acceleration (已有其他指標)
    
    # 新增 FreqAI 友好的滾動窗口特徵
    dataframe['volume_ratio_5'] = dataframe['volume'] / ta.SMA(dataframe['volume'], timeperiod=5)
    dataframe['volume_ratio_20'] = dataframe['volume'] / ta.SMA(dataframe['volume'], timeperiod=20)
    
    # 波動率標準化
    dataframe['volatility_normalized'] = (
        dataframe['atr'] / ta.SMA(dataframe['atr'], timeperiod=20)
    )
    
    return dataframe
```

2. **增加制度識別特徵（基於市場研究）:**
```python
# ADX 趨勢強度（研究建議）
dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

# Bollinger Band Width（突破市識別）
bb_upper, bb_middle, bb_lower = ta.BBANDS(dataframe)
dataframe['bb_width'] = (bb_upper - bb_lower) / dataframe['close']
dataframe['bb_width_roc'] = dataframe['bb_width'].pct_change(5)

# ATR Ratio（波動性擴展）
dataframe['atr_ratio'] = dataframe['atr'] / ta.SMA(dataframe['atr'], timeperiod=20)
```

3. **移除冗餘 SMA/EMA:**
```python
# 從 8+ 個 EMA 減少到關鍵的 4-5 個
for period in [12, 26, 50, 200]:  # 只保留關鍵週期
    dataframe[f'ema_{period}'] = ta.EMA(dataframe, timeperiod=period)
```

#### 預期效果

| 效果 | 說明 |
|------|------|
| ✅ 加快訓練速度 | 減少特徵 = 減少訓練時間 |
| ✅ 降低過擬合風險 | 移除噪聲特徵 |
| ✅ 改善預測準確度 | 聚焦關鍵特徵 |

#### 風險/缺點

| 風險 | 說明 |
|------|------|
| ⚠️ 可能移除有用特徵 | 需要嚴格驗證 |
| ⚠️ 增加開發時間 | 需要多次回測驗證 |
| ⚠️ 改變策略特性 | 需要重新評估績效 |

---

### 方向 D：Training 參數優化

**目標:** 調整 FreqAI 訓練參數提升模型品質

#### 具體修改內容

1. **調整 config_freqai.json:**
```json
{
    "freqai": {
        "train_period_days": 30,
        "backtest_period_days": 7,
        "feature_parameters": {
            "include_shifted_candles": 3,
            "label_period_candles": 24,
            "weight_factor": 0.85,
            "use_SVM_to_remove_outliers": true,
            "DI_threshold": 0.85
        },
        "data_split_parameters": {
            "test_size": 0.25,
            "shuffle": false
        },
        "model_training_parameters": {
            "n_estimators": 1000,
            "learning_rate": 0.02,
            "max_depth": 6,
            "num_leaves": 40,
            "min_child_samples": 150,
            "colsample_bytree": 0.8,
            "subsample": 0.8
        }
    }
}
```

2. **策略中新增 early stopping:**
```python
# 使用 PyTorch 或設定 early_stopping_patience（FreqAI 2026.3 新功能）
# 對於 LightGBM/XGBoost，可透過 n_estimators 控制
```

#### 預期效果

| 效果 | 說明 |
|------|------|
| ✅ 更好的泛化能力 | 更長訓練窗口減少過擬合 |
| ✅ 降低過擬合風險 | 減少 num_leaves, 增加 min_child_samples |
| ✅ 改善 OOS/IS ratio | 目標從 64% 提升至 70%+ |

#### 風險/缺點

| 風險 | 說明 |
|------|------|
| ⚠️ 訓練時間增加 | train_period_days 15→30 |
| ⚠️ 即時訓練延遲 | 更多數據需要更長時間 |
| ⚠️ 可能降低對近期市場的適應 | 訓練窗口過長 |

---

### 方向 E：幣種精簡與篩選

**目標:** 專注於高表現幣種，移除低表現幣種

#### 具體修改內容

1. **修改 pair_whitelist:**
```json
{
    "pair_whitelist": [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "SOL/USDT:USDT",
        "XRP/USDT:USDT",
        "LTC/USDT:USDT"
    ]
}
```

2. **新增 DynamicPairList 限制:**
```python
# 在 config 中使用 StaticPairList 替代 VolumePairList
"pairlists": [
    {
        "method": "StaticPairList"
    }
]
```

#### 預期效果（基於 multi_pair_comparison 報告）

| 效果 | 說明 |
|------|------|
| ✅ 提升總利潤 | 13.29% vs 10.03% (5幣 vs 15幣) |
| ✅ 提升勝率 | 61.9% vs 52.6% |
| ✅ 降低最大回撤 | 1.55% vs 4.43% |
| ✅ 提升 SQN | 2.86 vs 1.44 |

#### 風險/缺點

| 風險 | 說明 |
|------|------|
| ⚠️ 交易機會減少 | 5幣 vs 15幣 |
| ⚠️ 集中風險 | 如果單幣表現不佳 |
| ⚠️ 需要定期再評估 | 幣種表現可能改變 |

---

## 4. 優先順序建議

### 4.1 建議執行順序

| 優先順序 | 方向 | 理由 | 預期提升 |
|---------|------|------|----------|
| **1️⃣ 優先** | **E：幣種精簡** | 已被數據驗證，立即可執行 | +3.26% 利潤 |
| **2️⃣** | **B：ML閾值動態化** | 直接改善進場信號品質 | 減少錯誤信號 |
| **3️⃣** | **A：Model替換** | XGBoost 正則化更強 | OOS/IS +6% |
| **4️⃣** | **C：Feature簡化** | 加速訓練，降低過擬合 | 訓練速度 +20% |
| **5️⃣** | **D：Training參數** | 需要長期驗證 | OOS/IS +6% |

### 4.2 分階段實施計劃

```
Phase 1 (Week 1-2): 方向 E
├── 執行幣種精簡（5幣）
├── 回測驗證
└── 確認績效提升

Phase 2 (Week 3-4): 方向 B + A
├── 實作動態 ML 閾值
├── 替換為 XGBoost
├── 回測驗證
└── Walk-forward 驗證

Phase 3 (Week 5-6): 方向 C
├── 簡化特徵工程
├── 回測驗證
└── 確認訓練速度

Phase 4 (Week 7-8): 方向 D
├── 調整訓練參數
├── 長期回測驗證
└── OOS/IS ratio 確認 > 70%
```

### 4.3 量化預期目標

| 指標 | 目前 | Phase 1 後 | Phase 2 後 | 最終目標 |
|------|------|------------|------------|----------|
| 總利潤 % | ~10-13% | 13-15% | 15-18% | ≥15% |
| 勝率 | 62-65% | 62-65% | 63-67% | ≥55% |
| 最大回撤 | 1.22-4.43% | <2% | <2% | ≤12% |
| SQN | 2.26-2.86 | 2.5-3.0 | 2.5-3.0 | >2 |
| OOS/IS | 64% | 64% | 70%+ | >70% |

---

## 5. 關鍵風險提示

### 5.1 過擬合風險
- OOS/IS ratio 64% 低於 70% 閾值
- 建議加強 walk-forward 驗證

### 5.2 市場制度風險
- 研究顯示市場 49% 為震盪市
- 需要更保守的進場條件

### 5.3 模型更新風險
- 訓練窗口調整可能影響即時適應性
- 建議保留 `live_retrain_hours` 選項

---

## 6. 總結

本優化方案提供 5 個具體改進方向，建議優先執行「幣種精簡」（方向E），因為該方向已由 backtest data 驗證，能夠明確提升績效。隨後結合「ML閾值動態化」（方向B）和「Model替換」（方向A）進行綜合優化。

**核心原則：**
1. ✅ 以數據驅動決策
2. ✅ 分階段實施並驗證
3. ✅ 保持 OOS/IS ratio > 70%
4. ✅ 聚焦高表現幣種
5. ✅ 制度適應的 ML 閾值

---

*文件生成時間: 2026-04-30*