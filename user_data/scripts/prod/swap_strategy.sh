#!/bin/bash
# ==============================================
# swap_strategy.sh v2
# 策略抽換腳本 (含 rollback + flock + 冪等性)
#
# 用法:
#   bash swap_strategy.sh <slot> <new_strategy>  # 抽換策略
#   bash swap_strategy.sh --status               # 查看狀態
#   bash swap_strategy.sh <slot> <new> --dry-run # 僅驗證不執行
# ==============================================

set -e

BASE_DIR="/home/brian/freqtrade"
REGISTRY="$BASE_DIR/user_data/config/prod/registry.json"
LOCK_FILE="$BASE_DIR/user_data/config/prod/registry.lock"
STRATEGY_BASE="$BASE_DIR/user_data/strategies/prod"
BACKUP_BASE="$BASE_DIR/user_data/backups/prod"

# === 輔助函數 ===

log_info() { echo "ℹ️  $1"; }
log_ok() { echo "✅ $1"; }
log_warn() { echo "⚠️  $1"; }
log_error() { echo "❌ $1"; }

cleanup() {
    # 釋放 flock
    flock -u 200 2>/dev/null || true
    rm -f "$LOCK_FILE"
}

trap cleanup EXIT

# === 參數解析 ===

DRY_RUN=false
SHOW_STATUS=false
SLOT=""
NEW_STRATEGY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --status)
            SHOW_STATUS=true
            shift
            ;;
        -*)
            log_error "未知選項: $1"
            exit 1
            ;;
        *)
            if [[ -z "$SLOT" ]]; then
                SLOT="$1"
            elif [[ -z "$NEW_STRATEGY" ]]; then
                NEW_STRATEGY="$1"
            fi
            shift
            ;;
    esac
done

# === 狀態顯示 ===

if $SHOW_STATUS; then
    echo "=== Slot 狀態 ==="
    jq -r '.slots | to_entries[] | "Slot \(.key): \(.value.name) (\(.value.strategy)) — \(.value.status)"' "$REGISTRY"
    exit 0
fi

# === 參數驗證 ===

if [[ -z "$SLOT" || -z "$NEW_STRATEGY" ]]; then
    log_error "用法: swap_strategy.sh <slot> <new_strategy> [--dry-run]"
    exit 1
fi

# === 取得 flock ===

exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    log_error "Registry 被鎖定，可能有其他 swap 正在執行"
    log_info "鎖檔案: $LOCK_FILE"
    exit 1
fi
log_info "已取得 registry lock"

# === 冪等性檢查 ===

CURRENT_STRATEGY=$(jq -r ".slots.\"$SLOT\".strategy" "$REGISTRY")
if [[ "$CURRENT_STRATEGY" == "$NEW_STRATEGY" ]]; then
    log_ok "Slot $SLOT 已經是 $NEW_STRATEGY，無需抽換"
    exit 0
fi

log_info "抽換 Slot $SLOT: $CURRENT_STRATEGY → $NEW_STRATEGY"

# === 驗證檔案存在 ===

log_info "驗證檔案..."

# 檢查新策略 .py
if [[ ! -f "$STRATEGY_BASE/$NEW_STRATEGY.py" ]]; then
    log_error "找不到策略檔案: $STRATEGY_BASE/$NEW_STRATEGY.py"
    exit 1
fi
log_ok "策略檔案存在: $NEW_STRATEGY.py"

# 檢查新策略 .json (參數檔)
if [[ ! -f "$STRATEGY_BASE/$NEW_STRATEGY.json" ]]; then
    log_warn "找不到參數檔: $STRATEGY_BASE/$NEW_STRATEGY.json (將使用 .py defaults)"
fi

# 檢查 config
if [[ ! -f "$BASE_DIR/user_data/config/prod/slot_${SLOT}.json" ]]; then
    log_error "找不到配置檔: slot_${SLOT}.json"
    exit 1
fi
log_ok "配置檔存在: slot_${SLOT}.json"

if $DRY_RUN; then
    log_ok "Dry-run 驗證通過，不執行實際抽換"
    exit 0
fi

# === 備份當前狀態 ===

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE/slot_${SLOT}_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

log_info "備份到 $BACKUP_DIR..."

cp "$REGISTRY" "$BACKUP_DIR/registry.json"
cp "$STRATEGY_BASE/$CURRENT_STRATEGY.py" "$BACKUP_DIR/" 2>/dev/null || true
cp "$STRATEGY_BASE/$CURRENT_STRATEGY.json" "$BACKUP_DIR/" 2>/dev/null || true
cp "$BASE_DIR/user_data/config/prod/slot_${SLOT}.json" "$BACKUP_DIR/"

log_ok "備份完成"

# === 更新 Registry (status = swapping) ===

log_info "更新 registry (status = swapping)..."
TEMP_REGISTRY=$(mktemp)
jq ".slots.\"$SLOT\".status = \"swapping\" | .slots.\"$SLOT\".strategy = \"$NEW_STRATEGY\" | .slots.\"$SLOT\".last_deployed = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$REGISTRY" > "$TEMP_REGISTRY"
mv "$TEMP_REGISTRY" "$REGISTRY"

# === 停止 Bot ===

log_info "停止 Slot $SLOT..."
STOP_CMD="pkill -f 'freqtrade.*slot_${SLOT}.json' || true"
eval "$STOP_CMD"
sleep 5

# 確認已停止
if pgrep -f "freqtrade.*slot_${SLOT}.json" > /dev/null; then
    log_warn "Bot 未完全停止，強制終止..."
    pkill -9 -f "freqtrade.*slot_${SLOT}.json" || true
    sleep 2
fi
log_ok "Bot 已停止"

# === 日誌輪替 ===

LOG_FILE=$(jq -r ".slots.\"$SLOT\".log" "$REGISTRY")
if [[ -f "$BASE_DIR/user_data/logs/$LOG_FILE" ]]; then
    mv "$BASE_DIR/user_data/logs/$LOG_FILE" "$BASE_DIR/user_data/logs/${LOG_FILE%.log}_${TIMESTAMP}.log"
    log_info "日誌已輪替"
fi

# === 啟動 Bot ===

log_info "啟動 Slot $SLOT with $NEW_STRATEGY..."
DB=$(jq -r ".slots.\"$SLOT\".db" "$REGISTRY")
LOG=$(jq -r ".slots.\"$SLOT\".log" "$REGISTRY")
PORT=$(jq -r ".slots.\"$SLOT\".port" "$REGISTRY")

START_CMD="cd $BASE_DIR && source .venv/bin/activate && freqtrade trade --config user_data/config/prod/slot_${SLOT}.json -c user_data/strategies/prod/${NEW_STRATEGY}.json --db-url sqlite:///user_data/sqlite/$DB --logfile user_data/logs/$LOG --strategy-path user_data/strategies/prod --strategy $NEW_STRATEGY"

# 在背景啟動
nohup bash -c "$START_CMD" > /dev/null 2>&1 &

# === Health Check (重試 3 次) ===

log_info "Health check..."
HEALTHY=false
for i in 1 2 3; do
    sleep 5
    if curl -s "http://127.0.0.1:$PORT/api/v1/ping" > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    log_warn "Health check 失敗 ($i/3)，重試..."
done

if $HEALTHY; then
    log_ok "Health check 通過"
    
    # 更新 registry status = running
    TEMP_REGISTRY=$(mktemp)
    jq ".slots.\"$SLOT\".status = \"running\"" "$REGISTRY" > "$TEMP_REGISTRY"
    mv "$TEMP_REGISTRY" "$REGISTRY"
    
    # Git commit
    cd "$BASE_DIR"
    git add user_data/config/prod/registry.json
    git commit --no-verify -m "auto(prod): swap slot_${SLOT} $CURRENT_STRATEGY → $NEW_STRATEGY @ $TIMESTAMP" 2>/dev/null || true
    
    log_ok "抽換完成！"
else
    log_error "Health check 失敗，觸發 rollback..."
    
    # === Rollback ===
    log_info "還原備份..."
    cp "$BACKUP_DIR/registry.json" "$REGISTRY"
    
    # 重新啟動舊 bot
    OLD_STRATEGY="$CURRENT_STRATEGY"
    OLD_DB=$(jq -r ".slots.\"$SLOT\".db" "$REGISTRY")
    OLD_LOG=$(jq -r ".slots.\"$SLOT\".log" "$REGISTRY")
    
    START_CMD="cd $BASE_DIR && source .venv/bin/activate && freqtrade trade --config user_data/config/prod/slot_${SLOT}.json --db-url sqlite:///user_data/sqlite/$OLD_DB --logfile user_data/logs/$OLD_LOG --strategy-path user_data/strategies/prod --strategy $OLD_STRATEGY"
    nohup bash -c "$START_CMD" > /dev/null 2>&1 &
    
    sleep 5
    
    # 更新 registry status = error
    TEMP_REGISTRY=$(mktemp)
    jq ".slots.\"$SLOT\".status = \"error\"" "$REGISTRY" > "$TEMP_REGISTRY"
    mv "$TEMP_REGISTRY" "$REGISTRY"
    
    log_error "Rollback 完成，Slot $SLOT 狀態設為 error"
    log_info "請檢查日誌: user_data/logs/$OLD_LOG"
    exit 1
fi
