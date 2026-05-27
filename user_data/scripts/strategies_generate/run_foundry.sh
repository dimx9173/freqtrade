#!/bin/bash
# ============================================================================
# 策略鑄造廠啟動腳本 (The Foundry Launcher)
# 階段一：全自動化策略生成與海選
# ============================================================================

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FOUNDRY_DIR="${SCRIPT_DIR}/foundry"
LOG_DIR="${FOUNDRY_DIR}/logs"
PID_FILE="${LOG_DIR}/foundry.pid"
LOG_FILE="${LOG_DIR}/foundry_$(date +%Y%m%d).log"

# 確保目錄存在
mkdir -p "${LOG_DIR}"

# ============================================================================
# 函數定義
# ============================================================================

print_header() {
    echo -e "${CYAN}=====================================================================${NC}"
    echo -e "${CYAN}  🏭 策略鑄造廠 (The Foundry) - 階段一${NC}"
    echo -e "${CYAN}  全自動化策略生成與海選系統${NC}"
    echo -e "${CYAN}=====================================================================${NC}"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 檢查進程是否運行
is_running() {
    if [ -f "${PID_FILE}" ]; then
        local pid=$(cat "${PID_FILE}")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 啟動鑄造廠
start_foundry() {
    print_header
    echo ""

    if is_running; then
        print_warning "鑄造廠已經在運行中"
        print_info "PID: $(cat ${PID_FILE})"
        return 1
    fi

    # 驗證配置
    print_info "驗證配置..."
    cd "${FOUNDRY_DIR}"
    python3 foundry_config.py > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        print_error "配置驗證失敗"
        return 1
    fi
    print_status "配置驗證通過"

    # 啟動引擎
    print_info "啟動鑄造廠引擎..."
    nohup python3 foundry_engine.py > "${LOG_FILE}" 2>&1 &
    local pid=$!

    # 保存 PID
    echo "$pid" > "${PID_FILE}"

    # 等待啟動
    sleep 2

    if is_running; then
        print_status "鑄造廠啟動成功"
        echo ""
        print_info "PID: $pid"
        print_info "日誌: ${LOG_FILE}"
        echo ""
        print_info "查看實時日誌:"
        echo -e "  ${CYAN}tail -f ${LOG_FILE}${NC}"
        echo ""
        print_info "查看統計:"
        echo -e "  ${CYAN}$0 stats${NC}"
        echo ""
        print_info "停止運行:"
        echo -e "  ${CYAN}$0 stop${NC}"
        echo ""
    else
        print_error "鑄造廠啟動失敗"
        rm -f "${PID_FILE}"
        return 1
    fi
}

# 停止鑄造廠
stop_foundry() {
    print_header
    echo ""

    if ! is_running; then
        print_warning "鑄造廠未運行"
        return 1
    fi

    local pid=$(cat "${PID_FILE}")
    print_info "正在停止鑄造廠 (PID: $pid)..."

    # 嘗試優雅停止
    kill -15 "$pid" 2>/dev/null

    # 等待最多10秒
    for i in {1..10}; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            rm -f "${PID_FILE}"
            print_status "鑄造廠已停止"
            return 0
        fi
        sleep 1
    done

    # 強制停止
    print_warning "正在強制停止..."
    kill -9 "$pid" 2>/dev/null
    rm -f "${PID_FILE}"
    print_status "鑄造廠已強制停止"
}

# 查看狀態
status_foundry() {
    print_header
    echo ""

    if is_running; then
        local pid=$(cat "${PID_FILE}")
        print_status "鑄造廠運行中"
        print_info "PID: $pid"
        print_info "日誌: ${LOG_FILE}"

        # 顯示最近日誌
        echo ""
        echo -e "${CYAN}最近日誌：${NC}"
        tail -20 "${LOG_FILE}" 2>/dev/null || echo "無法讀取日誌"
    else
        print_warning "鑄造廠未運行"
    fi
}

# 查看統計
stats_foundry() {
    print_header
    echo ""

    local candidate_pool="${SCRIPT_DIR}/successful_strategies/candidate_pool"

    if [ ! -d "${candidate_pool}" ]; then
        print_warning "候選池目錄不存在"
        return 1
    fi

    local total_candidates=$(find "${candidate_pool}" -maxdepth 1 -type d | wc -l)
    total_candidates=$((total_candidates - 1))  # 排除目錄自身

    echo -e "${CYAN}=====================================================================${NC}"
    echo -e "${CYAN}  📊 鑄造廠統計報告${NC}"
    echo -e "${CYAN}=====================================================================${NC}"
    echo ""
    echo -e "${GREEN}✓${NC} 候選池策略數: ${MAGENTA}${total_candidates}${NC}"
    echo ""

    if [ $total_candidates -gt 0 ]; then
        echo -e "${CYAN}最近通過的策略：${NC}"
        find "${candidate_pool}" -maxdepth 1 -type d -name "candidate_*" | sort -r | head -5 | while read dir; do
            local name=$(basename "$dir")
            local metadata="${dir}/metadata.json"
            if [ -f "${metadata}" ]; then
                local indicators=$(jq -r '.indicators | join(", ")' "${metadata}" 2>/dev/null || echo "N/A")
                local win_rate=$(jq -r '.kpis."3m".win_rate // 0' "${metadata}" 2>/dev/null || echo "0")
                win_rate=$(echo "$win_rate * 100" | bc -l 2>/dev/null || echo "0")
                echo -e "  ${GREEN}•${NC} ${name}"
                echo -e "    指標: ${indicators}"
                echo -e "    勝率: ${win_rate}%"
            else
                echo -e "  ${GREEN}•${NC} ${name}"
            fi
        done
    fi

    echo ""
    echo -e "${CYAN}=====================================================================${NC}"
}

# 實時監控
watch_foundry() {
    print_header
    echo ""
    print_info "實時監控模式 (Ctrl+C 退出)"
    echo ""

    while true; do
        clear
        print_header
        echo ""

        if is_running; then
            print_status "運行中 (PID: $(cat ${PID_FILE}))"
        else
            print_error "未運行"
        fi

        echo ""
        echo -e "${CYAN}最近日誌：${NC}"
        tail -30 "${LOG_FILE}" 2>/dev/null || echo "無法讀取日誌"

        sleep 10
    done
}

# 清理舊日誌
cleanup_logs() {
    print_header
    echo ""
    print_info "清理 7 天前的日誌..."

    find "${LOG_DIR}" -name "foundry_*.log" -mtime +7 -delete

    print_status "清理完成"
}

# 顯示幫助
show_help() {
    print_header
    echo ""
    echo "用法: $0 {start|stop|restart|status|stats|watch|cleanup|help}"
    echo ""
    echo "命令說明:"
    echo "  start     - 啟動鑄造廠"
    echo "  stop      - 停止鑄造廠"
    echo "  restart   - 重啟鑄造廠"
    echo "  status    - 查看運行狀態"
    echo "  stats     - 查看統計報告"
    echo "  watch     - 實時監控"
    echo "  cleanup   - 清理舊日誌"
    echo "  help      - 顯示此幫助"
    echo ""
}

# ============================================================================
# 主邏輯
# ============================================================================

case "${1:-help}" in
    start)
        start_foundry
        ;;
    stop)
        stop_foundry
        ;;
    restart)
        stop_foundry
        sleep 2
        start_foundry
        ;;
    status)
        status_foundry
        ;;
    stats)
        stats_foundry
        ;;
    watch)
        watch_foundry
        ;;
    cleanup)
        cleanup_logs
        ;;
    help|*)
        show_help
        ;;
esac

exit 0
