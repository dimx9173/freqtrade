# AI Agent 驅動 Freqtrade 策略研發：學術研究與實務整合報告

**研究日期：** 2026-04-12
**涵蓋範圍：** 排除參數優化（hyperopt 領域），聚焦於 AI Agent 輔助策略構思、框架設計、程式實作、風險管理、多 Agent 協作架構

---

## 摘要

本報告整合 15 篇 arXiv 學術論文研究發現與實務開發經驗，為使用 AI Agent 加速 Freqtrade 加密貨幣交易策略研發提供完整指南。核心發現：當前 AI Agent 在策略研發中已能承擔假設生成、代碼骨架、系統整合等工作，但「完全的端到端自動化」仍存在顯著限制，特別是在動態市場中的決策穩定性。最佳實踐為「人類審核 + AI 加速」的混合模式。

---

## 第一部分：學術研究地圖

### 1.1 論文分類矩陣

| 論文 | 年份 | 主題 | 對 Freqtrade 的啟示 | 評級 |
|------|------|------|---------------------|------|
| **TradingAgents** (2412.20138) | 2024 | Multi-Agent LLM 交易框架 | ⭐⭐⭐⭐⭐ 直接相關 | 必讀 |
| **MountainLion** (2507.20474) | 2025 | 多模態 LLM Agent 可解釋交易 | ⭐⭐⭐⭐ 實用價值高 | 強推 |
| **AlphaForgeBench** (2602.18481) | 2026 | LLM 策略設計評測基準 | ⭐⭐⭐⭐ 理解限制 | 重要 |
| **SysTradeBench** (2604.04812) | 2026 | Strategy-to-Code 評測框架 | ⭐⭐⭐⭐ 軟體工程視角 | 重要 |
| **FinRL** (2011.09607) | 2020 | DRL 量化交易函式庫 | ⭐⭐⭐ 概念基礎 | 參考 |
| **TradingGPT** (2309.03736) | 2023 | 分層記憶多 Agent | ⭐⭐⭐ 記憶架構 | 參考 |
| **ATLAS** (2510.15949) | 2025 | 動態 Prompt 優化 + 協調整合 | ⭐⭐⭐⭐ 方法論創新 | 強推 |
| **Deep Ensemble Strategy** (2511.12120) | 2025 | PPO/A2C/DDPG 集成 | ⭐⭐⭐ 強化學習實作 | 參考 |
| **ContestTrade** (2508.00554) | 2025 | 內部競爭機制多 Agent | ⭐⭐⭐⭐ 組織架構創新 | 重要 |
| **MM-DREX** (2509.05080) | 2025 | 多模態動態路由專家 | ⭐⭐⭐ Regime 適應 | 參考 |
| **HMM + NN** (2407.19858) | 2024 | HMM 市場體制偵測 | ⭐⭐⭐⭐ Regime 偵測實證 | 強推 |
| **Adaptive Alpha + PPO** (2509.01393) | 2025 | PPO 動態優化 LLM Alpha 權重 | ⭐⭐⭐⭐ Alpha 整合 | 重要 |
| **FinDPO** (2507.18417) | 2025 | 情感分析偏好優化 | ⭐⭐⭐ 情緒訊號 | 參考 |
| **LLM Trading** (2504.10789) | 2025 | LLM Agent 市場模擬 | ⭐⭐⭐ 框架驗證 | 參考 |
| **LLM vs Market** (2505.07078) | 2025 | LLM 長期投資績效評估 | ⭐⭐⭐⭐ 限制分析 | 重要 |

---

## 第二部分：核心研究發現

### 2.1 TradingAgents：多 Agent 協作框架 (2412.20138)

**論文核心：**
提出一個受真實交易公司啟發的多 Agent 框架，模擬券商內部的分工結構：
- **基本面分析師 Agent**：處理財務報表、宏觀數據
- **情感分析師 Agent**：處理新聞、社群媒體情緒
- **技術分析師 Agent**：處理 K 線形態、指標信號
- **風險管理 Agent**：管理部位大小、停損設定
- **執行 Agent**：負責下單、訂單管理

**對 Freqtrade 的實務啟示：**

現有 5 個策略（NASOSv4、NASOSv5_mod3、BB_RPB_TSL_BI、SMAOffsetProtectOptV1、ElliotV5_SMA_ninja）可對應此架構重構：

```
多 Agent 協作架構（Freqtrade 版本）
├── 技術分析 Agent（主力策略）
│   ├── NASOS 系列（趨勢追蹤）
│   ├── BB_RPB_TSL_BI（均值回歸）
│   └── ElliotV5_SMA_ninja（波段交易）
├── Regime 偵測 Agent → 決定啟用哪個策略
├── 風控 Agent → 全域停損/部位管理
└── 數據整合 Agent → 跨時框分析
```

**限制：** 該論文基於股票市場，與加密貨幣的高波動性與 24/7 交易有本質差異。

---

### 2.2 MountainLion：多模態可解釋交易系統 (2507.20474)

**論文核心：**
提出整合多種資料型態（價格、成交量、訂單簿、新聞、社群媒體）的多 Agent 系統，強調**可解釋性**：
- 每個決策都附帶自然語言解釋
- 決策鏈路可追溯
- 適用於加密貨幣市場

**實務價值：**
MountainLion 的可解釋性設計非常適合 Freqtrade：
- 使用 ` informative_buy_signal`、`sell_signal` 屬性讓 AI 願意生成有意义的信号解释
- 結合 `plot_config` 讓 AI 能視覺化解釋進場邏輯

**Freqtrade 實作方向：**
```python
class AIEnhancedStrategy(IStrategy):
    @property
    def ai_signal_explanation(self) -> str:
        # AI 生成信號解釋，供日後審查與學習
        return f"""
        進場理由：
        - 趨勢：{self.ai_trend_analysis}
        - 動量：{self.ai_momentum_indicator}
        - Regime：{self.current_regime}
        - 風險評估：{self.ai_risk_level}
        """
```

---

### 2.3 AlphaForgeBench：LLM 策略設計的關鍵限制 (2602.18481)

**這篇論文是本報告最重要的發現之一。**

**論文核心（量化發現）：**
研究人員發現 LLM 交易 Agent 存在三個嚴重問題：

1. **極端運行間變異（Extreme Run-to-Run Variance）**
   - 相同設定下，兩次運行的結果可能截然不同
   - 原因：LLM 的隨機性 + 金融市場的不確定性疊加

2. **非理性動作翻轉（Irrational Action Flipping）**
   - 在相鄰時間步驟中，LLM 可能在沒有實質變化的情況下改變決策
   - 例如：t=1 買入 → t=2 賣出 → t=3 買回，沒有任何市場變化

3. **無狀態自回歸問題（Stateless Autoregression）**
   - LLM 沒有真正的市場狀態記憶，每個時間步都「重新思考」
   - 導致策略缺乏一致性

**對 Freqtrade 實務的影響：**

| 問題 | 嚴重程度 | Freqtrade 緩解方式 |
|------|---------|-------------------|
| 運行間變異 | 高 | 多次backtesting 評估穩定性 |
| 動作翻轉 | 高 | 使用固定策略邏輯，AI 只輔助不決策 |
| 無狀態記憶 | 中 | 利用 Freqtrade 的 `unfilledtrade` 狀態追蹤 |

**核心結論：不要讓 LLM 直接做交易決策。用 LLM 輔助策略設計，但最終決策邏輯必須是確定性的。**

---

### 2.4 SysTradeBench：Strategy-to-Code 評測框架 (2604.04812)

**論文核心：**
提出評估 LLM 將自然語言策略規格轉換為可執行交易程式碼的基準。強調三個評估維度：
1. **Build** — LLM 能否生成可運行的代碼
2. **Test** — 代碼在 backtesting 中表現如何
3. **Patch** — 發現問題後 LLM 能否自我修復

**Freqtrade 實務應用：**
AI Agent 輔助 Freqtrade 策略開發的迭代循環：

```
自然語言策略描述
       ↓ [AI Agent]
Strategy 程式碼骨架
       ↓
Freqtrade backtesting
       ↓
失敗/問題分析
       ↓ [AI Agent]
代碼 Patch / 策略調整
       ↓
再次 Backtesting
       (循環直到穩定)
```

---

### 2.5 ATLAS：動態 Prompt 優化 (2510.15949)

**論文核心：**
提出三大挑戰及解決方案：

| 挑戰 | ATLAS 解法 |
|------|----------|
| 獎勵延遲且充滿噪音 | Adaptive Prompt Feedback Loop |
| 異質資訊整合 | Multi-Agent Information Synthesis |
| 模型輸出 → 可執行交易 | Structured Output Bridge |

**對 Freqtrade 的啟示：**
ATLAS 的 Multi-Agent 資訊整合模式可直接應用於 Freqtrade 的多策略組合：

```
外部數據源                    Freqtrade 策略觸發
├── Binance K線 ──────────→ 技術指標 Agent
├── CoinGecko 幣種數據 ────→ 基本面 Agent  
├── 新聞情緒 API ─────────→ 情感分析 Agent
└── On-chain 數據 ────────→ 資金流向 Agent

                              ↓ 整合
                        Regime 判斷 Agent
                              ↓
                        策略觸發決策
```

---

### 2.6 HMM + Neural Networks：市場體制偵測實證 (2407.19858)

**這是少數有具體量化績效的論文。**

**論文核心（重要數據）：**
在 COVID 期間（2019-2022）採用 HMM + Neural Networks + Black-Litterman 組合：
- **83% 報酬率**
- **Sharpe Ratio: 0.77**
- 兩個風險模型增強風險管理
- 在波動期間表現出色

**對 Freqtrade Regime 偵測的實作價值：**

現有策略可結合 HMM Regime 偵測：

```python
import hmmlearn.hmm as HMM
import numpy as np

class RegimeDetector:
    """使用 HMM 偵測市場體制"""
    
    def __init__(self, n_states=3):
        self.n_states = n_states
        self.model = GaussianHMM(n_components=n_states, covariance_type="full")
    
    def detect_regime(self, features: np.array) -> int:
        """返回 regime 狀態: 0=多頭, 1=震盪, 2=空頭"""
        return self.model.predict(features)[-1]
    
    def get_regime_name(self, state: int) -> str:
        names = {0: "BULL", 1: "SIDEWAYS", 2: "BEAR"}
        return names.get(state, "UNKNOWN")
```

**現有策略與 Regime 的對應：**

| Regime | 適合策略 | Freqtrade 實作 |
|--------|---------|---------------|
| 多頭 (BULL) | NASOSv4/v5（趨勢追蹤） | `minimal_roi` 較高 |
| 震盪 (SIDEWAYS) | BB_RPB_TSL_BI（均值回歸） | `stoploss` 寬鬆 |
| 空頭 (BEAR) | 觀望或反向策略 | 降低倉位 |

---

### 2.7 ContestTrade：內部競爭機制 (2508.00554)

**論文核心創新：**
提出「內部競爭機制」的多 Agent 架構：
- **數據團隊**：處理並濃縮海量市場數據為文字因子（Text Factors）
- **研究團隊**：使用這些因子生成並評估交易策略
- **競爭機制**：多個研究 Agent 競爭，優勝者主導決策

**Freqtrade 實務應用：**
對於 Brian 的 5 個現有策略，可以建立「策略評估委員會」：

```python
class StrategyCommittee:
    """多策略競爭評估框架"""
    
    STRATEGIES = {
        'NASOSv4': NASOSv4(),
        'BB_RPB_TSL_BI': BB_RPB_TSL_BI(),
        'NASOSv5_mod3': NASOSv5_mod3(),
        'SMAOffsetProtectOptV1': SMAOffsetProtectOptV1(),
        'ElliotV5_SMA_ninja': ElliotV5_SMA_ninja(),
    }
    
    def select_best_strategy(self, pair: str, regime: int) -> str:
        """根據市場體制選擇最適策略"""
        scores = {}
        for name, strategy in self.STRATEGIES.items():
            scores[name] = self.evaluate(strategy, pair, regime)
        return max(scores, key=scores.get)
    
    def evaluate(self, strategy, pair, regime) -> float:
        # 計算策略在該 regime 下的預期得分
        # 結合 Sharpe Ratio、最大回撤、勝率
        pass
```

---

### 2.8 Adaptive Alpha Weighting with PPO (2509.01393)

**論文核心：**
提出用 PPO（Proximal Policy Optimization）動態優化多個 LLM 生成的 Alpha 權重。

**對 Freqtrade 的啟示：**
每個 Freqtrade 策略可視為一個「Alpha 來源」，可以用 RL 動態調整倉位權重：

```python
class DynamicWeightAllocator:
    """PPO 驅動的動態倉位分配器"""
    
    def __init__(self, strategies: list, alpha_dim: int):
        self.strategies = strategies
        self.alpha_dim = alpha_dim
        self.ppo_agent = PPOAgent(state_dim=alpha_dim * len(strategies))
    
    def allocate(self, alpha_features: dict) -> dict:
        """
        alpha_features: 每個策略的 Alpha 信號特徵
        返回: 每個策略的倉位權重
        """
        state = np.concatenate([alpha_features[s] for s in self.strategies])
        weights = self.ppo_agent.predict(state)
        return dict(zip(self.strategies, weights))
```

---

## 第三部分：Freqtrade 實作架構

### 3.1 推薦的 AI Agent 輔助 Freqtrade 架構

```
                    AI Agent Layer (Claude Code / OpenCode)
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   Strategy Design            Code Generation            System Integration
   Agent                       Agent                       Agent
        │                           │                           │
        ↓                           ↓                           ↓
   假設生成                     Freqtrade                 風控/部位管理
   Regime 偵測                  策略代碼                   數據流水線
   指標組合建議                 backtesting               監控告警
                                                    ┌───────────────┐
                                                    │  Human Review │
                                                    │  (Brian)      │
                                                    └───────────────┘
                                    │
                         Freqtrade Core Layer
        ┌────────────┬────────────┬────────────┬────────────┐
     config_1    config_3     config_4     config_5     config_6
     NASOSv4    BB_RPB_TSL   NASOSv5    SMAOffset    ElliotV5
                              _mod3     ProtectOpt
```

### 3.2 AI 增強策略模板

```python
"""
AI-Enhanced Freqtrade Strategy Framework
結合學術研究發現：MountainLion (可解釋性) + HMM Regime Detection
排除：LLM 直接交易決策（AlphaForgeBench 發現其不穩定性）
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import numpy as np

class AIEnhancedStrategy(IStrategy):
    """
    AI 增強策略框架
    
    AI 職責：
    - Regime 偵測與策略切換建議
    - 指標組合優化建議
    - 進場理由生成（用於日後審查）
    
    人類職責（最終決策）：
    - 策略邏輯確認
    - 風險參數設定
    - 實盤批准
    """
    
    # === Regime Detection (HMM-based) ===
    regime_detector = RegimeDetector(n_states=3)
    
    # === AI Signal Explanation ===
    ai_explanations = {
        'entry': [],
        'exit': [],
        'regime': None,
    }
    
    def detect_regime(self, dataframe: DataFrame) -> int:
        """使用 HMM 偵測市場體制"""
        features = self._build_regime_features(dataframe)
        return self.regime_detector.detect_regime(features)
    
    def ai_generate_entry_reason(self, dataframe: DataFrame, regime: int) -> str:
        """AI 生成進場理由（可解釋性）"""
        trend = self._ai_analyze_trend(dataframe)
        momentum = self._ai_analyze_momentum(dataframe)
        return (
            f"[Regime: {regime}] "
            f"Trend: {trend}, Momentum: {momentum}. "
            f"Reason: {'均值回歸' if regime == 1 else '趨勢追蹤' if regime == 0 else '防守觀望'}"
        )
    
    def _ai_analyze_trend(self, dataframe: DataFrame) -> str:
        # AI 輔助分析（實際調用 LLM API）
        return "上升趨勢" if dataframe['close'].iloc[-1] > dataframe['sma'].iloc[-1] else "下降趨勢"
    
    def _ai_analyze_momentum(self, dataframe: DataFrame) -> str:
        return "強動量" if dataframe['rsi'].iloc[-1] > 60 else "弱動量"
```

### 3.3 多策略 Regime 路由器

```python
class RegimeRouter:
    """
    根據 HMM Regime 動態路由到最適策略
    實作：ATLAS Multi-Agent Coordination + ContestTrade 競爭機制
    """
    
    REGIME_STRATEGY_MAP = {
        0: ['NASOSv4', 'NASOSv5_mod3'],     # 多頭 → 趨勢策略
        1: ['BB_RPB_TSL_BI', 'SMAOffsetProtectOptV1'],  # 震盪 → 均值回歸
        2: ['ElliotV5_SMA_ninja'],           # 空頭 → 波段策略
    }
    
    def route(self, pair: str, regime: int) -> list:
        """根據 Regime 返回優先策略列表"""
        candidates = self.REGIME_STRATEGY_MAP.get(regime, [])
        # ContestTrade 風格：評估候選策略，取最優
        ranked = self._rank_strategies(candidates, pair, regime)
        return ranked
    
    def _rank_strategies(self, candidates: list, pair: str, regime: int) -> list:
        """根據歷史表現排名候選策略（競爭機制）"""
        scores = {}
        for strat in candidates:
            scores[strat] = self._backtest_strategy(strat, pair, regime)
        return sorted(scores.keys(), key=scores.get, reverse=True)
```

---

## 第四部分：研究發現量化摘要

### 4.1 論文績效數據對照

| 論文 | 方法 | 市場 | 績效 | 備註 |
|------|------|------|------|------|
| HMM+NN (2407.19858) | HMM + NN + Black-Litterman | 加密+股票 | **+83%, Sharpe 0.77** | COVID 期間 |
| Deep Ensemble (2511.12120) | PPO/A2C/DDPG 集成 | 股票 | 優於單一 DRL | US 市場 |
| MountainLion (2507.20474) | 多模態 LLM Agent | 加密 | 可解釋 + 自適應 | 框架論文 |
| FinRL (2011.09607) | DRL | 股票 | Library 基準 | 非直接績效 |

**重要提醒：** 大多數論文的績效數據來自股票市場，加密貨幣的 24/7 交易、高波動性、交易所間價差等因素會顯著影響績效。HMM+NN 的 83% 報酬是在 COVID 特殊市場環境下達成。

### 4.2 LLM 直接交易的成功率評估

根據 AlphaForgeBench (2602.18481) 的發現：

| 指標 | 發現 | 對 Freqtrade 的影響 |
|------|------|---------------------|
| 運行間變異 | 極高 | Backtesting 需跑多次取平均 |
| 動作翻轉頻率 | 高 | 避免讓 LLM 直接控制交易 |
| 策略一致性 | 低 | 必須搭配固定邏輯框架 |
| Prompt 敏感性 | 極高 | 需要系統化的 Prompt 管理 |

**結論：LLM 適合「策略假設生成」和「代碼輔助」，不適合「即時交易決策」。**

---

## 第五部分：實作路線圖

### Phase 1：基礎架構（1-2 週）

**目標：** 建立 AI Agent 輔助開發環境

1. **開發環境整備**
   - Claude Code / OpenCode 配置完成
   - Freqtrade backtesting 腳本自動化
   - 歷史數據下載（`freqtrade download-data`）

2. **Regime 偵測模組**
   - 實作 HMM Regime Detector
   - 在歷史數據上驗證準確率
   - 對照 HMM+NN 論文的 COVID 期間數據

3. **策略評估框架**
   - 建立 Sharpe Ratio / 最大回撤 / 勝率 評估腳本
   - 支援多策略並發 backtesting

### Phase 2：原型開發（2-4 週）

**目標：** 產生第一個 AI 輔助設計的策略

1. **假設生成 Agent**
   - 輸入：過去 90 天 K線數據
   - 輸出：3-5 個候選進場假設
   - 每個假設包含：指標組合、进場條件、理論基礎

2. **代碼生成 Agent**
   - 將假設轉換為 Freqtrade 策略代碼
   - 自動生成 `minimal_roi`、`stoploss`、`plot_config`

3. **驗證循環**
   - Backtesting 評估
   - AI 根據失敗案例調整代碼
   - 迭代直到穩定

### Phase 3：多 Agent 整合（1-2 個月）

**目標：** 建立完整的多 Agent 協作系統

1. **整合 TradingAgents 架構**
   - 技術分析 Agent（主策略）
   - Regime 偵測 Agent（切換邏輯）
   - 風控 Agent（部位管理）

2. **實作 ATLAS Prompt 優化**
   - 建立 Prompt 版本管理
   - 追蹤不同 Prompt 的策略表現

3. **ContestTrade 競爭機制**
   - 多策略同時運行
   - 根據近期表現動態調整倉位

### Phase 4：生產部署（2-3 個月）

**目標：** 將原型轉為生產級系統

1. **監控與告警**
   - Bot 健康檢查（已建立 6 小時 cron）
   - Drawdown 自動暫停
   - 異常交易偵測

2. **策略版本控制**
   - Git 管理所有策略代碼
   - Backtesting 結果版本化

3. **風險管理系統**
   - 全域停損規則
   - 相關性倉位限制
   - 模擬虧損測試（Stresstest）

---

## 第六部分：現有策略的 AI 增強方案

### 6.1 現有策略現況分析

| 策略 | 類型 | 適合 Regime | 主要指標 | 建議增強方向 |
|------|------|------------|---------|------------|
| NASOSv4 | 趨勢追蹤 | 多頭 | 多時框 MA | + Regime 过滤器 |
| NASOSv5_mod3 | 趨勢追蹤 | 多頭 | Offset MA | + 動量確認 |
| BB_RPB_TSL_BI | 均值回歸 | 震盪 | Bollinger Bands | + Regime 偵測 |
| SMAOffsetProtectOptV1 | 混合 | 通用 | SMA Offset | + AI 信號解釋 |
| ElliotV5_SMA_ninja | 波段 | 空頭/震盪 | Elliot Wave | + HMM 確認 |

### 6.2 具體增強方案

**NASOS 系列 → + HMM Regime 過濾器：**
```
原本：MA 多頭 → 進場
增強：HMM Regime = 多頭 AND MA 多頭 → 進場
     HMM Regime = 空頭 → 觀望（避免逆勢）
```

**BB_RPB_TSL_BI → + 動量確認：**
```
原本：BB 下軌 → 進場
增強：BB 下軌 AND RSI < 30 AND 成交量放大 → 進場
```

---

## 第七部分：安全檢查清單

根據 AlphaForgeBench 研究發現，任何 AI 輔助策略上線前必須確認：

- [ ] **穩定性測試**：同一策略跑 5 次 backtesting，結果變異 < 10%
- [ ] **無動作翻轉**：在相似市場條件下，策略邏輯保持一致
- [ ] **確定性邏輯**：AI 生成的策略邏輯是確定的（無隨機決策）
- [ ] **Regime 測試**：策略在多頭/震盪/空頭 Regime 下分别測試
- [ ] **壓力測試**：在 2021 年 5 月、2022 年 11 月等極端行情下測試
- [ ] **人類審核**：所有 AI 生成的策略邏輯必須經過人工審查

---

## 第八部分：參考文獻

### 主要論文

1. Xiao et al. (2024). **TradingAgents: Multi-Agents LLM Financial Trading Framework**. arXiv:2412.20138
2. Wu et al. (2025). **MountainLion: Multi-Modal LLM-Based Agent System for Interpretable Financial Trading**. arXiv:2507.20474
3. Zhang et al. (2026). **AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with LLMs**. arXiv:2602.18481
4. Cao et al. (2026). **SysTradeBench: Iterative Build-Test-Patch Benchmark for Strategy-to-Code Trading Systems**. arXiv:2604.04812
5. Liu et al. (2020). **FinRL: Deep Reinforcement Learning Library for Automated Stock Trading**. arXiv:2011.09607
6. Li et al. (2023). **TradingGPT: Multi-Agent System with Layered Memory for Financial Trading**. arXiv:2309.03736
7. Papadakis et al. (2025). **ATLAS: Adaptive Trading with LLM Agents Through Dynamic Prompt Optimization**. arXiv:2510.15949
8. Yang et al. (2025). **Deep Reinforcement Learning for Automated Stock Trading: An Ensemble Strategy**. arXiv:2511.12120
9. Zhao et al. (2025). **ContestTrade: Multi-Agent Trading System Based on Internal Contest Mechanism**. arXiv:2508.00554
10. Monteiro (2024). **AI-Powered Energy Algorithmic Trading: Integrating HMM with Neural Networks**. arXiv:2407.19858
11. Chen et al. (2025). **Adaptive Alpha Weighting with PPO: Enhancing Prompt-Based LLM-Generated Alphas**. arXiv:2509.01393
12. Lopez-Lira (2025). **Can Large Language Models Trade? Testing Financial Theories with LLM Agents**. arXiv:2504.10789
13. Li et al. (2025). **Can LLM-based Financial Investing Strategies Outperform the Market?** arXiv:2505.07078

---

## 附錄：快速參考卡片

### AI Agent 在 Freqtrade 中的適用場景

| 場景 | 適合用 AI Agent | 不適合用 AI Agent |
|------|---------------|----------------|
| 策略假設生成 | ✅ | |
| 代碼骨架產生 | ✅ | |
| 指標組合建議 | ✅ | |
| 參數優化（Hyperopt） | | ❌（用 hyperopt） |
| Regime 偵測邏輯 | ✅ | |
| 風險規則設計 | ✅ | |
| 即時交易決策 | | ❌（不穩定） |
| 歷史邏輯審查 | ✅ | |

### 推薦閱讀順序

1. **先讀：** AlphaForgeBench (2602.18481) — 理解 LLM 的限制
2. **再讀：** TradingAgents (2412.20138) — 理解多 Agent 架構
3. **接著：** ATLAS (2510.15949) — 理解 Prompt 動態優化
4. **最後：** HMM+NN (2407.19858) — 理解 Regime 偵測實證
