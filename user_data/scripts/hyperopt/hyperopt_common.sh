#!/bin/bash

# =====================================================
# Freqtrade 通用 Hyperopt 比較優化系統
# 基於 hyperopt_scalping_optimized.sh 選單系統
# 四種優化配置比較分析
# =====================================================

# 預設配置
DEFAULT_STRATEGY="ElliotV5_SMA_ninja"
DEFAULT_CONFIG="user_data/config/config_6.json"
DEFAULT_TIME_MONTHS=6
DEFAULT_EPOCHS=250
DEFAULT_JOBS=1

# 可配置參數
STRATEGY="$DEFAULT_STRATEGY"
CONFIG="$DEFAULT_CONFIG"
TIME_MONTHS="$DEFAULT_TIME_MONTHS"
EPOCHS="$DEFAULT_EPOCHS"
JOBS="$DEFAULT_JOBS"
CUSTOM_TIMERANGE=""

# 系統變量
SESSION_ID=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="user_data/reports"
LOG_DIR="user_data/logs"
SESSION_LOG_DIR="${LOG_DIR}/${SESSION_ID}"
SESSION_REPORT_DIR="${REPORT_DIR}/${SESSION_ID}"
OPTIMIZATION_LOG="${SESSION_LOG_DIR}/hyperopt_common.log"

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

# 參數解析
for arg in "$@"; do
    case $arg in
        --menu)
        MENU_MODE=true
        shift
        ;;
        --strategy=*)
        STRATEGY="${arg#*=}"
        shift
        ;;
        --config=*)
        CONFIG="${arg#*=}"
        shift
        ;;
        --months=*)
        TIME_MONTHS="${arg#*=}"
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
        --help)
        echo "使用方法: $0 [選項]"
        echo "  --menu                 啟動交互式選單"
        echo "  --strategy=NAME        設定策略名稱 (預設: $DEFAULT_STRATEGY)"
        echo "  --config=PATH          設定配置文件路徑 (預設: $DEFAULT_CONFIG)"
        echo "  --months=N             設定時間月份數 (預設: $DEFAULT_TIME_MONTHS)"
        echo "  --epochs=N             設定hyperopt輪數 (預設: $DEFAULT_EPOCHS)"
        echo "  --jobs=N               設定並行任務數 (預設: $DEFAULT_JOBS)"
        echo "  --timerange=RANGE      自定義時間範圍 (覆蓋months設定)"
        echo "  --help                 顯示幫助"
        exit 0
        ;;
        *)
        echo "未知參數: $arg"
        echo "使用 --help 查看幫助"
        exit 1
        ;;
    esac
done

# 創建必要目錄
create_directories() {
    echo -e "${BLUE}🗂️  創建 Session ${SESSION_ID} 目錄結構...${NC}"
    mkdir -p "${REPORT_DIR}"
    mkdir -p "${LOG_DIR}"
    mkdir -p "${SESSION_LOG_DIR}"
    mkdir -p "${SESSION_REPORT_DIR}"
    mkdir -p "${SESSION_REPORT_DIR}/hyperopt_results"

    echo -e "${GREEN}✅ Session 目錄已建立:${NC}"
    echo -e "   日誌目錄: ${SESSION_LOG_DIR}"
    echo -e "   報告目錄: ${SESSION_REPORT_DIR}"
    echo ""
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

    # 檢查get_time_range.sh
    if [ ! -f "get_time_range.sh" ]; then
        echo -e "${YELLOW}⚠️ get_time_range.sh 不存在，將使用自定義時間範圍${NC}"
    else
        echo -e "${GREEN}✅ 時間範圍腳本: get_time_range.sh${NC}"
    fi

    echo ""
}

# 獲取時間範圍
get_time_range() {
    if [ -n "$CUSTOM_TIMERANGE" ]; then
        echo "$CUSTOM_TIMERANGE"
    elif [ -f "get_time_range.sh" ]; then
        zsh get_time_range.sh "$TIME_MONTHS"
    else
        # 簡單的時間範圍計算
        local end_date=$(date +%Y%m%d)
        local start_date=$(date -d "${TIME_MONTHS} months ago" +%Y%m%d 2>/dev/null || date -v -${TIME_MONTHS}m +%Y%m%d 2>/dev/null || echo "20240101")
        echo "${start_date}-${end_date}"
    fi
}

# 顯示當前設定
show_current_settings() {
    echo ""
    echo -e "${BLUE}📊 當前設定:${NC}"
    echo -e "   策略: ${GREEN}$STRATEGY${NC}"
    echo -e "   配置: ${GREEN}$CONFIG${NC}"
    echo -e "   時間: ${GREEN}$(get_time_range)${NC} (${TIME_MONTHS} 個月)"
    echo -e "   輪數: ${GREEN}$EPOCHS${NC} | 並行: ${GREEN}$JOBS${NC}"
    echo ""
}

# 修改策略
change_strategy() {
    clear
    echo "=========================================================================="
    echo -e "${CYAN}📋 修改策略名稱${NC}"
    echo "=========================================================================="
    echo ""
    echo -e "${BLUE}可用策略列表:${NC}"
    if [ -d "user_data/strategies" ]; then
        ls user_data/strategies/*.py 2>/dev/null | sed 's/.*\///;s/\.py$//' | nl -w2 -s') '
    fi

    echo ""
    echo -e "${YELLOW}當前策略: ${GREEN}$STRATEGY${NC}"
    echo ""
    echo "選擇方式："
    echo "1) 輸入編號 (如: 3)"
    echo "2) 輸入策略名稱 (如: ClucHAnix_5m)"
    echo "3) 按 Enter 返回"
    echo ""
    echo -n "請輸入: "
    read user_input

    # 處理用戶輸入
    if [ -z "$user_input" ]; then
        return
    elif [[ "$user_input" =~ ^[0-9]+$ ]]; then
        # 數字輸入 - 根據編號選擇策略
        local strategy_name=$(ls user_data/strategies/*.py 2>/dev/null | sed 's/.*\///;s/\.py$//' | sed -n "${user_input}p")
        if [ -n "$strategy_name" ]; then
            STRATEGY="$strategy_name"
            echo -e "${GREEN}✅ 策略已設定為: $STRATEGY${NC}"
        else
            echo -e "${RED}❌ 無效的編號${NC}"
        fi
    else
        # 直接輸入策略名稱
        if [ -f "user_data/strategies/$user_input.py" ]; then
            STRATEGY="$user_input"
            echo -e "${GREEN}✅ 策略已設定為: $STRATEGY${NC}"
        else
            echo -e "${RED}❌ 策略文件不存在: user_data/strategies/$user_input.py${NC}"
        fi
    fi

    echo ""
    echo "按任意鍵繼續..."
    read -n 1
}

# 修改配置文件
change_config() {
    clear
    echo "=========================================================================="
    echo -e "${CYAN}📋 修改配置文件${NC}"
    echo "=========================================================================="
    echo ""
    echo -e "${BLUE}可用配置文件:${NC}"
    if [ -d "user_data/config" ]; then
        find user_data/config -name "*.json" 2>/dev/null | nl -w2 -s') '
    fi

    echo ""
    echo -e "${YELLOW}當前配置: ${GREEN}$CONFIG${NC}"
    echo ""
    echo -n "請輸入配置文件路徑 (或按 Enter 返回): "
    read new_config

    if [ -n "$new_config" ] && [ -f "$new_config" ]; then
        CONFIG="$new_config"
        echo -e "${GREEN}✅ 配置文件已設定為: $CONFIG${NC}"
    elif [ -n "$new_config" ]; then
        echo -e "${RED}❌ 配置文件不存在: $new_config${NC}"
    fi

    echo ""
    echo "按任意鍵繼續..."
    read -n 1
}

# 修改時間和參數
change_params() {
    clear
    echo "=========================================================================="
    echo -e "${CYAN}⚙️ 修改優化參數${NC}"
    echo "=========================================================================="
    echo ""
    show_current_settings

    echo -n "請輸入月份數 (1-24, 當前: $TIME_MONTHS): "
    read new_months
    if [[ "$new_months" =~ ^[1-9][0-9]*$ ]] && [ "$new_months" -le 24 ]; then
        TIME_MONTHS="$new_months"
        CUSTOM_TIMERANGE=""
        echo -e "${GREEN}✅ 時間範圍已設定為: $TIME_MONTHS 個月${NC}"
    fi

    echo -n "請輸入優化輪數 (當前: $EPOCHS): "
    read new_epochs
    if [[ "$new_epochs" =~ ^[1-9][0-9]*$ ]]; then
        EPOCHS="$new_epochs"
        echo -e "${GREEN}✅ 優化輪數已設定為: $EPOCHS${NC}"
    fi

    echo -n "請輸入並行任務數 (當前: $JOBS): "
    read new_jobs
    if [[ "$new_jobs" =~ ^[1-9][0-9]*$ ]]; then
        JOBS="$new_jobs"
        echo -e "${GREEN}✅ 並行任務數已設定為: $JOBS${NC}"
    fi

    echo ""
    echo "按任意鍵繼續..."
    read -n 1
}

# 查看報告
show_reports() {
    clear
    echo "=========================================================================="
    echo -e "${CYAN}📊 歷史報告列表${NC}"
    echo "=========================================================================="
    echo ""

    if [ -d "$REPORT_DIR" ]; then
        echo -e "${BLUE}最近報告:${NC}"
        find "$REPORT_DIR" -name "common_hyperopt_results_*.md" -type f | sort -r | head -5 | nl
        echo ""
        echo -n "輸入報告編號查看，或按 Enter 返回: "
        read report_num

        if [[ "$report_num" =~ ^[0-9]+$ ]]; then
            local report_file=$(find "$REPORT_DIR" -name "common_hyperopt_results_*.md" -type f | sort -r | head -5 | sed -n "${report_num}p")
            if [ -f "$report_file" ]; then
                echo -e "${GREEN}📖 顯示報告: $(basename $report_file)${NC}"
                echo ""
                less "$report_file"
            else
                echo -e "${RED}❌ 報告不存在${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}📝 尚無歷史報告${NC}"
        echo "按任意鍵返回..."
        read -n 1
    fi
}

# 單一優化測試選單
show_single_test_menu() {
    clear
    echo "=========================================================================="
    echo -e "${CYAN}🧪 單一優化測試${NC}"
    echo "=========================================================================="
    echo ""
    echo -e "${YELLOW}請選擇優化配置:${NC}"
    echo "  1) ProfitDrawDown + Default Spaces"
    echo "  2) ProfitDrawDown + Custom Spaces (buy sell roi trades)"
    echo "  3) Sortino + Default Spaces"
    echo "  4) Sortino + Custom Spaces (buy sell roi trades)"
    echo "  5) 返回主選單"
    echo ""
    echo -n "請選擇 [1-5]: "
    read test_choice

    case $test_choice in
        1)
            run_single_hyperopt "ProfitDrawDown Default" "ProfitDrawDownHyperOptLoss" "default"
            ;;
        2)
            run_single_hyperopt "ProfitDrawDown Custom" "ProfitDrawDownHyperOptLoss" "buy sell roi trades"
            ;;
        3)
            run_single_hyperopt "Sortino Default" "SortinoHyperOptLoss" "default"
            ;;
        4)
            run_single_hyperopt "Sortino Custom" "SortinoHyperOptLoss" "buy sell roi trades"
            ;;
        5|"")
            return
            ;;
        *)
            echo -e "${RED}❌ 無效選擇${NC}"
            echo "按任意鍵繼續..."
            read -n 1
            ;;
    esac
}

# 執行單一hyperopt
run_single_hyperopt() {
    local test_name="$1"
    local loss_function="$2"
    local spaces="$3"

    echo -e "${PURPLE}🔄 執行 $test_name 優化...${NC}"
    echo "================================================="
    echo -e "損失函數: ${CYAN}$loss_function${NC}"
    echo -e "優化空間: ${CYAN}$spaces${NC}"
    echo -e "時間範圍: ${CYAN}$(get_time_range)${NC}"
    echo "================================================="

    local TIME_RANGE=$(get_time_range)
    local log_file="${SESSION_LOG_DIR}/single_${SESSION_ID}.log"

    # 記錄開始時間
    local start_time=$(date +%s)
    echo "開始時間: $(date)" | tee -a "$OPTIMIZATION_LOG"

    # 執行hyperopt
    freqtrade hyperopt \
        --config "$CONFIG" \
        --logfile "$log_file" \
        --hyperopt-loss "$loss_function" \
        --spaces $spaces \
        -e "$EPOCHS" \
        -j "$JOBS" \
        --timerange "$TIME_RANGE" \
        --strategy "$STRATEGY" \
        --print-all

    # 計算執行時間
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""
    echo -e "${GREEN}✅ $test_name 優化完成${NC}"
    echo -e "${BLUE}執行時間: ${duration} 秒${NC}"
    echo "結束時間: $(date)" | tee -a "$OPTIMIZATION_LOG"

    echo "按任意鍵繼續..."
    read -n 1
}

# 執行單個hyperopt測試
run_hyperopt_test() {
    local test_name="$1"
    local loss_function="$2"
    local spaces="$3"
    local log_suffix="$4"
    local report_file="$5"

    echo -e "${CYAN}🔄 執行 $test_name...${NC}"
    echo "損失函數: $loss_function"
    echo "優化空間: $spaces"
    echo ""

    # 記錄到報告
    cat >> "$report_file" << EOF
## $test_name

**損失函數:** $loss_function
**優化空間:** $spaces
**開始時間:** $(date)

EOF

    # 創建專用日誌文件
    local log_file="${SESSION_LOG_DIR}/${log_suffix}_${SESSION_ID}.log"
    local output_file="${SESSION_REPORT_DIR}/hyperopt_results/${log_suffix}_output.txt"

    mkdir -p "${SESSION_REPORT_DIR}/hyperopt_results"

    # 記錄開始時間
    local start_time=$(date +%s)

    # 執行hyperopt
    local TIME_RANGE=$(get_time_range)

    # 構建命令，正確處理spaces參數
    local cmd="freqtrade hyperopt --config \"$CONFIG\" --logfile \"$log_file\" --hyperopt-loss \"$loss_function\""
    cmd="$cmd --spaces $spaces"
    cmd="$cmd -e $EPOCHS -j $JOBS --timerange \"$TIME_RANGE\" --strategy \"$STRATEGY\" --print-all"

    echo "執行命令: $cmd" >> "$output_file"
    eval "$cmd" >> "$output_file" 2>&1

    # 計算執行時間
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # 提取結果並寫入報告
    cat >> "$report_file" << EOF
**完成時間:** $(date)
**執行時間:** ${duration} 秒

### 最佳結果
\`\`\`
$(tail -30 "$output_file" | grep -A 25 "Best result:" | head -25 || echo "結果處理中...")
\`\`\`

### 性能摘要
\`\`\`
$(grep -E "(Total profit|Avg profit|Total trades|Win rate|Best pair|Worst pair|Sharpe|Sortino|Max drawdown)" "$output_file" | tail -15 || echo "性能數據處理中...")
\`\`\`

---

EOF

    echo -e "${GREEN}✅ $test_name 完成 (${duration}秒)${NC}"
    echo ""
}

# 執行四種優化比較
run_comparative_analysis() {
    clear
    echo -e "${PURPLE}🚀 開始四種優化配置比較分析${NC}"
    echo "=========================================================================="
    echo -e "策略: ${GREEN}$STRATEGY${NC}"
    echo -e "配置: ${GREEN}$CONFIG${NC}"
    echo -e "時間: ${GREEN}$(get_time_range)${NC}"
    echo -e "輪數: ${GREEN}$EPOCHS${NC} | 並行: ${GREEN}$JOBS${NC}"
    echo "=========================================================================="

    # 清除上次的backtest_results和hyperopt_results
    rm -rf user_data/backtest_results/*
    rm -rf user_data/hyperopt_results/*

    # 初始化報告
    local report_file="${REPORT_DIR}/common_hyperopt_results_${SESSION_ID}.md"
    local TIME_RANGE=$(get_time_range)

    cat > "$report_file" << EOF
# Freqtrade Hyperopt 四種優化配置比較分析

**生成時間:** $(date)
**策略:** $STRATEGY
**配置文件:** $CONFIG
**時間範圍:** $TIME_RANGE
**優化輪數:** $EPOCHS
**並行任務:** $JOBS
**Session ID:** $SESSION_ID

## 執行摘要
本報告比較四種不同的hyperopt優化配置：

1. **ProfitDrawDown + Default Spaces** - 利潤回撤優化（全參數空間）
2. **ProfitDrawDown + Custom Spaces** - 利潤回撤優化（核心交易參數）
3. **Sortino + Default Spaces** - 風險調整優化（全參數空間）
4. **Sortino + Custom Spaces** - 風險調整優化（核心交易參數）

---

EOF

    echo -e "${BLUE}📝 報告文件: $report_file${NC}"
    echo ""

    # 執行四種優化
    run_hyperopt_test "ProfitDrawDown Default Spaces" "ProfitDrawDownHyperOptLoss" "default" "pd_default" "$report_file"
    run_hyperopt_test "ProfitDrawDown Custom Spaces" "ProfitDrawDownHyperOptLoss" "buy sell roi trades" "pd_custom" "$report_file"
    run_hyperopt_test "Sortino Default Spaces" "SortinoHyperOptLoss" "default" "sortino_default" "$report_file"
    run_hyperopt_test "Sortino Custom Spaces" "SortinoHyperOptLoss" "buy sell roi trades" "sortino_custom" "$report_file"

    # 生成總結
    generate_analysis_summary "$report_file"

    echo -e "${GREEN}🎉 四種優化配置比較完成！${NC}"
    echo -e "${BLUE}📊 完整報告: $report_file${NC}"

    echo ""
    echo -n "是否要查看報告？[y/N]: "
    read view_report
    if [[ "$view_report" =~ ^[Yy]$ ]]; then
        less "$report_file"
    fi

    if [ "$MENU_MODE" = "true" ]; then
        echo "按任意鍵返回主選單..."
        read -n 1
    fi
}

# 生成分析總結
generate_analysis_summary() {
    local report_file="$1"

    cat >> "$report_file" << EOF
## 比較分析總結

### 配置對比表
| 優化配置 | 損失函數 | 優化空間 | 特點 |
|---------|---------|----------|------|
| ProfitDrawDown Default | ProfitDrawDownHyperOptLoss | default | 全面優化，平衡利潤與回撤 |
| ProfitDrawDown Custom | ProfitDrawDownHyperOptLoss | buy sell roi trades | 專注核心交易參數優化 |
| Sortino Default | SortinoHyperOptLoss | default | 風險調整收益優化，重視下行風險 |
| Sortino Custom | SortinoHyperOptLoss | buy sell roi trades | 專注風險調整的核心參數 |

### 建議指南

1. **ProfitDrawDown 配置** - 適用於追求最大化利潤同時控制回撤的策略
2. **Sortino 配置** - 適用於風險意識較強，重視下行保護的交易風格
3. **Default Spaces** - 提供全面的參數優化，適合策略全面調優
4. **Custom Spaces** - 專注於核心交易邏輯參數，執行速度更快

### 實施步驟

1. 👀 **查看結果** - 比較上述四個配置的具體表現指標
2. 🎯 **選擇最優** - 根據你的風險偏好和收益目標選擇最佳配置
3. 📋 **應用參數** - 將最佳參數應用到你的策略文件中
4. 🧪 **樣本外測試** - 在新的時間段進行回測驗證
5. 📈 **監控表現** - 實盤或模擬交易中持續監控策略表現

### 技術說明

- **ProfitDrawDownHyperOptLoss**: 優化利潤同時最小化最大回撤
- **SortinoHyperOptLoss**: 基於Sortino比率，只考慮下行波動率
- **Default Spaces**: 包含所有可優化參數（buy, sell, roi, stoploss, trailing, protection等）
- **Custom Spaces**: 僅優化核心交易參數（buy, sell, roi, trades）

---

**報告生成完成時間:** $(date)
**總分析耗時:** 約 $(( $(date +%s) - $(date -d '1 hour ago' +%s) )) 分鐘（估算）
**Session ID:** $SESSION_ID

EOF
}

# 主選單
show_main_menu() {
    while true; do
        clear
        echo "=========================================================================="
        echo -e "${CYAN}🎯 Freqtrade 通用 Hyperopt 比較優化系統${NC}"
        echo "=========================================================================="

        show_current_settings

        echo -e "${YELLOW}請選擇操作:${NC}"
        echo "  1) 🚀 執行四種優化比較 (完整分析)"
        echo "  2) 📝 修改策略名稱"
        echo "  3) ⚙️ 修改配置文件"
        echo "  4) 🔧 修改參數設定"
        echo "  5) 📊 查看歷史報告"
        echo "  6) 🧪 單一優化測試"
        echo "  7) ❌ 退出"
        echo ""
        echo -n "請選擇 [1-7]: "
        read choice 2>/dev/null || choice="7"

        case $choice in
            1)
                run_comparative_analysis
                ;;
            2)
                change_strategy
                ;;
            3)
                change_config
                ;;
            4)
                change_params
                ;;
            5)
                show_reports
                ;;
            6)
                show_single_test_menu
                ;;
            7)
                echo -e "${GREEN}👋 感謝使用 Freqtrade Hyperopt 系統！${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ 無效選擇，請重新選擇${NC}"
                echo "按任意鍵繼續..."
                read -n 1
                ;;
        esac
    done
}

# 主程序
main() {
    # 系統檢查
    system_pre_check

    # 創建目錄
    create_directories

    # 根據模式執行
    if [ "$MENU_MODE" = true ]; then
        show_main_menu
    else
        echo -e "${BLUE}🎯 標準模式啟動${NC}"
        echo -e "${YELLOW}提示: 使用 --menu 參數啟動交互式選單模式${NC}"
        echo ""
        run_comparative_analysis
    fi
}

# 執行主程序
main
