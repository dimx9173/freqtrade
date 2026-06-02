# Math-Based GA 迭代框架 — 完整架構設計

**版本**: v3.0  
**作者**: Brian Tseng (Speculari)  
**設計日期**: 2026-05-29  
**狀態**: 設計階段，待實作  

---

## 目錄

1. [設計目標與數學鐵律](#一設計目標與數學鐵律)
2. [目錄結構](#二目錄結構)
3. [組件規格](#三組件規格)
4. [迭代流程與狀態機](#四迭代流程與狀態機)
5. [資料流設計](#五資料流設計)
6. [與數學理論的對齊檢查清單](#六與數學理論的對齊檢查清單)
7. [與現有元件的整合方式](#七與現有元件的整合方式)
8. [配置規格](#八配置規格)
9. [回報與可觀測性](#九回報與可觀測性)

---

## 一、設計目標與數學鐵律

### 1.1 核心設計目標

本框架的設計目標是**將數學驗證結果系統性地編碼到 GA 迭代流程中**，確保每一次超參數搜索都遵守已驗證的數學邊界條件。這與傳統 freqtrade hyperopt（NSGAIII 無約束搜索）有本質區別：

| 面向 | 傳統 freqtrade hyperopt | 本框架 |
|------|------------------------|--------|
| 參數空間 | 任意範圍 | 數學約束邊界 |
| 模型複雜度 | 無限制 | degree ≤ 2 |
| 正則化 | 無 | Ridge (α ∈ [0.1, 10]) |
| 模型選擇 | 無 | BIC |
| 時間處理 | 全局擬合 (expand) | 滾動窗口 |
| 預測目標 | 方向 (binary) | 連續收益率 |
| 多TF | 單一 timeframe | 4×TF 多元 (Wavelet MRA) |
| 驗證 | 單次 backtest | Walk-Forward + 穩健性檢查 |
| SNR 感知 | 無 | 基於 SNR≈0.02 的預期邊界 |

### 1.2 數學鐵律 (不可違反)

這些鐵律來自已完成的數學驗證，框架中的所有組件都必須遵守：

| # | 鐵律 | 數學依據 | 強制方式 |
|---|------|---------|---------|
| 1 | **degree ≤ 2** (最優 1.8) | 高次多項式在 SNR≈0.02 下必然 overfit | GA 搜索空間硬約束 + ConstraintValidator |
| 2 | **Ridge 正則化** (非 Lasso) | Lasso 在極低 SNR 下會錯誤地將係數歸零 | 策略模板強制使用 Ridge |
| 3 | **預測收益率** (連續值，非方向) | 方向分類損失資訊；連續值保留 SNR 微弱信號 | 損失函數設計 + Strategy 介面 |
| 4 | **BIC 模型選擇** | AIC 在低 SNR 下傾向過度複雜模型 | ModelSelector 組件 |
| 5 | **滾動窗口** (非全局擬合) | 全局擬合引入 look-ahead bias；金融時間序列非平穩 | RollingWindowManager 組件 |
| 6 | **多TF 作為多元變數** | Wavelet MRA 正交分解保證不同 TF 的特徵獨立性 | MultiTFEncoder 組件 |
| 7 | **SNR ≈ 0.02** (極低) | 決定 Sharp 比預期上限 ≈ 0.2-0.4 | SNR-aware 超參數邊界推導 |

---

## 二、目錄結構

```
user_data/strategies/math_based/ga_framework/
│
├── ARCHITECTURE.md                    # 本檔案：架構設計文件
├── README.md                          # 框架使用手冊 (由 ARCHITECTURE.md 產生)
│
├── bin/                               # 可執行入口 (CLI)
│   ├── ga_iterate.py                  # 主迭代入口：協調完整迭代循環
│   ├── ga_setup.py                    # 初始化：產生策略模板 + 參數空間 + 配置
│   ├── ga_validate.py                 # 驗證：對結果執行數學約束檢查
│   └── ga_report.py                   # 報告：產生迭代摘要與視覺化
│
├── lib/                               # 核心函式庫
│   ├── __init__.py
│   │
│   ├── constraints/                   # 數學約束驗證
│   │   ├── __init__.py
│   │   ├── validator.py               # ConstraintValidator: 檢查所有鐵律
│   │   ├── degree_constraint.py       # degree ≤ 2 檢查
│   │   ├── ridge_constraint.py        # Ridge α 範圍檢查
│   │   ├── bic_constraint.py          # BIC 選擇邏輯
│   │   └── snr_bounds.py             # SNR-aware 超參數邊界推導
│   │
│   ├── models/                        # 多項式回歸模型
│   │   ├── __init__.py
│   │   ├── polynomial_regressor.py    # 加權 Ridge 多項式回歸 (核心)
│   │   ├── rolling_window.py          # RollingWindowManager: 滾動窗口管理
│   │   ├── bic_selector.py            # BIC-based model selector
│   │   └── multi_tf_encoder.py        # MultiTFEncoder: Wavelet MRA 編碼
│   │
│   ├── optimizers/                    # GA 優化器 (取代 freqtrade hyperopt)
│   │   ├── __init__.py
│   │   ├── ga_engine.py               # GAEngine: 自訂 GA 搜索 (非 NSGAIII)
│   │   ├── fitness_function.py        # 多目標適應度函數 (含 SNR-aware 調整)
│   │   ├── param_space.py             # 參數空間定義 (含數學約束)
│   │   └── crossover_mutation.py      # 交配/突變算子 (保證約束滿足)
│   │
│   ├── validation/                    # 驗證框架
│   │   ├── __init__.py
│   │   ├── walk_forward.py            # WalkForward: 滾動窗口驗證
│   │   ├── monte_carlo.py             # Monte Carlo: 穩健性測試
│   │   ├── stability_metrics.py       # 穩定性指標 (CV, IC, rank correlation)
│   │   └── out_of_sample.py           # OOS 測試管理
│   │
│   ├── strategies/                    # 策略模板與工廠
│   │   ├── __init__.py
│   │   ├── base_strategy.py           # MathBasedStrategy: 基礎類別
│   │   ├── strategy_factory.py        # 動態策略產生器
│   │   └── templates/                 # Jinja2 模板
│   │       ├── polynomial_strategy.py.j2
│   │       └── config.json.j2
│   │
│   ├── data/                          # 資料管理
│   │   ├── __init__.py
│   │   ├── data_loader.py             # 多TF K 線載入
│   │   ├── feature_engineering.py     # 特徵工程 (收益率計算、標準化)
│   │   └── dataset_splitter.py        # 訓練/驗證/測試分割
│   │
│   └── reporting/                     # 報告與可觀測性
│       ├── __init__.py
│       ├── iteration_logger.py         # 迭代記錄器
│       ├── metrics_tracker.py          # MLflow/W&B 風格指標追蹤
│       ├── comparison_report.py        # 跨迭代比較
│       └── exporters/
│           ├── json_exporter.py        # JSON 參數匯出
│           ├── markdown_exporter.py    # Markdown 報告匯出
│           └── freqtrade_exporter.py   # Freqtrade 策略 JSON 匯出
│
├── config/                            # 配置檔案
│   ├── ga_config.yaml                 # 主配置：GA 參數、策略選擇、時間範圍
│   ├── param_spaces/                  # 參數空間定義
│   │   ├── polynomial_v1.yaml         # 多項式回歸 v1 參數空間
│   │   ├── adaptive_v1.yaml           # 自適應策略 v1 參數空間
│   │   └── custom_template.yaml       # 自訂範本
│   └── constraints/                   # 約束定義
│       └── math_laws.yaml             # 數學鐵律參數化
│
├── iterations/                        # 迭代記錄 (持久化)
│   ├── index.yaml                     # 迭代索引 (所有迭代的 metadata)
│   └── {strategy_name}/              # 每個策略獨立目錄
│       ├── iter_001/                  # 迭代 1
│       │   ├── config.yaml            # 該次迭代的配置快照
│       │   ├── params.json            # 最佳參數
│       │   ├── metrics.json           # 效能指標
│       │   ├── validation_report.md   # 驗證報告
│       │   ├── constraint_check.json  # 約束檢查結果
│       │   └── strategy.py            # 產生的策略程式碼 (如有)
│       ├── iter_002/
│       └── ...
│
├── reports/                           # 匯出報告 (舊目錄保留相容)
│   └── {strategy_name}/
│       └── {session_id}/
│
├── logs/                              # 執行日誌
│
├── tests/                             # 框架本身的測試
│   ├── test_constraints.py
│   ├── test_polynomial_regressor.py
│   ├── test_walk_forward.py
│   └── test_ga_engine.py
│
├── run_ga.sh                          # [保留] 舊版薄包裝 (向後相容)
├── analyze_results.py                 # [保留] 舊版分析器 (向後相容)
├── ga_config_template.json            # [保留] 舊版配置模板 (向後相容)
└── iteration_tracker.md               # [保留] 舊版追蹤器 (向後相容)
```

---

## 三、組件規格

### 3.1 核心引擎：`ga_iterate.py`

**角色**: 框架主入口，協調整個迭代循環。

**規格**:
```
功能:
  1. 讀取 ga_config.yaml 配置
  2. 初始化策略模板 (從 templates/)
  3. 設定參數空間 (從 param_spaces/)
  4. 啟動 GA 搜索 (調用 ga_engine.py)
  5. 對每代最優個體執行約束檢查 (調用 validator.py)
  6. 執行 Walk-Forward 驗證
  7. 產生迭代報告
  8. 匯出最佳參數為 freqtrade 相容 JSON

CLI 介面:
  ga_iterate.py --config config/ga_config.yaml --strategy polynomial_v1
  ga_iterate.py --resume --iteration-id iter_003
  ga_iterate.py --validate-only --params iterations/polynomial_v1/iter_001/params.json

狀態管理:
  - 每次迭代有唯一 iteration_id
  - 支援 resume (從中斷處繼續)
  - 支援 dry-run (僅驗證，不執行 GA)
```

### 3.2 數學約束驗證器：`validator.py`

**角色**: 保證每個參數組合符合數學鐵律。

**規格**:
```python
class ConstraintValidator:
    """
    數學約束驗證器。
    在 GA 搜索的兩個階段被調用：
    1. 參數生成時 (硬約束)：拒絕不合規的個體
    2. 結果驗證時 (軟約束)：產生警告但記錄結果
    """
    
    # 硬約束 (違反 → 拒絕個體)
    HARD_CONSTRAINTS = [
        "degree <= 2",                    # 鐵律 1
        "regularization == 'ridge'",      # 鐵律 2
        "BIC_selected == True",           # 鐵律 4
    ]
    
    # 軟約束 (違反 → 標記警告)
    SOFT_CONSTRAINTS = [
        "prediction_target == 'returns'", # 鐵律 3
        "use_rolling_window == True",     # 鐵律 5
        "multi_tf_enabled == True",       # 鐵律 6
        "expected_sharpe <= 0.4",        # 鐵律 7 (SNR≈0.02)
    ]
```

**輸入**: 參數 dict + 策略 metadata  
**輸出**: `(passed: bool, violations: List[Violation])`  
**Violation 結構**: `{constraint_id, severity (HARD/SOFT), actual_value, expected_range, message}`

### 3.3 多項式回歸模型：`polynomial_regressor.py`

**角色**: 核心預測模型，封裝加權 Ridge 多項式回歸。

**規格**:
```python
class WeightedRidgePolynomialRegressor:
    """
    加權 Ridge 多項式回歸。
    
    數學形式:
      y_hat = β₀ + β₁·x + β₂·x²  (degree ≤ 2)
      L(β) = Σ w_i·(y_i - ŷ_i)² + α·Σ β_j²  (Ridge)
      w_i = decay^(n-i)  (指數衰減加權)
    
    約束:
      - degree ∈ {1, 2} (嚴格 ≤ 2)
      - α ∈ [0.1, 10.0] (Ridge 正則化)
      - decay ∈ [0.85, 0.99] (時間衰減)
      - 預測目標: log_return(t+1)
    """
    
    def fit(self, prices, degree, alpha, decay):
        """擬合模型，返回 BIC 值"""
        
    def predict(self, prices):
        """預測下一根 K 線的收益率"""
        
    def get_bic(self):
        """返回 BIC 值 (用於模型選擇)"""
        
    def get_residuals(self):
        """返回殘差 (用於穩健性分析)"""
```

### 3.4 滾動窗口管理器：`rolling_window.py`

**角色**: 管理時間序列的滾動窗口分割。

**規格**:
```python
class RollingWindowManager:
    """
    滾動窗口管理器。
    
    金融時間序列非平穩，不可使用全局擬合。
    
    配置:
      window_size: 擬合窗口大小 (建議 200-500 candles)
      step_size: 滾動步長 (建議 window_size/4)
      min_train_windows: 最少訓練窗口數 (建議 10)
      
    輸出:
      List[Window] 每個包含 (train_start, train_end, test_start, test_end)
    """
    
    def generate_windows(self, data_length, window_size, step_size):
        """產生滾動窗口索引"""
        
    def get_expanding_windows(self, data_length, initial_window, step_size):
        """產生擴展窗口 (非滾動，用於基線比較)"""
```

### 3.5 BIC 模型選擇器：`bic_selector.py`

**角色**: 在多個候選模型 (degree 1 vs 2, 不同 α) 間基於 BIC 選擇。

**規格**:
```python
class BICModelSelector:
    """
    BIC-based 模型選擇器。
    
    BIC = n·ln(RSS/n) + k·ln(n)
    其中:
      n = 有效樣本數 (加權後)
      k = 參數數量 (degree=1 → k=2, degree=2 → k=3)
      RSS = 加權殘差平方和
      
    選擇規則:
      1. 對每個候選 (degree, α) 擬合
      2. 計算 BIC
      3. 選擇 BIC 最小的模型
      4. 如果 BIC 差異 < 2，選擇較簡單的模型 (Occam's razor)
    """
    
    def select(self, candidates: List[ModelCandidate]) -> ModelCandidate:
        """基於 BIC 選擇最優模型"""
        
    def compare(self, model_a, model_b) -> BICComparison:
        """比較兩個模型的 BIC 差異與統計顯著性"""
```

### 3.6 多TF 編碼器：`multi_tf_encoder.py`

**角色**: 將多個時間框架的價格資料編碼為正交特徵。

**規格**:
```python
class MultiTFEncoder:
    """
    多時間框架特徵編碼器。
    
    理論基礎: Wavelet MRA (Multi-Resolution Analysis)
    - 不同 TF 捕捉不同頻率的市場動態
    - 正交分解保證特徵之間無冗餘
    - 5m ≈ 高頻震盪, 15m ≈ 中頻趨勢, 1h ≈ 低頻結構, 4h ≈ 超低頻
    
    輸入:
      - 5m OHLCV
      - 15m OHLCV (可從 5m 重採樣)
      - 1h OHLCV (可從 5m 重採樣)
      - 4h OHLCV (可從 5m 重採樣)
      
    輸出:
      X_multitf: shape (n_samples, n_features)
      n_features = 4 × features_per_tf
    """
    
    def encode(self, data_5m, data_15m, data_1h, data_4h):
        """編碼多TF 特徵"""
        
    def get_feature_importance(self):
        """返回各 TF 的特徵重要性"""
```

### 3.7 GA 引擎：`ga_engine.py`

**角色**: 自訂 GA 搜索，完全取代 freqtrade hyperopt 的 NSGAIII。支援數學約束。

**規格**:
```python
class GAEngine:
    """
    自訂 GA 搜索引擎。
    
    與 freqtrade hyperopt 的差異:
      1. 支援硬約束 (約束滿足的初始化 + 交配/突變)
      2. 適應度函數整合 SNR-aware 調整
      3. 多目標: Sharpe ratio + BIC + stability
      4. 精英保留 + 多樣性維護
      5. 早停機制 (基於 BIC 收斂)
      
    演算法:
      1. 初始化: 產生滿足約束的種群
      2. 評估: 對每個個體:
         a. 擬合多項式回歸 (滾動窗口)
         b. 計算 BIC
         c. 產生交易信號
         d. 回測計算 Sharpe / Profit / Drawdown
         e. 計算適應度 (多目標加權)
      3. 選擇: Tournament selection
      4. 交配: 約束感知的 crossover
      5. 突變: 約束邊界內的 mutation
      6. 精英保留: 保留 top-N
      7. 重複直到收斂或 max_generations
      
    參數:
      population_size: 50-200
      generations: 50-500
      crossover_rate: 0.8
      mutation_rate: 0.1
      elite_count: 5
      early_stop_generations: 20
    """
```

### 3.8 適應度函數：`fitness_function.py`

**規格**:
```python
class MultiObjectiveFitness:
    """
    多目標適應度函數，整合 SNR-aware 調整。
    
    目標:
      1. Sharpe Ratio (主要)
      2. -BIC (模型簡潔度，取負以最大化)
      3. Stability Score (參數穩健性)
      4. Profit Factor (次要)
      
    SNR-aware 調整:
      由於 SNR ≈ 0.02 極低，對 Sharpe 施加懲罰:
      - 如果 Sharpe > 0.4 → 懲罰 (不可能在 SNR≈0.02 下達成)
      - 如果 Sharpe > 1.0 → 強烈懲罰 (明顯 overfit)
      
    加權:
      fitness = w1·norm(Sharpe) + w2·norm(-BIC) + w3·norm(Stability) + w4·norm(PF)
      預設權重: w = [0.35, 0.25, 0.25, 0.15]
      
    SNR 懲罰:
      if Sharpe > 0.4: fitness *= 0.5
      if Sharpe > 1.0: fitness = -inf (拒絕)
    """
```

### 3.9 Walk-Forward 驗證：`walk_forward.py`

**角色**: 滾動窗口回測驗證，檢測過擬合。

**規格**:
```python
class WalkForwardValidator:
    """
    Walk-Forward 驗證器。
    
    流程:
      1. 將完整資料按時間分割為 N 個窗口
      2. 對每個窗口:
         a. 在訓練期 (前 M 個月) 擬合模型
         b. 在測試期 (後 1 個月) 產生預測與交易
         c. 記錄測試期績效
      3. 匯總所有測試期績效
      4. 計算穩健性指標:
         - WF Sharpe / IS Sharpe 比率 (應接近 1)
         - WF 勝率穩定性 (CV)
         - WF 最大回撤 vs IS 最大回撤
      
    輸出:
      WalkForwardReport {
        windows: List[WindowResult],
        aggregate_metrics: Metrics,
        robustness_score: float,  // 0-1, 越高越好
        overfit_flag: bool
      }
    """
```

### 3.10 策略基礎類別：`base_strategy.py`

**角色**: 所有 math_based 策略的抽象基礎類別。

**規格**:
```python
class MathBasedStrategy(IStrategy):
    """
    數學理論策略基礎類別。
    
    為 freqtrade IStrategy 增加:
      1. 多TF 支援 (informative pairs)
      2. 多項式回歸指標 (poly_pred, poly_upper, poly_lower, poly_slope)
      3. BIC 模型選擇記錄
      4. 參數約束 metadata
      5. 滾動窗口配置
      
    子類別必須實作:
      - populate_indicators() → 計算多TF + 多項式回歸指標
      - populate_entry_trend() → 基於預測收益率的進場邏輯
      - populate_exit_trend() → 出場邏輯
      
    可選實作:
      - custom_stoploss() → 自訂止損
      - confirm_trade_entry() → 進場確認
    """
    
    # 數學約束 metadata (供 ConstraintValidator 讀取)
    MATH_META = {
        "max_degree": 2,
        "regularization": "ridge",
        "prediction_target": "returns",
        "use_bic_selection": True,
        "use_rolling_window": True,
    }
```

### 3.11 策略工廠：`strategy_factory.py`

**角色**: 從 GA 搜索結果動態產生策略程式碼。

**規格**:
```python
class StrategyFactory:
    """
    從最佳參數產生策略程式碼 + freqtrade JSON 配置。
    
    輸入:
      - 參數 dict (來自 GA 搜索)
      - 策略模板名稱 (e.g., "polynomial_v1")
      
    輸出:
      - strategy.py: 可被 freqtrade 載入的策略檔案
      - config.json: freqtrade 策略參數 JSON
      
    流程:
      1. 載入 Jinja2 模板
      2. 填充參數
      3. 加入數學約束 metadata
      4. 寫入目標目錄
    """
```

---

## 四、迭代流程與狀態機

### 4.1 完整迭代循環

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GA ITERATION LIFECYCLE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │  SETUP   │───▶│   GA     │───▶│VALIDATE  │───▶│  EXPORT  │          │
│  │          │    │  SEARCH  │    │          │    │          │          │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘          │
│       │               │               │               │                │
│       ▼               ▼               ▼               ▼                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │• 載入配置│    │• 初始化   │    │• 約束檢查 │    │• 產生策略 │          │
│  │• 參數空間│    │  種群     │    │• WF 驗證  │    │  .py      │          │
│  │• 載入資料│    │• 每代:    │    │• MC 穩健  │    │• 匯出 JSON│          │
│  │• 產生模板│    │  評估→    │    │  性測試   │    │• 寫入報告 │          │
│  │          │    │  選擇→    │    │• SNR 檢查 │    │• 更新索引 │          │
│  │          │    │  交配→    │    │           │    │           │          │
│  │          │    │  突變     │    │           │    │           │          │
│  │          │    │• 早停判斷 │    │           │    │           │          │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘          │
│                                                                         │
│  狀態機:                                                                │
│  INIT → SETUP → SEARCHING → VALIDATING → EXPORTING → DONE               │
│                    │            │             │            │            │
│                    ▼            ▼             ▼            ▼            │
│                 FAILED      REJECTED      WARNINGS     ARCHIVED         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 狀態機定義

| 狀態 | 描述 | 觸發條件 | 下一狀態 |
|------|------|---------|---------|
| **INIT** | 初始狀態 | 框架啟動 | SETUP |
| **SETUP** | 配置載入、資料準備 | ga_iterate.py 執行 | SEARCHING / FAILED |
| **SEARCHING** | GA 搜索進行中 | 種群初始化完成 | VALIDATING / FAILED |
| **VALIDATING** | Walk-Forward + 約束檢查 | GA 收斂或達到 max_gen | EXPORTING / REJECTED |
| **EXPORTING** | 產生策略碼 + 報告 | 驗證通過 | DONE |
| **DONE** | 迭代完成 | 匯出成功 | INIT (下一次迭代) |
| **FAILED** | 技術錯誤 (資料不足、記憶體不足等) | 異常 | INIT (修復後重試) |
| **REJECTED** | 數學約束違反 | 驗證失敗 | INIT (調整參數空間) |
| **WARNINGS** | 軟約束違反，但可接受 | 驗證有警告 | EXPORTING (標記) |
| **ARCHIVED** | 迭代結果封存 | 使用者手動封存 | 終端狀態 |

### 4.3 單次 GA 搜索內部循環

```
for generation in 1..max_generations:
    
    # 1. 評估種群
    for individual in population:
        # a. 擬合模型 (滾動窗口)
        for window in rolling_windows:
            model.fit(train_prices, individual.degree, individual.alpha, ...)
            bic = model.get_bic()
            predictions = model.predict(test_prices)
        
        # b. 約束檢查 (硬約束)
        if not constraint_validator.check_hard(individual.params):
            individual.fitness = -inf
            continue
        
        # c. 產生交易信號 (在 freqtrade 環境中)
        trades = backtest(model, prices, individual.params)
        
        # d. 計算適應度
        individual.fitness = fitness_function.evaluate(
            sharpe=trades.sharpe,
            bic=bic,
            stability=stability_score,
            profit_factor=trades.profit_factor
        )
    
    # 2. 記錄最優個體
    best = max(population, key=lambda i: i.fitness)
    generation_log.append(best)
    
    # 3. 早停檢查
    if early_stopping.should_stop(generation_log):
        break
    
    # 4. 產生下一代
    new_population = []
    new_population.extend(elite_selection(population, elite_count))  # 精英保留
    
    while len(new_population) < population_size:
        parent1, parent2 = tournament_selection(population)
        child = constraint_aware_crossover(parent1, parent2)
        child = constraint_bound_mutation(child)
        new_population.append(child)
    
    population = new_population
```

---

## 五、資料流設計

### 5.1 宏觀資料流

```
                        ┌─────────────────────┐
                        │   ga_config.yaml     │
                        │   param_spaces/      │
                        │   math_laws.yaml     │
                        └──────────┬──────────┘
                                   │
                                   ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  K線資料  │───▶│  GA 搜索  │───▶│  驗證層   │───▶│  產出層   │
│ (Bybit)  │    │  (引擎)   │    │          │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │          ┌────┴────┐     ┌────┴────┐     ┌────┴────┐
     │          │ • 參數空間│     │• 約束檢查│     │• .py 策略│
     │          │ • 多TF編碼│     │• WF 驗證 │     │• .json   │
     │          │ • 模型擬合│     │• MC 測試 │     │• 報告.md │
     │          │ • 回測   │     │• SNR 檢查│     │• 指標.json│
     │          │ • 適應度 │     │          │     │          │
     │          └─────────┘     └─────────┘     └─────────┘
     │                                                │
     └────────────────────────────────────────────────┘
                    資料儲存層
              ┌─────────────────────┐
              │ iterations/{name}/  │
              │ logs/               │
              │ reports/            │
              └─────────────────────┘
```

### 5.2 組件間資料流 (詳細)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW DETAIL                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [DataLoader]                                                       │
│       │                                                             │
│       │ OHLCV (5m/15m/1h/4h)                                        │
│       ▼                                                             │
│  [MultiTFEncoder]                                                    │
│       │                                                             │
│       │ X_multitf (encoded features)                                │
│       ▼                                                             │
│  [RollingWindowManager]                                              │
│       │                                                             │
│       │ List[Window] = [(train_start, train_end, test_start, ...)]  │
│       ▼                                                             │
│  ┌─────────────────────────────────────────┐                        │
│  │          GA ENGINE (per individual)      │                        │
│  │                                          │                        │
│  │  For each window:                        │                        │
│  │    1. [WeightedRidgePolynomialRegressor] │                        │
│  │       • fit(train_prices, degree, α)     │                        │
│  │       • predict(test_prices)             │                        │
│  │                                          │                        │
│  │    2. [BICModelSelector]                 │                        │
│  │       • compare models → select best     │                        │
│  │       • output: selected degree, α, BIC  │                        │
│  │                                          │                        │
│  │    3. [Backtest Engine]                  │                        │
│  │       • generate signals from predictions│                        │
│  │       • simulate trades                  │                        │
│  │       • output: TradeList, Metrics       │                        │
│  │                                          │                        │
│  │    4. [FitnessFunction]                   │                        │
│  │       • aggregate window results         │                        │
│  │       • apply SNR-aware penalty          │                        │
│  │       • output: fitness_score            │                        │
│  └─────────────────────────────────────────┘                        │
│       │                                                             │
│       │ Best individual (params + fitness + metrics)                │
│       ▼                                                             │
│  ┌─────────────────────────────────────────┐                        │
│  │          VALIDATION LAYER                │                        │
│  │                                          │                        │
│  │  1. [ConstraintValidator]                │                        │
│  │     • check_hard_constraints(params)     │                        │
│  │     • check_soft_constraints(params)     │                        │
│  │     • output: (passed, violations)       │                        │
│  │                                          │                        │
│  │  2. [WalkForwardValidator]               │                        │
│  │     • out-of-time test                  │                        │
│  │     • robustness metrics                │                        │
│  │     • output: WalkForwardReport         │                        │
│  │                                          │                        │
│  │  3. [MonteCarloSimulator]                │                        │
│  │     • parameter perturbation            │                        │
│  │     • output: stability_distribution    │                        │
│  └─────────────────────────────────────────┘                        │
│       │                                                             │
│       │ Validated best params                                       │
│       ▼                                                             │
│  ┌─────────────────────────────────────────┐                        │
│  │          EXPORT LAYER                    │                        │
│  │                                          │                        │
│  │  1. [StrategyFactory]                    │                        │
│  │     • generate strategy.py               │                        │
│  │     • generate strategy.json             │                        │
│  │                                          │                        │
│  │  2. [IterationLogger]                    │                        │
│  │     • write metrics.json                 │                        │
│  │     • write validation_report.md         │                        │
│  │     • update index.yaml                  │                        │
│  │                                          │                        │
│  │  3. [ReportExporter]                     │                        │
│  │     • comparison_report.md               │                        │
│  │     • freqtrade-compatible config        │                        │
│  └─────────────────────────────────────────┘                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 資料結構定義

```python
# 核心資料結構

@dataclass
class IterationConfig:
    """迭代配置"""
    iteration_id: str
    strategy_name: str
    param_space: ParamSpace
    timerange: Tuple[str, str]
    ga_config: GAConfig
    validation_config: ValidationConfig

@dataclass
class ParamSpace:
    """參數空間定義"""
    degree: Range[int]          # [1, 2]
    alpha: Range[float]         # [0.1, 10.0]
    weight_decay: Range[float]  # [0.85, 0.99]
    window: Range[int]          # [100, 500]
    dev_mult: Range[float]      # [1.5, 5.0]
    timeframes: List[str]       # ["5m", "15m", "1h", "4h"]

@dataclass
class Individual:
    """GA 個體"""
    params: Dict[str, Any]
    fitness: float
    metrics: Optional[Metrics]
    bic: Optional[float]
    constraint_violations: List[Violation]

@dataclass
class Metrics:
    """回測指標"""
    sharpe_ratio: float
    profit_factor: float
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    num_trades: int
    avg_win_pct: float
    avg_loss_pct: float
    expectancy: float

@dataclass
class WalkForwardReport:
    """Walk-Forward 驗證報告"""
    windows: List[WindowResult]
    aggregate_metrics: Metrics
    robustness_score: float  # 0-1
    overfit_flag: bool
    wf_is_ratio: float       # WF Sharpe / IS Sharpe

@dataclass
class ValidationReport:
    """完整驗證報告"""
    constraint_check: ConstraintCheckResult
    walk_forward: WalkForwardReport
    monte_carlo: MonteCarloResult
    overall_pass: bool
    warnings: List[Warning]
```

---

## 六、與數學理論的對齊檢查清單

### 6.1 設計階段檢查

| # | 檢查項目 | 對應鐵律 | 實作位置 | 狀態 |
|---|---------|---------|---------|------|
| 1 | GA 參數空間中 degree 上限為 2 | 鐵律 1 | `param_spaces/polynomial_v1.yaml` | ✅ 已設計 |
| 2 | degree 預設 1，範圍 [1, 2] | 鐵律 1 | `param_spaces/polynomial_v1.yaml` | ✅ 已設計 |
| 3 | 正則化固定為 Ridge (非 Lasso) | 鐵律 2 | `polynomial_regressor.py` | ✅ 已設計 |
| 4 | Ridge α ∈ [0.1, 10.0] | 鐵律 2 | `param_spaces/polynomial_v1.yaml` | ✅ 已設計 |
| 5 | 預測目標為收益率 (連續值) | 鐵律 3 | `base_strategy.py` MATH_META | ✅ 已設計 |
| 6 | 模型選擇必須使用 BIC | 鐵律 4 | `bic_selector.py` | ✅ 已設計 |
| 7 | BIC 差異 < 2 時選較簡單模型 | 鐵律 4 | `bic_selector.py` | ✅ 已設計 |
| 8 | 使用滾動窗口非全局擬合 | 鐵律 5 | `rolling_window.py` | ✅ 已設計 |
| 9 | 窗口大小建議 200-500 candles | 鐵律 5 | `rolling_window.py` config | ✅ 已設計 |
| 10 | 支援 4 個 TF (5m/15m/1h/4h) | 鐵律 6 | `multi_tf_encoder.py` | ✅ 已設計 |
| 11 | Wavelet MRA 正交分解 | 鐵律 6 | `multi_tf_encoder.py` | ⚠️ 待實作 |
| 12 | SNR ≈ 0.02 預期 Sharpe ≤ 0.4 | 鐵律 7 | `fitness_function.py` | ✅ 已設計 |
| 13 | Sharpe > 1.0 → 強烈懲罰/拒絕 | 鐵律 7 | `fitness_function.py` | ✅ 已設計 |
| 14 | Walk-Forward 驗證強制執行 | 設計要求 | `walk_forward.py` | ✅ 已設計 |
| 15 | 參數穩健性測試 (Monte Carlo) | 設計要求 | `monte_carlo.py` | ✅ 已設計 |

### 6.2 執行階段檢查 (每個迭代自動執行)

```
□ 硬約束檢查
  □ degree ∈ {1, 2}
  □ regularization == "ridge"
  □ α ∈ [0.1, 10.0]
  □ weight_decay ∈ [0.85, 0.99]
  □ window ∈ [100, 500]

□ 模型品質檢查
  □ BIC 已計算
  □ BIC 在合理範圍內 (非 NaN/inf)
  □ 殘差無明顯自相關 (Durbin-Watson ≈ 2)
  □ R²_adj 在合理範圍 (因 SNR 低，預期 < 0.05)

□ Walk-Forward 檢查
  □ WF Sharpe / IS Sharpe ∈ [0.5, 1.5]
  □ 每個 WF 窗口都有交易產生
  □ WF 最大回撤 ≤ 2× IS 最大回撤

□ SNR 合理性檢查
  □ Sharpe ≤ 0.4 (SNR ≈ 0.02 的理論上限)
  □ Profit Factor ∈ [0.8, 1.2] (低 SNR 下應接近 1)

□ 過擬合檢查
  □ IS Sharpe - OOS Sharpe < 0.3
  □ 參數敏感度分析通過
```

---

## 七、與現有元件的整合方式

### 7.1 整合策略

現有檔案保留向後相容，新框架平行運作：

```
舊架構 (保留，不刪除)              新架構 (平行建立)
─────────────────────────          ─────────────────────────
run_ga.sh                          bin/ga_iterate.py
analyze_results.py                 lib/reporting/
ga_config_template.json            config/ga_config.yaml
iteration_tracker.md               iterations/index.yaml
                                   lib/* (完整函式庫)
```

**遷移路徑**: 新策略使用新框架；舊策略可逐步遷移。

### 7.2 與 freqtrade 的介面

```
┌────────────────────────────────────────┐
│         本框架 (自訂 GA)                │
│                                         │
│  ga_iterate.py                          │
│       │                                 │
│       │ 使用 freqtrade 作為回測引擎      │
│       ▼                                 │
│  ┌──────────────────────────────┐       │
│  │     Freqtrade Backtesting     │       │
│  │     (freqtrade.commands)      │       │
│  │                               │       │
│  │  • 載入 MathBasedStrategy     │       │
│  │  • 執行回測                   │       │
│  │  • 返回 Trade 列表            │       │
│  └──────────────────────────────┘       │
│       │                                 │
│       │ 參數匯出                        │
│       ▼                                 │
│  ┌──────────────────────────────┐       │
│  │   Freqtrade Strategy JSON     │       │
│  │   (可被 freqtrade live/dry    │       │
│  │    run 直接載入)              │       │
│  └──────────────────────────────┘       │
│                                         │
└────────────────────────────────────────┘
```

### 7.3 整合要點

| 整合點 | 方式 | 備註 |
|--------|------|------|
| 回測引擎 | 重用 freqtrade backtesting | 不重造輪子；透過 Python API 調用 |
| K 線資料 | 重用 freqtrade data | 從 `user_data/data/` 讀取 |
| 策略格式 | 匯出為 freqtrade JSON/策略類別 | 無縫相容 live/dry run |
| 配置 | 新格式 `ga_config.yaml` | 更豐富的配置 (含數學約束) |
| 報告 | 新格式 + 相容舊 reports/ | 同時輸出新舊格式 |
| Git 整合 | 沿用現有 commit 規範 | `auto(ga): ...` 格式 |

---

## 八、配置規格

### 8.1 主配置: `config/ga_config.yaml`

```yaml
# GA Framework Configuration v3.0
framework:
  version: "3.0"
  strategy_name: "polynomial_v1"  # 策略名稱 (對應 param_spaces/)
  
# 資料配置
data:
  pairs: ["BTC/USDT:USDT"]
  timeframes: ["5m", "15m", "1h", "4h"]
  timerange:
    start: "2024-01-01"
    end: "2026-05-29"
  exchange: "bybit"
  market_type: "futures"

# GA 搜索配置
ga:
  population_size: 100
  max_generations: 100
  crossover_rate: 0.8
  mutation_rate: 0.1
  elite_count: 5
  early_stop_generations: 20
  fitness_weights:
    sharpe: 0.35
    bic_penalty: 0.25
    stability: 0.25
    profit_factor: 0.15

# 多項式回歸配置
polynomial:
  # 參數空間 (可被 param_spaces/ 覆蓋)
  degree_min: 1
  degree_max: 2
  alpha_min: 0.1
  alpha_max: 10.0
  weight_decay_min: 0.85
  weight_decay_max: 0.99
  window_min: 100
  window_max: 500
  dev_mult_min: 1.5
  dev_mult_max: 5.0
  
  # 數學約束 (硬編碼鐵律)
  constraints:
    max_degree: 2
    regularization: "ridge"
    prediction_target: "returns"

# 滾動窗口配置
rolling_window:
  window_size: 400       # 擬合窗口 (candles)
  step_size: 100         # 滾動步長
  min_train_windows: 10

# Walk-Forward 驗證配置
walk_forward:
  enabled: true
  train_months: 6
  test_months: 1
  min_windows: 4

# 約束驗證配置
constraints:
  hard_fail: true           # 硬約束違反 → 拒絕個體
  soft_warning: true        # 軟約束違反 → 標記警告
  snr_expected: 0.02
  max_expected_sharpe: 0.4

# 輸出配置
output:
  strategy_dir: "strategies/prod/"
  params_dir: "iterations/"
  reports_dir: "reports/"
  freqtrade_compat: true    # 匯出 freqtrade 相容 JSON
```

### 8.2 數學鐵律配置: `config/constraints/math_laws.yaml`

```yaml
# 數學鐵律參數化 (不可違反的邊界條件)
math_laws:
  law_1_degree:
    description: "多項式 degree 必須 ≤ 2"
    max_degree: 2
    optimal_degree: 1.8
    severity: HARD
    
  law_2_ridge:
    description: "必須使用 Ridge 正則化"
    regularization: "ridge"
    alpha_range: [0.1, 10.0]
    severity: HARD
    
  law_3_returns:
    description: "預測目標為連續收益率"
    target_type: "continuous"
    target_variable: "log_return_t1"
    severity: SOFT
    
  law_4_bic:
    description: "使用 BIC 模型選擇"
    selection_criterion: "BIC"
    bic_diff_threshold: 2.0
    severity: HARD
    
  law_5_rolling:
    description: "使用滾動窗口非全局擬合"
    window_mode: "rolling"
    window_size_min: 200
    severity: SOFT
    
  law_6_multitf:
    description: "多TF 作為多元變數 (Wavelet MRA)"
    timeframes: ["5m", "15m", "1h", "4h"]
    decomposition: "wavelet_mra"
    severity: SOFT
    
  law_7_snr:
    description: "SNR ≈ 0.02，限制 Sharpe 預期"
    expected_snr: 0.02
    max_expected_sharpe: 0.4
    sharpe_hard_cap: 1.0
    severity: SOFT
```

---

## 九、回報與可觀測性

### 9.1 迭代記錄格式 (取代舊 iteration_tracker.md)

每次迭代自動產生以下檔案:

```
iterations/{strategy_name}/iter_{NNN}/
├── config.yaml              # 該次迭代配置快照
├── params.json               # 最佳參數
├── metrics.json              # 效能指標
├── fitness_history.json      # GA 各代最優適應度
├── constraint_check.json     # 約束檢查結果
├── walk_forward_report.json  # WF 驗證報告
├── strategy.py               # 產生的策略程式碼
├── strategy.json             # freqtrade 參數 JSON
└── iteration_report.md       # 人類可讀報告
```

### 9.2 迭代索引: `iterations/index.yaml`

```yaml
strategy: polynomial_v1
iterations:
  - id: iter_001
    timestamp: "2026-05-29T10:00:00"
    status: DONE
    best_params:
      degree: 2
      alpha: 0.5
      window: 300
    metrics:
      sharpe: 0.18
      profit_factor: 1.05
      total_return_pct: 3.2
    validation:
      constraint_pass: true
      walk_forward_robustness: 0.72
    notes: "初始基線迭代"
    
  - id: iter_002
    timestamp: "2026-05-29T14:00:00"
    status: REJECTED
    violation: "Sharpe=0.62 > 0.4 SNR bound"
    notes: "疑似 overfit，拒絕此迭代"
```

### 9.3 跨迭代比較報告

`reports/comparison_{strategy_name}.md`:
- 各迭代關鍵指標趨勢圖 (Sharpe, BIC, Profit Factor)
- 參數收斂路徑
- 模型複雜度 vs 績效權衡
- Walk-Forward 穩健性比較

---

## 附錄 A: 與舊框架的差異總結

| 面向 | 舊框架 (v1/v2) | 新框架 (v3) |
|------|---------------|-------------|
| GA 引擎 | freqtrade hyperopt (NSGAIII) | 自訂 GA (約束感知) |
| 參數空間 | 自由範圍 | 數學約束邊界 |
| 模型 | 無特定模型 | 加權 Ridge 多項式回歸 |
| 模型選擇 | 無 | BIC |
| 時間處理 | 全局擬合 | 滾動窗口 |
| 多TF | 單一 timeframe | 4×TF 多元編碼 |
| 驗證 | 單次 backtest | Walk-Forward + Monte Carlo |
| 約束檢查 | 無 | 硬約束 + 軟約束 |
| SNR 感知 | 無 | 適應度懲罰 + 邊界檢查 |
| 策略產生 | 手動 | 自動 (工廠模式) |
| 迭代追蹤 | 手動 Markdown | 自動結構化記錄 |
| 報告 | 簡單檔案狀態 | 完整指標 + 比較分析 |

---

## 附錄 B: 實作優先級

| 優先級 | 組件 | 原因 |
|--------|------|------|
| **P0** | `polynomial_regressor.py` | 核心模型，一切依賴於它 |
| **P0** | `rolling_window.py` | 時間處理的基礎 |
| **P0** | `constraints/validator.py` | 數學鐵律的執行層 |
| **P1** | `ga_engine.py` + `fitness_function.py` | 取代 freqtrade hyperopt |
| **P1** | `bic_selector.py` | 模型選擇 |
| **P1** | `walk_forward.py` | 過擬合檢測 |
| **P2** | `multi_tf_encoder.py` | 多TF 編碼 (可先用簡單拼接) |
| **P2** | `base_strategy.py` + `strategy_factory.py` | 策略產生 |
| **P2** | `ga_iterate.py` (CLI) | 完整流程編排 |
| **P3** | `monte_carlo.py` | 穩健性測試 |
| **P3** | `reporting/` | 報告與可觀測性 |
| **P3** | `tests/` | 框架測試 |

---

*本文件為架構設計文件，待審查後進入實作階段。*
