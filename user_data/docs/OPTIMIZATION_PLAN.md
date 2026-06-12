# 策略學習系統優化方案

## 一、現有系統問題分析

### 1. 數據現狀
- 數據庫只有 1 條記錄：`TestTV_VOFjU544`
- 17天結果：profit=0.0, trades=0, winrate=0.0 (無交易)
- 112天結果：profit=-11.26%, trades=12, winrate=75%
- 最終分數：-20.27 (負數！)

### 2. 核心算法問題

#### 問題 2.1：穩定性計算災難性錯誤
```python
# 當前代碼 (strategy_learner.py:33)
stability = 1 - abs(result_17d['profit'] - result_112d['profit'])
```

**問題**：當 17天profit=0 而 112天profit=-11.26% 時：
```
stability = 1 - abs(0 - (-11.26)) = 1 - 11.26 = -10.26  ❌
```

這不是穩定性，這是一個**虧損幅度**。結果應該在 [-1, 1] 範圍內，但公式會產生任何實數。

**修復方案**：
```python
# 方案A：標準化穩定性 (推薦)
profit_diff = result_17d['profit'] - result_112d['profit']
stability = 1 - min(1.0, abs(profit_diff) / 10.0)  # 10% 差異 = 0 穩定性

# 方案B：方向保護
stability = 1 - min(1.0, abs(profit_diff) / max(abs(result_112d['profit']), 0.1))
```

#### 問題 2.2：勝率穩定性計算無意義
```python
winrate_stability = 1 - abs(result_17d['winrate'] - result_112d['winrate'])
```

**問題**：當 17天無交易(winrate=0) vs 112天有交易(winrate=0.75)時：
```
winrate_stability = 1 - abs(0 - 0.75) = 0.25
```

這不是穩定性，這只是兩個比率的差值。沒有交易時的勝率應該被特殊處理。

**修復方案**：
```python
# 無交易時應降低置信度
if result_17d['trades'] < 5:
    winrate_stability = 0.0  # 樣本不足，不計算穩定性
else:
    winrate_stability = 1 - abs(result_17d['winrate'] - result_112d['winrate'])
```

#### 問題 2.3：基礎分數使用利潤直接計算
```python
base_score = result_17d['profit']  # 直接使用，利潤可能為負
```

**問題**：17天profit=0 時，base_score=0。但 profit=-11.26% 是 112天的結果，直接比較不公平。

**修復方案**：
```python
# 使用相對表現 (vs buy&hold)
base_score = result_112d['profit'] - market_change

# 或者使用 Sharpe-like 比率
if result_112d['trades'] > 0:
    base_score = result_112d['profit'] / (result_112d['trades'] ** 0.5)
else:
    base_score = result_112d['profit']
```

#### 問題 2.4：門檻自動調整反饋循環
```python
# auto_learn.py:adjust_thresholds()
if fail_rate > 0.8:
    learner.threshold = max(5.0, learner.threshold - 2.0)
elif fail_rate < 0.2:
    learner.threshold = min(30.0, learner.threshold + 1.0)
```

**問題**：
- 系統剛啟動，樣本極少（1個）時，失敗率 = 100% 或 0%
- 根據失敗率調整門檻，但失敗率本身受門檻影響
- 反饋循環：門檻低 → 更多策略合格 → 失敗率降低 → 門檻提高 → 更少策略合格 → 失敗率提高 → ...

**修復方案**：
```python
# 加入冷卻期和最小樣本數
if total < 10:
    return {'adjusted': False, 'reason': 'insufficient_samples'}
    
# 移動平均平滑
current_rate = (current_rate * 0.7 + fail_rate * 0.3)
```

### 3. 評估維度不足

現有評估只考慮：
1. 17天 profit
2. 17天 vs 112天穩定性
3. 勝率穩定性

**缺少的關鍵維度**：
| 維度 | 重要性 | 當前狀態 |
|------|--------|----------|
| 風險調整收益 (Sharpe/Sortino) | ⭐⭐⭐⭐⭐ | ❌ 缺失 |
| 最大回撤 | ⭐⭐⭐⭐⭐ | ❌ 缺失 |
| 交易頻率合理性 | ⭐⭐⭐ | ❌ 缺失 |
| 市場狀態適應性 | ⭐⭐⭐⭐ | ⚠️ 記錄但未使用 |
| 盈虧比 | ⭐⭐⭐⭐ | ❌ 缺失 |
| 連續虧損次數 | ⭐⭐⭐ | ❌ 缺失 |

### 4. 數據稀疏性問題

當只有 1 個數據點時，系統無法做出可靠判斷。當前的 `recent_failures` 機制在單樣本時會快速觸發調整。

```python
# 問題代碼
if not qualified:
    self.recent_failures += 1

# 門檻調整
if self.recent_failures > 3:
    self.threshold = 20.0
elif self.recent_failures > 6:
    self.threshold = 25.0
```

**修復方案**：
```python
# 最低樣本要求
MIN_SAMPLES_BEFORE_ADJUST = 5

# 基於 Bayesian 推断
if total_evaluations < MIN_SAMPLES_BEFORE_ADJUST:
    # 使用先驗分佈，不輕易調整
    pass
```

## 二、改進方案設計

### 改進 2.1：多維度評分系統

```python
def evaluate_strategy(self, name: str, result_17d: dict, result_112d: dict,
                     market_regime: str = 'ranging', market_change: float = 0.0) -> dict:
    """
    改進後的評估算法
    """
    scores = {}
    
    # 1. 風險調整收益 (核心指標)
    # 使用 Sortino Ratio 近似: (收益 - 無風險利率) / 下行標準差
    # 簡化版：利潤 / (|最大損失| + 1)
    if result_112d['profit'] > 0 and result_112d.get('max_drawdown', 0) != 0:
        risk_adjusted = result_112d['profit'] / abs(result_112d.get('max_drawdown', 1))
    else:
        risk_adjusted = result_112d['profit'] / 10.0  # 預設
    scores['risk_adjusted'] = max(-2, min(2, risk_adjusted))  # 標準化到 [-2, 2]
    
    # 2. 市場適應性 (與市場方向相關的表現)
    expected_return = market_change * 0.3  # 策略應至少貢獻 30% 的市場暴露
    market_beating = result_112d['profit'] - expected_return
    scores['market_beating'] = max(-2, min(2, market_beating / 5.0))
    
    # 3. 穩定性 (標準化後)
    if result_17d['trades'] < 5 or result_112d['trades'] < 10:
        scores['stability'] = 0.0  # 樣本不足
    else:
        profit_diff = abs(result_17d['profit'] - result_112d['profit'])
        scores['stability'] = 1 - min(1.0, profit_diff / 10.0)
    
    # 4. 勝率質量 (盈虧比加權)
    if result_112d['trades'] >= 10:
        winrate_quality = result_112d['winrate'] * result_112d.get('profit_factor', 1.5)
        scores['winrate_quality'] = max(0, min(1, (winrate_quality - 0.5)))
    else:
        scores['winrate_quality'] = 0.0
    
    # 5. 交易頻率合理性
    expected_trades = result_112d['trades'] / 112 * 17  # 按天數比例估算
    if result_17d['trades'] < expected_trades * 0.5:
        scores['frequency'] = -0.5  # 交易太少
    elif result_17d['trades'] > expected_trades * 2:
        scores['frequency'] = -0.5  # 交易太多
    else:
        scores['frequency'] = 0.5  # 合理
    
    # 6. 組合最終分數
    weights = {
        'risk_adjusted': 0.35,    # 權重最高
        'market_beating': 0.25,
        'stability': 0.20,
        'winrate_quality': 0.15,
        'frequency': 0.05
    }
    
    final_score = sum(scores[k] * weights[k] for k in weights)
    
    # 7. 門檻動態調整 (基於數據量)
    base_threshold = 0.1  # 基準門檻
    data_confidence = min(1.0, result_112d['trades'] / 50)  # 50筆交易為滿分置信度
    adaptive_threshold = base_threshold * (2 - data_confidence)
    
    return {
        'qualified': final_score >= adaptive_threshold,
        'score': round(final_score, 4),
        'threshold': round(adaptive_threshold, 4),
        'components': {k: round(v, 4) for k, v in scores.items()},
        'reason': self._explain_failure(scores, final_score, adaptive_threshold)
    }
```

### 改進 2.2：門檻調整冷卻機制

```python
def adjust_thresholds(self, conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    安全的門檻調整（防止反饋循環）
    """
    cursor = conn.cursor()
    
    # 檢查最小樣本
    cursor.execute("""
        SELECT COUNT(*) FROM strategy_results
        WHERE is_qualified IS NOT NULL
    """)
    total_evaluated = cursor.fetchone()[0]
    
    if total_evaluated < 5:
        return {
            'adjusted': False,
            'reason': f'insufficient_data ({total_evaluated} < 5)',
            'current_threshold': self.threshold
        }
    
    # 檢查最近調整時間
    cursor.execute("""
        SELECT MAX(created_at) FROM threshold_adjustments
    """)
    last_adjust = cursor.fetchone()[0]
    
    if last_adjust:
        days_since_adjust = (datetime.now() - parse(last_adjust)).days
        if days_since_adjust < 7:
            return {
                'adjusted': False,
                'reason': f'cooling_period ({days_since_adjust} days < 7)',
                'current_threshold': self.threshold
            }
    
    # 讀取當前失敗率 (移動平均)
    fail_rate = self._get_smoothed_fail_rate(conn, window=14)
    
    if fail_rate > 0.85:
        self.threshold = max(0.05, self.threshold * 0.9)
    elif fail_rate < 0.15:
        self.threshold = min(0.5, self.threshold * 1.1)
    
    return {'adjusted': True, 'new_threshold': self.threshold}
```

### 改進 2.3：市場狀態感知評估

```python
# 根據市場狀態調整期望
def get_market_adjusted_expectation(market_regime: str, market_change: float) -> dict:
    """
    根據市場狀態返回評估期望
    """
    expectations = {
        'trending_up': {
            'min_profit': market_change * 0.5,  # 至少跑贏市場 50%
            'max_drawdown': -8.0,
            'min_trades': 15
        },
        'trending_down': {
            'min_profit': max(market_change * 0.3, -5.0),  # 逆勢也應獲利或虧損少
            'max_drawdown': -5.0,
            'min_trades': 10
        },
        'ranging': {
            'min_profit': 1.0,  # 震盪市場至少賺 1%
            'max_drawdown': -3.0,
            'min_trades': 8
        }
    }
    return expectations.get(market_regime, expectations['ranging'])
```

## 三、預期效果

### 改進前
| 指標 | 數值 |
|------|------|
| 評估維度 | 3個 (利潤、穩定性、勝率穩定性) |
| 分數範圍 | 任意實數 (包括負數) |
| 門檻調整 | 基於失敗率，無冷卻 |
| 市場關聯 | 僅記錄，未使用 |

### 改進後
| 指標 | 數值 |
|------|------|
| 評估維度 | 5+個 (風險調整收益、市場適應性、穩定性、勝率質量、交易頻率) |
| 分數範圍 | [-2, 2] 標準化 |
| 門檻調整 | 冷卻7天，最少5樣本 |
| 市場關聯 | 動態期望值 |

## 四、實施步驟

1. **階段一：修復核心算法** (高優先級)
   - 修正穩定性計算公式
   - 添加多維度評分
   - 標準化分數範圍

2. **階段二：添加數據採集** (中優先級)
   - 要求 backtest 結果包含 max_drawdown, profit_factor
   - 修改 extract_metrics() 支援新欄位

3. **階段三：門檻調整改進** (中優先級)
   - 添加 threshold_adjustments 表
   - 實現冷卻機制
   - Bayesian 信心調整

4. **階段四：市場狀態感知** (低優先級)
   - 根據市場狀態調整期望
   - 添加 regime-specific 評估

## 五、測試案例

```python
# Test Case 1: 理想策略
result_17d = {'profit': 5.5, 'trades': 25, 'winrate': 0.58}
result_112d = {'profit': 4.2, 'trades': 180, 'winrate': 0.55}
market_change = 3.0
# 期望: qualified=True, score > 0.1

# Test Case 2: 高勝率但虧損
result_17d = {'profit': 0.0, 'trades': 0, 'winrate': 0.0}
result_112d = {'profit': -11.26, 'trades': 12, 'winrate': 0.75}
market_change = 0.0
# 期望: qualified=False, score < 0.05

# Test Case 3: 無交易策略
result_17d = {'profit': 0.0, 'trades': 0, 'winrate': 0.0}
result_112d = {'profit': 0.0, 'trades': 0, 'winrate': 0.0}
market_change = 5.0
# 期望: qualified=False, score=0, reason='no_trades'
```

## 六、總結

當前系統的核心問題是**評估算法基礎假設錯誤**：
1. 穩定性公式產生任意實數而非 [-1, 1]
2. 缺少風險調整維度
3. 門檻調整機制會產生反饋循環
4. 市場狀態未被有效利用

通過實施上述改進，系統將能夠：
- 產生有意義的標準化分數
- 防止過度調整
- 根據市場狀態動態調整期望
- 在數據稀疏時保守估計
