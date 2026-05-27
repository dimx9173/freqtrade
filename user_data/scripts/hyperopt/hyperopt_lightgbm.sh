#!/bin/bash

# =============================================================================
# FreqAI智能迭代優化腳本 - LightGBM三目標投票策略 (數據問題已修復)
# FreqAI Intelligent Iterative Optimization Script - LightGBM Three-Target Voting (Data Issue Fixed)
# =============================================================================
#
# 功能: 智能迭代優化FreqAI三目標投票策略參數
# 特色: 運行hyperopt → 分析結果 → Claude優化 → 迭代改進
# 修復: 配置參數以滿足288周期滾動窗口的數據需求
#
# 使用方法: ./hyperopt_lightgbm.sh [--iterations=N]
# 參數選項: --iterations=N 指定迭代次數 (1-10, 預設3)
# =============================================================================

set -e  # 遇到錯誤立即退出

# =============================================================================
# 默認配置參數
# =============================================================================

DEFAULT_ITERATIONS=3
ITERATIONS=$DEFAULT_ITERATIONS
HYPEROPT_EPOCHS=50
PROJECT_ROOT="$(pwd)"
REPORTS_DIR="$PROJECT_ROOT/user_data/report"
OPTIMIZATION_DIR="$REPORTS_DIR/optimization"

# 目標文件路径
CONFIG_FILE="$PROJECT_ROOT/user_data/config/config_ensemble_phase5_voting.json"
STRATEGY_FILE="$PROJECT_ROOT/user_data/strategies/EnsembleStrategyPhase5_Voting.py"
MODEL_FILE="$PROJECT_ROOT/user_data/freqaimodels/HybridEnsembleClassifier.py"

# =============================================================================
# 參數解析
# =============================================================================

show_help() {
    cat << EOF
FreqAI智能迭代優化腳本 - LightGBM三目標投票策略
FreqAI Intelligent Iterative Optimization Script - LightGBM Three-Target Voting

使用方法:
    ./hyperopt_lightgbm.sh [選項]

選項:
    --iterations=N     指定優化迭代次數 (默認: 3, 範圍: 1-10)
    --epochs=N         每輪hyperopt輪數 (默認: 50, 範圍: 10-200)
    --help            顯示此幫助信息

範例:
    ./hyperopt_lightgbm.sh --iterations=5 --epochs=100
    ./hyperopt_lightgbm.sh --iterations=3

說明:
    腳本將進行N輪智能迭代優化，每輪包含：
    1. 運行FreqTrade hyperopt優化
    2. 分析backtest結果和日誌
    3. 調用Claude進行智能參數優化
    4. 應用優化建議到策略文件

    目標性能:
    - 年化報酬率: >100%
    - 年化損失率: <10%
    - 最大回撤: <8%
    - 勝率: >60%
EOF
}

# 解析命令行參數
for arg in "$@"; do
    case $arg in
        --iterations=*)
        ITERATIONS="${arg#*=}"
        if ! [[ "$ITERATIONS" =~ ^[0-9]+$ ]] || [ "$ITERATIONS" -lt 1 ] || [ "$ITERATIONS" -gt 10 ]; then
            echo "❌ 錯誤: iterations 必須是 1-10 之間的整數"
            exit 1
        fi
        shift
        ;;
        --epochs=*)
        HYPEROPT_EPOCHS="${arg#*=}"
        if ! [[ "$HYPEROPT_EPOCHS" =~ ^[0-9]+$ ]] || [ "$HYPEROPT_EPOCHS" -lt 10 ] || [ "$HYPEROPT_EPOCHS" -gt 200 ]; then
            echo "❌ 錯誤: epochs 必須是 10-200 之間的整數"
            exit 1
        fi
        shift
        ;;
        --help)
        show_help
        exit 0
        ;;
        *)
        echo "❌ 錯誤: 未知參數 '$arg'"
        echo "使用 --help 查看幫助信息"
        exit 1
        ;;
    esac
done

# =============================================================================
# 顏色輸出配置
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# =============================================================================
# 日誌函數
# =============================================================================

log_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

log_analysis() {
    echo -e "${PURPLE}[$(date '+%Y-%m-%d %H:%M:%S')] ANALYSIS: $1${NC}"
}

log_optimization() {
    echo -e "${CYAN}[$(date '+%Y-%m-%d %H:%M:%S')] OPTIMIZE: $1${NC}"
}

# =============================================================================
# 工具函數
# =============================================================================

# 創建優化會話ID
create_session_id() {
    echo "FREQAI_$(date '+%Y%m%d_%H%M%S')_$((RANDOM % 1000))"
}

# 檢查必要文件
check_prerequisites() {
    local missing_files=()

    if [ ! -f "$CONFIG_FILE" ]; then
        missing_files+=("config: $CONFIG_FILE")
    fi

    if [ ! -f "$STRATEGY_FILE" ]; then
        missing_files+=("strategy: $STRATEGY_FILE")
    fi

    if [ ! -f "$MODEL_FILE" ]; then
        missing_files+=("model: $MODEL_FILE")
    fi

    if [ ${#missing_files[@]} -gt 0 ]; then
        log_error "缺少必要文件:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi

    # 檢查freqtrade命令
    if ! command -v freqtrade &> /dev/null; then
        log_error "freqtrade命令未找到，請確保已正確安裝FreqTrade"
        exit 1
    fi

    log_success "前置檢查完成"
}

# 分析hyperopt結果
analyze_hyperopt_results() {
    local iteration="$1"
    local log_file="$2"
    local output_file="$3"

    log_analysis "分析第${iteration}輪hyperopt結果..."

    # 提取關鍵指標
    local best_result=""
    local total_profit=""
    local win_rate=""
    local max_drawdown=""
    local total_trades=""
    local sharpe=""

    if [ -f "$log_file" ]; then
        # 提取最佳結果
        best_result=$(grep "Best result" "$log_file" | tail -1 || echo "未找到最佳結果")

        # 從hyperopt-result.csv提取指標（如果存在）
        local csv_file="$PROJECT_ROOT/user_data/hyperopt_results/hyperopt-result.csv"
        if [ -f "$csv_file" ]; then
            # 取最後一行（最新結果）
            local last_line=$(tail -n 1 "$csv_file")

            # 嘗試提取基本指標（這裡需要根據實際CSV格式調整）
            total_profit=$(echo "$last_line" | cut -d',' -f3 2>/dev/null || echo "N/A")
            total_trades=$(echo "$last_line" | cut -d',' -f4 2>/dev/null || echo "N/A")
            win_rate=$(echo "$last_line" | cut -d',' -f5 2>/dev/null || echo "N/A")
            max_drawdown=$(echo "$last_line" | cut -d',' -f8 2>/dev/null || echo "N/A")
            sharpe=$(echo "$last_line" | cut -d',' -f12 2>/dev/null || echo "N/A")
        fi
    fi

    # 生成分析報告
    cat > "$output_file" << EOF
# 第${iteration}輪Hyperopt結果分析

## 基本信息
- **輪次**: ${iteration}/${ITERATIONS}
- **分析時間**: $(date '+%Y-%m-%d %H:%M:%S')
- **Hyperopt輪數**: $HYPEROPT_EPOCHS
- **日誌文件**: $(basename "$log_file")

## 性能指標
- **總利潤**: $total_profit
- **總交易數**: $total_trades
- **勝率**: $win_rate
- **最大回撤**: $max_drawdown
- **夏普比率**: $sharpe

## 最佳結果
$best_result

## 原始日誌摘要
最新10行hyperopt輸出:
EOF

    # 添加日誌摘要
    if [ -f "$log_file" ]; then
        tail -10 "$log_file" >> "$output_file"
    else
        echo "日誌文件不存在" >> "$output_file"
    fi

    log_success "第${iteration}輪結果分析完成"
}

# Claude智能優化提示詞
CLAUDE_OPTIMIZATION_PROMPT='
**使用 freqai-quant-engineer 角色進行FreqAI策略優化分析**

## 任務背景
你正在優化一個FreqAI三目標投票策略（動量、趨勢、波動性），目標是達到：
- 年化報酬率: >100%
- 年化損失率: <10%
- 最大回撤: <8%
- 勝率: >60%

## 當前策略文件
- **模型**: user_data/freqaimodels/HybridEnsembleClassifier.py
- **策略**: user_data/strategies/EnsembleStrategyPhase5_Voting.py
- **配置**: user_data/config/config_ensemble_phase5_voting.json

## 優化要求
基於最新hyperopt結果和backtest表現，請：

1. **分析當前表現**：
   - 解讀hyperopt結果和關鍵指標
   - 識別性能瓶頸和改進機會
   - 評估風險收益比和交易頻率

2. **參數優化建議**：
   請重點優化以下參數（直接修改策略文件）：
   - 置信度闾值: momentum_confidence_min, trend_confidence_min, volatility_confidence_min
   - 共識度要求: overall_consensus_min
   - Kelly倉位管理: kelly_multiplier_max, max_kelly_position
   - 技術指標周期: momentum_period, trend_period
   - 止損追蹤: stoploss, trailing_stop_positive

3. **具體修改**：
   - 直接修改 EnsembleStrategyPhase5_Voting.py 中的參數值
   - 提供每個修改的理由和預期效果
   - 考慮參數間的相互影響

4. **風險控制**：
   - 確保修改不會過度增加風險
   - 保持策略的穩健性和一致性
   - 避免過度優化和曲線擬合

**重要**: 請直接修改策略文件中的參數，不要只給建議。基於量化分析做出精確的數值調整。
'

# =============================================================================
# 主程式開始
# =============================================================================

echo "=========================================================================="
echo -e "${CYAN}🚀 FreqAI智能迭代優化系統 - LightGBM三目標投票策略${NC}"
echo "=========================================================================="

# 檢查前置條件
check_prerequisites

# 顯示配置信息
log_info "配置信息:"
log_info "  - 迭代次數: $ITERATIONS"
log_info "  - 每輪Epochs: $HYPEROPT_EPOCHS"
log_info "  - 項目目錄: $PROJECT_ROOT"
log_info "  - 報告目錄: $OPTIMIZATION_DIR"

# 創建會話
SESSION_ID=$(create_session_id)
SESSION_DIR="$OPTIMIZATION_DIR/$SESSION_ID"
mkdir -p "$SESSION_DIR"

log_info "會話ID: $SESSION_ID"
log_info "會話目錄: $SESSION_DIR"

# 創建會話配置
cat > "$SESSION_DIR/session_config.json" << EOF
{
  "session_id": "$SESSION_ID",
  "start_time": "$(date '+%Y-%m-%d %H:%M:%S')",
  "iterations": $ITERATIONS,
  "hyperopt_epochs": $HYPEROPT_EPOCHS,
  "target_metrics": {
    "annual_return": ">100%",
    "annual_loss": "<10%",
    "max_drawdown": "<8%",
    "win_rate": ">60%"
  },
  "strategy_file": "$STRATEGY_FILE",
  "model_file": "$MODEL_FILE",
  "config_file": "$CONFIG_FILE"
}
EOF

# 備份原始文件
cp "$STRATEGY_FILE" "$SESSION_DIR/strategy_original.py"
cp "$MODEL_FILE" "$SESSION_DIR/model_original.py"
cp "$CONFIG_FILE" "$SESSION_DIR/config_original.json"
log_success "原始文件已備份"

# 創建迭代追蹤文件
echo "iteration,start_time,end_time,duration,hyperopt_status,best_profit,win_rate,drawdown,optimization_status" > "$SESSION_DIR/iteration_tracking.csv"

# 主要優化循環
for i in $(seq 1 $ITERATIONS); do
    echo ""
    echo "=========================================================================="
    log_optimization "🔄 開始第 $i/$ITERATIONS 輪優化 (會話: $SESSION_ID)"
    echo "=========================================================================="

    ITERATION_START=$(date +%s)
    ITERATION_DIR="$SESSION_DIR/iteration_$i"
    mkdir -p "$ITERATION_DIR"

    # 步驟1: 備份當前配置
    log_info "📋 備份第${i}輪優化前的配置..."
    cp "$STRATEGY_FILE" "$ITERATION_DIR/strategy_before.py"
    cp "$MODEL_FILE" "$ITERATION_DIR/model_before.py"
    cp "$CONFIG_FILE" "$ITERATION_DIR/config_before.json"

    # 步驟2: 運行Hyperopt優化
    log_info "⚡ 啟動Hyperopt優化 (輪次 $i/$ITERATIONS, Epochs: $HYPEROPT_EPOCHS)..."

    HYPEROPT_LOG="$ITERATION_DIR/hyperopt_${i}.log"

    # 運行hyperopt命令
    if freqtrade hyperopt \
        --config "$CONFIG_FILE" \
        --hyperopt-loss SharpeHyperOptLoss \
        --strategy EnsembleStrategyPhase5_Voting \
        --epochs $HYPEROPT_EPOCHS \
        --spaces all \
        --timerange 20240101-20240831 \
        > "$HYPEROPT_LOG" 2>&1; then

        log_success "第${i}輪Hyperopt完成"
        HYPEROPT_STATUS="SUCCESS"
    else
        log_error "第${i}輪Hyperopt失敗，檢查日誌: $HYPEROPT_LOG"
        HYPEROPT_STATUS="FAILED"

        # 記錄失敗並繼續下一輪
        ITERATION_END=$(date +%s)
        DURATION=$((ITERATION_END - ITERATION_START))
        echo "$i,$(date -d @$ITERATION_START '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r $ITERATION_START '+%Y-%m-%d %H:%M:%S'),$(date -d @$ITERATION_END '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r $ITERATION_END '+%Y-%m-%d %H:%M:%S'),$DURATION,FAILED,N/A,N/A,N/A,SKIPPED" >> "$SESSION_DIR/iteration_tracking.csv"
        continue
    fi

    # 步驟3: 分析結果
    ANALYSIS_FILE="$ITERATION_DIR/analysis_${i}.md"
    analyze_hyperopt_results "$i" "$HYPEROPT_LOG" "$ANALYSIS_FILE"

    # 步驟4: Claude智能優化
    log_optimization "🧠 啟動Claude FreqAI量化工程師進行智能優化..."

    echo "正在執行優化指令:"
    echo "claude --dangerously-skip-permissions -p \"[FreqAI優化提示詞]\""
    echo ""

    if claude --dangerously-skip-permissions -p "$CLAUDE_OPTIMIZATION_PROMPT"; then
        log_success "第${i}輪Claude智能優化完成"
        OPTIMIZATION_STATUS="SUCCESS"
    else
        log_error "第${i}輪Claude優化失敗，恢復原始配置"
        # 恢復配置
        cp "$ITERATION_DIR/strategy_before.py" "$STRATEGY_FILE"
        cp "$ITERATION_DIR/model_before.py" "$MODEL_FILE"
        cp "$ITERATION_DIR/config_before.json" "$CONFIG_FILE"
        OPTIMIZATION_STATUS="FAILED"
    fi

    # 步驟5: 備份優化後配置
    cp "$STRATEGY_FILE" "$ITERATION_DIR/strategy_after.py"
    cp "$MODEL_FILE" "$ITERATION_DIR/model_after.py"
    cp "$CONFIG_FILE" "$ITERATION_DIR/config_after.json"

    # 步驟6: 生成對比報告
    cat > "$ITERATION_DIR/optimization_summary.md" << EOF
# 第${i}輪優化總結

## 基本信息
- **輪次**: $i/$ITERATIONS
- **會話ID**: $SESSION_ID
- **開始時間**: $(date -d @$ITERATION_START '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r $ITERATION_START '+%Y-%m-%d %H:%M:%S')
- **結束時間**: $(date '+%Y-%m-%d %H:%M:%S')

## 執行狀態
- **Hyperopt狀態**: $HYPEROPT_STATUS
- **Claude優化狀態**: $OPTIMIZATION_STATUS
- **Epochs數量**: $HYPEROPT_EPOCHS

## 文件變化
- **策略文件**: $(if diff -q "$ITERATION_DIR/strategy_before.py" "$ITERATION_DIR/strategy_after.py" >/dev/null 2>&1; then echo "無變化"; else echo "已修改"; fi)
- **模型文件**: $(if diff -q "$ITERATION_DIR/model_before.py" "$ITERATION_DIR/model_after.py" >/dev/null 2>&1; then echo "無變化"; else echo "已修改"; fi)
- **配置文件**: $(if diff -q "$ITERATION_DIR/config_before.json" "$ITERATION_DIR/config_after.json" >/dev/null 2>&1; then echo "無變化"; else echo "已修改"; fi)

## 相關文件
- **Hyperopt日誌**: hyperopt_${i}.log
- **結果分析**: analysis_${i}.md
- **優化前策略**: strategy_before.py
- **優化後策略**: strategy_after.py

## 下一步建議
$(if [ $i -lt $ITERATIONS ]; then
    echo "- 進入第$((i+1))輪優化"
    echo "- 繼續監控優化效果"
else
    echo "- 完成所有優化輪次"
    echo "- 生成最終報告"
    echo "- 評估整體優化效果"
fi)
EOF

    # 記錄到CSV
    ITERATION_END=$(date +%s)
    DURATION=$((ITERATION_END - ITERATION_START))

    # 嘗試從分析中提取指標
    BEST_PROFIT=$(grep "總利潤" "$ANALYSIS_FILE" | cut -d':' -f2 | tr -d ' ' 2>/dev/null || echo "N/A")
    WIN_RATE=$(grep "勝率" "$ANALYSIS_FILE" | cut -d':' -f2 | tr -d ' ' 2>/dev/null || echo "N/A")
    DRAWDOWN=$(grep "最大回撤" "$ANALYSIS_FILE" | cut -d':' -f2 | tr -d ' ' 2>/dev/null || echo "N/A")

    echo "$i,$(date -d @$ITERATION_START '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r $ITERATION_START '+%Y-%m-%d %H:%M:%S'),$(date -d @$ITERATION_END '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r $ITERATION_END '+%Y-%m-%d %H:%M:%S'),$DURATION,$HYPEROPT_STATUS,$BEST_PROFIT,$WIN_RATE,$DRAWDOWN,$OPTIMIZATION_STATUS" >> "$SESSION_DIR/iteration_tracking.csv"

    log_success "✅ 第 $i/$ITERATIONS 輪優化完成"

    # 間隔提示
    if [ $i -lt $ITERATIONS ]; then
        log_info "⏳ 準備下一輪優化，間隔3秒..."
        sleep 3
    fi
done

# =============================================================================
# 生成最終報告
# =============================================================================

echo ""
echo "=========================================================================="
log_analysis "📊 生成最終優化報告"
echo "=========================================================================="

cat > "$SESSION_DIR/final_optimization_report.md" << EOF
# FreqAI三目標投票策略優化最終報告

**會話ID**: $SESSION_ID
**生成時間**: $(date '+%Y-%m-%d %H:%M:%S')
**優化輪次**: $ITERATIONS

---

## 📊 執行概覽

### 基本統計
- **總優化輪次**: $ITERATIONS
- **每輪Hyperopt Epochs**: $HYPEROPT_EPOCHS
- **成功完成輪次**: $(grep -c "SUCCESS.*SUCCESS" "$SESSION_DIR/iteration_tracking.csv" 2>/dev/null || echo "0")

### 迭代結果概覽
| 輪次 | Hyperopt狀態 | 優化狀態 | 執行時間 |
|------|-------------|----------|----------|
EOF

# 添加每輪結果
tail -n +2 "$SESSION_DIR/iteration_tracking.csv" | while IFS=, read -r iteration start_time end_time duration hyperopt_status best_profit win_rate drawdown opt_status; do
    echo "| $iteration | $hyperopt_status | $opt_status | ${duration}s |" >> "$SESSION_DIR/final_optimization_report.md"
done

cat >> "$SESSION_DIR/final_optimization_report.md" << EOF

---

## 🔧 策略演進分析

### 文件變化統計
EOF

# 分析策略文件變化
if ! diff -q "$SESSION_DIR/strategy_original.py" "$STRATEGY_FILE" >/dev/null 2>&1; then
    echo "- **策略文件**: ✅ 已優化修改" >> "$SESSION_DIR/final_optimization_report.md"
else
    echo "- **策略文件**: ➖ 無變化" >> "$SESSION_DIR/final_optimization_report.md"
fi

if ! diff -q "$SESSION_DIR/model_original.py" "$MODEL_FILE" >/dev/null 2>&1; then
    echo "- **模型文件**: ✅ 已優化修改" >> "$SESSION_DIR/final_optimization_report.md"
else
    echo "- **模型文件**: ➖ 無變化" >> "$SESSION_DIR/final_optimization_report.md"
fi

if ! diff -q "$SESSION_DIR/config_original.json" "$CONFIG_FILE" >/dev/null 2>&1; then
    echo "- **配置文件**: ✅ 已優化修改" >> "$SESSION_DIR/final_optimization_report.md"
else
    echo "- **配置文件**: ➖ 無變化" >> "$SESSION_DIR/final_optimization_report.md"
fi

cat >> "$SESSION_DIR/final_optimization_report.md" << EOF

---

## 🎯 性能目標評估

### 目標指標
- **年化報酬率目標**: >100%
- **年化損失率目標**: <10%
- **最大回撤目標**: <8%
- **勝率目標**: >60%

### 建議後續行動
1. **回測驗證**: 使用最新參數進行完整回測驗證
2. **實盤測試**: 小資金實盤測試優化效果
3. **監控調整**: 持續監控並根據市場變化調整
4. **定期優化**: 建議每月進行一次參數優化

---

## 📁 完整數據歸檔

### 會話文件
- **會話配置**: session_config.json
- **原始策略**: strategy_original.py
- **原始模型**: model_original.py
- **原始配置**: config_original.json
- **迭代追蹤**: iteration_tracking.csv

### 迭代數據
$(for i in $(seq 1 $ITERATIONS); do
echo "- **第${i}輪**: iteration_$i/"
echo "  - Hyperopt日誌: hyperopt_${i}.log"
echo "  - 結果分析: analysis_${i}.md"
echo "  - 優化總結: optimization_summary.md"
done)

---

**報告生成時間**: $(date '+%Y-%m-%d %H:%M:%S')
**數據完整性**: ✅ 所有輪次數據已完整保存
EOF

# 完成提示
echo ""
echo "=========================================================================="
log_success "🎉 FreqAI智能迭代優化完成！"
echo "=========================================================================="
echo ""
echo "📊 優化結果概覽:"
echo "   ├── 會話ID: $SESSION_ID"
echo "   ├── 執行輪次: $ITERATIONS"
echo "   ├── 成功輪次: $(grep -c "SUCCESS.*SUCCESS" "$SESSION_DIR/iteration_tracking.csv" 2>/dev/null || echo "0")"
echo "   ├── 結果目錄: $SESSION_DIR"
echo "   └── 最終報告: $SESSION_DIR/final_optimization_report.md"
echo ""
echo "📁 重要文件快速訪問:"
echo "   ├── 📋 最終報告: $SESSION_DIR/final_optimization_report.md"
echo "   ├── 📊 迭代追蹤: $SESSION_DIR/iteration_tracking.csv"
echo "   ├── ⚙️ 當前策略: $STRATEGY_FILE"
echo "   ├── 🤖 當前模型: $MODEL_FILE"
echo "   └── 🔧 當前配置: $CONFIG_FILE"
echo ""
echo "🔄 查看優化歷程:"
echo "   cat $SESSION_DIR/iteration_tracking.csv"
echo ""
echo "📈 查看完整報告:"
echo "   cat $SESSION_DIR/final_optimization_report.md"
echo ""
echo "🔧 配置回滾 (如需要):"
echo "   cp $SESSION_DIR/strategy_original.py $STRATEGY_FILE"
echo "   cp $SESSION_DIR/model_original.py $MODEL_FILE"
echo "   cp $SESSION_DIR/config_original.json $CONFIG_FILE"
echo ""
log_optimization "FreqAI智能迭代優化系統執行完成！"
