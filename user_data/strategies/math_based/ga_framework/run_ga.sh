#!/bin/bash

# =====================================================
# 數學策略 GA 迭代框架
# Math-Based Strategy Genetic Algorithm Framework
# =====================================================

set -e

# 預設配置
MATH_BASED_DIR="strategies/math_based"
GA_FRAMEWORK_DIR="$MATH_BASED_DIR/ga_framework"
REPORTS_DIR="$GA_FRAMEWORK_DIR/reports"
LOGS_DIR="$GA_FRAMEWORK_DIR/logs"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 參數解析
STRATEGY=""
CONFIG=""
EPOCHS=500
JOBS=1
TIME_MONTHS=6
LOSS_FUNCTION="ProfitDrawDownHyperOptLoss"
SPACES="default"

show_help() {
    echo "數學策略 GA 迭代框架"
    echo ""
    echo "用法: $0 [選項]"
    echo ""
    echo "必要參數:"
    echo "  --strategy=NAME        策略名稱 (必須在 math_based/ 下)"
    echo ""
    echo "選用參數:"
    echo "  --config=PATH          Config 路徑 (預設: 自動尋找策略目錄下的 config.json)"
    echo "  --epochs=N             GA 迭代輪數 (預設: 500)"
    echo "  --jobs=N               並行任務數 (預設: 1)"
    echo "  --months=N             回測月份數 (預設: 6)"
    echo "  --loss=NAME            損失函數 (預設: ProfitDrawDownHyperOptLoss)"
    echo "  --spaces=SPACES        優化空間 (預設: default)"
    echo "  --list                 列出所有數學策略"
    echo "  --help                 顯示幫助"
    echo ""
    echo "範例:"
    echo "  $0 --strategy=MathCombo_Adaptive_v1 --epochs=1000"
    echo "  $0 --strategy=nsgaii_bb_rpb_tsl_bi --loss=SortinoHyperOptLoss"
}

list_strategies() {
    echo -e "${BLUE}📊 數學策略列表:${NC}"
    echo ""
    local i=1
    for dir in "$MATH_BASED_DIR"/*/; do
        if [ -f "$dir"*.py ]; then
            local name=$(basename "$dir")
            echo "  $i. $name"
            ((i++))
        fi
    done
}

# 解析參數
while [[ $# -gt 0 ]]; do
    case $1 in
        --strategy=*)
            STRATEGY="${1#*=}"
            shift
            ;;
        --config=*)
            CONFIG="${1#*=}"
            shift
            ;;
        --epochs=*)
            EPOCHS="${1#*=}"
            shift
            ;;
        --jobs=*)
            JOBS="${1#*=}"
            shift
            ;;
        --months=*)
            TIME_MONTHS="${1#*=}"
            shift
            ;;
        --loss=*)
            LOSS_FUNCTION="${1#*=}"
            shift
            ;;
        --spaces=*)
            SPACES="${1#*=}"
            shift
            ;;
        --list)
            list_strategies
            exit 0
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知參數: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 驗證策略
if [ -z "$STRATEGY" ]; then
    echo -e "${RED}❌ 錯誤: 必須指定策略名稱${NC}"
    show_help
    exit 1
fi

STRATEGY_DIR="$MATH_BASED_DIR/$STRATEGY"
if [ ! -d "$STRATEGY_DIR" ]; then
    echo -e "${RED}❌ 錯誤: 策略 '$STRATEGY' 不存在於 $MATH_BASED_DIR/${NC}"
    list_strategies
    exit 1
fi

# 自動尋找 config
if [ -z "$CONFIG" ]; then
    if [ -f "$STRATEGY_DIR/config.json" ]; then
        CONFIG="$STRATEGY_DIR/config.json"
    else
        echo -e "${YELLOW}⚠️ 警告: 找不到 $STRATEGY_DIR/config.json，使用預設 config${NC}"
        CONFIG="config.json"
    fi
fi

# 建立目錄
SESSION_ID=$(date +%Y%m%d_%H%M%S)
SESSION_DIR="$REPORTS_DIR/$STRATEGY/$SESSION_ID"
mkdir -p "$SESSION_DIR"
mkdir -p "$LOGS_DIR"

# 計算時間範圍
END_DATE=$(date +%Y%m%d)
START_DATE=$(date -d "$TIME_MONTHS months ago" +%Y%m%d 2>/dev/null || date -v-${TIME_MONTHS}m +%Y%m%d)
TIMERANGE="${START_DATE}-${END_DATE}"

# 記錄迭代資訊
ITERATION_LOG="$SESSION_DIR/iteration.md"
cat > "$ITERATION_LOG" << EOF
# GA 迭代記錄

## 基本資訊
- **策略**: $STRATEGY
- **Session ID**: $SESSION_ID
- **開始時間**: $(date)
- **時間範圍**: $TIMERANGE ($TIME_MONTHS 個月)
- **迭代輪數**: $EPOCHS
- **損失函數**: $LOSS_FUNCTION
- **優化空間**: $SPACES

## 檔案位置
- **策略**: $STRATEGY_DIR
- **Config**: $CONFIG
- **報告**: $SESSION_DIR
- **Log**: $LOGS_DIR/ga_${STRATEGY}_${SESSION_ID}.log

## 執行指令
\`\`\`bash
freqtrade hyperopt \\
    --config "$CONFIG" \\
    --hyperopt-loss "$LOSS_FUNCTION" \\
    --spaces "$SPACES" \\
    -e "$EPOCHS" \\
    -j "$JOBS" \\
    --timerange "$TIMERANGE" \\
    --strategy "$STRATEGY" \\
    --print-all
\`\`\`

## 結果

*執行後自動更新*

EOF

echo -e "${GREEN}🚀 開始 GA 迭代優化${NC}"
echo "================================================"
echo -e "策略: ${CYAN}$STRATEGY${NC}"
echo -e "時間: ${CYAN}$TIMERANGE${NC}"
echo -e "輪數: ${CYAN}$EPOCHS${NC}"
echo -e "損失函數: ${CYAN}$LOSS_FUNCTION${NC}"
echo -e "報告: ${CYAN}$SESSION_DIR${NC}"
echo "================================================"

# 執行 GA
LOG_FILE="$LOGS_DIR/ga_${STRATEGY}_${SESSION_ID}.log"

freqtrade hyperopt \
    --config "$CONFIG" \
    --logfile "$LOG_FILE" \
    --hyperopt-loss "$LOSS_FUNCTION" \
    --spaces "$SPACES" \
    -e "$EPOCHS" \
    -j "$JOBS" \
    --timerange "$TIMERANGE" \
    --strategy "$STRATEGY" \
    --print-all

# 更新迭代記錄
END_TIME=$(date)
cat >> "$ITERATION_LOG" << EOF

## 執行結果
- **結束時間**: $END_TIME
- **Log 檔案**: $LOG_FILE

## 最佳參數

*請手動填入或執行 analyze_results.py 自動分析*

EOF

echo ""
echo -e "${GREEN}✅ GA 迭代完成${NC}"
echo -e "報告: ${CYAN}$SESSION_DIR${NC}"
