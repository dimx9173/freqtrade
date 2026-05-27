# 加密貨幣剝头皮策略风险报酬比 (Risk/Reward Ratio) 设计研究

**研究日期**: 2025-04-27  
**研究目标**: 分析高杠杆期货交易中为何高胜率却亏损，设计最佳风险报酬比

---

## 目录

1. [核心问题分析](#1-核心问题分析)
2. [为何高胜率却亏损](#2-为何高胜率却亏损)
3. [最佳风险报酬比设计](#3-最佳风险报酬比设计)
4. [止损策略类型比较](#4-止损策略类型比较)
5. [Freqtrade 实现方案](#5-freqtrade-实现方案)
6. [具体数字建议](#6-具体数字建议)

---

## 1. 核心问题分析

### Modified_EMA_Scalp 案例分析

| 指标 | 数值 |
|------|------|
| 胜率 | 68.9% |
| 总交易 | 1423 笔 |
| 总盈亏 | **-26.63%** |
| 盈亏平衡胜率(需) | >60% |

**ROI 出场**: 980 笔, +1008 USDT (平均 +1.09%)  
**止损出场**: 439 笔, -1274 USDT (平均 -3.12%)

**问题根源**: 止盈 2%/1% vs 止损 3% → R/R = 1:1.5（不利）

### 计算验证

```
假设 1000 USDT, 每笔 100 USDT
赢的trade: 100 × 1.09% × 980 = +1068 USDT
输的trade: 100 × 3.12% × 439 = -1369 USDT
净亏损: -301 USDT (-30.1%)

胜率 68.9% 但 R/R = 0.67 (1:1.5)
期望值 = 0.689 × 1.09% - 0.311 × 3.12% = 0.75% - 0.97% = -0.22%
```

---

## 2. 为何高胜率却亏损

### 2.1 核心问题：不利的 Risk/Reward Ratio

**Modified_EMA_Scalp 的致命缺陷**:
- 止盈 2%/1% (ROI 表格: `"0": 0.02, "30": 0.01`)
- 止损 3%
- **风险报酬比 = 1:1.5**（应该 >= 1:2）

```
要打平需要的胜率:
Win% × TP% = Loss% × (1-Win%)
Win% × 1.5% = 3% × (1-Win%)
Win% = 66.7% 才能打平
```

### 2.2 大额亏损的单笔效应

| 出场原因 | 交易数 | 平均亏损 | 总亏损 |
|---------|--------|----------|--------|
| Stop Loss | 439 | -3.12% | -1274 USDT |
| ROI | 980 | +1.09% | +1008 USDT |

**关键洞察**: 
- 30.8% 的交易触发止损
- 每笔止损损失是止盈获利的 **2.86 倍**
- 单笔大亏吃掉了多笔小赚

### 2.3 数学证明

```
期望值 = Win% × avg_win - Loss% × avg_loss
     = 0.689 × 1.09% - 0.311 × 3.12%
     = 0.751% - 0.971%
     = -0.22% per trade

即使胜率 68.9%，期望值为负！
```

---

## 3. 最佳风险报酬比设计

### 3.1 基础原则

**剥头皮策略推荐 R/R >= 1:2**

| 止损 | 止盈 | R/R | 盈亏平衡胜率 |
|------|------|-----|--------------|
| 3% | 3% | 1:1 | 50% |
| 3% | 4.5% | 1:1.5 | 40% |
| 2% | 4% | 1:2 | 33% |
| 1.5% | 4.5% | 1:3 | 25% |
| 1% | 4% | 1:4 | 20% |

### 3.2 针对不同市场状态的动态 R/R

#### 趋势市场 (ADX > 25)
```
止盈: 3-4× 止损
止损: 1.5%
止盈: 4.5-6%
```

#### 盘整市场 (ADX < 20)
```
止盈: 2× 止损
止损: 1%
止盈: 2%
```

#### 高波动市场 (ATR > 1.5× 平均)
```
止损: 扩大到 2%
止盈: 至少 4%
R/R 保持 1:2
```

### 3.3 ATR 动态止盈/止损计算

```python
def calculate_atr_based_levels(current_price, atr, market_state):
    """
    ATR 动态计算止盈止损
    
    Parameters:
    - current_price: 当前价格
    - atr: ATR(14) 值
    - market_state: 'trend', 'ranging', 'volatile'
    
    Returns:
    - stop_loss_pct: 止损百分比
    - take_profit_pct: 止盈百分比
    """
    if market_state == 'trend':
        # 趋势市场: 宽松止损，大幅止盈
        stop_multiplier = 2.0
        profit_multiplier = 5.0
    elif market_state == 'ranging':
        # 盘整市场: 紧凑止损，适中止盈
        stop_multiplier = 1.5
        profit_multiplier = 3.0
    else:  # volatile
        # 高波动: 宽松止损，R/R 保持 1:2
        stop_multiplier = 2.5
        profit_multiplier = 5.0
    
    stop_pct = (atr * stop_multiplier) / current_price
    profit_pct = (atr * profit_multiplier) / current_price
    
    # 确保最小 R/R = 1:2
    if profit_pct < stop_pct * 2:
        profit_pct = stop_pct * 2
    
    return stop_pct, profit_pct
```

---

## 4. 止损策略类型比较

### 4.1 三种止损策略对比

| 类型 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **固定百分比** | 简单稳定 | 不适应波动 | 高频剥头皮 |
| **ATR 动态** | 适应市场 | 计算复杂 | 所有场景 |
| **技术位止损** | 精准 | 需要识别 | 有明显支撑阻力 |

### 4.2 追踪止损 (Trailing Stop) 在剥头皮的应用

```python
# Freqtrade trailing stop 配置示例
trailing_stop = True
trailing_stop_positive = 0.005  # 从利润 0.5% 开始追踪
trailing_stop_positive_offset = 0.015  # 利润达到 1.5% 后激活
trailing_only_offset_is_reached = True  # 只有达到偏移才激活
```

**剥头皮推荐配置**:
```
趋势强时: trailing_stop_positive = 0.3%, offset = 1%
盘整时:   禁用 trailing，使用固定止盈
```

### 4.3 时间止损 (Time-based Exit) 的价值

```python
def time_based_exit(trade, current_time, max_hold_minutes=60):
    """
    时间止损：防止持仓过夜捕捉突发事件
    """
    hold_minutes = (current_time - trade.open_date).seconds / 60
    return hold_minutes >= max_hold_minutes
```

**建议**:
- 5m timeframe: 最大持仓 30-45 分钟
- 15m timeframe: 最大持仓 60-90 分钟

---

## 5. Freqtrade 实现方案

### 5.1 推荐的 ROI 表格设计（分层止盈）

```python
class Scalp_Risk_Reward_Optimized(IStrategy):
    """
    风险报酬比优化的剥头皮策略
    核心: R/R >= 1:2, 动态止损
    """
    
    # ------------------------------
    # 止损设置 (基础值，实际使用 custom_stoploss)
    # ------------------------------
    stoploss = -0.02  # 基础 2% 止损
    
    # ------------------------------
    # 分层止盈 ROI 表格
    # ------------------------------
    minimal_roi = {
        "0": 0.04,      # 立即 4% 止盈 (R/R = 1:2)
        "15": 0.03,     # 15分钟后 3%
        "30": 0.025,    # 30分钟后 2.5%
        "60": 0.02,     # 60分钟后 2%
    }
    
    # ------------------------------
    # 追踪止损
    # ------------------------------
    trailing_stop = True
    trailing_stop_positive = 0.005  # 0.5% 利润后开始追踪
    trailing_stop_positive_offset = 0.015  # 1.5% 激活
    trailing_only_offset_is_reached = True
    
    # ------------------------------
    # ATR 参数
    # ------------------------------
    atr_period = 14
    atr_multiplier = 2.0  # 止损 ATR 倍数
    profit_multiplier = 4.0  # 止盈 ATR 倍数
```

### 5.2 动态 Custom Stoploss 实现

```python
def custom_stoploss(self, pair: str, trade: Trade, current_time,
                   current_rate: float, current_profit: float,
                   after_open_rate: float, before_open_rate: float,
                   current_entry_rate: float, current_exit_rate: float,
                   **kwargs) -> float:
    """
    ATR 动态止损
    根据市场波动状态调整止损位置
    """
    dataframe, _ = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)
    
    if dataframe is None or len(dataframe) < self.atr_period:
        return -0.02  # 默认 2%
    
    # 获取 ATR
    atr_value = dataframe.iloc[-1]["atr"]
    if atr_value is None or np.isnan(atr_value):
        return -0.02
    
    # 计算动态止损百分比
    atr_stop_pct = (atr_value * self.atr_multiplier) / current_rate
    
    # 市场状态识别
    adx = dataframe.iloc[-1]["adx"]
    
    # 根据 ADX 调整止损
    if adx > 25:  # 趋势市场
        # 趋势市场放宽止损
        atr_stop_pct = max(0.015, min(0.04, atr_stop_pct))
    elif adx < 20:  # 盘整市场
        # 盘整市场收紧止损
        atr_stop_pct = max(0.01, min(0.025, atr_stop_pct))
    else:  # 过渡市场
        atr_stop_pct = max(0.012, min(0.03, atr_stop_pct))
    
    return -atr_stop_pct
```

### 5.3 Custom Exit 实现动态止盈

```python
def custom_exit(self, pair: str, trade: Trade, current_time,
               current_rate: float, current_profit: float,
               **kwargs) -> Optional[str]:
    """
    动态止盈：根据市场状态调整止盈水平
    """
    dataframe, _ = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)
    
    if dataframe is None or len(dataframe) < self.atr_period:
        return None
    
    atr_value = dataframe.iloc[-1]["atr"]
    adx = dataframe.iloc[-1]["adx"]
    
    if atr_value is None or np.isnan(atr_value):
        return None
    
    # 计算 ATR 止盈
    atr_profit_pct = (atr_value * self.profit_multiplier) / current_rate
    
    # 最小止盈确保 R/R >= 1:2
    stoploss = abs(self.custom_stoploss(pair, trade, current_time, 
                                       current_rate, current_profit, **kwargs))
    min_profit = stoploss * 2.0
    
    # 使用较大的止盈
    take_profit = max(atr_profit_pct, min_profit, 0.02)  # 最少 2%
    
    # 检查是否达到止盈
    if current_profit >= take_profit:
        return "atr_take_profit"
    
    # 高波动市场 ADX > 30 且利润已达 1.5%
    if adx > 30 and current_profit >= 0.015:
        return "high_momentum_exit"
    
    return None
```

### 5.4 市场状态识别指标

```python
def detect_market_state(dataframe, adx_threshold_trend=25, 
                       adx_threshold_ranging=20) -> str:
    """
    识别市场状态：趋势、盘整、过渡
    """
    adx = dataframe.iloc[-1]["adx"]
    
    if adx > adx_threshold_trend:
        return 'trend'
    elif adx < adx_threshold_ranging:
        return 'ranging'
    else:
        return 'transition'

# BB Width 用于确认波动率
def calculate_bb_width(dataframe):
    """计算布林带宽度作为波动率指标"""
    bb_upper = dataframe.iloc[-1]["bb_upper"]
    bb_lower = dataframe.iloc[-1]["bb_lower"]
    bb_middle = dataframe.iloc[-1]["bb_middle"]
    
    return (bb_upper - bb_lower) / bb_middle
```

### 5.5 风险报酬比监控

```python
class RiskRewardMonitor:
    """
    监控策略的风险报酬比
    """
    
    def __init__(self):
        self.trades = []
        self.wins = []
        self.losses = []
    
    def add_trade(self, profit_pct, is_win: bool):
        self.trades.append(profit_pct)
        if is_win:
            self.wins.append(profit_pct)
        else:
            self.losses.append(profit_pct)
    
    def calculate_risk_reward_ratio(self) -> float:
        """计算实际 R/R"""
        if not self.wins or not self.losses:
            return 0.0
        
        avg_win = sum(self.wins) / len(self.wins)
        avg_loss = abs(sum(self.losses) / len(self.losses))
        
        return avg_win / avg_loss if avg_loss > 0 else 0.0
    
    def calculate_win_rate(self) -> float:
        """计算胜率"""
        return len(self.wins) / len(self.trades) if self.trades else 0.0
    
    def calculate_expectancy(self) -> float:
        """计算期望值"""
        win_rate = self.calculate_win_rate()
        rr = self.calculate_risk_reward_ratio()
        avg_loss = abs(sum(self.losses) / len(self.losses)) if self.losses else 0
        
        return win_rate * (rr * avg_loss) - (1 - win_rate) * avg_loss
    
    def get_report(self) -> dict:
        """生成风险报告"""
        return {
            'total_trades': len(self.trades),
            'win_rate': self.calculate_win_rate() * 100,
            'avg_win': sum(self.wins) / len(self.wins) if self.wins else 0,
            'avg_loss': abs(sum(self.losses) / len(self.losses)) if self.losses else 0,
            'risk_reward_ratio': self.calculate_risk_reward_ratio(),
            'expectancy': self.calculate_expectancy(),
        }
```

---

## 6. 具体数字建议

### 6.1 不同槓桿倍數的推薦設置

| 槓桿 | 止損 | 止盈 | R/R | 盈虧平衡勝率 |
|------|------|------|------|--------------|
| 3x | 2.0% | 4.0% | 1:2 | 33% |
| 5x | 1.5% | 4.5% | 1:3 | 25% |
| 10x | 1.0% | 4.0% | 1:4 | 20% |
| 20x | 0.5% | 3.0% | 1:6 | 14% |

### 6.2 Modified_EMA_Scalp 修復建議

**當前設置**:
```python
minimal_roi = {
    "0": 0.02,   # 2%
    "30": 0.01,  # 1%
}
stoploss = -0.03  # 3%
# R/R = 1:1.5, 需要 >66.7% 勝率才能打平
```

**優化後設置**:
```python
minimal_roi = {
    "0": 0.04,   # 4% (立即)
    "15": 0.03,  # 3%
    "30": 0.025, # 2.5%
    "60": 0.02,  # 2%
}
stoploss = -0.02  # 2%
# R/R = 1:2, 只需要 >33% 勝率就能打平
```

**或使用 ATR 動態止損**:
```python
# ATR(14) × 2.0 = 止損
# ATR(14) × 4.0 = 止盈
# 確保 R/R >= 1:2
```

### 6.3 止损类型选择建议

```
┌─────────────────────────────────────────────────────────────┐
│                    止损策略选择流程                         │
├─────────────────────────────────────────────────────────────┤
│  市场状态        │  推荐止损类型      │  原因                │
├─────────────────────────────────────────────────────────────┤
│  高频剥头皮      │  固定百分比 1-2%   │  快速执行，低延迟     │
│  (seconds-1m)   │                    │                      │
├─────────────────────────────────────────────────────────────┤
│  趋势市场        │  ATR 动态          │  适应波动，趋势持稳   │
│  (ADX > 25)     │  止损 1.5-2%       │                      │
├─────────────────────────────────────────────────────────────┤
│  盘整市场        │  技术位止损        │  明确的支撑阻力位     │
│  (ADX < 20)     │  或紧密固定止损    │                      │
├─────────────────────────────────────────────────────────────┤
│  高波动事件      │  ATR + 时间止损    │  防止突发事件扩大损失 │
│  (新闻/非农)     │  组合              │                      │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 关键结论

1. **胜率不是唯一指标**: 68.9% 胜率仍然亏损，因为 R/R = 1:1.5 不利
2. **R/R >= 1:2 是目标**: 这将盈亏平衡胜率降低到 33%
3. **动态止损优于固定**: ATR 动态止损适应市场状态
4. **分层止盈捕获趋势**: 让利润奔跑，在关键位置部分止盈
5. **监控 R/R 实际值**: 定期检查策略的实际 R/R 是否符合设计

---

## 参考资料

- Modified_EMA_Scalp 回测结果: `freqtrade/research/backtest_Modified_EMA_Scalp_20240427.md`
- Scalping Variants 研究: `freqtrade/research/scalping_variants_research.md`
- Freqtrade 官方文档: Custom Stoploss & ROI

---

*本文档为 Brian 的 freqtrade 研究成果，2025-04-27*
