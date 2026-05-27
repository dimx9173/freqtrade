#!/bin/bash
# ============================================================================
# 精煉工坊啟動腳本 (The Refinery Launcher)
# 階段二：半自動化潛力優化
# ============================================================================

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REFINERY_DIR="${SCRIPT_DIR}/refinery"
LOG_DIR="${REFINERY_DIR}/logs"
LOG_FILE="${LOG_DIR}/refinery_$(date +%Y%m%d_%H%M%S).log"

# 確保目錄存在
mkdir -p "${LOG_DIR}"

# ============================================================================
# 函數定義
# ============================================================================

print_header() {
    echo -e "${MAGENTA}=====================================================================${NC}"
    echo -e "${MAGENTA}  🔧 精煉工坊 (The Refinery) - 階段二${NC}"
    echo -e "${MAGENTA}  半自動化潛力優化系統${NC}"
    echo -e "${MAGENTA}=====================================================================${NC}"
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

# 驗證配置
validate_config() {
    cd "${REFINERY_DIR}"
    python3 refinery_config.py > /dev/null 2>&1
    return $?
}

# 運行優化
run_optimization() {
    local max_strategies=${1:-5}

    print_header
    echo ""

    print_info "驗證配置..."
    if ! validate_config; then
        print_error "配置驗證失敗"
        return 1
    fi
    print_status "配置驗證通過"
    echo ""

    print_info "開始優化候選策略 (最多 ${max_strategies} 個)..."
    echo ""

    cd "${REFINERY_DIR}"
    python3 refinery_engine.py 2>&1 | tee "${LOG_FILE}"

    local exit_code=${PIPESTATUS[0]}

    echo ""
    if [ $exit_code -eq 0 ]; then
        print_status "優化完成"
        print_info "日誌已保存: ${LOG_FILE}"
    else
        print_error "優化過程中發生錯誤"
        print_info "查看日誌: ${LOG_FILE}"
        return 1
    fi
}

# 查看統計
show_stats() {
    print_header
    echo ""

    local optimized_dir="${SCRIPT_DIR}/successful_strategies/optimized_candidates"

    if [ ! -d "${optimized_dir}" ]; then
        print_warning "優化池目錄不存在"
        return 1
    fi

    local total_optimized=$(find "${optimized_dir}" -maxdepth 1 -type d -name "optimized_*" | wc -l)

    echo -e "${CYAN}=====================================================================${NC}"
    echo -e "${CYAN}  📊 精煉工坊統計報告${NC}"
    echo -e "${CYAN}=====================================================================${NC}"
    echo ""
    echo -e "${GREEN}✓${NC} 優化策略數: ${MAGENTA}${total_optimized}${NC}"
    echo ""

    if [ $total_optimized -gt 0 ]; then
        echo -e "${CYAN}最近優化的策略：${NC}"
        find "${optimized_dir}" -maxdepth 1 -type d -name "optimized_*" | sort -r | head -5 | while read dir; do
            local name=$(basename "$dir")
            local report="${dir}/optimization_report.json"
            if [ -f "${report}" ]; then
                local sharpe_before=$(jq -r '.performance_comparison.sharpe_before // 0' "${report}" 2>/dev/null || echo "0")
                local sharpe_after=$(jq -r '.performance_comparison.sharpe_after // 0' "${report}" 2>/dev/null || echo "0")
                local improvement=$(jq -r '.performance_comparison.sharpe_improvement // 0' "${report}" 2>/dev/null || echo "0")
                improvement=$(echo "$improvement * 100" | bc -l 2>/dev/null || echo "0")

                echo -e "  ${GREEN}•${NC} ${name}"
                echo -e "    夏普: ${sharpe_before} → ${sharpe_after} (+${improvement}%)"
            else
                echo -e "  ${GREEN}•${NC} ${name}"
            fi
        done
    fi

    echo ""
    echo -e "${CYAN}=====================================================================${NC}"
}

# 顯示幫助
show_help() {
    print_header
    echo ""
    echo "用法: $0 {run|stats|help} [選項]"
    echo ""
    echo "命令說明:"
    echo "  run [N]   - 運行優化 (可選：最多優化 N 個策略，默認 5)"
    echo "  stats     - 查看統計報告"
    echo "  help      - 顯示此幫助"
    echo ""
    echo "範例:"
    echo "  $0 run        # 優化最多 5 個策略"
    echo "  $0 run 10     # 優化最多 10 個策略"
    echo "  $0 stats      # 查看統計"
    echo ""
}

# ============================================================================
# 主邏輯
# ============================================================================

case "${1:-help}" in
    run)
        run_optimization "${2:-5}"
        ;;
    stats)
        show_stats
        ;;
    help|*)
        show_help
        ;;
esac

exit 0
