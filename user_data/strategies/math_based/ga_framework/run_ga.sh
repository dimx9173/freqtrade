#!/bin/bash

# =====================================================
# 數學策略 GA 迭代框架
# Math-Based Strategy Genetic Algorithm Framework
# =====================================================
#
# 修復記錄 (v2.0, 2026-05-29):
#   1. 使用 venv 絕對路徑的 freqtrade (source ~/freqtrade/.venv/bin/activate)
#   2. 所有路徑改為絕對路徑
#   3. 加入 --strategy-path 參數傳遞
#   4. 修復 list_strategies() glob bug
#   5. 修復 --config fallback 路徑
#   6. 加入錯誤處理 (trap ERR，記錄錯誤後繼續，而非 set -e 直接退出)

# ---- venv 啟動 ----
FREQTRADE_BIN="$HOME/freqtrade/.venv/bin/freqtrade"
FREQTRADE_VENV="$HOME/freqtrade/.venv/bin/activate"

if [ -f "$FREQTRADE_VENV" ]; then
    source "$FREQTRADE_VENV"
fi

if [ ! -x "$FREQTRADE_BIN" ]; then
    echo "❌ 找不到 freqtrade: $FREQTRADE_BIN"
    exit 1
fi

# ---- 錯誤處理 ----
ERROR_LOG=""
trap 'ERROR_LOG="錯誤發生於行 $LINENO，退出碼 $?"' ERR

# ---- 絕對路徑 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MATH_BASED_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GA_FRAMEWORK_DIR="$SCRIPT_DIR"
REPORTS_DIR="$GA_FRAMEWORK_DIR/reports"
LOGS_DIR="$GA_FRAMEWORK_DIR/logs"
STRATEGY_PATH="$MATH_BASED_DIR"

# ---- 顏色定義 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---- 參數預設值 ----
STRATEGY=""
CONFIG=""
EPOCHS=500
JOBS=1
TIME_MONTHS=6
LOSS_FUNCTION="ProfitDrawDownHyperOptLoss"
SPACES="default"
HYPEROPT_FILENAME=""

show_help() {
    echo "數學策略 GA 迭代框架 v2.0"
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
    echo "  --hyperopt-filename=FILENAME  從現有 hyperopt 檔案繼續 (可選)"
    echo "  --list                 列出所有數學策略"
    echo "  --help                 顯示幫助"
    echo ""
    echo "範例:"
    echo "  $0 --strategy=PolyReg_Adaptive_v2 --epochs=1000"
    echo "  $0 --strategy=nsgaii_bb_rpb_tsl_bi --loss=SortinoHyperOptLoss"
    echo "  $0 --list"
}

list_strategies() {
    echo -e "${BLUE}📊 數學策略列表:${NC}"
    echo ""

    local i=1
    local seen=()

    # 1. 搜尋子目錄中的策略 (如 nsgaii_bb_rpb_tsl_bi/)
    for dir in "$MATH_BASED_DIR"/*/; do
        # 跳過非策略目錄
        local dirname=$(basename "$dir")
        [[ "$dirname" == "ga_framework" ]] && continue
        [[ "$dirname" == "__pycache__" ]] && continue

        # 在子目錄中尋找 .py 策略檔
        local py_files=("$dir"*.py)
        if [ -f "${py_files[0]}" ]; then
            for pyfile in "${py_files[@]}"; do
                local classname=$(basename "$pyfile" .py)
                echo "  $i. $classname  (in $dirname/)"
                ((i++))
                seen+=("$classname")
            done
        fi
    done

    # 2. 搜尋頂層 .py 策略檔
    for pyfile in "$MATH_BASED_DIR"/*.py; do
        [ ! -f "$pyfile" ] && continue
        local classname=$(basename "$pyfile" .py)
        # 跳過已列出的
        local already=0
        for s in "${seen[@]}"; do
            [[ "$s" == "$classname" ]] && already=1 && break
        done
        [ $already -eq 1 ] && continue

        echo "  $i. $classname"
        ((i++))
    done

    if [ $i -eq 1 ]; then
        echo "  (無策略檔案)"
    fi
    echo ""
}

# ---- 參數解析 ----
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
        --hyperopt-filename=*)
            HYPEROPT_FILENAME="${1#*=}"
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

# ---- 驗證策略 ----
if [ -z "$STRATEGY" ]; then
    echo -e "${RED}❌ 錯誤: 必須指定策略名稱${NC}"
    show_help
    exit 1
fi

# 尋找策略檔案位置 (可能在子目錄或頂層)
STRATEGY_FILE=""
STRATEGY_SUBDIR=""

# 先找子目錄中的
for dir in "$MATH_BASED_DIR"/*/; do
    local_dirname=$(basename "$dir")
    [[ "$local_dirname" == "ga_framework" ]] && continue
    [[ "$local_dirname" == "__pycache__" ]] && continue
    if [ -f "$dir/${STRATEGY}.py" ]; then
        STRATEGY_FILE="$dir/${STRATEGY}.py"
        STRATEGY_SUBDIR="$dir"
        break
    fi
done

# 再找頂層
if [ -z "$STRATEGY_FILE" ]; then
    if [ -f "$MATH_BASED_DIR/${STRATEGY}.py" ]; then
        STRATEGY_FILE="$MATH_BASED_DIR/${STRATEGY}.py"
        STRATEGY_SUBDIR="$MATH_BASED_DIR"
    fi
fi

if [ -z "$STRATEGY_FILE" ]; then
    echo -e "${RED}❌ 錯誤: 策略 '$STRATEGY' 不存在於 $MATH_BASED_DIR/${NC}"
    list_strategies
    exit 1
fi

echo -e "${GREEN}✅ 找到策略: $STRATEGY_FILE${NC}"

# ---- 自動尋找 config ----
if [ -z "$CONFIG" ]; then
    # 先找策略目錄下的 config.json
    if [ -f "$STRATEGY_SUBDIR/config.json" ]; then
        CONFIG="$STRATEGY_SUBDIR/config.json"
    elif [ -f "$GA_FRAMEWORK_DIR/ga_config_template.json" ]; then
        CONFIG="$GA_FRAMEWORK_DIR/ga_config_template.json"
    else
        echo -e "${YELLOW}⚠️ 警告: 找不到 config，使用預設 config.json${NC}"
        CONFIG="$HOME/freqtrade/config.json"
    fi
fi

echo -e "${GREEN}✅ Config: $CONFIG${NC}"

# ---- 建立目錄 ----
SESSION_ID=$(date +%Y%m%d_%H%M%S)
SESSION_DIR="$REPORTS_DIR/$STRATEGY/$SESSION_ID"
mkdir -p "$SESSION_DIR"
mkdir -p "$LOGS_DIR"

# ---- 計算時間範圍 ----
END_DATE=$(date +%Y%m%d)
START_DATE=$(date -d "$TIME_MONTHS months ago" +%Y%m%d 2>/dev/null || date -v-${TIME_MONTHS}m +%Y%m%d)
TIMERANGE="${START_DATE}-${END_DATE}"

# ---- 記錄迭代資訊 ----
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
- **策略**: $STRATEGY_FILE
- **Config**: $CONFIG
- **報告**: $SESSION_DIR
- **Log**: $LOGS_DIR/ga_${STRATEGY}_${SESSION_ID}.log

## 執行指令
\`\`\`bash
$FREQTRADE_BIN hyperopt \\
    --config "$CONFIG" \\
    --strategy-path "$STRATEGY_PATH" \\
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
echo -e "策略路徑: ${CYAN}$STRATEGY_PATH${NC}"
echo -e "時間: ${CYAN}$TIMERANGE${NC}"
echo -e "輪數: ${CYAN}$EPOCHS${NC}"
echo -e "損失函數: ${CYAN}$LOSS_FUNCTION${NC}"
echo -e "報告: ${CYAN}$SESSION_DIR${NC}"
echo "================================================"

# ---- 執行 GA ----
LOG_FILE="$LOGS_DIR/ga_${STRATEGY}_${SESSION_ID}.log"

# 建構指令
CMD=(
    "$FREQTRADE_BIN" hyperopt
    --config "$CONFIG"
    --strategy-path "$STRATEGY_PATH"
    --logfile "$LOG_FILE"
    --hyperopt-loss "$LOSS_FUNCTION"
    --spaces "$SPACES"
    -e "$EPOCHS"
    -j "$JOBS"
    --timerange "$TIMERANGE"
    --strategy "$STRATEGY"
    --print-all
)

# 如果有 hyperopt-filename，加入
if [ -n "$HYPEROPT_FILENAME" ]; then
    CMD+=(--hyperopt-filename "$HYPEROPT_FILENAME")
fi

echo -e "${PURPLE}執行: ${CMD[*]}${NC}"
echo ""

# 執行並擷取退出碼
EXIT_CODE=0
"${CMD[@]}" || EXIT_CODE=$?

# ---- 更新迭代記錄 ----
END_TIME=$(date)
{
    echo ""
    echo "## 執行結果"
    echo "- **結束時間**: $END_TIME"
    echo "- **Log 檔案**: $LOG_FILE"
    echo "- **退出碼**: $EXIT_CODE"
    echo ""

    if [ -n "$ERROR_LOG" ]; then
        echo "## 錯誤"
        echo "- $ERROR_LOG"
        echo ""
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        echo "## ⚠️ GA 未正常完成"
        echo "- 退出碼: $EXIT_CODE"
        echo "- 請檢查 log: $LOG_FILE"
        echo ""
    else
        echo "## 最佳參數"
        echo ""
        echo "*請手動填入或執行 analyze_results.py 自動分析*"
        echo ""
    fi
} >> "$ITERATION_LOG"

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ GA 迭代完成${NC}"
else
    echo -e "${RED}❌ GA 迭代失敗 (退出碼: $EXIT_CODE)${NC}"
    if [ -n "$ERROR_LOG" ]; then
        echo -e "${RED}   $ERROR_LOG${NC}"
    fi
fi
echo -e "報告: ${CYAN}$SESSION_DIR${NC}"
echo -e "Log: ${CYAN}$LOG_FILE${NC}"

exit $EXIT_CODE
