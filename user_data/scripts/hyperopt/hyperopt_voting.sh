#!/bin/bash

# =====================================================
# FreqAI Phase 6: 三目標投票系統智能迭代優化系統
# Target: 100%+ Annual Returns with <10% Annual Loss
# =====================================================

# 設定變量
STRATEGY="EnsembleStrategyPhase5_Voting"
CONFIG="user_data/config/config_ensemble_phase5_voting.json"
TIMERANGE="20240701-20250801"  # 一年數據：2024全年+2025上半年
EPOCHS=100                      # 快速測試：100次迭代
JOBS=8                          # 並行工作數

# 智能迭代優化變量
CLAUDE_CLI_PATH="/Users/carlos/.claude/local/claude"  # Claude CLI 路徑
REPORT_DIR="user_data/report"
SESSION_ID=$(date +%Y%m%d_%H%M%S)
OPTIMIZATION_LOG="${REPORT_DIR}/optimization_${SESSION_ID}.log"
PERFORMANCE_TARGET_ANNUAL_RETURN=100.0  # 100%+ 年化收益目標
PERFORMANCE_TARGET_MAX_LOSS=10.0        # <10% 年化損失目標

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 交互模式變量
MENU_MODE=false
INTELLIGENT_MODE=false
ITERATIONS=1
CLAUDE_ANALYSIS_ENABLED=true
TEST_CLAUDE_MODE=false

# 參數解析
for arg in "$@"; do
    case $arg in
        --menu)
        MENU_MODE=true
        shift
        ;;
        --intelligent)
        INTELLIGENT_MODE=true
        ITERATIONS=3
        shift
        ;;
        --iterations=*)
        ITERATIONS="${arg#*=}"
        INTELLIGENT_MODE=true
        shift
        ;;
        --epochs=*)
        EPOCHS="${arg#*=}"
        shift
        ;;
        --claude-path=*)
        CLAUDE_CLI_PATH="${arg#*=}"
        shift
        ;;
        --no-claude)
        CLAUDE_ANALYSIS_ENABLED=false
        shift
        ;;
        --test-claude)
        TEST_CLAUDE_MODE=true
        ;;
        --target-return=*)
        PERFORMANCE_TARGET_ANNUAL_RETURN="${arg#*=}"
        shift
        ;;
        --max-loss=*)
        PERFORMANCE_TARGET_MAX_LOSS="${arg#*=}"
        shift
        ;;
        --help)
        echo "使用方法: $0 [選項]"
        echo "  --menu              啟動交互式選單"
        echo "  --intelligent       智能迭代優化模式"
        echo "  --iterations=N      設定迭代次數 (默認: 3)"
        echo "  --epochs=N          設定hyperopt輪數 (默認: 100)"
        echo "  --claude-path=PATH  設定Claude CLI路徑 (默認: /usr/local/bin/claude)"
        echo "  --no-claude         禁用Claude分析"
        echo "  --test-claude       測試Claude CLI功能和連接"
        echo "  --target-return=N   設定年化收益目標% (默認: 100)"
        echo "  --max-loss=N        設定最大年化損失% (默認: 10)"
        echo "  --help              顯示幫助"
        exit 0
        ;;
        *)
        echo "未知參數: $arg"
        echo "使用 --help 查看幫助"
        exit 1
        ;;
    esac
done

# =====================================================
# 智能優化核心函數
# =====================================================

# Claude CLI 功能測試
test_claude_functionality() {
    echo -e "${CYAN}🔍 開始測試 Claude CLI 功能...${NC}"
    echo ""

    # 檢查 Claude CLI 路徑
    echo -e "${BLUE}📍 檢查 Claude CLI 路徑...${NC}"
    echo "   路徑: ${CLAUDE_CLI_PATH}"

    if [ ! -f "${CLAUDE_CLI_PATH}" ]; then
        echo -e "${RED}❌ Claude CLI 文件不存在: ${CLAUDE_CLI_PATH}${NC}"
        echo -e "${YELLOW}💡 請檢查路徑或使用 --claude-path=PATH 指定正確路徑${NC}"
        return 1
    fi

    if [ ! -x "${CLAUDE_CLI_PATH}" ]; then
        echo -e "${RED}❌ Claude CLI 沒有執行權限: ${CLAUDE_CLI_PATH}${NC}"
        echo -e "${YELLOW}💡 請執行: chmod +x ${CLAUDE_CLI_PATH}${NC}"
        return 1
    fi

    echo -e "${GREEN}✅ Claude CLI 路徑檢查通過${NC}"
    echo ""

    # 測試基本連接
    echo -e "${BLUE}🔗 測試 Claude CLI 基本連接...${NC}"
    local test_prompt="請簡短回應'Claude CLI 測試成功'以確認連接正常。"
    local test_output_file="/tmp/claude_test_$$"

    echo -e "${YELLOW}   發送測試提示: ${test_prompt}${NC}"

    # 使用 here-document 發送測試請求
    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${test_output_file}" 2>&1 << EOF
${test_prompt}
EOF

    local exit_code=$?

    if [ $exit_code -eq 0 ] && [ -s "${test_output_file}" ]; then
        echo -e "${GREEN}✅ Claude CLI 連接測試成功${NC}"
        echo -e "${BLUE}📝 Claude 響應:${NC}"
        echo -e "${CYAN}$(head -5 "${test_output_file}")${NC}"

        # 檢查響應內容
        if grep -qi "claude\|成功\|測試" "${test_output_file}"; then
            echo -e "${GREEN}✅ Claude 響應內容驗證通過${NC}"
        else
            echo -e "${YELLOW}⚠️  Claude 響應內容可能異常，請檢查上述輸出${NC}"
        fi
    else
        echo -e "${RED}❌ Claude CLI 連接測試失敗 (退出碼: $exit_code)${NC}"
        echo -e "${RED}📝 錯誤輸出:${NC}"
        echo -e "${RED}$(cat "${test_output_file}")${NC}"
        rm -f "${test_output_file}"
        return 1
    fi

    rm -f "${test_output_file}"
    echo ""

    # 測試 FreqAI 相關提示
    echo -e "${BLUE}🎯 測試 FreqAI 分析能力...${NC}"
    local freqai_test_prompt="請簡短說明你對 FreqAI (Freqtrade AI) 量化交易策略優化的了解程度。"
    local freqai_output_file="/tmp/claude_freqai_test_$$"

    echo -e "${YELLOW}   發送 FreqAI 測試提示...${NC}"

    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${freqai_output_file}" 2>&1 << EOF
${freqai_test_prompt}
EOF

    exit_code=$?

    if [ $exit_code -eq 0 ] && [ -s "${freqai_output_file}" ]; then
        echo -e "${GREEN}✅ FreqAI 知識測試成功${NC}"
        echo -e "${BLUE}📝 Claude FreqAI 知識回應:${NC}"
        echo -e "${CYAN}$(head -10 "${freqai_output_file}")${NC}"

        # 檢查是否包含 FreqAI 相關關鍵詞
        if grep -qi "freqai\|freqtrade\|機器學習\|量化\|交易" "${freqai_output_file}"; then
            echo -e "${GREEN}✅ FreqAI 知識驗證通過${NC}"
        else
            echo -e "${YELLOW}⚠️  FreqAI 知識可能有限，但不影響基本功能${NC}"
        fi
    else
        echo -e "${RED}❌ FreqAI 知識測試失敗${NC}"
        echo -e "${RED}📝 錯誤輸出:${NC}"
        echo -e "${RED}$(cat "${freqai_output_file}")${NC}"
        rm -f "${freqai_output_file}"
        return 1
    fi

    rm -f "${freqai_output_file}"
    echo ""

    # 最終測試結果
    echo -e "${GREEN}🎉 Claude CLI 功能測試完成！${NC}"
    echo -e "${GREEN}✅ 所有測試項目均通過${NC}"
    echo ""
    echo -e "${BLUE}📋 測試摘要:${NC}"
    echo -e "   🔧 CLI 路徑: ${CLAUDE_CLI_PATH}"
    echo -e "   🔗 連接狀態: ${GREEN}正常${NC}"
    echo -e "   🎯 FreqAI 支持: ${GREEN}可用${NC}"
    echo -e "   💡 建議: 可以開始使用 hyperopt 智能優化功能"
    echo ""
    echo -e "${YELLOW}💡 使用建議:${NC}"
    echo -e "   - 執行完整優化: ${CYAN}./hyperopt_voting.sh --intelligent${NC}"
    echo -e "   - 交互式設置: ${CYAN}./hyperopt_voting.sh --menu${NC}"
    echo -e "   - 快速測試: ${CYAN}./hyperopt_voting.sh --intelligent --epochs=10 --iterations=1${NC}"
}

# 初始化智能優化系統
initialize_intelligent_optimization() {
    echo -e "${CYAN}🤖 初始化智能迭代優化系統...${NC}"

    # 創建基本報告目錄
    mkdir -p "${REPORT_DIR}"
    mkdir -p "${REPORT_DIR}/optimization"
    mkdir -p "${REPORT_DIR}/analysis"

    # 初始化主日誌
    OPTIMIZATION_LOG="${REPORT_DIR}/optimization/${SESSION_ID}/optimization.log"
    mkdir -p "$(dirname "${OPTIMIZATION_LOG}")"

    echo "========================================================================" > "${OPTIMIZATION_LOG}"
    echo "FreqAI 智能迭代優化系統 - Session: ${SESSION_ID}" >> "${OPTIMIZATION_LOG}"
    echo "目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+ 年化收益, <${PERFORMANCE_TARGET_MAX_LOSS}% 年化損失" >> "${OPTIMIZATION_LOG}"
    echo "開始時間: $(date)" >> "${OPTIMIZATION_LOG}"
    echo "========================================================================" >> "${OPTIMIZATION_LOG}"

    # 創建完整系統備份
    create_comprehensive_backup "${SESSION_ID}"
}

# 創建完整的系統備份
create_comprehensive_backup() {
    local session_id=$1
    local backup_root="${REPORT_DIR}/optimization/${session_id}"

    echo -e "${BLUE}🛡️  創建完整系統備份...${NC}"

    # 創建主備份目錄結構
    mkdir -p "${backup_root}"
    mkdir -p "${backup_root}/original_files"
    mkdir -p "${backup_root}/models_backup"

    # 備份策略文件
    if [ -f "user_data/strategies/${STRATEGY}.py" ]; then
        cp "user_data/strategies/${STRATEGY}.py" "${backup_root}/strategy_original.py"
        echo -e "${GREEN}✅ 策略文件備份完成: ${STRATEGY}.py${NC}"
    fi

    # 備份配置文件
    if [ -f "${CONFIG}" ]; then
        cp "${CONFIG}" "${backup_root}/config_original.json"
        echo -e "${GREEN}✅ 配置文件備份完成: $(basename ${CONFIG})${NC}"
    fi

    # 備份主要模型文件
    if [ -f "user_data/freqaimodels/HybridEnsembleClassifier.py" ]; then
        cp "user_data/freqaimodels/HybridEnsembleClassifier.py" "${backup_root}/model_original.py"
        echo -e "${GREEN}✅ 主要模型文件備份完成${NC}"
    fi

    # 備份所有FreqAI模型文件
    if [ -d "user_data/freqaimodels" ]; then
        cp -r "user_data/freqaimodels"/* "${backup_root}/models_backup/" 2>/dev/null || true
        echo -e "${GREEN}✅ 所有FreqAI模型文件備份完成${NC}"
    fi

    # 創建會話配置文件
    create_session_config "${backup_root}/session_config.json"

    # 創建迭代追蹤文件
    echo "iteration,timestamp,hyperopt_status,claude_status,duration_seconds,annual_return,win_rate,max_drawdown,trades_count,notes" > "${backup_root}/iteration_tracking.csv"

    echo -e "${GREEN}🛡️  完整系統備份完成: ${backup_root}${NC}"
    echo "$(date): 系統備份創建完成: ${backup_root}" >> "${OPTIMIZATION_LOG}"
}

# 創建會話配置文件
create_session_config() {
    local config_file=$1

    cat > "${config_file}" << EOF
{
  "session_id": "${SESSION_ID}",
  "start_time": "$(date '+%Y-%m-%d %H:%M:%S')",
  "mode": "$(if [ "$INTELLIGENT_MODE" = true ]; then echo "intelligent"; else echo "single"; fi)",
  "iterations": ${ITERATIONS},
  "hyperopt_epochs": ${EPOCHS},
  "jobs": ${JOBS},
  "timerange": "${TIMERANGE}",
  "target_metrics": {
    "annual_return": ">${PERFORMANCE_TARGET_ANNUAL_RETURN}%",
    "annual_loss": "<${PERFORMANCE_TARGET_MAX_LOSS}%",
    "max_drawdown": "<8%",
    "win_rate": ">60%"
  },
  "strategy_file": "$(pwd)/user_data/strategies/${STRATEGY}.py",
  "model_file": "$(pwd)/user_data/freqaimodels/HybridEnsembleClassifier.py",
  "config_file": "$(pwd)/${CONFIG}"
}
EOF
}

# 備份當前配置 (每輪迭代前)
backup_current_configuration() {
    local round_num=$1
    local backup_dir="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_${round_num}"

    mkdir -p "${backup_dir}"

    # 備份策略文件 (before)
    if [ -f "user_data/strategies/${STRATEGY}.py" ]; then
        cp "user_data/strategies/${STRATEGY}.py" "${backup_dir}/strategy_before.py"
    fi

    # 備份配置文件 (before)
    if [ -f "${CONFIG}" ]; then
        cp "${CONFIG}" "${backup_dir}/config_before.json"
    fi

    # 備份模型文件 (before)
    if [ -f "user_data/freqaimodels/HybridEnsembleClassifier.py" ]; then
        cp "user_data/freqaimodels/HybridEnsembleClassifier.py" "${backup_dir}/model_before.py"
    fi

    echo "$(date): Round ${round_num} - 迭代前配置備份完成: ${backup_dir}" >> "${OPTIMIZATION_LOG}"
}

# 保存迭代後的文件 (每輪迭代後)
save_iteration_results() {
    local round_num=$1
    local backup_dir="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_${round_num}"
    local hyperopt_log=$2

    # 備份策略文件 (after)
    if [ -f "user_data/strategies/${STRATEGY}.py" ]; then
        cp "user_data/strategies/${STRATEGY}.py" "${backup_dir}/strategy_after.py"
    fi

    # 備份配置文件 (after)
    if [ -f "${CONFIG}" ]; then
        cp "${CONFIG}" "${backup_dir}/config_after.json"
    fi

    # 備份模型文件 (after)
    if [ -f "user_data/freqaimodels/HybridEnsembleClassifier.py" ]; then
        cp "user_data/freqaimodels/HybridEnsembleClassifier.py" "${backup_dir}/model_after.py"
    fi

    # 備份hyperopt日誌
    if [ -f "${hyperopt_log}" ]; then
        cp "${hyperopt_log}" "${backup_dir}/hyperopt_${round_num}.log"
    fi

    echo "$(date): Round ${round_num} - 迭代後結果保存完成: ${backup_dir}" >> "${OPTIMIZATION_LOG}"
}

# 更新迭代追蹤記錄
update_iteration_tracking() {
    local round_num=$1
    local hyperopt_log=$2
    local tracking_file="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_tracking.csv"

    # 提取性能指標
    local annual_return=$(tail -100 "${hyperopt_log}" | grep -o "Total profit.*%" | tail -1 | grep -o "[0-9.-]*%" | sed 's/%//' || echo "N/A")
    local win_rate=$(tail -100 "${hyperopt_log}" | grep -o "Win.*%" | tail -1 | grep -o "[0-9.-]*%" | sed 's/%//' || echo "N/A")
    local max_drawdown=$(tail -100 "${hyperopt_log}" | grep -o "Max Drawdown.*%" | tail -1 | grep -o "[0-9.-]*%" | sed 's/%//' || echo "N/A")
    local trades_count=$(tail -100 "${hyperopt_log}" | grep -o "[0-9]\+ total trades" | grep -o "[0-9]\+" | tail -1 || echo "N/A")

    # 計算執行時間 (簡化版)
    local duration="N/A"

    # 增加記錄到CSV
    echo "${round_num},$(date -Iseconds),SUCCESS,PENDING,${duration},${annual_return},${win_rate},${max_drawdown},${trades_count},Hyperopt completed" >> "${tracking_file}"

    echo "$(date): Round ${round_num} - 迭代追蹤更新完成" >> "${OPTIMIZATION_LOG}"
}

# 生成優化報告
generate_optimization_report() {
    local round_num=$1
    local hyperopt_log=$2
    local report_file="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_${round_num}/optimization_summary.md"

    # 解析hyperopt結果
    local best_result=$(tail -100 "${hyperopt_log}" | grep -E "Best result:|Total profit|Total profit %" | tail -3)
    local trades_count=$(tail -100 "${hyperopt_log}" | grep -E "Trades" | tail -1)
    local win_rate=$(tail -100 "${hyperopt_log}" | grep -E "Win/Loss" | tail -1)

    # 提取更多詳細指標
    local annual_return=$(tail -100 "${hyperopt_log}" | grep -o "Total profit.*%" | tail -1 | grep -o "[0-9.-]*%" | sed 's/%//' || echo "N/A")
    local win_rate=$(tail -100 "${hyperopt_log}" | grep -o "Win.*%" | tail -1 | grep -o "[0-9.-]*%" | sed 's/%//' || echo "N/A")
    local max_drawdown=$(tail -100 "${hyperopt_log}" | grep -o "Max Drawdown.*%" | tail -1 | grep -o "[0-9.-]*%" | sed 's/%//' || echo "N/A")
    local sharpe_ratio=$(tail -100 "${hyperopt_log}" | grep -o "Sharpe.*[0-9.-]\+" | tail -1 | grep -o "[0-9.-]\+" || echo "N/A")

    # 生成Markdown報告
    cat > "${report_file}" << EOF
# 第${round_num}輪優化結果報告

**會話ID**: ${SESSION_ID}
**輪次**: ${round_num}
**時間**: $(date '+%Y-%m-%d %H:%M:%S')
**Hyperopt Epochs**: ${EPOCHS}

## 📈 性能指標

| 指標 | 結果 | 目標 | 狀態 |
|------|------|------|------|
| 年化收益 | ${annual_return}% | >${PERFORMANCE_TARGET_ANNUAL_RETURN}% | $(if (( $(echo "${annual_return:-0} > ${PERFORMANCE_TARGET_ANNUAL_RETURN}" | bc -l) )); then echo "✅達成"; else echo "❌未達成"; fi) |
| 勝率 | ${win_rate}% | >60% | $(if (( $(echo "${win_rate:-0} > 60" | bc -l) )); then echo "✅達成"; else echo "❌未達成"; fi) |
| 最大回撤 | ${max_drawdown}% | <8% | $(if (( $(echo "${max_drawdown:-100} < 8" | bc -l) )); then echo "✅達成"; else echo "❌超過"; fi) |
| 交易次數 | ${trades_count} | >10 | $(if (( ${trades_count:-0} > 10 )); then echo "✅充足"; else echo "❌不足"; fi) |
| Sharpe比率 | ${sharpe_ratio} | >1.0 | $(if (( $(echo "${sharpe_ratio:-0} > 1.0" | bc -l) )); then echo "✅優秀"; else echo "❌待改進"; fi) |

## 📁 文件位置

- **Hyperopt日誌**: ${hyperopt_log}
- **策略備份**: iteration_${round_num}/strategy_before.py
- **模型備份**: iteration_${round_num}/model_before.py
- **配置備份**: iteration_${round_num}/config_before.json

## 🔍 关键結果

\`\`\`
${best_result}
${trades_count}
${win_rate}
\`\`\`

---
*生成時間: $(date)*
EOF

    echo "$(date): Round ${round_num} - 優化報告生成: ${report_file}" >> "${OPTIMIZATION_LOG}"
}

# Claude CLI 分析調用 (增強版)
call_claude_analysis() {
    local round_num=$1
    local report_file="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_${round_num}/optimization_summary.md"
    local claude_output="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_${round_num}/analysis_${round_num}.md"

    if [ "$CLAUDE_ANALYSIS_ENABLED" = false ]; then
        echo "$(date): Round ${round_num} - Claude分析已禁用，跳過" >> "${OPTIMIZATION_LOG}"
        return 0
    fi

    if [ ! -f "${CLAUDE_CLI_PATH}" ]; then
        echo "$(date): Round ${round_num} - Claude CLI未找到: ${CLAUDE_CLI_PATH}" >> "${OPTIMIZATION_LOG}"
        return 1
    fi

    # 提取優化結果的關鍵指標
    local hyperopt_log=$(grep -A 20 "Best result" "${OPTIMIZATION_LOG}" | tail -20)
    local current_performance=$(tail -100 "${LOG_FILE}" 2>/dev/null | grep -E "Total profit|Win|Loss|Trades" | tail -5)

    # 構建增強的Claude分析提示 - 包含歷史記憶傳承
    local tracking_file="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_tracking.csv"
    local historical_analysis=""
    local previous_analysis=""

    # 準備歷史演化分析文件路徑參考
    if [ -f "${tracking_file}" ] && [ $round_num -gt 1 ]; then
        historical_analysis="## 歷史演化分析 (記憶傳承)
請讀取並分析歷史追蹤文件: ${tracking_file}

### 分析要求:
- 總輪次: $((round_num - 1)) 輪已完成
- 分析重點: 識別性能演化模式、改進趨勢、有效調整方向
- 學習重點: 識別哪些調整方向有效，哪些需要避免
- 輸出格式: 提取年化收益、勝率、回撤、交易數等關鍵指標趨勢"
    fi

    # 準備前輪分析文件路徑參考
    if [ $round_num -gt 1 ]; then
        local prev_analysis_file="${REPORT_DIR}/optimization/${SESSION_ID}/iteration_$((round_num-1))/analysis_$((round_num-1)).md"
        if [ -f "${prev_analysis_file}" ]; then
            previous_analysis="

## 前輪優化建議回顧 (累積學習)
請讀取並分析前輪分析文件: ${prev_analysis_file}

### 學習要求:
- 回顧第$((round_num-1))輪的關鍵建議和策略
- 分析前輪建議的執行效果和實際結果
- 識別成功的優化方向和需要避免的調整
- 基於累積經驗調整本輪優化策略"
        fi
    fi

    local claude_prompt="# FreqAI量化策略優化分析 - 第${round_num}輪 (智能記憶傳承)

使用 freqai-quant-engineer agent
## 模型：
"user_data/freqaimodels/HybridEnsembleClassifier.py"
## 策略：
"user_data/strategies/EnsembleStrategyPhase5_Voting.py"
## 設定：
"config/config_ensemble_phase5_voting.json"
## 只能針對以上檔案直接優化，不要額外複製策略，不要額外複製模型，不要額外複製設定

## 目標設定
- 目標年化收益率: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+
- 最大年化損失率: <${PERFORMANCE_TARGET_MAX_LOSS}%
- 策略: ${STRATEGY}
- 時間範圍: ${TIMERANGE}

${historical_analysis}

${previous_analysis}

## 當前輪優化結果
${current_performance}

## 詳細優化報告
請讀取並分析詳細優化報告文件: ${report_file}

### 分析要求:
- 檢查文件是否存在並讀取內容
- 如果文件不存在，請提示需要先生成優化報告
- 分析報告中的性能指標、參數配置和優化建議

## 分析任務 (基於歷史記憶的智能優化)
請基於歷史演化數據和前輪學習經驗，提供具體的、可執行的優化建議：

1. **歷史趨勢分析**: 基於上述歷史數據，識別性能演化模式和改進/退化趨勢
2. **累積學習應用**: 總結前幾輪優化的有效策略和無效嘗試，避免重復錯誤
3. **關鍵問題分析**: 識別當前策略的主要弱點，結合歷史模式判斷根本原因
4. **參數調整**: 具體的數值調整建議 (epochs, learning_rate, 等)，參考歷史成功案例
5. **策略改進**: 交易邏輯和信號過濾的改進點，基於演化趨勢分析
6. **模型優化**: HybridEnsembleClassifier的架構調整建議，考慮歷史性能變化
7. **配置調優**: config文件中需要調整的具體參數，避免已證實無效的配置
8. **智能演化策略**: 第$((round_num + 1))輪的重點方向，基於累積學習制定漸進式改進計劃

請以**記憶傳承和累積學習**為導向，提供可立即實施的具體建議，避免重復已證實無效的嘗試。"

    echo "$(date): Round ${round_num} - 開始Claude分析..." >> "${OPTIMIZATION_LOG}"

    # 調用Claude CLI進行智能分析 - 使用here-document避免參數長度限制
    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${claude_output}" 2>&1 << EOF
$claude_prompt
EOF


    if [ $? -eq 0 ] && [ -s "${claude_output}" ]; then
        echo "$(date): Round ${round_num} - Claude分析完成: ${claude_output}" >> "${OPTIMIZATION_LOG}"
        echo -e "${GREEN}🤖 Claude分析完成！正在應用優化建議...${NC}"
        return 0
    else
        echo "$(date): Round ${round_num} - Claude分析失敗" >> "${OPTIMIZATION_LOG}"
        echo -e "${RED}❌ Claude分析失敗，將繼續下一輪優化${NC}"
        return 1
    fi
}

# 應用Claude建議的優化
apply_claude_optimizations() {
    local round_num=$1
    local claude_analysis="${REPORT_DIR}/analysis/round_${round_num}_claude_analysis.txt"

    if [ ! -f "${claude_analysis}" ]; then
        echo "$(date): Round ${round_num} - Claude分析文件不存在，跳過優化應用" >> "${OPTIMIZATION_LOG}"
        return 1
    fi

    echo "$(date): Round ${round_num} - Claude分析完成，開始自動應用優化" >> "${OPTIMIZATION_LOG}"

    # 自動分析結果並提供摘要
    if [ -f "${claude_analysis}" ] && [ -s "${claude_analysis}" ]; then
        echo -e "${GREEN}🤖 Claude分析摘要:${NC}"
        echo -e "${BLUE}   分析文件: ${claude_analysis}${NC}"

        # 顯示關鍵建議摘要
        local key_suggestions=$(grep -A 3 -E "關鍵問題|建議|優化|調整" "${claude_analysis}" | head -10)
        if [ -n "$key_suggestions" ]; then
            echo -e "${YELLOW}📊 關鍵建議摘要:${NC}"
            echo "$key_suggestions" | head -5
            echo -e "${BLUE}   (詳細分析請查看: ${claude_analysis})${NC}"
        fi

        # 自動繼續到下一輪
        if [ $round_num -lt $ITERATIONS ]; then
            echo -e "${GREEN}⏰ 3秒後自動開始下一輪優化... (Ctrl+C取消)${NC}"
            sleep 3
        fi
    else
        echo -e "${RED}❌ Claude分析結果為空或無效${NC}"
        if [ $round_num -lt $ITERATIONS ]; then
            echo -e "${YELLOW}按Enter鍵繼續下一輪優化，或Ctrl+C退出...${NC}"
            read -r
        fi
    fi
}

# 性能驗證
validate_performance() {
    local round_num=$1
    local hyperopt_log=$2

    # 提取關鍵性能指標
    local total_profit=$(tail -100 "${hyperopt_log}" | grep -o "Total profit.*%" | tail -1 | grep -o "[0-9.-]*%" | sed 's/%//')

    echo "$(date): Round ${round_num} - 性能驗證 - Total Profit: ${total_profit}%" >> "${OPTIMIZATION_LOG}"

    # 檢查是否達到目標
    if (( $(echo "${total_profit:-0} > ${PERFORMANCE_TARGET_ANNUAL_RETURN}" | bc -l) )); then
        echo "$(date): Round ${round_num} - ✅ 達成年化收益目標!" >> "${OPTIMIZATION_LOG}"
        return 0
    else
        echo "$(date): Round ${round_num} - ❌ 未達成年化收益目標 (當前: ${total_profit}%, 目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%)" >> "${OPTIMIZATION_LOG}"
        return 1
    fi
}


# 執行既有模型策略回測
run_existing_model_backtest() {
    echo -e "${BLUE}🚀 使用既有模型執行策略回測...${NC}"

    local backtest_log="logs/backtest_existing_model_$(date +%Y%m%d_%H%M%S).log"

    # 確保配置正確設置使用既有模型
    echo -e "${BLUE}📋 驗證既有模型配置...${NC}"
    local follow_mode=$(grep -o '"follow_mode": [a-z]*' "${CONFIG}" | grep -o '[a-z]*$')
    local continual_learning=$(grep -o '"continual_learning": [a-z]*' "${CONFIG}" | grep -o '[a-z]*$')

    if [ "$follow_mode" != "true" ] || [ "$continual_learning" != "false" ]; then
        echo -e "${RED}❌ 配置不正確，無法使用既有模型${NC}"
        echo -e "${YELLOW}當前配置: follow_mode=$follow_mode, continual_learning=$continual_learning${NC}"
        return 1
    fi

    echo -e "${GREEN}✅ 既有模型配置驗證通過${NC}"
    echo -e "${BLUE}📊 執行回測...${NC}"
    echo -e "${BLUE}📄 日誌文件: ${backtest_log}${NC}"

    # 執行純策略回測
    freqtrade backtesting \
        --config "${CONFIG}" \
        --strategy "${STRATEGY}" \
        --freqaimodel HybridEnsembleClassifier \
        --timerange "${TIMERANGE}" \
        --logfile "${backtest_log}" \
        -v

    local backtest_exit_code=$?

    echo ""
    if [ $backtest_exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ 既有模型策略回測完成！${NC}"
        echo -e "${BLUE}📄 回測結果日誌: ${backtest_log}${NC}"
        echo -e "${YELLOW}💡 這是使用既有模型的純策略評估，無重新訓練${NC}"
    else
        echo -e "${RED}❌ 既有模型回測失敗 (退出代碼: $backtest_exit_code)${NC}"
        echo -e "${YELLOW}請檢查日誌文件: ${backtest_log}${NC}"
    fi

    echo ""
    echo -e "${YELLOW}按任意鍵繼續...${NC}"
    read -n 1
}

# 設置純策略hyperopt模式（禁用FreqAI）
setup_strategy_only_hyperopt() {
    echo -e "${BLUE}🔧 設置純策略hyperopt模式...${NC}"

    # 備份原始配置
    local backup_file="${CONFIG}.backup_strategy_only_$(date +%Y%m%d_%H%M%S)"
    cp "${CONFIG}" "${backup_file}"
    echo -e "${GREEN}✅ 配置已備份至: ${backup_file}${NC}"

    # 臨時禁用FreqAI以進行純策略優化
    if command -v jq >/dev/null 2>&1; then
        local temp_config="/tmp/config_strategy_only_$$"
        jq '.freqai.enabled = false' "${CONFIG}" > "${temp_config}"
        mv "${temp_config}" "${CONFIG}"
        echo -e "${GREEN}✅ 使用jq禁用FreqAI${NC}"
    else
        sed -i '' 's/"enabled": true/"enabled": false/' "${CONFIG}"
        echo -e "${GREEN}✅ 使用sed禁用FreqAI${NC}"
    fi

    # 驗證修改
    local freqai_enabled=$(grep -A 5 '"freqai"' "${CONFIG}" | grep -o '"enabled": [a-z]*' | grep -o '[a-z]*$')
    echo -e "${BLUE}📋 配置驗證: FreqAI enabled = ${freqai_enabled}${NC}"

    if [ "$freqai_enabled" = "false" ]; then
        echo -e "${GREEN}✅ 純策略hyperopt配置設置成功！${NC}"
        echo -e "${BLUE}📊 此模式將優化策略參數而不涉及ML模型${NC}"
    else
        echo -e "${RED}❌ FreqAI禁用可能失敗，請手動檢查配置文件${NC}"
    fi
}

# 執行純ML模型回測
run_pure_ml_backtest() {
    echo -e "${BLUE}🤖 使用既有ML模型執行純策略回測...${NC}"
    echo -e "${RED}⚠️  重要提醒: FreqAI在backtesting模式下無法避免重新訓練${NC}"
    echo -e "${YELLOW}💡 真正的"不重新訓練"需要使用dry-run模式${NC}"
    echo ""

    echo -e "${CYAN}📋 可用選項:${NC}"
    echo -e "${BLUE}1) 執行backtesting (會重新訓練，但使用既有配置)${NC}"
    echo -e "${BLUE}2) 執行dry-run模式 (真正使用既有模型，不重新訓練)${NC}"
    echo -e "${BLUE}3) 返回主選單${NC}"
    echo ""
    echo -e "${BLUE}請選擇 [1-3]: ${NC}"
    read -r backtest_choice

    case $backtest_choice in
        1)
            run_backtest_mode
            ;;
        2)
            run_dryrun_mode
            ;;
        3|*)
            return 0
            ;;
    esac
}

run_backtest_mode() {
    echo -e "${YELLOW}⚠️  執行backtesting模式 - 會重新訓練模型${NC}"

    local backtest_log="logs/pure_ml_backtest_$(date +%Y%m%d_%H%M%S).log"

    # 檢查既有模型是否存在
    local model_path="user_data/models/three_target_voting_15m_enhanced"
    if [ ! -d "${model_path}" ]; then
        echo -e "${RED}❌ 找不到既有ML模型目錄: ${model_path}${NC}"
        echo -e "${YELLOW}💡 請先訓練模型或確認模型路徑正確${NC}"
        echo ""
        echo -e "${YELLOW}按任意鍵繼續...${NC}"
        read -n 1
        return 1
    fi

    echo -e "${GREEN}✅ 找到既有ML模型: ${model_path}${NC}"
    echo -e "${BLUE}📊 開始執行backtesting (會重新訓練)...${NC}"
    echo -e "${BLUE}📄 日誌文件: ${backtest_log}${NC}"
    echo ""

    # 執行backtesting
    freqtrade backtesting \
        --config "${CONFIG}" \
        --strategy "${STRATEGY}" \
        --freqaimodel HybridEnsembleClassifier \
        --timerange "${TIMERANGE}" \
        --logfile "${backtest_log}" \
        -v

    local backtest_exit_code=$?

    echo ""
    echo -e "${BLUE}================================================${NC}"
    if [ $backtest_exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Backtesting完成！${NC}"
        echo -e "${YELLOW}📊 查看詳細結果: tail -50 ${backtest_log}${NC}"
    else
        echo -e "${RED}❌ Backtesting失敗 (退出代碼: $backtest_exit_code)${NC}"
        echo -e "${RED}📝 請檢查日誌: ${backtest_log}${NC}"
    fi

    echo ""
    echo -e "${YELLOW}按任意鍵繼續...${NC}"
    read -n 1
}

run_dryrun_mode() {
    echo -e "${GREEN}✅ 執行dry-run模式 - 真正使用既有模型，不重新訓練${NC}"

    local dryrun_log="logs/dryrun_existing_model_$(date +%Y%m%d_%H%M%S).log"

    # 檢查既有模型
    local model_path="user_data/models/three_target_voting_15m_enhanced"
    if [ ! -d "${model_path}" ]; then
        echo -e "${RED}❌ 找不到既有ML模型目錄: ${model_path}${NC}"
        return 1
    fi

    # 創建臨時配置文件 (dry-run + follow_mode)
    local temp_config="config_dryrun_existing_model.json"

    # 複製原配置並修改為dry-run
    jq '.dry_run = true | .freqai.follow_mode = true | .freqai.continual_learning = false | .freqai.live_retrain_hours = 0' "${CONFIG}" > "${temp_config}"

    echo -e "${GREEN}✅ 臨時配置文件已創建: ${temp_config}${NC}"
    echo -e "${BLUE}🔧 配置修改:${NC}"
    echo -e "  - dry_run: true"
    echo -e "  - follow_mode: true"
    echo -e "  - continual_learning: false"
    echo -e "  - live_retrain_hours: 0"
    echo ""

    echo -e "${BLUE}📊 開始執行dry-run (使用既有模型)...${NC}"
    echo -e "${BLUE}📄 日誌文件: ${dryrun_log}${NC}"
    echo -e "${YELLOW}💡 運行10分鐘後自動停止...${NC}"
    echo ""

    # 執行dry-run模式 (會在背景運行10分鐘)
    timeout 600 freqtrade trade \
        --config "${temp_config}" \
        --strategy "${STRATEGY}" \
        --freqaimodel HybridEnsembleClassifier \
        --logfile "${dryrun_log}" \
        -v &

    local freqtrade_pid=$!

    echo -e "${GREEN}🚀 FreqTrade已在背景啟動 (PID: $freqtrade_pid)${NC}"
    echo -e "${BLUE}⏳ 運行10分鐘，監控既有模型使用情況...${NC}"

    # 監控運行狀態
    local count=0
    while [ $count -lt 60 ]; do
        if kill -0 $freqtrade_pid 2>/dev/null; then
            echo -e "${CYAN}⏱️  運行中... ($((count*10))秒) - 檢查日誌: tail -f ${dryrun_log}${NC}"
            sleep 10
            count=$((count + 1))
        else
            echo -e "${YELLOW}🛑 FreqTrade已停止${NC}"
            break
        fi
    done

    # 停止進程 (如果仍在運行)
    if kill -0 $freqtrade_pid 2>/dev/null; then
        echo -e "${YELLOW}⏹️  停止FreqTrade...${NC}"
        kill $freqtrade_pid
        wait $freqtrade_pid 2>/dev/null
    fi

    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${GREEN}✅ Dry-run測試完成！${NC}"
    echo -e "${GREEN}🎉 此模式真正使用既有ML模型，不重新訓練${NC}"
    echo ""
    echo -e "${CYAN}📊 結果分析:${NC}"
    echo -e "  - 配置文件: ${temp_config}"
    echo -e "  - 日誌文件: ${dryrun_log}"
    echo -e "  - 模型路徑: ${model_path}"
    echo ""

    # 檢查是否有重新訓練的跡象
    if grep -q "Starting training\|Training.*pairs" "${dryrun_log}" 2>/dev/null; then
        echo -e "${RED}⚠️  警告: 發現訓練日誌，可能仍有重新訓練${NC}"
    else
        echo -e "${GREEN}✅ 確認: 沒有重新訓練，成功使用既有模型${NC}"
    fi

    echo -e "${YELLOW}💡 查看完整日誌: tail -100 ${dryrun_log}${NC}"
    echo -e "${YELLOW}💡 查看模型使用: grep -i "model\|load" ${dryrun_log}${NC}"

    # 清理臨時配置文件
    rm -f "${temp_config}"

}

# 交互式選單函數
show_interactive_menu() {
    while true; do
        clear
        echo "=========================================================================="
        echo -e "${CYAN}🚀 FreqAI三目標投票系統 - 專業量化優化選單${NC}"
        echo "=========================================================================="
        echo ""
        echo -e "${BLUE}📊 當前配置:${NC}"
        echo -e "   策略: ${STRATEGY}"
        echo -e "   時間框架: 15分鐘"
        echo -e "   時間範圍: ${TIMERANGE}"
        echo -e "   並行任務: ${JOBS}"
        echo ""
        echo -e "${YELLOW}🎯 請選擇優化模式:${NC}"
        echo ""
        echo -e "   ${GREEN}1)${NC} 快速單次優化 - 適合日常調優 [⚡ 15-30分鐘]"
        echo -e "   ${GREEN}2)${NC} 深度單次優化 - 更精確的參數搜索 [⚡ 45-60分鐘]"
        echo -e "   ${GREEN}3)${NC} 智能迭代優化 - Claude AI自動分析 [🧠 2-3小時]"
        echo -e "   ${GREEN}4)${NC} 超級智能優化 - 頂級量化策略+報告 [🤖 4-5小時]"
        echo -e "   ${GREEN}5)${NC} 目標導向優化 - 100%+收益/<10%損失 [🎯 3-6小時]"
        echo -e "   ${GREEN}6)${NC} 自定義配置 - 手動設置所有參數"
        echo -e "   ${CYAN}7)${NC} Claude 工具箱 - 測試與獨立分析 [🤖 即時]"
        echo -e "   ${PURPLE}8)${NC} 既有模型回測 - 使用已訓練模型進行策略回測 [⚡ 快速]"
        echo -e "   ${PURPLE}9)${NC} 純ML模型回測 - 既有ML模型backtesting評估 [⚡ 即時]"
        echo -e "   ${RED}q)${NC} 退出"
        echo ""
        echo -e "${PURPLE}💡 建議: 首次使用選擇模式1進行快速測試，有既有模型時選擇模式8或9${NC}"
        echo ""
        echo -n "請輸入選項 [1-9/q]: "
        read choice

        case $choice in
            1)
                echo ""
                echo -e "${YELLOW}⚡ 啟動快速單次優化模式...${NC}"
                EPOCHS=100
                INTELLIGENT_MODE=false
                CLAUDE_ANALYSIS_ENABLED=false
                return 0
                ;;
            2)
                echo ""
                echo -e "${YELLOW}🔥 啟動深度單次優化模式...${NC}"
                EPOCHS=300
                INTELLIGENT_MODE=false
                CLAUDE_ANALYSIS_ENABLED=false
                return 0
                ;;
            3)
                echo ""
                echo -e "${YELLOW}🧠 啟動智能迭代優化模式...${NC}"
                EPOCHS=150
                ITERATIONS=3
                INTELLIGENT_MODE=true
                CLAUDE_ANALYSIS_ENABLED=true
                return 0
                ;;
            4)
                echo ""
                echo -e "${YELLOW}🤖 啟動超級智能優化模式...${NC}"
                EPOCHS=200
                ITERATIONS=5
                INTELLIGENT_MODE=true
                CLAUDE_ANALYSIS_ENABLED=true
                return 0
                ;;
            5)
                echo ""
                echo -e "${YELLOW}🎯 啟動目標導向優化模式...${NC}"
                EPOCHS=250
                ITERATIONS=7
                INTELLIGENT_MODE=true
                CLAUDE_ANALYSIS_ENABLED=true
                PERFORMANCE_TARGET_ANNUAL_RETURN=100.0
                PERFORMANCE_TARGET_MAX_LOSS=10.0
                return 0
                ;;
            6)
                show_custom_config_menu
                # 如果用戶在自定義選單中選擇開始優化，則退出主選單
                if [ $? -eq 0 ]; then
                    return 0
                fi
                ;;
            7)
                show_claude_toolbox_menu
                ;;
            8)
                echo ""
                echo -e "${YELLOW}⚡ 啟動既有模型回測模式...${NC}"
                echo -e "${BLUE}💡 此模式使用已訓練模型進行策略回測，不重新訓練${NC}"
                echo ""
                echo -e "${CYAN}選擇既有模型使用方式:${NC}"
                echo -e "  ${GREEN}a)${NC} 純策略回測 - 使用既有ML模型評估策略性能"
                echo -e "  ${GREEN}b)${NC} 純策略hyperopt - 禁用FreqAI，只優化策略參數"
                echo ""
                echo -n "請選擇 [a/b]: "
                read existing_choice

                case $existing_choice in
                    a|A)
                        echo -e "${GREEN}✅ 選擇純策略回測模式${NC}"
                        # 使用backtesting而非hyperopt
                        echo -e "${BLUE}🚀 執行既有模型策略回測...${NC}"
                        run_existing_model_backtest
                        return 0
                        ;;
                    b|B)
                        echo -e "${GREEN}✅ 選擇純策略hyperopt模式${NC}"
                        # 禁用FreqAI進行純策略優化
                        setup_strategy_only_hyperopt
                        EPOCHS=150
                        INTELLIGENT_MODE=false
                        CLAUDE_ANALYSIS_ENABLED=true
                        echo -e "${GREEN}✅ 純策略hyperopt模式已設置${NC}"
                        return 0
                        ;;
                    *)
                        echo -e "${RED}❌ 無效選項，返回主選單${NC}"
                        sleep 2
                        ;;
                esac
                ;;
            9)
                echo ""
                echo -e "${YELLOW}⚡ 啟動純ML模型回測模式...${NC}"
                echo -e "${BLUE}💡 此模式直接使用既有ML模型進行策略回測${NC}"

                # 執行純ML模型回測
                run_pure_ml_backtest
                return 0
                ;;
            q|Q)
                echo ""
                echo -e "${GREEN}👋 感謝使用FreqAI量化優化系統！${NC}"
                exit 0
                ;;
            *)
                echo ""
                echo -e "${RED}❌ 無效選項，請重新選擇${NC}"
                sleep 2
                ;;
        esac
    done
}

# 自定義配置選單
show_custom_config_menu() {
    while true; do
        clear
        echo "=========================================================================="
        echo -e "${CYAN}⚙️ FreqAI自定義配置選單${NC}"
        echo "=========================================================================="
        echo ""
        echo -e "${BLUE}📊 當前配置:${NC}"
        echo -e "   Hyperopt輪數: ${EPOCHS}"
        echo -e "   迭代次數: ${ITERATIONS}"
        echo -e "   並行任務: ${JOBS}"
        echo -e "   時間範圍: ${TIMERANGE}"
        echo -e "   智能模式: $(if [ "$INTELLIGENT_MODE" = true ]; then echo "✅ 已啟用"; else echo "❌ 未啟用"; fi)"
        echo -e "   Claude分析: $(if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then echo "✅ 已啟用"; else echo "❌ 未啟用"; fi)"
        echo -e "   收益目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+"
        echo -e "   損失限制: <${PERFORMANCE_TARGET_MAX_LOSS}%"
        echo ""
        echo -e "${YELLOW}🔧 請選擇要配置的參數:${NC}"
        echo ""
        echo -e "   ${GREEN}1)${NC} 設置Hyperopt輪數 (當前: ${EPOCHS})"
        echo -e "   ${GREEN}2)${NC} 設置迭代次數 (當前: ${ITERATIONS})"
        echo -e "   ${GREEN}3)${NC} 設置並行任務數 (當前: ${JOBS})"
        echo -e "   ${GREEN}4)${NC} 設置時間範圍 (當前: ${TIMERANGE})"
        echo -e "   ${GREEN}5)${NC} 切換智能模式 ($(if [ "$INTELLIGENT_MODE" = true ]; then echo "當前: 已啟用"; else echo "當前: 未啟用"; fi))"
        echo -e "   ${GREEN}6)${NC} 切換Claude分析 ($(if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then echo "當前: 已啟用"; else echo "當前: 未啟用"; fi))"
        echo -e "   ${GREEN}7)${NC} 設置收益目標% (當前: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%)"
        echo -e "   ${GREEN}8)${NC} 設置損失限制% (當前: ${PERFORMANCE_TARGET_MAX_LOSS}%)"
        echo -e "   ${GREEN}s)${NC} 開始優化 (使用當前配置)"
        echo -e "   ${RED}b)${NC} 返回主選單"
        echo ""
        echo -n "請輸入選項 [1-8/s/b]: "
        read choice

        case $choice in
            1)
                echo -n "請輸入Hyperopt輪數 (10-500): "
                read epochs
                if [[ "$epochs" =~ ^[0-9]+$ ]] && [ "$epochs" -ge 10 ] && [ "$epochs" -le 500 ]; then
                    EPOCHS=$epochs
                    echo -e "${GREEN}✅ Hyperopt輪數已設置為: $EPOCHS${NC}"
                else
                    echo -e "${RED}❌ 無效輸入，請輸入10-500之間的數字${NC}"
                fi
                sleep 2
                ;;
            2)
                echo -n "請輸入迭代次數 (1-10): "
                read iter
                if [[ "$iter" =~ ^[0-9]+$ ]] && [ "$iter" -ge 1 ] && [ "$iter" -le 10 ]; then
                    ITERATIONS=$iter
                    INTELLIGENT_MODE=true
                    echo -e "${GREEN}✅ 迭代次數已設置為: $ITERATIONS (智能模式已自動啟用)${NC}"
                else
                    echo -e "${RED}❌ 無效輸入，請輸入1-10之間的數字${NC}"
                fi
                sleep 2
                ;;
            3)
                echo -n "請輸入並行任務數 (1-16): "
                read jobs
                if [[ "$jobs" =~ ^[0-9]+$ ]] && [ "$jobs" -ge 1 ] && [ "$jobs" -le 16 ]; then
                    JOBS=$jobs
                    echo -e "${GREEN}✅ 並行任務數已設置為: $JOBS${NC}"
                else
                    echo -e "${RED}❌ 無效輸入，請輸入1-16之間的數字${NC}"
                fi
                sleep 2
                ;;
            4)
                echo -e "${BLUE}當前時間範圍格式: YYYYMMDD-YYYYMMDD${NC}"
                echo -e "${BLUE}範例: 20240701-20250801${NC}"
                echo -n "請輸入新的時間範圍: "
                read timerange
                if [[ "$timerange" =~ ^[0-9]{8}-[0-9]{8}$ ]]; then
                    TIMERANGE=$timerange
                    echo -e "${GREEN}✅ 時間範圍已設置為: $TIMERANGE${NC}"
                else
                    echo -e "${RED}❌ 無效格式，請使用YYYYMMDD-YYYYMMDD格式${NC}"
                fi
                sleep 2
                ;;
            5)
                if [ "$INTELLIGENT_MODE" = true ]; then
                    INTELLIGENT_MODE=false
                    echo -e "${YELLOW}⚡ 智能模式已關閉，切換為快速模式${NC}"
                else
                    INTELLIGENT_MODE=true
                    echo -e "${GREEN}🧠 智能模式已啟用，將進行迭代優化${NC}"
                fi
                sleep 2
                ;;
            6)
                if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then
                    CLAUDE_ANALYSIS_ENABLED=false
                    echo -e "${YELLOW}🤖 Claude分析已關閉${NC}"
                else
                    CLAUDE_ANALYSIS_ENABLED=true
                    echo -e "${GREEN}🤖 Claude分析已啟用，將自動進行策略分析${NC}"
                fi
                sleep 2
                ;;
            7)
                echo -n "請輸入年化收益目標% (50-200): "
                read target_return
                if [[ "$target_return" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$target_return >= 50 && $target_return <= 200" | bc -l) )); then
                    PERFORMANCE_TARGET_ANNUAL_RETURN=$target_return
                    echo -e "${GREEN}✅ 年化收益目標已設置為: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%${NC}"
                else
                    echo -e "${RED}❌ 無效輸入，請輸入50-200之間的數字${NC}"
                fi
                sleep 2
                ;;
            8)
                echo -n "請輸入最大年化損失% (5-30): "
                read max_loss
                if [[ "$max_loss" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$max_loss >= 5 && $max_loss <= 30" | bc -l) )); then
                    PERFORMANCE_TARGET_MAX_LOSS=$max_loss
                    echo -e "${GREEN}✅ 最大年化損失已設置為: <${PERFORMANCE_TARGET_MAX_LOSS}%${NC}"
                else
                    echo -e "${RED}❌ 無效輸入，請輸入5-30之間的數字${NC}"
                fi
                sleep 2
                ;;
            s|S)
                echo ""
                echo -e "${GREEN}🚀 開始使用自定義配置進行優化...${NC}"
                echo -e "${BLUE}最終配置確認:${NC}"
                echo -e "  - Hyperopt輪數: ${EPOCHS}"
                echo -e "  - 迭代次數: ${ITERATIONS}"
                echo -e "  - 並行任務: ${JOBS}"
                echo -e "  - 時間範圍: ${TIMERANGE}"
                echo -e "  - 智能模式: $(if [ "$INTELLIGENT_MODE" = true ]; then echo "已啟用"; else echo "未啟用"; fi)"
                echo -e "  - Claude分析: $(if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then echo "已啟用"; else echo "未啟用"; fi)"
                echo -e "  - 收益目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+"
                echo -e "  - 損失限制: <${PERFORMANCE_TARGET_MAX_LOSS}%"
                return 0
                ;;
            b|B)
                return 1
                ;;
            *)
                echo ""
                echo -e "${RED}❌ 無效選項，請重新選擇${NC}"
                sleep 2
                ;;
        esac
    done
}

# Claude 工具箱選單函數
show_claude_toolbox_menu() {
    while true; do
        clear
        echo "=========================================================================="
        echo -e "${CYAN}🤖 Claude 工具箱 - FreqAI 量化分析專家${NC}"
        echo "=========================================================================="
        echo ""
        echo -e "${BLUE}📊 Claude CLI 狀態:${NC}"
        echo -e "   CLI 路徑: ${CLAUDE_CLI_PATH}"
        echo -e "   分析功能: $(if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then echo "${GREEN}✅ 已啟用${NC}"; else echo "${RED}❌ 已禁用${NC}"; fi)"
        echo ""
        echo -e "${YELLOW}🛠️ 請選擇 Claude 功能:${NC}"
        echo ""
        echo -e "   ${GREEN}1)${NC} Claude CLI 連接測試 - 驗證基本功能 [🔍 30秒]"
        echo -e "   ${GREEN}2)${NC} FreqAI 策略分析 - 分析當前策略配置 [📊 2-3分鐘]"
        echo -e "   ${GREEN}3)${NC} 歷史性能分析 - 分析回測結果和性能 [📈 3-5分鐘]"
        echo -e "   ${GREEN}4)${NC} 參數優化建議 - 基於目標的參數調整 [🎯 5-10分鐘]"
        echo -e "   ${GREEN}5)${NC} 風險評估報告 - 策略風險和回撤分析 [⚠️ 3-5分鐘]"
        echo -e "   ${GREEN}6)${NC} 自定義 Claude 分析 - 手動輸入問題 [💭 即時]"
        echo -e "   ${CYAN}7)${NC} 設置 Claude CLI 路徑"
        echo -e "   ${PURPLE}8)${NC} 查看 Claude 分析歷史"
        echo -e "   ${RED}b)${NC} 返回主選單"
        echo ""
        echo -e "${PURPLE}💡 提示: 建議先執行連接測試確保 Claude CLI 正常工作${NC}"
        echo ""
        echo -n "請輸入選項 [1-8/b]: "
        read choice

        case $choice in
            1)
                echo ""
                echo -e "${CYAN}🔍 執行 Claude CLI 連接測試...${NC}"
                test_claude_functionality
                echo ""
                echo -e "${YELLOW}按任意鍵繼續...${NC}"
                read -n 1
                ;;
            2)
                echo ""
                echo -e "${CYAN}📊 啟動 FreqAI 策略分析...${NC}"
                claude_strategy_analysis
                echo ""
                echo -e "${YELLOW}按任意鍵繼續...${NC}"
                read -n 1
                ;;
            3)
                echo ""
                echo -e "${CYAN}📈 啟動歷史性能分析...${NC}"
                claude_performance_analysis
                echo ""
                echo -e "${YELLOW}按任意鍵繼續...${NC}"
                read -n 1
                ;;
            4)
                echo ""
                echo -e "${CYAN}🎯 啟動參數優化建議...${NC}"
                claude_parameter_optimization
                echo ""
                echo -e "${YELLOW}按任意鍵繼續...${NC}"
                read -n 1
                ;;
            5)
                echo ""
                echo -e "${CYAN}⚠️ 啟動風險評估報告...${NC}"
                claude_risk_assessment
                echo ""
                echo -e "${YELLOW}按任意鍵繼續...${NC}"
                read -n 1
                ;;
            6)
                echo ""
                echo -e "${CYAN}💭 自定義 Claude 分析模式${NC}"
                claude_custom_analysis
                echo ""
                echo -e "${YELLOW}按任意鍵繼續...${NC}"
                read -n 1
                ;;
            7)
                echo ""
                echo -n "請輸入新的 Claude CLI 路徑: "
                read new_path
                if [ -f "$new_path" ] && [ -x "$new_path" ]; then
                    CLAUDE_CLI_PATH="$new_path"
                    echo -e "${GREEN}✅ Claude CLI 路徑已更新為: $CLAUDE_CLI_PATH${NC}"
                else
                    echo -e "${RED}❌ 路徑無效或文件不可執行: $new_path${NC}"
                fi
                sleep 2
                ;;
            8)
                echo ""
                echo -e "${CYAN}📜 查看 Claude 分析歷史...${NC}"
                claude_analysis_history
                echo ""
                echo -e "${YELLOW}按任意鍵繼續...${NC}"
                read -n 1
                ;;
            b|B)
                return 0
                ;;
            *)
                echo ""
                echo -e "${RED}❌ 無效選項，請重新選擇${NC}"
                sleep 2
                ;;
        esac
    done
}

# Claude 策略分析功能
claude_strategy_analysis() {
    echo -e "${BLUE}📊 分析當前 FreqAI 策略配置...${NC}"

    local analysis_output="${REPORT_DIR}/claude_analysis/strategy_analysis_$(date +%Y%m%d_%H%M%S).md"
    mkdir -p "$(dirname "${analysis_output}")"

    local strategy_prompt="請分析以下 FreqAI 策略配置，提供專業的量化交易建議：

## 策略文件
請讀取並分析策略文件: user_data/strategies/${STRATEGY}.py

## 配置文件
請讀取並分析配置文件: ${CONFIG}

## 模型文件
請讀取並分析模型文件: user_data/freqaimodels/HybridEnsembleClassifier.py

## 分析要求
1. **策略邏輯分析**: 評估買賣信號邏輯的合理性
2. **風險管理評估**: 分析止損、倉位管理等風險控制
3. **參數配置檢查**: 評估當前參數設置的合理性
4. **性能預期分析**: 基於配置預估可能的收益和風險
5. **優化建議**: 提供具體的改進建議

使用 freqai-quant-engineer agent 進行專業分析。"

    echo -e "${YELLOW}🤖 正在向 Claude 發送策略分析請求...${NC}"

    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${analysis_output}" 2>&1 << EOF
${strategy_prompt}
EOF

    if [ $? -eq 0 ] && [ -s "${analysis_output}" ]; then
        echo -e "${GREEN}✅ 策略分析完成！${NC}"
        echo -e "${BLUE}📝 分析報告已保存至: ${analysis_output}${NC}"
        echo ""
        echo -e "${CYAN}📊 分析摘要:${NC}"
        head -20 "${analysis_output}"
        echo ""
        echo -e "${YELLOW}💡 完整報告請查看: ${analysis_output}${NC}"
    else
        echo -e "${RED}❌ 策略分析失敗${NC}"
        echo -e "${RED}📝 錯誤信息:${NC}"
        cat "${analysis_output}" 2>/dev/null || echo "無法讀取錯誤信息"
    fi
}

# Claude 歷史性能分析功能
claude_performance_analysis() {
    echo -e "${BLUE}📈 分析歷史性能數據...${NC}"

    local analysis_output="${REPORT_DIR}/claude_analysis/performance_analysis_$(date +%Y%m%d_%H%M%S).md"
    mkdir -p "$(dirname "${analysis_output}")"

    # 查找最新的回測結果文件
    local latest_backtest_file=""
    if [ -d "user_data/hyperopt_results" ]; then
        latest_backtest_file=$(find user_data/hyperopt_results -name "*${STRATEGY}*" -type f | head -1)
    fi

    local performance_prompt="請分析 FreqAI 策略的歷史性能表現：

## 回測結果文件
$(if [ -n "$latest_backtest_file" ] && [ -f "$latest_backtest_file" ]; then
    echo "請讀取並分析回測結果文件: $latest_backtest_file"
else
    echo "未找到回測結果文件，請基於策略配置進行理論分析"
fi)

## 配置參數
- 策略: ${STRATEGY}
- 時間範圍: ${TIMERANGE}
- 收益目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+
- 損失限制: <${PERFORMANCE_TARGET_MAX_LOSS}%

## 分析要求
1. **關鍵指標分析**: 年化收益、最大回撤、勝率、盈虧比
2. **風險評估**: 波動率、VaR、風險調整收益
3. **交易統計**: 交易頻率、持倉時間、成功率
4. **市場適應性**: 不同市場條件下的表現
5. **改進建議**: 基於歷史表現的優化方向

使用 freqai-quant-engineer agent 進行專業分析。"

    echo -e "${YELLOW}🤖 正在向 Claude 發送性能分析請求...${NC}"

    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${analysis_output}" 2>&1 << EOF
${performance_prompt}
EOF

    if [ $? -eq 0 ] && [ -s "${analysis_output}" ]; then
        echo -e "${GREEN}✅ 性能分析完成！${NC}"
        echo -e "${BLUE}📝 分析報告已保存至: ${analysis_output}${NC}"
        echo ""
        echo -e "${CYAN}📈 性能摘要:${NC}"
        head -20 "${analysis_output}"
        echo ""
        echo -e "${YELLOW}💡 完整報告請查看: ${analysis_output}${NC}"
    else
        echo -e "${RED}❌ 性能分析失敗${NC}"
        echo -e "${RED}📝 錯誤信息:${NC}"
        cat "${analysis_output}" 2>/dev/null || echo "無法讀取錯誤信息"
    fi
}

# Claude 參數優化建議功能
claude_parameter_optimization() {
    echo -e "${BLUE}🎯 生成參數優化建議...${NC}"

    local analysis_output="${REPORT_DIR}/claude_analysis/parameter_optimization_$(date +%Y%m%d_%H%M%S).md"
    mkdir -p "$(dirname "${analysis_output}")"

    local optimization_prompt="請針對 FreqAI 策略提供參數優化建議：

## 目標設定
- 目標年化收益率: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+
- 最大年化損失率: <${PERFORMANCE_TARGET_MAX_LOSS}%
- 策略: ${STRATEGY}
- 時間範圍: ${TIMERANGE}

## 配置文件
請讀取並分析配置文件: ${CONFIG}

## 分析要求
1. **關鍵參數識別**: 識別對性能影響最大的參數
2. **參數調整建議**: 提供具體的數值調整建議
3. **風險控制優化**: 優化止損、倉位管理參數
4. **特徵工程建議**: 優化 FreqAI 特徵參數
5. **模型參數調整**: LightGBM/XGBoost 等模型參數建議
6. **實施優先級**: 按影響程度排序優化建議

使用 freqai-quant-engineer agent 進行專業分析。"

    echo -e "${YELLOW}🤖 正在向 Claude 發送優化建議請求...${NC}"

    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${analysis_output}" 2>&1 << EOF
${optimization_prompt}
EOF

    if [ $? -eq 0 ] && [ -s "${analysis_output}" ]; then
        echo -e "${GREEN}✅ 參數優化建議完成！${NC}"
        echo -e "${BLUE}📝 建議報告已保存至: ${analysis_output}${NC}"
        echo ""
        echo -e "${CYAN}🎯 優化摘要:${NC}"
        head -20 "${analysis_output}"
        echo ""
        echo -e "${YELLOW}💡 完整建議請查看: ${analysis_output}${NC}"
    else
        echo -e "${RED}❌ 參數優化建議失敗${NC}"
        echo -e "${RED}📝 錯誤信息:${NC}"
        cat "${analysis_output}" 2>/dev/null || echo "無法讀取錯誤信息"
    fi
}

# Claude 風險評估報告功能
claude_risk_assessment() {
    echo -e "${BLUE}⚠️ 生成風險評估報告...${NC}"

    local analysis_output="${REPORT_DIR}/claude_analysis/risk_assessment_$(date +%Y%m%d_%H%M%S).md"
    mkdir -p "$(dirname "${analysis_output}")"

    local risk_prompt="請對 FreqAI 策略進行全面的風險評估：

## 策略配置
請讀取並分析以下文件：
- 策略文件: user_data/strategies/${STRATEGY}.py
- 配置文件: ${CONFIG}
- 模型文件: user_data/freqaimodels/HybridEnsembleClassifier.py

## 風險參數
- 最大可接受年化損失: ${PERFORMANCE_TARGET_MAX_LOSS}%
- 目標年化收益: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%
- 交易時間框架: 15分鐘

## 風險分析要求
1. **市場風險**: 不同市場條件下的表現風險
2. **模型風險**: FreqAI 模型過擬合、數據洩漏等風險
3. **流動性風險**: 交易品種和時間的流動性評估
4. **技術風險**: 策略邏輯、程式錯誤等技術風險
5. **回撤風險**: 最大回撤、連續虧損的可能性
6. **Black Swan 風險**: 極端市場情況的影響
7. **風險控制建議**: 具體的風險緩解措施

使用 freqai-quant-engineer agent 進行專業風險分析。"

    echo -e "${YELLOW}🤖 正在向 Claude 發送風險評估請求...${NC}"

    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${analysis_output}" 2>&1 << EOF
${risk_prompt}
EOF

    if [ $? -eq 0 ] && [ -s "${analysis_output}" ]; then
        echo -e "${GREEN}✅ 風險評估報告完成！${NC}"
        echo -e "${BLUE}📝 風險報告已保存至: ${analysis_output}${NC}"
        echo ""
        echo -e "${CYAN}⚠️ 風險摘要:${NC}"
        head -20 "${analysis_output}"
        echo ""
        echo -e "${YELLOW}💡 完整風險評估請查看: ${analysis_output}${NC}"
    else
        echo -e "${RED}❌ 風險評估失敗${NC}"
        echo -e "${RED}📝 錯誤信息:${NC}"
        cat "${analysis_output}" 2>/dev/null || echo "無法讀取錯誤信息"
    fi
}

# Claude 自定義分析功能
claude_custom_analysis() {
    echo -e "${BLUE}💭 自定義 Claude 分析模式${NC}"
    echo ""
    echo -e "${YELLOW}請輸入您想要 Claude 分析的問題或主題:${NC}"
    echo -e "${PURPLE}(可以是任何與 FreqAI 量化交易相關的問題)${NC}"
    echo ""
    read -p "您的問題: " user_question

    if [ -z "$user_question" ]; then
        echo -e "${RED}❌ 問題不能為空${NC}"
        return 1
    fi

    local analysis_output="${REPORT_DIR}/claude_analysis/custom_analysis_$(date +%Y%m%d_%H%M%S).md"
    mkdir -p "$(dirname "${analysis_output}")"

    local custom_prompt="FreqAI 量化交易專家諮詢：

## 用戶問題
${user_question}

## 當前策略環境
- 策略: ${STRATEGY}
- 配置: ${CONFIG}
- 時間範圍: ${TIMERANGE}
- 目標收益: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+
- 損失限制: <${PERFORMANCE_TARGET_MAX_LOSS}%

## 相關文件 (如需要請讀取分析)
- 策略文件: user_data/strategies/${STRATEGY}.py
- 配置文件: ${CONFIG}
- 模型文件: user_data/freqaimodels/HybridEnsembleClassifier.py

請使用 freqai-quant-engineer agent 提供專業、詳細的回答。"

    echo ""
    echo -e "${YELLOW}🤖 正在向 Claude 發送自定義分析請求...${NC}"
    echo -e "${BLUE}問題: ${user_question}${NC}"

    "${CLAUDE_CLI_PATH}" --dangerously-skip-permissions > "${analysis_output}" 2>&1 << EOF
${custom_prompt}
EOF

    if [ $? -eq 0 ] && [ -s "${analysis_output}" ]; then
        echo -e "${GREEN}✅ 自定義分析完成！${NC}"
        echo -e "${BLUE}📝 分析結果已保存至: ${analysis_output}${NC}"
        echo ""
        echo -e "${CYAN}💭 Claude 的回答:${NC}"
        head -30 "${analysis_output}"
        echo ""
        echo -e "${YELLOW}💡 完整回答請查看: ${analysis_output}${NC}"
    else
        echo -e "${RED}❌ 自定義分析失敗${NC}"
        echo -e "${RED}📝 錯誤信息:${NC}"
        cat "${analysis_output}" 2>/dev/null || echo "無法讀取錯誤信息"
    fi
}

# Claude 分析歷史功能
claude_analysis_history() {
    echo -e "${BLUE}📜 查看 Claude 分析歷史...${NC}"

    local analysis_dir="${REPORT_DIR}/claude_analysis"

    if [ ! -d "$analysis_dir" ]; then
        echo -e "${YELLOW}⚠️ 尚未找到 Claude 分析歷史記錄${NC}"
        echo -e "${BLUE}💡 請先執行一些 Claude 分析功能來生成歷史記錄${NC}"
        return 1
    fi

    echo ""
    echo -e "${CYAN}📋 最近的 Claude 分析記錄:${NC}"
    echo ""

    local count=0
    for file in $(ls -t "$analysis_dir"/*.md 2>/dev/null | head -10); do
        if [ -f "$file" ]; then
            local filename=$(basename "$file")
            local filesize=$(ls -lh "$file" | awk '{print $5}')
            local filetime=$(ls -l "$file" | awk '{print $6" "$7" "$8}')

            count=$((count + 1))
            echo -e "   ${GREEN}${count})${NC} $filename"
            echo -e "      大小: $filesize | 時間: $filetime"
            echo -e "      路徑: $file"
            echo ""
        fi
    done

    if [ $count -eq 0 ]; then
        echo -e "${YELLOW}⚠️ 沒有找到分析記錄${NC}"
    else
        echo -e "${BLUE}💡 總共找到 $count 個分析記錄${NC}"
        echo ""
        echo -n "要查看某個分析記錄的內容嗎？請輸入編號 (1-$count) 或按 Enter 跳過: "
        read view_choice

        if [[ "$view_choice" =~ ^[0-9]+$ ]] && [ "$view_choice" -ge 1 ] && [ "$view_choice" -le $count ]; then
            local selected_file=$(ls -t "$analysis_dir"/*.md 2>/dev/null | sed -n "${view_choice}p")
            if [ -f "$selected_file" ]; then
                echo ""
                echo -e "${CYAN}📄 查看文件: $(basename "$selected_file")${NC}"
                echo -e "${YELLOW}================================================${NC}"
                head -50 "$selected_file"
                echo ""
                echo -e "${YELLOW}================================================${NC}"
                echo -e "${BLUE}💡 完整內容請查看: $selected_file${NC}"
            fi
        fi
    fi
}

# 如果啟用Claude測試模式，執行測試並退出
if [ "$TEST_CLAUDE_MODE" = true ]; then
    test_claude_functionality
    exit $?
fi

# 如果啟用選單模式，顯示交互界面
if [ "$MENU_MODE" = true ]; then
    show_interactive_menu
fi

# 初始化智能優化系統
if [ "$INTELLIGENT_MODE" = true ]; then
    echo -e "${CYAN}🤖 初始化智能迭代優化系統...${NC}"
    initialize_intelligent_optimization
fi

echo -e "${GREEN}=================================================="
echo -e "🎯 FreqAI Phase 6: 三目標投票系統智能優化"
echo -e "=================================================="
echo -e "策略: ${STRATEGY}"
echo -e "配置: ${CONFIG}"
echo -e "時間範圍: ${TIMERANGE}"
echo -e "優化輪數: ${EPOCHS}"
echo -e "並行任務: ${JOBS}"
if [ "$INTELLIGENT_MODE" = true ]; then
    echo -e "智能模式: ✅ 啟用 (${ITERATIONS} 輪迭代)"
    echo -e "Claude分析: $(if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then echo "✅ 啟用"; else echo "❌ 禁用"; fi)"
    echo -e "收益目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+"
    echo -e "損失限制: <${PERFORMANCE_TARGET_MAX_LOSS}%"
fi
echo -e "==================================================${NC}"

# 檢查必要文件和FreqAI數據完整性
echo -e "${BLUE}📋 檢查必要文件...${NC}"

if [ ! -f "user_data/strategies/${STRATEGY}.py" ]; then
    echo -e "${RED}❌ 策略文件不存在: user_data/strategies/${STRATEGY}.py${NC}"
    exit 1
fi

if [ ! -f "${CONFIG}" ]; then
    echo -e "${RED}❌ 配置文件不存在: ${CONFIG}${NC}"
    exit 1
fi

if [ ! -f "user_data/freqaimodels/HybridEnsembleClassifier.py" ]; then
    echo -e "${RED}❌ 模型文件不存在: user_data/freqaimodels/HybridEnsembleClassifier.py${NC}"
    exit 1
fi

# 檢查startup_candle_count是否足夠
echo -e "${BLUE}🔍 檢查策略配置...${NC}"
STARTUP_COUNT=$(grep -E "startup_candle_count.*=.*[0-9]+" "user_data/strategies/${STRATEGY}.py" | grep -o "[0-9]\+" | head -1)
if [ -n "$STARTUP_COUNT" ] && [ "$STARTUP_COUNT" -lt 350 ]; then
    echo -e "${YELLOW}⚠️  startup_candle_count過低 (${STARTUP_COUNT}), 需要≥350${NC}"
    echo -e "${YELLOW}🔧 自動修復startup_candle_count...${NC}"
    sed -i '' 's/startup_candle_count.*=.*[0-9]*/startup_candle_count: int = 350  # AUTO-FIX: Sufficient for rolling operations/' "user_data/strategies/${STRATEGY}.py"
    echo -e "${GREEN}✅ startup_candle_count已修復為350${NC}"
fi

# 檢查FreqAI訓練數據
echo -e "${BLUE}📊 檢查FreqAI數據完整性...${NC}"
DATA_PATH="user_data/data/binance/ETH_USDT-15m.feather"
if [ ! -f "$DATA_PATH" ]; then
    echo -e "${YELLOW}⚠️  數據文件不存在，正在下載...${NC}"
    freqtrade download-data --timeframes 15m --pairs ETH/USDT:USDT --exchange binance --timerange 20240301-20250830 --config "${CONFIG}" --trading-mode futures -q
fi

# 智能檢查Claude CLI (如果啟用)
if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then
    # 嘗試多個可能的Claude CLI路徑
    if [ -f "${CLAUDE_CLI_PATH}" ]; then
        echo -e "${GREEN}✅ Claude CLI已找到: ${CLAUDE_CLI_PATH}${NC}"
    elif command -v claude >/dev/null 2>&1; then
        CLAUDE_CLI_PATH=$(command -v claude)
        echo -e "${GREEN}✅ Claude CLI已找到: ${CLAUDE_CLI_PATH}${NC}"
    else
        echo -e "${YELLOW}⚠️  Claude CLI未找到，將禁用Claude分析功能${NC}"
        echo -e "${BLUE}💡 提示: 安裝Claude CLI後可使用 --claude-path=路徑 指定${NC}"
        CLAUDE_ANALYSIS_ENABLED=false
    fi
fi

echo -e "${GREEN}✅ 所有必要文件檢查完成${NC}"

# 清理舊的優化結果
echo -e "${YELLOW}🧹 清理舊的優化結果...${NC}"
rm -rf user_data/hyperopt_results/*hyperopt_${STRATEGY}* 2>/dev/null || true
rm -rf user_data/models/three_target_voting* 2>/dev/null || true

# 創建結果目錄
mkdir -p user_data/hyperopt_results
mkdir -p logs

# =====================================================
# 智能迭代優化主循環
# =====================================================

if [ "$INTELLIGENT_MODE" = true ]; then
    echo -e "${CYAN}🚀 開始智能迭代優化循環 (${ITERATIONS} 輪)...${NC}"

    for ((round=1; round<=ITERATIONS; round++)); do
        echo ""
        echo -e "${PURPLE}========================================================================${NC}"
        echo -e "${PURPLE}🔄 第 ${round}/${ITERATIONS} 輪優化 - Session: ${SESSION_ID}${NC}"
        echo -e "${PURPLE}========================================================================${NC}"

        # 備份當前配置
        backup_current_configuration $round

        # 設定本輪日誌文件
        LOG_FILE="logs/hyperopt_round${round}_$(date +%Y%m%d_%H%M%S).log"

        echo -e "${BLUE}🚀 第 ${round} 輪優化開始...${NC}"
        echo -e "${BLUE}📄 日誌文件: ${LOG_FILE}${NC}"

        # 執行Hyperopt優化
        freqtrade hyperopt \
            --config "${CONFIG}" \
            --strategy "${STRATEGY}" \
            --freqaimodel HybridEnsembleClassifier \
            --timerange "${TIMERANGE}" \
            --epochs ${EPOCHS} \
            --spaces buy \
            -j ${JOBS} \
            --hyperopt-loss SharpeHyperOptLoss \
            --random-state $((42 + round)) \
            --min-trades 10 \
            --logfile "${LOG_FILE}" \
            -v

        HYPEROPT_EXIT_CODE=$?

        if [ $HYPEROPT_EXIT_CODE -eq 0 ]; then
            echo -e "${GREEN}✅ 第 ${round} 輪優化成功完成！${NC}"

            # 保存迭代結果
            save_iteration_results $round "${LOG_FILE}"

            # 生成優化報告
            generate_optimization_report $round "${LOG_FILE}"

            # 性能驗證
            validate_performance $round "${LOG_FILE}"

            # 更新迭代追蹤
            update_iteration_tracking $round "${LOG_FILE}"

            # Claude分析 (如果啟用)
            if [ "$CLAUDE_ANALYSIS_ENABLED" = true ]; then
                call_claude_analysis $round
                apply_claude_optimizations $round
            else
                echo -e "${YELLOW}📊 第 ${round} 輪優化完成，Claude分析已禁用${NC}"
                if [ $round -lt $ITERATIONS ]; then
                    echo -e "${YELLOW}按Enter鍵繼續下一輪優化，或Ctrl+C退出...${NC}"
                    read -r
                fi
            fi

        else
            echo -e "${RED}❌ 第 ${round} 輪優化失敗 (退出代碼: $HYPEROPT_EXIT_CODE)${NC}"
            echo -e "${YELLOW}請檢查日誌文件: ${LOG_FILE}${NC}"

            # 記錄失敗
            echo "$(date): Round ${round} - 優化失敗 (退出代碼: $HYPEROPT_EXIT_CODE)" >> "${OPTIMIZATION_LOG}"

            # 詢問是否繼續
            if [ $round -lt $ITERATIONS ]; then
                echo -e "${YELLOW}是否繼續下一輪優化? [y/N]: ${NC}"
                read -r continue_choice
                if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
                    break
                fi
            fi
        fi

        echo -e "${PURPLE}🔄 第 ${round}/${ITERATIONS} 輪優化完成${NC}"
    done

    # 最終報告
    echo ""
    echo -e "${GREEN}========================================================================${NC}"
    echo -e "${GREEN}🎉 智能迭代優化完成! (${ITERATIONS} 輪)${NC}"
    echo -e "${GREEN}========================================================================${NC}"
    echo -e "${BLUE}📊 最終結果:${NC}"
    echo -e "  會話ID: ${SESSION_ID}"
    echo -e "  目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+ 年化收益, <${PERFORMANCE_TARGET_MAX_LOSS}% 年化損失"
    echo -e "  完成輪數: ${ITERATIONS}"
    echo -e "  優化日誌: ${OPTIMIZATION_LOG}"
    echo -e "  報告目錄: ${REPORT_DIR}"

else
    # 傳統單次優化模式
    LOG_FILE="logs/hyperopt_three_target_$(date +%Y%m%d_%H%M%S).log"

    echo -e "${BLUE}🚀 開始三目標投票系統優化...${NC}"
    echo -e "${BLUE}📄 日誌文件: ${LOG_FILE}${NC}"

    # 執行Hyperopt優化
    freqtrade hyperopt \
        --config "${CONFIG}" \
        --strategy "${STRATEGY}" \
        --freqaimodel HybridEnsembleClassifier \
        --timerange "${TIMERANGE}" \
        --epochs ${EPOCHS} \
        --spaces buy \
        -j ${JOBS} \
        --hyperopt-loss SharpeHyperOptLoss \
        --random-state 42 \
        --min-trades 10 \
        --logfile "${LOG_FILE}" \
        -v

    HYPEROPT_EXIT_CODE=$?

    echo ""
    echo -e "${BLUE}📊 優化結果分析...${NC}"

    if [ $HYPEROPT_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ 優化成功完成！${NC}"
        echo ""
        echo -e "${GREEN}🎉 三目標投票系統優化成功完成！${NC}"
        echo -e "${BLUE}核心改進:${NC}"
        echo -e "  📊 三個核心預測目標: momentum + trend + volatility"
        echo -e "  🎯 三重驗證投票機制: 嚴格信號品質控制"
        echo -e "  💰 Kelly公式動態倉位管理: 基於信號品質調整"
        echo -e "  📈 目標性能: 年化收益>100%, 最大回撤<8%, 勝率>60%"
        echo ""
        echo -e "${YELLOW}📁 結果文件位置:${NC}"
        echo -e "  優化結果: user_data/hyperopt_results/"
        echo -e "  日誌文件: ${LOG_FILE}"

    else
        echo -e "${RED}❌ 優化失敗 (退出代碼: $HYPEROPT_EXIT_CODE)${NC}"
        echo -e "${YELLOW}請檢查日誌文件: ${LOG_FILE}${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}🔥 FreqAI Phase 6 三目標投票系統優化完成！🔥${NC}"
