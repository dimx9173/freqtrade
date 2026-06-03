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
TIME_MONTHS=4
LOSS_FUNCTION="ProfitDrawDownHyperOptLoss"
SPACES="default"
HYPEROPT_FILENAME=""
ALLOW_SHORT_WINDOW=false
FORCE_PREFLIGHT=false

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
    echo "  --months=N             回測月份數 (預設: 4, 最小 4)"
    echo "  --loss=NAME            損失函數 (預設: ProfitDrawDownHyperOptLoss)"
    echo "  --spaces=SPACES        優化空間 (預設: default)"
    echo "  --hyperopt-filename=FILENAME  從現有 hyperopt 檔案繼續 (可選)"
    echo "  --allow-short-window   允許 < 4 個月回測窗口 (預設: 不允許)"
    echo "  --force                跳過 pre-flight 失敗，強制執行 GA"
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
        --allow-short-window)
            ALLOW_SHORT_WINDOW=true
            shift
            ;;
        --force)
            FORCE_PREFLIGHT=true
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

# ---- 檢查回測窗口長度 ----
if [ "$TIME_MONTHS" -lt 4 ] && [ "$ALLOW_SHORT_WINDOW" != true ]; then
    echo -e "${RED}❌ 錯誤: 回測窗口為 ${TIME_MONTHS} 個月，少於最低要求的 4 個月${NC}"
    echo -e "${YELLOW}   短窗口容易隱藏 regime 切換問題（見 01_process_bottlenecks.md）。${NC}"
    echo -e "${YELLOW}   若確定要使用短窗口，請加上 --allow-short-window 旗標。${NC}"
    exit 1
fi

if [ "$TIME_MONTHS" -lt 4 ] && [ "$ALLOW_SHORT_WINDOW" = true ]; then
    echo -e "${YELLOW}⚠️  警告: 回測窗口僅 ${TIME_MONTHS} 個月（已透過 --allow-short-window 強制允許）${NC}"
    echo ""
fi

# ---- 建立目錄 ----
SESSION_ID=$(date +%Y%m%d_%H%M%S)
SESSION_DIR="$REPORTS_DIR/$STRATEGY/$SESSION_ID"
mkdir -p "$SESSION_DIR"
mkdir -p "$LOGS_DIR"

# ---- 計算時間範圍 ----
END_DATE=$(date +%Y%m%d)
START_DATE=$(date -d "$TIME_MONTHS months ago" +%Y%m%d 2>/dev/null || date -v-${TIME_MONTHS}m +%Y%m%d)
TIMERANGE="${START_DATE}-${END_DATE}"

# ---- 執行 Pre-flight Smoke Test ----
PREFLIGHT_LOG="$LOGS_DIR/preflight_${SESSION_ID}.log"
PREFLIGHT_SCRIPT="$SCRIPT_DIR/pre_flight_smoke_test.py"

if [ -f "$PREFLIGHT_SCRIPT" ]; then
    echo -e "${BLUE}🔍 執行 Pre-flight Smoke Test...${NC}"
    python3 "$PREFLIGHT_SCRIPT" \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        > "$PREFLIGHT_LOG" 2>&1
    PREFLIGHT_EXIT=$?

    echo -e "Pre-flight 結果寫入: ${CYAN}$PREFLIGHT_LOG${NC}"

    if [ $PREFLIGHT_EXIT -eq 2 ]; then
        echo -e "${RED}❌ Pre-flight 失敗: 進場信號過少（exit code 2）${NC}"
        if [ "$FORCE_PREFLIGHT" != true ]; then
            echo -e "${YELLOW}   策略進場條件可能過嚴，GA 終止（避免浪費 70 分鐘）。${NC}"
            echo -e "${YELLOW}   若要強制執行，請加上 --force 旗標。${NC}"
            cat "$PREFLIGHT_LOG"
            exit 2
        else
            echo -e "${YELLOW}⚠️  已透過 --force 強制繼續${NC}"
        fi
    elif [ $PREFLIGHT_EXIT -eq 3 ]; then
        echo -e "${RED}❌ Pre-flight 失敗: 過度交易（exit code 3）${NC}"
        if [ "$FORCE_PREFLIGHT" != true ]; then
            echo -e "${YELLOW}   策略產生過多信號，GA 終止。${NC}"
            cat "$PREFLIGHT_LOG"
            exit 3
        else
            echo -e "${YELLOW}⚠️  已透過 --force 強制繼續${NC}"
        fi
    elif [ $PREFLIGHT_EXIT -eq 4 ]; then
        echo -e "${RED}❌ Pre-flight 失敗: Negative KB 偵測到 DANGER 模式（exit code 4）${NC}"
        if [ "$FORCE_PREFLIGHT" != true ]; then
            echo -e "${YELLOW}   策略存在已知陷阱（如 exit_trend LEVEL 振盪），GA 終止。${NC}"
            cat "$PREFLIGHT_LOG"
            exit 4
        else
            echo -e "${YELLOW}⚠️  已透過 --force 強制繼續${NC}"
        fi
    elif [ $PREFLIGHT_EXIT -eq 1 ]; then
        echo -e "${YELLOW}⚠️  Pre-flight 警告（exit code 1）${NC}"
        head -20 "$PREFLIGHT_LOG"
    elif [ $PREFLIGHT_EXIT -eq 0 ]; then
        echo -e "${GREEN}✅ Pre-flight 通過${NC}"
    else
        echo -e "${YELLOW}⚠️  Pre-flight 未知退出碼: $PREFLIGHT_EXIT${NC}"
        head -20 "$PREFLIGHT_LOG"
    fi
    echo ""
else
    echo -e "${YELLOW}⚠️  找不到 pre_flight_smoke_test.py，跳過 pre-flight${NC}"
    echo ""
fi

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
    # Phase 1 review NEEDS-FIX #3: reject path traversal / absolute paths to
    # keep the file within user_data/hyperopt_results/.
    if [[ "$HYPEROPT_FILENAME" == *..* ]] || [[ "$HYPEROPT_FILENAME" == /* ]]; then
        echo -e "${RED}❌ --hyperopt-filename 不能包含 .. 或絕對路徑（避免路徑注入）${NC}"
        exit 1
    fi
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
# ---- 自動 Freqtrade Config 驗證 (LAW-07..09) (2026-06-03 新增) ----
# 防止 GA 找到 infeasible 參數（如 trailing_stop_positive_offset < positive）
if [ $EXIT_CODE -eq 0 ]; then
    echo "🔍 執行 Freqtrade Config 驗證 (LAW-07..09)..."
    if [ -n "$HYPEROPT_FILENAME" ]; then
        VALIDATION_FILE="$HYPEROPT_FILENAME"
    else
        VALIDATION_FILE=$(ls -t /home/brian/freqtrade/user_data/hyperopt_results/*${STRATEGY}*.fthypt 2>/dev/null | head -1)
    fi
    if [ -n "$VALIDATION_FILE" ]; then
        python3 "$SCRIPT_DIR/analyze_results.py" \
            --strategy="$STRATEGY" \
            --hyperopt-filename="$VALIDATION_FILE" \
            --no-append 2>&1 | grep -E "LAW-|✅|🔴|⚠️  警告|所有.*通過" | head -20
    else
        echo "⚠️  找不到 hyperopt 結果檔案，跳過驗證"
    fi
    echo ""
fi

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
