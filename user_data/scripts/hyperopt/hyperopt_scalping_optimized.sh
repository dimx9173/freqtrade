#!/bin/bash

# =====================================================
# ScalpingStrategy 智能迭代優化系統
# Target: 100%+ Annual Returns with <10% Annual Loss
# Based on hyperopt_voting.sh menu system
# =====================================================

# 策略專用配置
STRATEGY="ScalpingStrategy"
CONFIG="user_data/config/config_ScalpingStrategy.json"
TIMERANGE="20250501-20250801"      # 最新3個月數據
DEFAULT_EPOCHS=150                 # 預設迭代次數
DEFAULT_JOBS=8                     # 預設並行數
DEFAULT_ITERATIONS=3               # 預設優化迭代次數

# 性能目標
PERFORMANCE_TARGET_ANNUAL_RETURN=100.0  # 100%+ 年化收益目標
PERFORMANCE_TARGET_MAX_LOSS=10.0         # <10% 年化損失目標
ENABLE_TARGET_STOPPING=true             # 達成目標時自動停止 (預設啟用)

# 系統變量
SESSION_ID=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="user_data/reports"
LOG_DIR="user_data/logs"
SESSION_LOG_DIR="${LOG_DIR}/${SESSION_ID}"
SESSION_REPORT_DIR="${REPORT_DIR}/${SESSION_ID}"
OPTIMIZATION_LOG="${SESSION_LOG_DIR}/scalping_optimization.log"
BACKUP_DIR="${SESSION_REPORT_DIR}/backups"

# 最佳策略管理
BEST_STRATEGY_DIR="user_data/best_strategy"
BEST_STRATEGY_FILE="${BEST_STRATEGY_DIR}/${STRATEGY}.py"
BEST_STRATEGY_PARAMS="${BEST_STRATEGY_DIR}/${STRATEGY}.json"
BEST_STRATEGY_CONFIG="${BEST_STRATEGY_DIR}/config.json"
BEST_STRATEGY_ANALYSIS="${BEST_STRATEGY_DIR}/analysis.md"
BEST_STRATEGY_PERFORMANCE="${BEST_STRATEGY_DIR}/performance_metrics.json"

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
EPOCHS=$DEFAULT_EPOCHS
JOBS=$DEFAULT_JOBS
ITERATIONS=$DEFAULT_ITERATIONS
CUSTOM_TIMERANGE=""
CLAUDE_ANALYSIS_ENABLED=true
CLAUDE_CLI_PATH="/Users/carlos/.claude/local/claude --print --dangerously-skip-permissions"

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
        --jobs=*)
        JOBS="${arg#*=}"
        shift
        ;;
        --timerange=*)
        CUSTOM_TIMERANGE="${arg#*=}"
        shift
        ;;
        --target-return=*)
        PERFORMANCE_TARGET_ANNUAL_RETURN="${arg#*=}"
        shift
        ;;
        --max-loss=*)
        PERFORMANCE_TARGET_MAX_LOSS="${arg#*=}"
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
        --help)
        echo "使用方法: $0 [選項]"
        echo "  --menu              啟動交互式選單"
        echo "  --intelligent       智能迭代優化模式"
        echo "  --iterations=N      設定迭代次數 (預設: 3)"
        echo "  --epochs=N          設定hyperopt輪數 (預設: 100)"
        echo "  --jobs=N            設定並行任務數 (預設: 8)"
        echo "  --timerange=RANGE   自定義時間範圍 (預設: 20250501-20250801)"
        echo "  --target-return=N   設定年化收益目標% (預設: 100)"
        echo "  --max-loss=N        設定最大年化損失% (預設: 10)"
        echo "  --claude-path=PATH  設定Claude CLI路徑 (預設: /usr/local/bin/claude)"
        echo "  --no-claude         禁用Claude分析"
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

# 如果設定了自定義時間範圍，使用它
if [ -n "$CUSTOM_TIMERANGE" ]; then
    TIMERANGE="$CUSTOM_TIMERANGE"
fi

# 創建必要目錄
create_directories() {
    echo -e "${BLUE}🗂️  創建 Session ${SESSION_ID} 目錄結構...${NC}"
    mkdir -p "${REPORT_DIR}"
    mkdir -p "${LOG_DIR}"
    mkdir -p "${SESSION_LOG_DIR}"
    mkdir -p "${SESSION_REPORT_DIR}"
    mkdir -p "${BACKUP_DIR}"
    mkdir -p "${SESSION_REPORT_DIR}/analysis"
    mkdir -p "${SESSION_REPORT_DIR}/performance"
    mkdir -p "${SESSION_REPORT_DIR}/backtesting"
    mkdir -p "${SESSION_REPORT_DIR}/hyperopt"
    mkdir -p "${SESSION_REPORT_DIR}/claude"
    mkdir -p "${BEST_STRATEGY_DIR}"

    echo -e "${GREEN}✅ Session 目錄已建立:${NC}"
    echo -e "   日誌目錄: ${SESSION_LOG_DIR}"
    echo -e "   報告目錄: ${SESSION_REPORT_DIR}"
    echo -e "   最佳策略目錄: ${BEST_STRATEGY_DIR}"

    # 檢查是否存在最佳策略
    if [ -f "$BEST_STRATEGY_PERFORMANCE" ]; then
        local best_performance=$(cat "$BEST_STRATEGY_PERFORMANCE" 2>/dev/null || echo "{}")
        local best_return=$(echo "$best_performance" | grep -o '"total_profit_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        local best_drawdown=$(echo "$best_performance" | grep -o '"max_drawdown_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        echo -e "${CYAN}📊 當前最佳策略性能: 收益=${best_return:-N/A}%, 回撤=${best_drawdown:-N/A}%${NC}"
    else
        echo -e "${YELLOW}📊 尚未建立最佳策略基準${NC}"
    fi
}

# 系統預檢查
system_pre_check() {
    echo -e "${CYAN}🔍 系統預檢查...${NC}"
    echo "=========================="

    # 檢查策略文件
    if [ ! -f "user_data/strategies/$STRATEGY.py" ]; then
        echo -e "${RED}❌ 策略文件不存在: user_data/strategies/$STRATEGY.py${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ 策略文件: user_data/strategies/$STRATEGY.py${NC}"

    # 檢查配置文件
    if [ ! -f "$CONFIG" ]; then
        echo -e "${RED}❌ 配置文件不存在: $CONFIG${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ 配置文件: $CONFIG${NC}"

    # 檢查freqtrade
    if ! command -v freqtrade &> /dev/null; then
        echo -e "${RED}❌ Freqtrade 未安裝或不在 PATH 中${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Freqtrade: $(freqtrade --version | head -1)${NC}"

    echo ""
}

# 顯示主選單
show_main_menu() {
    while true; do
        clear
        echo "=========================================================================="
        echo -e "${CYAN}🎯 ScalpingStrategy 智能優化系統${NC}"
        echo -e "${CYAN}目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%+ 年化收益, <${PERFORMANCE_TARGET_MAX_LOSS}% 年化損失${NC}"
        echo "=========================================================================="
        echo ""
        echo -e "${BLUE}📊 當前狀態:${NC}"
        echo -e "   策略: ${STRATEGY}"
        echo -e "   時間範圍: ${TIMERANGE}"
        echo -e "   Hyperopt輪數: ${EPOCHS}"
        echo -e "   並行任務: ${JOBS}"
        echo -e "   迭代次數: ${ITERATIONS}"
        echo ""
        echo -e "${YELLOW}請選擇優化模式:${NC}"
        echo ""
        echo -e "   ${GREEN}1)${NC} 快速單次優化 - 純Hyperopt，無Claude分析 [⚡ 15-30分鐘]"
        echo -e "   ${GREEN}2)${NC} 深度單次優化 - 更精確的參數搜索 [⚡ 45-60分鐘]"
        echo -e "   ${GREEN}3)${NC} 智能迭代優化 - 多輪自動優化 [🧠 1-2小時]"
        echo -e "   ${GREEN}4)${NC} 超級深度優化 - 頂級量化策略+報告 [🤖 2-3小時]"
        echo -e "   ${GREEN}5)${NC} 緊急修復模式 - 針對當前策略問題 [🔧 30-45分鐘]"
        echo -e "   ${GREEN}6)${NC} 自定義配置 - 手動設置所有參數"
        echo -e "   ${CYAN}7)${NC} 性能分析 - 分析現有策略表現 [📊 即時]"
        echo -e "   ${PURPLE}8)${NC} 參數回測 - 使用現有參數進行回測 [⚡ 快速]"
        echo -e "   ${YELLOW}9)${NC} 最佳策略管理 - 查看/恢復最佳策略 [🏆 管理]"
        echo -e "   ${BLUE}a)${NC} 策略比較報告 - 生成詳細的策略性能比較 [📊 分析]"
        echo -e "   ${RED}q)${NC} 退出"
        echo ""
        echo -n "請輸入選擇: "

        read choice
        case $choice in
            1)
                echo -e "${GREEN}🚀 啟動快速單次優化...${NC}"
                EPOCHS=50
                ITERATIONS=1
                run_fast_optimization
                ;;
            2)
                echo -e "${GREEN}🚀 啟動深度單次優化...${NC}"
                EPOCHS=150
                ITERATIONS=1
                run_optimization_sequence
                ;;
            3)
                echo -e "${GREEN}🚀 啟動智能迭代優化...${NC}"
                EPOCHS=100
                ITERATIONS=3
                INTELLIGENT_MODE=true
                run_optimization_sequence
                ;;
            4)
                echo -e "${GREEN}🚀 啟動超級深度優化...${NC}"
                EPOCHS=200
                ITERATIONS=5
                INTELLIGENT_MODE=true
                run_optimization_sequence
                ;;
            5)
                echo -e "${GREEN}🚀 啟動緊急修復模式...${NC}"
                run_emergency_fix_mode
                ;;
            6)
                show_custom_config_menu
                ;;
            7)
                analyze_current_performance
                ;;
            8)
                run_backtest_with_current_params
                ;;
            9)
                show_best_strategy_management
                ;;
            a|A)
                generate_strategy_comparison_report
                ;;
            q|Q)
                echo -e "${YELLOW}👋 感謝使用 ScalpingStrategy 優化系統！${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ 無效選擇，請重新選擇${NC}"
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
        echo -e "${CYAN}⚙️ ScalpingStrategy 自定義配置選單${NC}"
        echo "=========================================================================="
        echo ""
        echo -e "${BLUE}📊 當前配置:${NC}"
        echo -e "   Hyperopt輪數: ${EPOCHS}"
        echo -e "   迭代次數: ${ITERATIONS}"
        echo -e "   並行任務: ${JOBS}"
        echo -e "   時間範圍: ${TIMERANGE}"
        echo -e "   年化收益目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%"
        echo -e "   最大年化損失: ${PERFORMANCE_TARGET_MAX_LOSS}%"
        echo -e "   目標導向停止: $( [ "$ENABLE_TARGET_STOPPING" = true ] && echo "啟用" || echo "停用" )"
        echo ""
        echo -e "${YELLOW}配置選項:${NC}"
        echo ""
        echo -e "   ${GREEN}e)${NC} 設置 Epochs (當前: ${EPOCHS})"
        echo -e "   ${GREEN}i)${NC} 設置迭代次數 (當前: ${ITERATIONS})"
        echo -e "   ${GREEN}j)${NC} 設置並行任務數 (當前: ${JOBS})"
        echo -e "   ${GREEN}t)${NC} 設置時間範圍 (當前: ${TIMERANGE})"
        echo -e "   ${GREEN}r)${NC} 設置收益目標 (當前: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%)"
        echo -e "   ${GREEN}l)${NC} 設置損失限制 (當前: ${PERFORMANCE_TARGET_MAX_LOSS}%)"
        echo -e "   ${GREEN}a)${NC} 切換目標導向停止 (當前: $( [ "$ENABLE_TARGET_STOPPING" = true ] && echo "啟用" || echo "停用" ))"
        echo -e "   ${CYAN}p)${NC} 預覽完整配置"
        echo -e "   ${GREEN}s)${NC} 開始優化"
        echo -e "   ${YELLOW}b)${NC} 返回主選單"
        echo ""
        echo -n "請輸入選擇: "

        read choice
        case $choice in
            e|E)
                echo -n "輸入新的 Epochs 數量 (建議: 50-500): "
                read new_epochs
                if [[ "$new_epochs" =~ ^[0-9]+$ ]] && [ "$new_epochs" -gt 0 ] && [ "$new_epochs" -le 1000 ]; then
                    EPOCHS="$new_epochs"
                    echo -e "${GREEN}✅ Epochs 已設置為: ${EPOCHS}${NC}"
                else
                    echo -e "${RED}❌ 無效數值，請輸入1-1000之間的整數${NC}"
                fi
                sleep 2
                ;;
            i|I)
                echo -n "輸入迭代次數 (建議: 1-100): "
                read new_iterations
                if [[ "$new_iterations" =~ ^[0-9]+$ ]] && [ "$new_iterations" -gt 0 ] && [ "$new_iterations" -le 100 ]; then
                    ITERATIONS="$new_iterations"
                    if [ "$ITERATIONS" -gt 1 ]; then
                        INTELLIGENT_MODE=true
                    fi
                    echo -e "${GREEN}✅ 迭代次數已設置為: ${ITERATIONS}${NC}"
                else
                    echo -e "${RED}❌ 無效數值，請輸入1-10之間的整數${NC}"
                fi
                sleep 2
                ;;
            j|J)
                echo -n "輸入並行任務數 (建議: 1-16): "
                read new_jobs
                if [[ "$new_jobs" =~ ^[0-9]+$ ]] && [ "$new_jobs" -gt 0 ] && [ "$new_jobs" -le 32 ]; then
                    JOBS="$new_jobs"
                    echo -e "${GREEN}✅ 並行任務數已設置為: ${JOBS}${NC}"
                else
                    echo -e "${RED}❌ 無效數值，請輸入1-32之間的整數${NC}"
                fi
                sleep 2
                ;;
            t|T)
                echo "時間範圍格式: YYYYMMDD-YYYYMMDD"
                echo "例如: 20250101-20250801"
                echo -n "輸入新的時間範圍: "
                read new_timerange
                if [[ "$new_timerange" =~ ^[0-9]{8}-[0-9]{8}$ ]]; then
                    TIMERANGE="$new_timerange"
                    echo -e "${GREEN}✅ 時間範圍已設置為: ${TIMERANGE}${NC}"
                else
                    echo -e "${RED}❌ 無效格式，請使用 YYYYMMDD-YYYYMMDD 格式${NC}"
                fi
                sleep 2
                ;;
            r|R)
                echo -n "輸入年化收益目標% (建議: 50-200): "
                read new_return
                if [[ "$new_return" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$new_return > 0" | bc -l) )); then
                    PERFORMANCE_TARGET_ANNUAL_RETURN="$new_return"
                    echo -e "${GREEN}✅ 年化收益目標已設置為: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%${NC}"
                else
                    echo -e "${RED}❌ 無效數值，請輸入正數${NC}"
                fi
                sleep 2
                ;;
            l|L)
                echo -n "輸入最大年化損失% (建議: 5-20): "
                read new_loss
                if [[ "$new_loss" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$new_loss > 0" | bc -l) )); then
                    PERFORMANCE_TARGET_MAX_LOSS="$new_loss"
                    echo -e "${GREEN}✅ 最大年化損失已設置為: ${PERFORMANCE_TARGET_MAX_LOSS}%${NC}"
                else
                    echo -e "${RED}❌ 無效數值，請輸入正數${NC}"
                fi
                sleep 2
                ;;
            a|A)
                if [ "$ENABLE_TARGET_STOPPING" = true ]; then
                    ENABLE_TARGET_STOPPING=false
                    echo -e "${YELLOW}✅ 目標導向停止已停用${NC}"
                    echo -e "${BLUE}💡 迭代次數將完整執行，不會提前停止${NC}"
                else
                    ENABLE_TARGET_STOPPING=true
                    echo -e "${GREEN}✅ 目標導向停止已啟用${NC}"
                    echo -e "${BLUE}💡 達成年化收益≥${PERFORMANCE_TARGET_ANNUAL_RETURN}%且損失≤${PERFORMANCE_TARGET_MAX_LOSS}%時將提前停止${NC}"
                fi
                sleep 3
                ;;
            p|P)
                echo ""
                echo -e "${CYAN}📋 完整配置預覽:${NC}"
                echo "=================================="
                echo -e "策略: ${STRATEGY}"
                echo -e "配置文件: ${CONFIG}"
                echo -e "時間範圍: ${TIMERANGE}"
                echo -e "Hyperopt輪數: ${EPOCHS}"
                echo -e "迭代次數: ${ITERATIONS}"
                echo -e "並行任務: ${JOBS}"
                echo -e "年化收益目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%"
                echo -e "最大年化損失: ${PERFORMANCE_TARGET_MAX_LOSS}%"
                echo -e "目標導向停止: $( [ "$ENABLE_TARGET_STOPPING" = true ] && echo "啟用" || echo "停用" )"
                echo -e "智能模式: $( [ "$INTELLIGENT_MODE" = true ] && echo "啟用" || echo "停用" )"
                echo ""
                echo "按任意鍵返回..."
                read
                ;;
            s|S)
                echo ""
                echo -e "${GREEN}🚀 開始使用自定義配置進行優化...${NC}"
                echo -e "${BLUE}最終配置確認:${NC}"
                echo -e "  - Hyperopt輪數: ${EPOCHS}"
                echo -e "  - 迭代次數: ${ITERATIONS}"
                echo -e "  - 並行任務: ${JOBS}"
                echo -e "  - 時間範圍: ${TIMERANGE}"
                echo -e "  - 收益目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%"
                echo -e "  - 損失限制: ${PERFORMANCE_TARGET_MAX_LOSS}%"
                echo ""
                echo "確認開始優化？(y/N): "
                read confirm
                if [[ "$confirm" =~ ^[Yy]$ ]]; then
                    run_optimization_sequence
                    return
                else
                    echo -e "${YELLOW}已取消優化${NC}"
                    sleep 1
                fi
                ;;
            b|B)
                return
                ;;
            *)
                echo -e "${RED}❌ 無效選擇，請重新選擇${NC}"
                sleep 1
                ;;
        esac
    done
}

# 創建系統備份
create_backup() {
    echo -e "${BLUE}🛡️  創建策略備份...${NC}"

    # 備份策略文件
    if [ -f "user_data/strategies/$STRATEGY.py" ]; then
        cp "user_data/strategies/$STRATEGY.py" "${BACKUP_DIR}/${STRATEGY}.py.backup"
        echo -e "${GREEN}✅ 策略文件已備份${NC}"
    fi

    # 備份參數文件（如果存在）
    if [ -f "user_data/strategies/$STRATEGY.json" ]; then
        cp "user_data/strategies/$STRATEGY.json" "${BACKUP_DIR}/${STRATEGY}.json.backup"
        echo -e "${GREEN}✅ 參數文件已備份${NC}"
    fi

    # 備份配置文件
    if [ -f "$CONFIG" ]; then
        cp "$CONFIG" "${BACKUP_DIR}/config.json.backup"
        echo -e "${GREEN}✅ 配置文件已備份${NC}"
    fi
    # 清除上次的hyperopt_results
    rm -rf user_data/backtest_results/*
    rm -rf user_data/hyperopt_results/*
}

# Claude CLI 分析功能
run_claude_analysis() {
    local iteration=$1
    local analysis_type=$2

    if [ "$CLAUDE_ANALYSIS_ENABLED" != true ]; then
        echo -e "${YELLOW}⚠️  Claude 分析已禁用，跳過分析步驟${NC}"
        return 0
    fi
    # 準備Claude命令（第二次以後使用continue模式）
    local claude_full_cmd="$CLAUDE_CLI_PATH"
    if [ "$iteration" -gt 1 ]; then
        # 第二次以後使用continue模式（-c 與 --continue 相同，移除重複）
        claude_full_cmd="/Users/carlos/.claude/local/claude --print -c --dangerously-skip-permissions"
    fi

    # 檢查Claude CLI是否可用
    local claude_cmd="/Users/carlos/.claude/local/claude"
    if [ ! -f "$claude_cmd" ] || [ ! -x "$claude_cmd" ]; then
        echo -e "${YELLOW}⚠️  Claude CLI 不可用 ($claude_cmd)，跳過分析步驟${NC}"
        return 0
    fi

    # 檢查是否為優化前分析階段，如果是則跳過（需要先執行hyperopt）
    if [[ "$analysis_type" == "pre_optimization" || "$analysis_type" == "pre_single_optimization" || "$analysis_type" == "emergency_diagnosis" ]]; then
        echo -e "${YELLOW}⚠️  跳過優化前的Claude分析，優化將直接開始${NC}"
        return 0
    fi

    echo -e "${PURPLE}🤖 執行 Claude AI 策略直接優化 - ${analysis_type}${NC}"
    echo "=================================================================="

    local analysis_file="${SESSION_REPORT_DIR}/analysis/claude_optimization_${analysis_type}_iter${iteration}.md"

    # 獲取當前回測結果
    local backtest_output="${SESSION_REPORT_DIR}/backtesting/backtest_${iteration}.txt"
    echo -e "${BLUE}📊 運行當前狀態回測...${NC}"

    freqtrade backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --enable-protections \
        --cache day > "$backtest_output" 2>&1

    # 創建 Claude 提示文件來避免 "Prompt is too long" 錯誤
    local claude_prompt_file="${SESSION_REPORT_DIR}/claude/claude_prompt_${analysis_type}_${iteration}.txt"

    # 找到上一次的 hyperopt 和 backtest 日誌文件
    local prev_hyperopt_log=$(find user_data/hyperopt_results -name "*.log" -type f -exec ls -t {} + | head -1 2>/dev/null)

    cat > "$claude_prompt_file" << PROMPT_EOF
freqtrade-scalping-architect: 優化策略 ${STRATEGY} (迭代${iteration})

任務：直接修改 user_data/strategies/${STRATEGY}.py 與 user_data/config/${CONFIG}.json 優化剝頭皮交易性能，不要另建新策略
目標：${PERFORMANCE_TARGET_ANNUAL_RETURN}%+ 年化收益，≤${PERFORMANCE_TARGET_MAX_LOSS}% 回撤

前次結果分析參考：
$(if [ -n "$prev_hyperopt_log" ] && [ -f "$prev_hyperopt_log" ]; then echo "- 上次Hyperopt日誌：$prev_hyperopt_log"; fi)
- 當前回測結果：$backtest_output

關鍵文件：
- 當前策略：user_data/strategies/${STRATEGY}.py
- 當前配置：user_data/config/${CONFIG}.json
- 配置文件：${CONFIG}
- 最佳策略文件：${BEST_STRATEGY_FILE}
- 最佳策略參數：${BEST_STRATEGY_PARAMS}
- 最佳策略分析：${BEST_STRATEGY_ANALYSIS}
- 最佳策略性能：${BEST_STRATEGY_PERFORMANCE}
- 主要優化日誌：${OPTIMIZATION_LOG}
- Session日誌目錄：${SESSION_LOG_DIR}/
- 分析報告目錄：${SESSION_REPORT_DIR}/analysis/

優化步驟：
1. 讀取最佳策略相關文件學習成功要素
2. 檢視歷史優化記錄了解經驗教訓
3. 分析當前回測結果識別問題
4. 基於學習直接修改策略文件：ROI表、止損、指標參數、hyperopt範圍
5. 專注剝頭皮特性：短持倉、但不要過於頻繁交易、快速止盈止損、利用勝率與盈虧比提升收益
6. 考慮簡化：如果發現策略在實盤中表現不佳，可以嘗試逐步簡化它。移除一些相關性高或表現不佳的指標，看看是否能提高其魯棒性。
7. 保存修改並提供優化摘要

要求：
- 實際修改文件，非僅建議
- 優先學習最佳策略和歷史經驗
- 避免重複失敗的修改方向
- 延續成功的優化思路
- 語法正確性檢查
- 讓hyperopt優化更多指標參數
- 可優化/替換社區指標：基於剝頭皮策略特性選用快速反應指標
- 剝頭皮導向：偏好短週期、高靈敏度、快速信號的技術指標
- 指標最多5個, 且盡可能不要同性質指標

開始分析優化。
PROMPT_EOF

    echo -e "${BLUE}🧠 發送分析請求到 Claude AI (使用管道避免長度限制)...${NC}"

    # 執行 Claude 直接優化 - 使用管道傳遞提示內容避免命令行長度限制
    echo -e "${BLUE}📝 執行命令: cat prompt_file | $claude_full_cmd${NC}"
    cat "$claude_prompt_file" | bash -c "$claude_full_cmd" > "$analysis_file" 2>"${analysis_file}.error"
    local exit_code=$?
    if [ $exit_code -eq 0 ] && [ -s "$analysis_file" ]; then
        echo -e "${GREEN}✅ Claude 策略優化完成${NC}"
        echo -e "${BLUE}📝 優化記錄已保存: ${analysis_file}${NC}"

        # 顯示優化摘要
        echo ""
        echo -e "${CYAN}🎯 Claude AI 策略優化摘要:${NC}"
        echo "=================================================="
        tail -20 "$analysis_file" | head -10
        echo "=================================================="
        echo ""

        # Claude策略優化完成
        echo -e "${GREEN}🎯 Claude策略優化完成，將繼續後續優化流程${NC}"

        # 目標導向停止模式直接繼續
        if [ "$ENABLE_TARGET_STOPPING" = true ]; then
            echo -e "${GREEN}🎯 目標導向優化已啟用，自動繼續流程${NC}"
        elif [ "$MENU_MODE" = true ]; then
            echo -e "${YELLOW}是否繼續後續 Hyperopt 優化？(Y/n): ${NC}"
            read continue_hyperopt
            if [[ "$continue_hyperopt" =~ ^[Nn]$ ]]; then
                echo -e "${YELLOW}已暫停優化流程${NC}"
                return 1
            fi
        fi
    else
        echo -e "${RED}❌ Claude 策略優化失敗${NC}"
        echo -e "${YELLOW}命令退出碼: $exit_code${NC}"
        if [ -f "${analysis_file}.error" ] && [ -s "${analysis_file}.error" ]; then
            echo -e "${YELLOW}錯誤詳情:${NC}"
            cat "${analysis_file}.error" | head -10
        fi
        if [ -f "$analysis_file" ] && [ -s "$analysis_file" ]; then
            echo -e "${YELLOW}輸出內容:${NC}"
            head -5 "$analysis_file"
        fi
        echo -e "${YELLOW}將繼續進行 Hyperopt 優化${NC}"
        rm -f "${analysis_file}.error"
    fi

    # 清理臨時文件
    rm -f "$backtest_output"
    return 0
}

# 執行單次優化 - 整合 hyperopt + backtesting
run_single_optimization() {
    local phase_name=$1
    local loss_function=$2
    local spaces=$3
    local current_epochs=$4
    local backtest_months=${5:-3}  # 預設 3 個月回測

    echo -e "${CYAN}🚀 執行 ${phase_name} (Hyperopt + Backtesting)...${NC}"
    echo "========================================"

    local hyperopt_log_file="${SESSION_LOG_DIR}/hyperopt_${phase_name}.log"
    local backtest_log="${SESSION_LOG_DIR}/backtest_${phase_name}.log"
    local summary_log="${SESSION_LOG_DIR}/summary_${phase_name}.log"

    # === Phase 1: Hyperopt ===
    echo -e "${BLUE}Phase 1: 執行 Hyperopt 優化...${NC}" | tee -a "$summary_log"

    # 構建完整的freqtrade命令
    local hyperopt_cmd="freqtrade hyperopt --config \"$CONFIG\" --hyperopt-loss \"$loss_function\" --spaces $spaces -e \"$current_epochs\" -j \"$JOBS\" --timerange \"$TIMERANGE\" --strategy \"$STRATEGY\" --enable-protections --print-json"

    echo "執行命令: $hyperopt_cmd" | tee -a "$hyperopt_log_file"
    echo "Hyperopt 開始時間: $(date)" | tee -a "$hyperopt_log_file"
    echo "========================================" | tee -a "$hyperopt_log_file"

    # 執行命令並同時輸出到螢幕和日誌文件
    local temp_exit_file="${SESSION_REPORT_DIR}/hyperopt/hyperopt_exit_${SESSION_ID}_${RANDOM}"

    # 執行命令，將退出碼寫入臨時文件
    (eval "$hyperopt_cmd" 2>&1; echo $? > "$temp_exit_file") | tee -a "$hyperopt_log_file"

    # 讀取退出碼
    local exit_code=$(cat "$temp_exit_file" 2>/dev/null || echo "1")
    rm -f "$temp_exit_file"

    echo "========================================" | tee -a "$hyperopt_log_file"
    echo "Hyperopt 結束時間: $(date)" | tee -a "$hyperopt_log_file"
    echo "Hyperopt 退出碼: $exit_code" | tee -a "$hyperopt_log_file"

    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}❌ ${phase_name} Hyperopt 失敗 (退出碼: $exit_code)${NC}"
        return $exit_code
    fi

    echo -e "${GREEN}✅ ${phase_name} Hyperopt 完成${NC}" | tee -a "$summary_log"

    # === Phase 2: 提取最佳參數 ===
    echo -e "${BLUE}Phase 2: 提取最佳參數...${NC}" | tee -a "$summary_log"

    # 提取最佳參數
    local best_result_file="${SESSION_REPORT_DIR}/hyperopt/best_result_${SESSION_ID}_${phase_name}.txt"
    freqtrade hyperopt-list --best --no-header --config "$CONFIG" --strategy "$STRATEGY" 2>/dev/null > "$best_result_file"

    if [[ -s "$best_result_file" ]]; then
        local best_result=$(head -1 "$best_result_file")
        echo "最佳 hyperopt 結果: $best_result" | tee -a "$summary_log"
        local epoch_num=$(echo "$best_result" | awk '{print $1}')
        echo "最佳 epoch: $epoch_num" | tee -a "$summary_log"

        # 提取並應用最佳參數
        if extract_and_apply_params; then
            echo -e "${GREEN}✅ 最佳參數已提取並應用${NC}" | tee -a "$summary_log"
        else
            echo -e "${YELLOW}⚠️ 參數提取失敗，將使用 hyperopt 優化後的參數進行回測${NC}" | tee -a "$summary_log"
        fi
    else
        echo -e "${YELLOW}⚠️ 無法提取最佳參數，將使用當前參數進行回測${NC}" | tee -a "$summary_log"
    fi

    rm -f "$best_result_file"

    # === Phase 3: 回測驗證 ===
    echo -e "${BLUE}Phase 3: 執行回測驗證...${NC}" | tee -a "$summary_log"

    # 計算回測時間範圍
    local backtest_timerange
    if command -v bash >/dev/null 2>&1; then
        backtest_timerange=$(bash get_time_range.sh $backtest_months 2>/dev/null || echo "$TIMERANGE")
    else
        backtest_timerange="$TIMERANGE"
    fi

    echo "回測時間範圍: $backtest_timerange" | tee -a "$backtest_log"
    echo "回測開始時間: $(date)" | tee -a "$backtest_log"

    # 構建回測命令
    local backtest_cmd="freqtrade backtesting --strategy \"$STRATEGY\" --config \"$CONFIG\" --timerange \"$backtest_timerange\" --enable-protections --cache day"

    echo "執行回測命令: $backtest_cmd" | tee -a "$backtest_log"
    echo "========================================" | tee -a "$backtest_log"

    # 執行回測並保存結果
    local backtest_result_file="${SESSION_REPORT_DIR}/backtesting/backtest_result_${SESSION_ID}_${phase_name}.txt"
    eval "$backtest_cmd" 2>&1 | tee -a "$backtest_log" > "$backtest_result_file"
    local backtest_exit_code=$?

    echo "========================================" | tee -a "$backtest_log"
    echo "回測結束時間: $(date)" | tee -a "$backtest_log"
    echo "回測退出碼: $backtest_exit_code" | tee -a "$backtest_log"

    if [ $backtest_exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ ${phase_name} 回測完成${NC}" | tee -a "$summary_log"

        # === Phase 4: 結果分析和摘要 ===
        echo -e "${CYAN}📊 ${phase_name} 性能摘要:${NC}"
        echo "=================================================="

        # 提取關鍵指標
        local profit_line=$(grep -E "Total profit.*%" "$backtest_result_file" | tail -1 || echo "Total profit: N/A")
        local trades_line=$(grep -E "Total trades" "$backtest_result_file" | tail -1 || echo "Total trades: N/A")
        local win_rate_line=$(grep -E "Win %" "$backtest_result_file" | tail -1 || echo "Win %: N/A")
        local sharpe_line=$(grep -E "Sharpe" "$backtest_result_file" | tail -1 || echo "Sharpe: N/A")
        local drawdown_line=$(grep -E "Max Drawdown.*%" "$backtest_result_file" | tail -1 || echo "Max Drawdown: N/A")

        # 顯示結果
        echo "$profit_line"
        echo "$trades_line"
        echo "$win_rate_line"
        echo "$sharpe_line"
        echo "$drawdown_line"
        echo "=================================================="

        # 保存到摘要日誌
        echo "=== ${phase_name} 最終結果摘要 ===" >> "$summary_log"
        echo "Hyperopt 輪數: $current_epochs" >> "$summary_log"
        echo "回測時間範圍: $backtest_timerange" >> "$summary_log"
        echo "$profit_line" >> "$summary_log"
        echo "$trades_line" >> "$summary_log"
        echo "$win_rate_line" >> "$summary_log"
        echo "$sharpe_line" >> "$summary_log"
        echo "$drawdown_line" >> "$summary_log"
        echo "完成時間: $(date)" >> "$summary_log"
        echo "========================================" >> "$summary_log"

        # 清理臨時文件
        rm -f "$backtest_result_file"

        return 0
    else
        echo -e "${RED}❌ ${phase_name} 回測失敗 (退出碼: $backtest_exit_code)${NC}" | tee -a "$summary_log"
        rm -f "$backtest_result_file"
        return $backtest_exit_code
    fi
}

# 提取和應用最佳參數
extract_and_apply_params() {
    echo -e "${BLUE}🔧 提取和應用最佳參數...${NC}"

    local temp_params="${SESSION_REPORT_DIR}/hyperopt/best_params_${STRATEGY}_${SESSION_ID}.json"
    local strategy_params="user_data/strategies/${STRATEGY}.json"

    # 提取最佳參數
    freqtrade hyperopt-show --config "$CONFIG" --best --print-json > "$temp_params"
    local extract_exit_code=$?

    if [ $extract_exit_code -eq 0 ] && [ -s "$temp_params" ]; then
        # 備份現有參數
        if [ -f "$strategy_params" ]; then
            cp "$strategy_params" "${strategy_params}.backup.$(date +%Y%m%d_%H%M%S)"
        fi

        # 應用新參數
        cp "$temp_params" "$strategy_params"
        echo -e "${GREEN}✅ 最佳參數已應用到: ${strategy_params}${NC}"

        # 清理臨時文件
        rm -f "$temp_params"
        return 0
    else
        echo -e "${RED}❌ 參數提取失敗${NC}"
        rm -f "$temp_params"
        return 1
    fi
}

# Hyperopt 後驗證和最佳策略比較
validate_hyperopt_and_compare_best() {
    local phase_name=$1

    echo -e "${BLUE}📊 步驟: 提取和應用 hyperopt 最佳參數...${NC}"

    # 提取和應用最佳參數
    if ! extract_and_apply_params; then
        echo -e "${RED}❌ 參數提取失敗，跳過驗證${NC}"
        return 1
    fi

    echo -e "${BLUE}📊 步驟: 運行 backtesting 驗證 hyperopt 結果...${NC}"

    # 運行回測驗證 hyperopt 結果
    local validation_backtest_file="${SESSION_REPORT_DIR}/backtesting/hyperopt_validation_${SESSION_ID}_${phase_name}.txt"
    echo "開始驗證回測: $(date)" | tee -a "${SESSION_LOG_DIR}/hyperopt_validation_${phase_name}.log"

    freqtrade backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --enable-protections \
        --cache day 2>&1 | tee -a "${SESSION_LOG_DIR}/hyperopt_validation_${phase_name}.log" > "$validation_backtest_file"

    local backtest_exit_code=$?
    echo "結束驗證回測: $(date), 退出碼: $backtest_exit_code" | tee -a "${SESSION_LOG_DIR}/hyperopt_validation_${phase_name}.log"

    if [ $backtest_exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ 驗證回測完成${NC}"

        # 解析回測結果
        local validation_performance=$(parse_backtest_performance "$validation_backtest_file")
        local validation_performance_file=$(save_current_performance "$validation_backtest_file" "$validation_performance")

        echo -e "${PURPLE}🏆 步驟: 比較與最佳策略性能...${NC}"

        # 檢查是否需要更新最佳策略
        if [ -f "$BEST_STRATEGY_PERFORMANCE" ]; then
            if compare_with_best_strategy "$validation_performance_file"; then
                echo -e "${GREEN}🎉 當前 hyperopt 結果優於最佳策略，正在更新...${NC}"
                update_best_strategy "$validation_performance_file" "hyperopt_${phase_name}"
            else
                local current_profit=$(echo "$validation_performance" | cut -d'|' -f1)
                local current_drawdown=$(echo "$validation_performance" | cut -d'|' -f2)
                local best_performance=$(cat "$BEST_STRATEGY_PERFORMANCE" 2>/dev/null || echo "{}")
                local best_profit=$(echo "$best_performance" | grep -o '"total_profit_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
                local best_drawdown=$(echo "$best_performance" | grep -o '"max_drawdown_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
                echo -e "${YELLOW}📊 當前 hyperopt 結果未優於最佳策略${NC}"
                echo -e "${BLUE}當前: 收益=${current_profit:-0}%, 回撤=${current_drawdown:-0}%${NC}"
                echo -e "${BLUE}最佳: 收益=${best_profit:-0}%, 回撤=${best_drawdown:-0}%${NC}"
            fi
        else
            echo -e "${GREEN}🎉 首次建立最佳策略基準（來自 hyperopt 驗證）${NC}"
            update_best_strategy "$validation_performance_file" "hyperopt_${phase_name}"
        fi

        # 清理臨時文件
        rm -f "$validation_backtest_file"
        return 0
    else
        echo -e "${RED}❌ 驗證回測失敗 (退出碼: $backtest_exit_code)${NC}"
        rm -f "$validation_backtest_file"
        return 1
    fi
}

# 運行最終回測
run_final_backtest() {
    echo -e "${BLUE}📈 運行最終回測驗證...${NC}"

    freqtrade backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --enable-protections \
        --cache day \
        --breakdown month

    local backtest_exit_code=$?

    if [ $backtest_exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ 最終回測完成${NC}"
        return 0
    else
        echo -e "${RED}❌ 最終回測失敗 (退出碼: $backtest_exit_code)${NC}"
        return $backtest_exit_code
    fi
}

# 增強版回測 - 帶詳細報告和交易導出
run_enhanced_backtest() {
    local phase_name=$1
    local export_trades=${2:-false}

    echo -e "${BLUE}📈 運行增強回測: ${phase_name}...${NC}"

    local backtest_log="${SESSION_LOG_DIR}/backtest_${phase_name}.log"
    local backtest_result_file="${SESSION_REPORT_DIR}/backtesting/backtest_${phase_name}_${SESSION_ID}.txt"

    # 構建回測命令
    local backtest_cmd="freqtrade backtesting --strategy \"$STRATEGY\" --config \"$CONFIG\" --timerange \"$TIMERANGE\" --enable-protections --cache day --breakdown month"

    # 如果需要導出交易記錄
    if [ "$export_trades" = true ]; then
        local trades_file="${SESSION_REPORT_DIR}/performance/trades_${phase_name}.json"
        backtest_cmd="$backtest_cmd --export trades --export-filename \"$trades_file\""
        echo -e "${BLUE}📊 將導出交易記錄到: ${trades_file}${NC}"
    fi

    echo "執行回測命令: $backtest_cmd" | tee -a "$backtest_log"
    echo "開始時間: $(date)" | tee -a "$backtest_log"
    echo "========================================" | tee -a "$backtest_log"

    # 執行回測並同時保存到多個文件
    eval "$backtest_cmd" 2>&1 | tee -a "$backtest_log" > "$backtest_result_file"
    local backtest_exit_code=$?

    echo "========================================" | tee -a "$backtest_log"
    echo "結束時間: $(date)" | tee -a "$backtest_log"
    echo "退出碼: $backtest_exit_code" | tee -a "$backtest_log"

    if [ $backtest_exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ 增強回測完成: ${phase_name}${NC}"

        # 提取並顯示關鍵指標
        echo -e "${CYAN}📊 ${phase_name} 性能摘要:${NC}"
        echo "=================================================="

        # 提取關鍵指標
        local profit_line=$(grep -E "Total Profit.*%" "$backtest_result_file" | tail -1 || echo "Total Profit: N/A")
        local trades_line=$(grep -E "Total Trades" "$backtest_result_file" | tail -1 || echo "Total Trades: N/A")
        local win_rate_line=$(grep -E "Win.*%" "$backtest_result_file" | tail -1 || echo "Win Rate: N/A")
        local sharpe_line=$(grep -E "Sharpe" "$backtest_result_file" | tail -1 || echo "Sharpe: N/A")
        local drawdown_line=$(grep -E "Max Drawdown.*%" "$backtest_result_file" | tail -1 || echo "Max Drawdown: N/A")

        echo "$profit_line"
        echo "$trades_line"
        echo "$win_rate_line"
        echo "$sharpe_line"
        echo "$drawdown_line"
        echo "=================================================="

        # 保存結果摘要到日誌
        echo "=== ${phase_name} 結果摘要 ===" >> "$backtest_log"
        echo "$profit_line" >> "$backtest_log"
        echo "$trades_line" >> "$backtest_log"
        echo "$win_rate_line" >> "$backtest_log"
        echo "$sharpe_line" >> "$backtest_log"
        echo "$drawdown_line" >> "$backtest_log"

        # 清理臨時文件
        rm -f "$backtest_result_file"
        return 0
    else
        echo -e "${RED}❌ 增強回測失敗: ${phase_name} (退出碼: $backtest_exit_code)${NC}"
        rm -f "$backtest_result_file"
        return $backtest_exit_code
    fi
}

# 保存當前策略性能到JSON
save_current_performance() {
    local backtest_result_file=$1
    local performance_data=$2
    local session_performance_file="${SESSION_REPORT_DIR}/performance/current_performance.json"

    local total_profit_pct=$(echo "$performance_data" | cut -d'|' -f1)
    local max_drawdown_pct=$(echo "$performance_data" | cut -d'|' -f2)
    local trades_count=$(echo "$performance_data" | cut -d'|' -f3)
    local win_rate=$(echo "$performance_data" | cut -d'|' -f4)

    cat > "$session_performance_file" << EOF
{
    "session_id": "${SESSION_ID}",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "strategy": "${STRATEGY}",
    "timerange": "${TIMERANGE}",
    "total_profit_pct": ${total_profit_pct:-0},
    "max_drawdown_pct": ${max_drawdown_pct:-0},
    "trades_count": ${trades_count:-0},
    "win_rate": ${win_rate:-0},
    "performance_target_return": ${PERFORMANCE_TARGET_ANNUAL_RETURN},
    "performance_target_max_loss": ${PERFORMANCE_TARGET_MAX_LOSS}
}
EOF

    echo "$session_performance_file"
}

# 比較當前策略與最佳策略性能
compare_with_best_strategy() {
    local current_performance_file=$1

    if [ ! -f "$current_performance_file" ] || [ ! -f "$BEST_STRATEGY_PERFORMANCE" ]; then
        return 1  # 無法比較
    fi

    # 讀取當前性能
    local current_profit=$(grep -o '"total_profit_pct":[^,}]*' "$current_performance_file" | cut -d':' -f2 | tr -d ' ')
    local current_drawdown=$(grep -o '"max_drawdown_pct":[^,}]*' "$current_performance_file" | cut -d':' -f2 | tr -d ' ')

    # 讀取最佳性能
    local best_profit=$(grep -o '"total_profit_pct":[^,}]*' "$BEST_STRATEGY_PERFORMANCE" | cut -d':' -f2 | tr -d ' ')
    local best_drawdown=$(grep -o '"max_drawdown_pct":[^,}]*' "$BEST_STRATEGY_PERFORMANCE" | cut -d':' -f2 | tr -d ' ')

    # 比較邏輯：收益率更高且回撤更低，或收益率顯著更高
    local profit_better=$(echo "${current_profit:-0} > ${best_profit:-0}" | bc -l 2>/dev/null || echo "0")
    local drawdown_better=$(echo "${current_drawdown:-0} < ${best_drawdown:-0}" | bc -l 2>/dev/null || echo "0")
    local profit_significantly_better=$(echo "${current_profit:-0} > ${best_profit:-0} + 5" | bc -l 2>/dev/null || echo "0")

    if [ "$profit_better" -eq 1 ] && [ "$drawdown_better" -eq 1 ]; then
        return 0  # 當前更好（收益更高且回撤更低）
    elif [ "$profit_significantly_better" -eq 1 ]; then
        return 0  # 當前更好（收益顯著更高）
    else
        return 1  # 最佳策略仍然更好
    fi
}

# 更新最佳策略
update_best_strategy() {
    local current_performance_file=$1
    local source_type=${2:-"backtesting"}  # 預設為 backtesting，也可以是 hyperopt_*

    echo -e "${PURPLE}🏆 更新最佳策略 (來源: ${source_type})...${NC}"

    # 備份當前最佳策略（如果存在）
    if [ -f "$BEST_STRATEGY_FILE" ]; then
        local backup_timestamp=$(date +%Y%m%d_%H%M%S)
        cp "$BEST_STRATEGY_FILE" "${BEST_STRATEGY_DIR}/previous_best_${backup_timestamp}.py" 2>/dev/null
        cp "$BEST_STRATEGY_PERFORMANCE" "${BEST_STRATEGY_DIR}/previous_performance_${backup_timestamp}.json" 2>/dev/null

        # 在性能檔案中記錄備份資訊
        echo -e "${BLUE}ℹ️ 已備份前一次最佳策略到: previous_best_${backup_timestamp}.py${NC}"
    fi

    # 複製當前策略為最佳策略
    cp "user_data/strategies/${STRATEGY}.py" "$BEST_STRATEGY_FILE"

    # 複製策略參數（如果存在）
    if [ -f "user_data/strategies/${STRATEGY}.json" ]; then
        cp "user_data/strategies/${STRATEGY}.json" "$BEST_STRATEGY_PARAMS"
    fi

    # 複製配置文件
    cp "$CONFIG" "$BEST_STRATEGY_CONFIG"

    # 更新性能數據，加入來源資訊
    local temp_performance="${SESSION_REPORT_DIR}/hyperopt/best_strategy_performance_${SESSION_ID}.json"
    local current_performance=$(cat "$current_performance_file" 2>/dev/null || echo "{}")

    # 加入來源和更新資訊
    echo "$current_performance" | jq --arg source "$source_type" --arg session "$SESSION_ID" \
        '. + {"source": $source, "updated_session_id": $session, "updated_timestamp": (now | strftime("%Y-%m-%dT%H:%M:%SZ"))}' \
        2>/dev/null > "$temp_performance" || {
        # fallback 如果 jq 不可用
        local current_profit=$(echo "$current_performance" | grep -o '"total_profit_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        local current_drawdown=$(echo "$current_performance" | grep -o '"max_drawdown_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        local current_trades=$(echo "$current_performance" | grep -o '"trades_count":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        local current_win_rate=$(echo "$current_performance" | grep -o '"win_rate":[^,}]*' | cut -d':' -f2 | tr -d ' "')

        cat > "$temp_performance" << EOF
{
    "session_id": "${SESSION_ID}",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "strategy": "${STRATEGY}",
    "timerange": "${TIMERANGE}",
    "total_profit_pct": ${current_profit:-0},
    "max_drawdown_pct": ${current_drawdown:-0},
    "trades_count": ${current_trades:-0},
    "win_rate": ${current_win_rate:-0},
    "source": "$source_type",
    "updated_session_id": "${SESSION_ID}",
    "updated_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    }

    cp "$temp_performance" "$BEST_STRATEGY_PERFORMANCE"
    rm -f "$temp_performance"

    # 生成最佳策略分析報告
    local current_profit=$(grep -o '"total_profit_pct":[^,}]*' "$BEST_STRATEGY_PERFORMANCE" | cut -d':' -f2 | tr -d ' "')
    local current_drawdown=$(grep -o '"max_drawdown_pct":[^,}]*' "$BEST_STRATEGY_PERFORMANCE" | cut -d':' -f2 | tr -d ' "')
    local current_trades=$(grep -o '"trades_count":[^,}]*' "$BEST_STRATEGY_PERFORMANCE" | cut -d':' -f2 | tr -d ' "')
    local current_win_rate=$(grep -o '"win_rate":[^,}]*' "$BEST_STRATEGY_PERFORMANCE" | cut -d':' -f2 | tr -d ' "')

    cat > "$BEST_STRATEGY_ANALYSIS" << EOF
# 最佳策略分析報告

## 基本資訊
- **更新時間**: $(date)
- **Session ID**: ${SESSION_ID}
- **策略名稱**: ${STRATEGY}
- **時間範圍**: ${TIMERANGE}
- **更新來源**: ${source_type}

## 性能指標
- **總收益率**: ${current_profit:-0}%
- **最大回撤**: ${current_drawdown:-0}%
- **交易次數**: ${current_trades:-0}
- **勝率**: ${current_win_rate:-0}%

## 優化目標達成情況
- **收益目標**: ${PERFORMANCE_TARGET_ANNUAL_RETURN}% (當前: ${current_profit:-0}%)
- **回撤限制**: ${PERFORMANCE_TARGET_MAX_LOSS}% (當前: ${current_drawdown:-0}%)

## 更新原因
此策略因性能優於前一個最佳策略而被選為新的最佳基準。

## 性能來源
- **測試類型**: ${source_type}
- **測試說明**: $(
if [[ "$source_type" == hyperopt_* ]]; then
    echo "此性能來自 hyperopt 優化過程中的最佳參數組合，經過回測驗證"
else
    echo "此性能來自完整的回測測試結果"
fi)

## 策略文件
- **策略文件**: ${BEST_STRATEGY_FILE}
- **參數文件**: ${BEST_STRATEGY_PARAMS}
- **配置文件**: ${BEST_STRATEGY_CONFIG}

## 使用指南
1. **恢復最佳策略**: 使用脚本選單中的最佳策略管理功能
2. **參考優化**: Claude 會自動參考此最佳策略進行優化建議
3. **性能基準**: 新的優化結果會與此基準比較

---
*此報告由 ScalpingStrategy 優化系統自動生成*
EOF

    echo -e "${GREEN}✅ 最佳策略已更新！${NC}"
    echo -e "${GREEN}📊 新的最佳性能: 收益=${current_profit:-0}%, 回撤=${current_drawdown:-0}%${NC}"
    return 0
}

# 解析回測結果並檢查是否達到性能目標
parse_backtest_performance() {
    local backtest_output_file=$1

    if [ ! -f "$backtest_output_file" ]; then
        echo "0|0|0|0"  # total_profit_pct|max_drawdown_pct|trades_count|win_rate
        return 1
    fi

    # 從回測結果中提取關鍵指標
    local total_profit_pct=$(grep -E "Total Profit.*%" "$backtest_output_file" | tail -1 | grep -o -E '[+-]?[0-9]+\.?[0-9]*%' | head -1 | sed 's/%//')
    local max_drawdown_pct=$(grep -E "Max Drawdown.*%" "$backtest_output_file" | tail -1 | grep -o -E '[+-]?[0-9]+\.?[0-9]*%' | head -1 | sed 's/%//')
    local trades_count=$(grep -E "Total Trades" "$backtest_output_file" | tail -1 | grep -o -E '[0-9]+' | head -1)
    local win_rate=$(grep -E "Win.*%" "$backtest_output_file" | tail -1 | grep -o -E '[0-9]+\.?[0-9]*%' | head -1 | sed 's/%//')

    # 處理空值
    total_profit_pct=${total_profit_pct:-0}
    max_drawdown_pct=${max_drawdown_pct:-0}
    trades_count=${trades_count:-0}
    win_rate=${win_rate:-0}

    echo "${total_profit_pct}|${max_drawdown_pct}|${trades_count}|${win_rate}"
}

# 檢查是否達到性能目標
check_performance_targets() {
    local performance_data=$1
    local total_profit_pct=$(echo "$performance_data" | cut -d'|' -f1)
    local max_drawdown_pct=$(echo "$performance_data" | cut -d'|' -f2)

    # 將百分比轉換為數字進行比較
    local profit_target=$(echo "$PERFORMANCE_TARGET_ANNUAL_RETURN" | sed 's/%//')
    local loss_limit=$(echo "$PERFORMANCE_TARGET_MAX_LOSS" | sed 's/%//')

    # 檢查是否達到目標（使用bc進行浮點數比較）
    local profit_achieved=$(echo "$total_profit_pct >= $profit_target" | bc -l 2>/dev/null || echo "0")
    local drawdown_acceptable=$(echo "${max_drawdown_pct#-} <= $loss_limit" | bc -l 2>/dev/null || echo "1")

    if [ "$profit_achieved" -eq 1 ] && [ "$drawdown_acceptable" -eq 1 ]; then
        return 0  # 達到目標
    else
        return 1  # 未達到目標
    fi
}

# 分析回測結果
analyze_backtest_results() {
    echo -e "${CYAN}📊 分析回測結果...${NC}"

    # 這裡可以添加結果分析邏輯
    # 例如：檢查是否達到目標收益率和風險控制
    echo -e "${BLUE}性能目標檢查:${NC}"
    echo -e "  目標年化收益: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%"
    echo -e "  最大允許損失: ${PERFORMANCE_TARGET_MAX_LOSS}%"
    echo ""
    echo -e "${YELLOW}💡 建議查看上述回測報告，確認是否達到性能目標${NC}"
}

# [舊的遞歸優化函數已移除，統一使用ITERATIONS參數與目標導向停止機制]

# 解析並應用Claude建議到策略參數

# 快速單次優化（無Claude分析）
run_fast_optimization() {
    echo -e "${CYAN}⚡ 快速單次優化 - 純Hyperopt模式${NC}"
    echo "=================================================================="

    # 初始化
    create_directories
    create_backup

    # 記錄開始時間
    local start_time=$(date)
    echo "開始時間: $start_time" | tee -a "$OPTIMIZATION_LOG"

    echo -e "${BLUE}🎯 快速優化模式 - 跳過Claude分析${NC}"

    # 階段1: ROI優化
    run_single_optimization "快速ROI優化" "SharpeHyperOptLoss" "buy sell roi" "$EPOCHS"

    # 階段2: 風險管理
    run_single_optimization "快速風險管理" "CalmarHyperOptLoss" "buy sell stoploss" "$EPOCHS"

    # 階段3: 綜合優化
    run_single_optimization "快速綜合優化" "SortinoHyperOptLoss" "default" "$EPOCHS"

    # 提取並應用參數
    extract_and_apply_params

    # 最終回測
    run_final_backtest

    # 分析結果
    analyze_backtest_results

    # 記錄結束時間
    local end_time=$(date)
    echo "結束時間: $end_time" | tee -a "$OPTIMIZATION_LOG"

    echo ""
    echo -e "${GREEN}⚡ === 快速優化完成 === ⚡${NC}"
    echo -e "${BLUE}Session ID: ${SESSION_ID}${NC}"
    echo -e "${BLUE}主要日誌: ${OPTIMIZATION_LOG}${NC}"
    echo -e "${BLUE}日誌目錄: ${SESSION_LOG_DIR}${NC}"
    echo -e "${BLUE}報告目錄: ${SESSION_REPORT_DIR}${NC}"
    echo -e "${BLUE}備份目錄: ${BACKUP_DIR}${NC}"

    # 如果是選單模式，等待用戶確認
    if [ "$MENU_MODE" = true ]; then
        echo ""
        echo "按任意鍵返回主選單..."
        read
    fi
}

# 主要優化序列
run_optimization_sequence() {
    echo -e "${CYAN}🚀 開始 ScalpingStrategy 優化序列${NC}"
    echo "=================================================================="

    # 初始化
    create_directories
    create_backup

    # 記錄開始時間
    local start_time=$(date)
    echo "開始時間: $start_time" | tee -a "$OPTIMIZATION_LOG"

    if [ "$INTELLIGENT_MODE" = true ] && [ "$ITERATIONS" -gt 1 ]; then
        echo -e "${PURPLE}🧠 智能迭代模式: $ITERATIONS 次迭代${NC}"
        echo -e "${BLUE}每輪順序: 回測 → Claude優化 → Hyperopt${NC}"

        for ((iter=1; iter<=ITERATIONS; iter++)); do
            echo ""
            echo -e "${CYAN}===== 迭代 $iter/$ITERATIONS =====${NC}"

            # 步驟1: 執行回測評估
            echo -e "${BLUE}📋 步驟1: 執行回測評估...迭代${iter}${NC}"
            run_final_backtest

            # 步驟2: Claude 策略優化 - 基於回測結果
            echo -e "${PURPLE}🤖 步驟2: Claude AI 策略優化 - 基於回測結果${NC}"
            run_claude_analysis "$iter" "strategy_optimization"

            # 步驟3: Hyperopt優化 - 基於Claude優化後的策略
            echo -e "${CYAN}⚡ 步驟3: Hyperopt優化 - 基於Claude優化後的策略${NC}"
            if run_single_optimization "綜合優化_迭代${iter}" "SortinoHyperOptLoss" "default" "$EPOCHS"; then
                validate_hyperopt_and_compare_best "綜合優化_迭代${iter}"
            fi

            # 目標導向停止檢查
            if [ "$ENABLE_TARGET_STOPPING" = true ]; then
                echo -e "${BLUE}🎯 檢查是否達成性能目標...${NC}"

                # 運行回測並保存結果
                local backtest_result_file="${SESSION_REPORT_DIR}/backtesting/backtest_target_check_${SESSION_ID}_${iter}.txt"
                freqtrade backtesting \
                    --strategy "$STRATEGY" \
                    --config "$CONFIG" \
                    --timerange "$TIMERANGE" \
                    --enable-protections \
                    --cache day \
                    --breakdown month > "$backtest_result_file" 2>&1

                # 解析性能數據並檢查目標
                local current_performance=$(parse_backtest_performance "$backtest_result_file")
                if check_performance_targets "$current_performance"; then
                    local current_profit=$(echo "$current_performance" | cut -d'|' -f1)
                    local current_drawdown=$(echo "$current_performance" | cut -d'|' -f2)
                    echo ""
                    echo -e "${GREEN}🎉 === 性能目標達成！提前完成優化 === 🎉${NC}"
                    echo -e "${GREEN}✅ 年化收益: ${current_profit}% (目標: ${PERFORMANCE_TARGET_ANNUAL_RETURN}%)${NC}"
                    echo -e "${GREEN}✅ 最大回撤: ${current_drawdown}% (限制: ${PERFORMANCE_TARGET_MAX_LOSS}%)${NC}"
                    echo -e "${GREEN}✅ 在第 $iter/$ITERATIONS 次迭代達成目標${NC}"
                    echo ""
                    # 清理臨時文件
                    rm -f "$backtest_result_file"

                    # 設置提前完成標記
                    local early_completion=true
                    break
                else
                    local current_profit=$(echo "$current_performance" | cut -d'|' -f1)
                    local current_drawdown=$(echo "$current_performance" | cut -d'|' -f2)
                    echo -e "${YELLOW}⏳ 未達成目標 - 繼續優化${NC}"
                    echo -e "${BLUE}當前結果: 收益=${current_profit}%, 回撤=${current_drawdown}%${NC}"
                    echo -e "${BLUE}目標: 收益≥${PERFORMANCE_TARGET_ANNUAL_RETURN}%, 回撤≤${PERFORMANCE_TARGET_MAX_LOSS}%${NC}"
                    rm -f "$backtest_result_file"
                fi
            fi

            # 如果提前完成，跳過後續分析
            if [ "$early_completion" = true ]; then
                echo -e "${BLUE}🎯 目標已達成，跳過後續分析${NC}"
                break
            fi

            # Claude 分析 - 迭代完成總結
            run_claude_analysis "$iter" "iteration_complete"

            echo -e "${GREEN}✅ 迭代 $iter 完成 (順序: 回測 → Claude優化 → Hyperopt)${NC}"
            sleep 2
        done

        # 多輪迭代完成後的最終回測
        if [ "$early_completion" != true ]; then
            echo ""
            echo -e "${BLUE}📈 執行最終驗證回測...${NC}"
            run_final_backtest
        fi
    else
        echo -e "${BLUE}🎯 單次優化模式 (順序: 回測 → Claude優化 → Hyperopt)${NC}"

        # 步驟1: 執行初始回測評估
        echo -e "${BLUE}📋 步驟1: 執行初始回測評估...${NC}"
        run_final_backtest

        # 步驟2: Claude策略優化 - 基於回測結果
        echo -e "${PURPLE}🤖 步驟2: Claude AI 策略優化 - 基於回測結果${NC}"
        run_claude_analysis "1" "strategy_optimization"

        # 步驟3: Hyperopt優化 - 基於Claude優化後的策略
        echo -e "${CYAN}⚡ 步驟3: Hyperopt優化 - 基於Claude優化後的策略${NC}"
        if run_single_optimization "綜合優化" "SortinoHyperOptLoss" "default" "$EPOCHS"; then
            validate_hyperopt_and_compare_best "綜合優化"
        fi

        # 最終驗證回測
        echo -e "${BLUE}📈 步驟4: 最終驗證回測...${NC}"
        run_final_backtest

        # Claude分析 - 最終總結
        run_claude_analysis "1" "final_analysis"
    fi

    # 如果沒有提早完成，才進行結果分析
    if [ "$early_completion" != true ]; then
        # 分析結果
        analyze_backtest_results
    else
        echo -e "${GREEN}🎊 優化提前完成，已達成性能目標！${NC}"
    fi

    # 最佳策略狀態報告
    echo ""
    echo -e "${PURPLE}🏆 最佳策略狀態...${NC}"

    if [ -f "$BEST_STRATEGY_PERFORMANCE" ]; then
        local best_performance=$(cat "$BEST_STRATEGY_PERFORMANCE" 2>/dev/null || echo "{}")
        local best_profit=$(echo "$best_performance" | grep -o '"total_profit_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        local best_drawdown=$(echo "$best_performance" | grep -o '"max_drawdown_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        local best_source=$(echo "$best_performance" | grep -o '"source":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        echo -e "${GREEN}🎆 當前最佳策略性能:${NC}"
        echo -e "${BLUE}  收益率: ${best_profit:-0}%${NC}"
        echo -e "${BLUE}  回撤率: ${best_drawdown:-0}%${NC}"
        echo -e "${BLUE}  來源: ${best_source:-未知}${NC}"
        echo -e "${YELLOW}📝 每次 hyperopt 完成後都已自動檢查和更新最佳策略${NC}"
    else
        echo -e "${YELLOW}⚠️ 尚未建立最佳策略基準${NC}"
    fi

    # 記錄結束時間
    local end_time=$(date)
    echo "結束時間: $end_time" | tee -a "$OPTIMIZATION_LOG"

    echo ""
    echo -e "${GREEN}🎉 === 優化完成 === 🎉${NC}"
    echo -e "${BLUE}Session ID: ${SESSION_ID}${NC}"
    echo -e "${BLUE}主要日誌: ${OPTIMIZATION_LOG}${NC}"
    echo -e "${BLUE}日誌目錄: ${SESSION_LOG_DIR}${NC}"
    echo -e "${BLUE}報告目錄: ${SESSION_REPORT_DIR}${NC}"
    echo -e "${BLUE}備份目錄: ${BACKUP_DIR}${NC}"

    # 如果是選單模式，等待用戶確認
    if [ "$MENU_MODE" = true ]; then
        echo ""
        echo "按任意鍵返回主選單..."
        read
    fi
}

# 緊急修復模式 - 基於近期策略問題
run_emergency_fix_mode() {
    echo -e "${RED}🚨 緊急修復模式${NC}"
    echo "針對當前策略的已知問題進行優化"
    echo ""
    echo -e "${YELLOW}已知問題:${NC}"
    echo "1. Exit signals 造成損失"
    echo "2. Stoploss 設置過寬"
    echo "3. Entry signals 過於寬鬆"
    echo ""
    echo "確認執行緊急修復？(y/N): "
    read confirm

    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}🔧 執行緊急修復優化...${NC}"

        # 初始化目錄和備份
        create_directories
        create_backup

        # 使用緊急修復專用參數
        EPOCHS=75
        ITERATIONS=2
        INTELLIGENT_MODE=true

        # Claude 分析 - 緊急修復前診斷
        if ! run_claude_analysis "emergency" "emergency_diagnosis"; then
            echo -e "${YELLOW}⚠️  用戶選擇跳過緊急修復${NC}"
            return
        fi

        # 專注於修復已知問題的空間
        if run_single_optimization "緊急修復_Entry" "SharpeHyperOptLoss" "buy" "50"; then
            validate_hyperopt_and_compare_best "緊急修復_Entry"
        fi

        # Claude 分析 - Entry 修復後
        run_claude_analysis "emergency" "post_entry_fix"

        if run_single_optimization "緊急修復_Exit" "CalmarHyperOptLoss" "sell" "50"; then
            validate_hyperopt_and_compare_best "緊急修復_Exit"
        fi

        # Claude 分析 - Exit 修復後
        run_claude_analysis "emergency" "post_exit_fix"

        if run_single_optimization "緊急修復_Risk" "SortinoHyperOptLoss" "stoploss roi" "75"; then
            validate_hyperopt_and_compare_best "緊急修復_Risk"
        fi

        # Claude 分析 - Risk 修復後
        run_claude_analysis "emergency" "post_risk_fix"

        extract_and_apply_params
        run_final_backtest

        # Claude 分析 - 緊急修復完成總結
        run_claude_analysis "emergency" "emergency_fix_complete"

        analyze_backtest_results

        echo -e "${GREEN}✅ 緊急修復完成${NC}"
    else
        echo -e "${YELLOW}已取消緊急修復${NC}"
    fi

    if [ "$MENU_MODE" = true ]; then
        echo "按任意鍵返回主選單..."
        read
    fi
}

# 分析當前性能
analyze_current_performance() {
    echo -e "${CYAN}📊 分析當前策略性能...${NC}"

    # 初始化目錄
    create_directories

    echo "運行當前參數回測..."
    run_final_backtest

    # Claude 分析 - 性能分析
    run_claude_analysis "analysis" "performance_analysis"

    echo ""
    echo -e "${BLUE}性能分析完成${NC}"
    echo -e "${YELLOW}💡 請查看上述回測結果，評估當前策略表現${NC}"

    if [ "$MENU_MODE" = true ]; then
        echo "按任意鍵返回主選單..."
        read
    fi
}

# 使用現有參數回測
run_backtest_with_current_params() {
    echo -e "${CYAN}⚡ 使用現有參數運行回測...${NC}"

    if [ -f "user_data/strategies/${STRATEGY}.json" ]; then
        echo -e "${BLUE}找到參數文件: user_data/strategies/${STRATEGY}.json${NC}"
        run_final_backtest
    else
        echo -e "${YELLOW}⚠️  未找到參數文件，使用預設參數回測${NC}"
        run_final_backtest
    fi

    if [ "$MENU_MODE" = true ]; then
        echo "按任意鍵返回主選單..."
        read
    fi
}

# 生成策略比較報告
generate_strategy_comparison_report() {
    echo -e "${CYAN}📊 生成策略性能比較報告...${NC}"
    echo "=================================================================="

    # 初始化目錄
    create_directories

    local analysis_dir="${SESSION_REPORT_DIR}/strategy_comparison"
    mkdir -p "$analysis_dir"

    local comparison_report="${analysis_dir}/strategy_comparison_$(date +%Y%m%d_%H%M%S).md"
    local csv_report="${analysis_dir}/strategy_data_$(date +%Y%m%d_%H%M%S).csv"
    local summary_report="${analysis_dir}/performance_summary.txt"

    echo -e "${BLUE}🔍 搜索可用的策略結果數據...${NC}"

    # 創建報告標題
    cat > "$comparison_report" << EOF
# ScalpingStrategy 性能比較報告

生成時間: $(date)
Session ID: ${SESSION_ID}

## 概要
本報告分析了所有可用的 hyperopt + backtesting 結果，提供全面的策略性能比較。

EOF

    # CSV 標題
    echo "Phase,Strategy,Hyperopt_Epochs,Total_Profit_%,Max_Drawdown_%,Total_Trades,Win_Rate_%,Sharpe_Ratio,Date" > "$csv_report"

    # 搜索所有摘要日誌
    local summary_files=($(find "${LOG_DIR}" -name "summary_*.log" 2>/dev/null | sort))
    local backtest_files=($(find "${LOG_DIR}" -name "backtest_*.log" 2>/dev/null | sort))

    if [[ ${#summary_files[@]} -eq 0 ]]; then
        echo -e "${YELLOW}⚠️ 未找到策略優化結果，請先執行策略優化${NC}"
        echo "沒有找到優化結果數據" > "$summary_report"

        if [ "$MENU_MODE" = true ]; then
            echo "按任意鍵返回主選單..."
            read
        fi
        return
    fi

    echo -e "${GREEN}✅ 找到 ${#summary_files[@]} 個策略結果文件${NC}"

    echo "## 詳細分析" >> "$comparison_report"
    echo "" >> "$comparison_report"

    # 創建控制台輸出表格
    echo -e "${CYAN}📋 策略性能對比表:${NC}"
    printf "%-25s %-8s %-12s %-12s %-8s %-8s %-10s\n" "階段" "輪數" "總收益%" "最大回撤%" "交易數" "勝率%" "夏普比"
    printf "%-25s %-8s %-12s %-12s %-8s %-8s %-10s\n" "-----" "----" "------" "--------" "------" "----" "------"

    local best_profit=""
    local best_profit_phase=""
    local best_sharpe=""
    local best_sharpe_phase=""
    local lowest_drawdown=""
    local lowest_drawdown_phase=""

    # 分析每個摘要文件
    for summary_file in "${summary_files[@]}"; do
        if [[ -f "$summary_file" && -s "$summary_file" ]]; then
            local phase_name=$(basename "$summary_file" .log | sed 's/summary_//')
            local file_date=$(stat -f "%Sm" -t "%Y-%m-%d" "$summary_file" 2>/dev/null || date +%Y-%m-%d)

            echo "### $phase_name" >> "$comparison_report"
            echo "文件: $summary_file" >> "$comparison_report"
            echo "日期: $file_date" >> "$comparison_report"
            echo "" >> "$comparison_report"

            # 提取關鍵指標
            local epochs=$(grep "Hyperopt 輪數:" "$summary_file" | tail -1 | grep -o '[0-9]\+' || echo "N/A")
            local profit=$(grep "Total profit.*%" "$summary_file" | tail -1 | grep -o '[+-]*[0-9]\+\.*[0-9]*%' | head -1 | sed 's/%//' || echo "0")
            local drawdown=$(grep "Max Drawdown.*%" "$summary_file" | tail -1 | grep -o '[+-]*[0-9]\+\.*[0-9]*%' | head -1 | sed 's/%//' || echo "0")
            local trades=$(grep "Total trades" "$summary_file" | tail -1 | grep -o '[0-9]\+' || echo "0")
            local win_rate=$(grep "Win %" "$summary_file" | tail -1 | grep -o '[0-9]\+\.*[0-9]*%' | head -1 | sed 's/%//' || echo "0")
            local sharpe=$(grep "Sharpe" "$summary_file" | tail -1 | grep -o '[+-]*[0-9]\+\.*[0-9]*' || echo "0")

            # 清理數據
            profit=${profit:-0}
            drawdown=${drawdown:-0}
            trades=${trades:-0}
            win_rate=${win_rate:-0}
            sharpe=${sharpe:-0}
            epochs=${epochs:-N/A}

            # 輸出到控制台表格
            printf "%-25s %-8s %-12s %-12s %-8s %-8s %-10s\n" \
                "$(echo "$phase_name" | cut -c1-23)" \
                "$epochs" \
                "$profit" \
                "$drawdown" \
                "$trades" \
                "$win_rate" \
                "$sharpe"

            # 添加到 CSV
            echo "$phase_name,$STRATEGY,$epochs,$profit,$drawdown,$trades,$win_rate,$sharpe,$file_date" >> "$csv_report"

            # 添加到 Markdown 報告
            echo "- **輪數**: $epochs" >> "$comparison_report"
            echo "- **總收益**: $profit%" >> "$comparison_report"
            echo "- **最大回撤**: $drawdown%" >> "$comparison_report"
            echo "- **交易數量**: $trades" >> "$comparison_report"
            echo "- **勝率**: $win_rate%" >> "$comparison_report"
            echo "- **夏普比率**: $sharpe" >> "$comparison_report"
            echo "" >> "$comparison_report"

            # 記錄最佳表現
            if [[ -n "$profit" && "$profit" != "0" && "$profit" != "N/A" ]]; then
                if [[ -z "$best_profit" ]] || (( $(echo "$profit > $best_profit" | bc -l 2>/dev/null || echo "0") )); then
                    best_profit="$profit"
                    best_profit_phase="$phase_name"
                fi
            fi

            if [[ -n "$sharpe" && "$sharpe" != "0" && "$sharpe" != "N/A" ]]; then
                if [[ -z "$best_sharpe" ]] || (( $(echo "$sharpe > $best_sharpe" | bc -l 2>/dev/null || echo "0") )); then
                    best_sharpe="$sharpe"
                    best_sharpe_phase="$phase_name"
                fi
            fi

            if [[ -n "$drawdown" && "$drawdown" != "0" && "$drawdown" != "N/A" ]]; then
                local abs_drawdown=$(echo "$drawdown" | sed 's/-//')
                if [[ -z "$lowest_drawdown" ]] || (( $(echo "$abs_drawdown < $lowest_drawdown" | bc -l 2>/dev/null || echo "0") )); then
                    lowest_drawdown="$abs_drawdown"
                    lowest_drawdown_phase="$phase_name"
                fi
            fi
        fi
    done

    echo ""

    # 生成總結
    echo -e "${GREEN}🏆 性能總結:${NC}"
    if [[ -n "$best_profit_phase" ]]; then
        echo -e "   最高收益: ${best_profit}% ($best_profit_phase)"
    fi
    if [[ -n "$best_sharpe_phase" ]]; then
        echo -e "   最佳風險調整收益: 夏普比 ${best_sharpe} ($best_sharpe_phase)"
    fi
    if [[ -n "$lowest_drawdown_phase" ]]; then
        echo -e "   最低回撤: ${lowest_drawdown}% ($lowest_drawdown_phase)"
    fi

    # 添加到報告
    echo "## 總結" >> "$comparison_report"
    echo "" >> "$comparison_report"
    echo "### 性能指標冠軍" >> "$comparison_report"
    if [[ -n "$best_profit_phase" ]]; then
        echo "- **最高收益**: ${best_profit}% (${best_profit_phase})" >> "$comparison_report"
    fi
    if [[ -n "$best_sharpe_phase" ]]; then
        echo "- **最佳風險調整收益**: 夏普比 ${best_sharpe} (${best_sharpe_phase})" >> "$comparison_report"
    fi
    if [[ -n "$lowest_drawdown_phase" ]]; then
        echo "- **最低風險**: ${lowest_drawdown}% 回撤 (${lowest_drawdown_phase})" >> "$comparison_report"
    fi
    echo "" >> "$comparison_report"

    echo "### 建議" >> "$comparison_report"
    echo "1. 重點關注收益和風險平衡最佳的策略配置" >> "$comparison_report"
    echo "2. 考慮將最佳配置參數應用到新的優化中" >> "$comparison_report"
    echo "3. 定期重新評估策略在新市場條件下的表現" >> "$comparison_report"
    echo "" >> "$comparison_report"

    echo "---" >> "$comparison_report"
    echo "*報告由 ScalpingStrategy 優化系統自動生成*" >> "$comparison_report"

    # 創建簡要總結文件
    cat > "$summary_report" << EOF
ScalpingStrategy 性能總結
========================

最佳收益策略: ${best_profit_phase:-未知} (${best_profit:-0}%)
最佳風險調整: ${best_sharpe_phase:-未知} (夏普比: ${best_sharpe:-0})
最低回撤策略: ${lowest_drawdown_phase:-未知} (${lowest_drawdown:-0}%)

總分析的策略階段數: ${#summary_files[@]}
報告生成時間: $(date)

詳細報告: $comparison_report
CSV 數據: $csv_report
EOF

    echo ""
    echo -e "${GREEN}📄 報告生成完成！${NC}"
    echo "=================================================="
    echo -e "${BLUE}詳細報告: $comparison_report${NC}"
    echo -e "${BLUE}CSV 數據文件: $csv_report${NC}"
    echo -e "${BLUE}總結文件: $summary_report${NC}"
    echo -e "${BLUE}分析目錄: $analysis_dir${NC}"
    echo "=================================================="

    if [ "$MENU_MODE" = true ]; then
        echo ""
        echo "按任意鍵返回主選單..."
        read
    fi
}

# 主執行邏輯
main() {
    clear
    echo -e "${CYAN}🎯 ScalpingStrategy 智能優化系統啟動${NC}"
    echo "=========================================================================="

    # 系統檢查
    system_pre_check

    # 根據模式執行
    if [ "$MENU_MODE" = true ]; then
        show_main_menu
    elif [ "$INTELLIGENT_MODE" = true ]; then
        echo -e "${PURPLE}🧠 智能模式啟動${NC}"
        run_optimization_sequence
    else
        echo -e "${BLUE}🎯 標準模式啟動${NC}"
        run_optimization_sequence
    fi
}

# 最佳策略管理
show_best_strategy_management() {
    while true; do
        clear
        echo "=========================================================================="
        echo -e "${CYAN}🏆 ScalpingStrategy 最佳策略管理系統${NC}"
        echo "=========================================================================="
        echo ""

        if [ -f "$BEST_STRATEGY_PERFORMANCE" ]; then
            echo -e "${BLUE}📊 當前最佳策略資訊:${NC}"
            echo ""

            # 讀取性能數據
            local best_performance=$(cat "$BEST_STRATEGY_PERFORMANCE" 2>/dev/null || echo "{}")
            local best_profit=$(echo "$best_performance" | grep -o '"total_profit_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
            local best_drawdown=$(echo "$best_performance" | grep -o '"max_drawdown_pct":[^,}]*' | cut -d':' -f2 | tr -d ' "')
            local best_trades=$(echo "$best_performance" | grep -o '"trades_count":[^,}]*' | cut -d':' -f2 | tr -d ' "')
            local best_win_rate=$(echo "$best_performance" | grep -o '"win_rate":[^,}]*' | cut -d':' -f2 | tr -d ' "')
            local best_timestamp=$(echo "$best_performance" | grep -o '"timestamp":[^,}]*' | cut -d':' -f2- | tr -d ' "')

            echo -e "   總收益率: ${GREEN}${best_profit:-0}%${NC}"
            echo -e "   最大回撤: ${RED}${best_drawdown:-0}%${NC}"
            echo -e "   交易次數: ${best_trades:-0}"
            echo -e "   勝率: ${best_win_rate:-0}%"
            echo -e "   更新時間: ${best_timestamp:-未知}"
            echo ""

            echo -e "${YELLOW}管理選項:${NC}"
            echo ""
            echo -e "   ${GREEN}1)${NC} 查看最佳策略詳細分析"
            echo -e "   ${GREEN}2)${NC} 恢復最佳策略到當前工作目錄"
            echo -e "   ${GREEN}3)${NC} 比較當前策略與最佳策略"
            echo -e "   ${CYAN}4)${NC} 備份當前策略為最佳策略"
            echo -e "   ${RED}5)${NC} 刪除最佳策略記錄"
        else
            echo -e "${YELLOW}⚠️  尚未建立最佳策略基準${NC}"
            echo ""
            echo -e "${YELLOW}管理選項:${NC}"
            echo ""
            echo -e "   ${CYAN}4)${NC} 備份當前策略為最佳策略"
        fi

        echo -e "   ${YELLOW}b)${NC} 返回主選單"
        echo ""
        echo -n "請輸入選擇: "

        read choice
        case $choice in
            1)
                if [ -f "$BEST_STRATEGY_ANALYSIS" ]; then
                    echo ""
                    echo -e "${CYAN}📄 最佳策略分析報告:${NC}"
                    echo "=================================================="
                    cat "$BEST_STRATEGY_ANALYSIS"
                    echo ""
                    echo "按任意鍵繼續..."
                    read
                else
                    echo -e "${RED}❌ 分析報告不存在${NC}"
                    sleep 2
                fi
                ;;
            2)
                if [ -f "$BEST_STRATEGY_FILE" ]; then
                    echo ""
                    echo -e "${GREEN}🔄 恢復最佳策略到當前工作目錄...${NC}"

                    # 備份當前策略
                    local restore_timestamp=$(date +%Y%m%d_%H%M%S)
                    cp "user_data/strategies/${STRATEGY}.py" "user_data/strategies/${STRATEGY}.py.backup.${restore_timestamp}" 2>/dev/null

                    # 恢復最佳策略
                    cp "$BEST_STRATEGY_FILE" "user_data/strategies/${STRATEGY}.py"

                    # 恢復參數（如果存在）
                    if [ -f "$BEST_STRATEGY_PARAMS" ]; then
                        cp "$BEST_STRATEGY_PARAMS" "user_data/strategies/${STRATEGY}.json"
                    fi

                    echo -e "${GREEN}✅ 最佳策略已恢復到工作目錄${NC}"
                    echo -e "${BLUE}備份文件: user_data/strategies/${STRATEGY}.py.backup.${restore_timestamp}${NC}"
                    sleep 3
                else
                    echo -e "${RED}❌ 最佳策略文件不存在${NC}"
                    sleep 2
                fi
                ;;
            3)
                echo ""
                echo -e "${CYAN}📊 比較當前策略與最佳策略...${NC}"

                # 運行當前策略回測
                local comparison_file="${SESSION_REPORT_DIR}/backtesting/current_vs_best_${SESSION_ID}.txt"
                freqtrade backtesting \
                    --strategy "$STRATEGY" \
                    --config "$CONFIG" \
                    --timerange "$TIMERANGE" \
                    --enable-protections \
                    --cache day > "$comparison_file" 2>&1

                local current_performance=$(parse_backtest_performance "$comparison_file")
                local current_profit=$(echo "$current_performance" | cut -d'|' -f1)
                local current_drawdown=$(echo "$current_performance" | cut -d'|' -f2)

                echo ""
                echo -e "${BLUE}📈 性能比較結果:${NC}"
                echo "=================================="
                echo -e "當前策略:"
                echo -e "  收益率: ${current_profit:-0}%"
                echo -e "  回撤: ${current_drawdown:-0}%"
                echo ""
                echo -e "最佳策略:"
                echo -e "  收益率: ${best_profit:-0}%"
                echo -e "  回撤: ${best_drawdown:-0}%"

                rm -f "$comparison_file"
                echo ""
                echo "按任意鍵繼續..."
                read
                ;;
            4)
                echo ""
                echo -e "${CYAN}💾 備份當前策略為最佳策略...${NC}"

                # 運行回測獲取性能
                local backup_file="${SESSION_REPORT_DIR}/backtesting/backup_performance_${SESSION_ID}.txt"
                freqtrade backtesting \
                    --strategy "$STRATEGY" \
                    --config "$CONFIG" \
                    --timerange "$TIMERANGE" \
                    --enable-protections \
                    --cache day > "$backup_file" 2>&1

                local backup_performance=$(parse_backtest_performance "$backup_file")
                local backup_performance_file=$(save_current_performance "$backup_file" "$backup_performance")

                update_best_strategy "$backup_performance_file" "manual_backup"
                rm -f "$backup_file"

                echo ""
                echo "按任意鍵繼續..."
                read
                ;;
            5)
                if [ -f "$BEST_STRATEGY_PERFORMANCE" ]; then
                    echo ""
                    echo -e "${RED}⚠️  確認刪除最佳策略記錄？這將無法恢復！ (y/N): ${NC}"
                    read confirm_delete
                    if [[ "$confirm_delete" =~ ^[Yy]$ ]]; then
                        rm -rf "$BEST_STRATEGY_DIR"
                        mkdir -p "$BEST_STRATEGY_DIR"
                        echo -e "${GREEN}✅ 最佳策略記錄已刪除${NC}"
                    else
                        echo -e "${YELLOW}已取消刪除${NC}"
                    fi
                    sleep 2
                else
                    echo -e "${YELLOW}⚠️  沒有最佳策略記錄可以刪除${NC}"
                    sleep 2
                fi
                ;;
            b|B)
                return
                ;;
            *)
                echo -e "${RED}❌ 無效選擇，請重新選擇${NC}"
                sleep 1
                ;;
        esac
    done
}

# 執行主程序
main
