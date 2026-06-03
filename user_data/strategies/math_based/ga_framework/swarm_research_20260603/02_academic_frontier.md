# 學術前沿整合建議（2026-06-03 Swarm 研究）

> **方法說明**: arXiv API 今日 rate-limited (HTTP 429)，本報告基於既有 `quant-finance-patterns.md` cheat-sheet + `math-based-trading-framework` skill 已記錄的 ORCA/Generating Alpha 引用 + 2025-2026 量化金融主流方法。**3 個候選方法** + 1 個**不建議採用**的方案。

---

## 候選方法 1: Walk-Forward Regime-Segmented Backtest

**核心概念**: 把 backtest 切成多個 regime segment（依 regime 偵測結果），每段獨立計算期望值，最終加權平均。這能根本解決「2 個月 vs 4 個月 backtest 結果差異大」的問題。

**為何適合我們**:
- 現狀：2 個月 backtest 顯示 -0.17%，4 個月顯示 -0.90%（差異 5.3 倍）
- 根因：uptrend (2 月) vs downtrend (4-5 月) regime 切換導致策略表現劇變
- walk-forward + regime segmentation 會把每段的損益分開記錄，可立即識別「該策略只在 uptrend 有效」

**整合難度**: 中（3-5 hr）— 需要包裝 freqtrade backtest 結果的後處理 script

**實作路徑**:
```python
# analyze_results.py 新增 function
def regime_segmented_backtest(backtest_df, regime_series):
    """
    輸入: freqtrade backtest 結果 + regime 偵測序列
    輸出: 每段 regime 的 profit/WR/MaxDD + 加權平均
    """
    segments = []
    for regime_id in [0, 1, 2]:  # ranging/transition/trending
        mask = regime_series == regime_id
        if mask.sum() < 10: continue  # 樣本太少
        seg_profit = backtest_df[mask]['profit_abs'].sum()
        seg_wr = backtest_df[mask]['profit_abs'] > 0).mean()
        seg_max_dd = backtest_df[mask]['profit_abs'].cumsum().min()
        segments.append({'regime': regime_id, 'n': mask.sum(), 'profit': seg_profit, 'wr': seg_wr, 'max_dd': seg_max_dd})
    return pd.DataFrame(segments)
```

**預期效益**:
- 立即識別「-0.90% 是 regime 1 (transition) 拖累的」vs「regime 2 (uptrend) 實際 +0.5%」
- 若確認 uptrend-only，自動建議 D 選項（接受架構限制 + 暫停 downtrend 期間部署）
- 預防 future session 再浪費 4-8 小時做 2 個月 vs 4 個月反覆驗證

---

## 候選方法 2: Bayesian Optimization 取代 GA 搜索

**核心概念**: 用 Gaussian Process + Expected Improvement 取代 NSGA-II/GA 的多目標優化。特別適合**參數維度低（<20）**、**目標函數評估昂貴**的情境。

**為何適合我們**:
- 現狀：GA 50 epochs = 7 min，500 epochs = 70 min（不斷增加 epoch 尋找「打平」參數）
- 痛點：GA 找到「打平非獲利」參數集 → 架構紅利已用完
- Bayesian Optimization 在 < 100 trials 內收斂更快，且**天然支援不確定性估計**（告訴你「這個區域可能還有更好解」）

**整合難度**: 中-高（5-8 hr）— 需要引入 scikit-optimize 或 optuna，替換 run_ga.sh 的搜索邏輯

**實作路徑**:
```python
# run_ga.sh 改成 optuna
import optuna
study = optuna.create_study(
    direction='maximize',  # 或 multi-objective: ['maximize profit', 'minimize max_dd']
    sampler=optuna.samplers.TPESampler(seed=42)
)
def objective(trial):
    return freqtrade_backtest(
        roi_t1=trial.suggest_int('roi_t1', 30, 300),
        stoploss=trial.suggest_float('stoploss', -0.05, -0.01),
        # ...
    )
study.optimize(objective, n_trials=100)  # 比 GA 500 epochs 收斂快
```

**預期效益**:
- 100 trials Bayesian ≈ 500 epochs GA 的效果（文獻常見結論）
- 7 分鐘 → 預估 3-4 分鐘
- 多目標 Pareto front 視覺化（profit vs max_dd vs WR）
- **不確定性估計**：知道何時該停止（vs GA 永遠不知道是否收斂）

**風險**:
- 需 pip install optuna（venv 內）
- 與 freqtrade hyperopt 整合需自定義 loss function

---

## 候選方法 3: Online Regime Change Detection（線上體制變化偵測）

**核心概念**: 用 Bayesian Online Change-Point Detection (BOCPD) 或 Page-Hinkley Test 監控 regime 變化點。**已在 live trading 期間持續運作**，不是 backtest 用。

**為何適合我們**:
- 現狀：regime 偵測 (ADX 多 TF 共識) 在 1h/4h 計算 → 有延遲，熊市轉牛市反應慢
- 痛點：2 月 peak → 4-5 月 downtrend 期間策略仍在 trading → 虧損
- BOCPD 可在 regime 改變時**立即發出警告**，觸發策略暫停或切換模式

**整合難度**: 中（4-6 hr）— 需要 freqtrade custom callback + 統計方法實作

**實作路徑**:
```python
# strategies/math_based/online_regime_detector.py
import numpy as np
from scipy.stats import t

def bocpd_detect(prices: np.ndarray, hazard: float = 1/100) -> int:
    """
    Bayesian Online Change-Point Detection
    返回: 0=穩定, 1=可能改變, 2=確認改變
    """
    # 簡化版：計算 returns 序列的 t-檢定
    # 真實版用 BOCPD 完整算法
    if len(prices) < 50: return 0
    recent = np.diff(np.log(prices[-50:]))
    baseline = np.diff(np.log(prices[-200:-50]))
    t_stat, p_value = ttest_ind(recent, baseline)
    if p_value < 0.01: return 2  # 強烈改變
    if p_value < 0.05: return 1  # 可能改變
    return 0

# 在 freqtrade bot_start / bot_loop 中調用
if bocpd_detect(self.datacenter.get_recent_prices('BTC/USDT:USDT')) >= 1:
    logger.warning("⚠️ Regime change detected, consider pausing strategy")
```

**預期效益**:
- 從「熊市期間持續虧損」→「熊市來臨 24-48 小時內暫停」
- 與現有 ADX regime 偵測互補（ADX 反應慢 + BOCPD 反應快）
- 可作為**自動風控機制**，保護資金

**風險**:
- False positive 可能讓策略在震盪市場過度暫停
- 需要至少 200 根 K 線 warm-up

---

## 不建議採用: LLM-based 策略生成

**理由**:
- TradingAgents (arXiv:2412.20138) 等 LLM multi-agent 框架在學術 benchmark 表現尚可
- 但 Brian 流程的核心價值是**數學嚴謹 + 可解釋性**，LLM 生成的策略黑盒特性違背此原則
- AlphaForgeBench (arXiv:2602.18481) 已揭露 LLM 策略穩定性問題
- 與現有 Freqtrade + Python 工具鏈整合成本極高（5-10x 重寫）

**例外**: 可用 LLM 輔助**文獻回顧**（這次研究就是）+ **負面知識庫條目生成**（從錯誤 commit message 提取），但**不直接生成策略代碼**。

---

## 整合優先級

| 優先級 | 方法 | 時間 | 對應痛點 | 推薦時機 |
|--------|------|------|----------|----------|
| **P0** | Walk-Forward Regime-Segmented Backtest | 3-5 hr | 2 個月 vs 4 個月差異 5x | **下次 session 第一個做**（影響所有後續決策） |
| **P1** | Online Regime Change Detection | 4-6 hr | regime 偵測延遲 | live trading 前必做（風控） |
| **P2** | Bayesian Optimization 取代 GA | 5-8 hr | GA 找打平不找獲利 | 架構紅利用完後再做（避免重複勞動） |
| ❌ | LLM 策略生成 | 30+ hr | — | 永不採用 |

---

## 與 Swarm 兄弟報告的整合

| 兄弟報告 | 與本報告的關係 |
|----------|----------------|
| `01_process_bottlenecks.md` | P0=regime-segmented backtest 直接解決其「過去 2 個月 backtest 隱藏體制風險」P1#2 |
| `03_process_automation.md` | P0 的 fail-fast 機制可用 regime segmentation 結果作觸發條件（如 regime=1 比例 > 30% → 警告） |
| `04_tactical_priority.md` | P0 選項 E（套用 dynamic custom_stoploss）若先跑 regime segmentation，可更精準評估 E 在每個 regime 的改善幅度 |

---

## 來源與限制

**本報告限制**:
- arXiv API 今日 rate-limited (HTTP 429)，未即時驗證 2026 Q1-Q2 是否有更新的方法
- Walk-Forward 在金融領域是教科書方法（並非新研究），列為 P0 是因為**尚未在我們的流程中實作**
- Bayesian Optimization (P2) 應用於 Freqtrade hyperopt 的實際表現需要 A/B 驗證

**既有 skill 已涵蓋**:
- ORCA (arXiv:2604.17251) — Spectral regime detection（已記錄於 math-based-trading-framework skill）
- Generating Alpha (arXiv:2601.19504) — Hybrid AI regime-adaptive（已記錄於同 skill）

**未來驗證方向**:
- 待 arXiv 解除 rate limit 後，搜尋 2026 Q1-Q2 的 "regime-aware hyperparameter optimization" 與 "online portfolio rebalancing"
- 比較 BO vs GA 在 6 個已知 Freqtrade 策略的實測收斂速度
