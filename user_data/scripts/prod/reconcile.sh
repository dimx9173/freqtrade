#!/bin/bash
# ==============================================
# reconcile.sh
# 強制同步 registry ↔ 實際狀態
#
# 用法:
#   bash reconcile.sh              # 偵測漂移
#   bash reconcile.sh --apply      # 以實際狀態為準更新 registry
# ==============================================

set -e

BASE_DIR="/home/brian/freqtrade"
REGISTRY="$BASE_DIR/user_data/config/prod/registry.json"
LOCK_FILE="$BASE_DIR/user_data/config/prod/registry.lock"

APPLY=false
if [[ "$1" == "--apply" ]]; then
    APPLY=true
fi

# 取得 flock
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "❌ Registry 被鎖定"
    exit 1
fi

cleanup() {
    flock -u 200 2>/dev/null || true
}
trap cleanup EXIT

echo "=== 狀態漂移偵測 ==="
echo ""

DRIFT_COUNT=0

# 讀取 registry slots
SLOTS=$(jq -r '.slots | keys[]' "$REGISTRY" | sort -n)

for SLOT_ID in $SLOTS; do
    NAME=$(jq -r ".slots.\"$SLOT_ID\".name" "$REGISTRY")
    PORT=$(jq -r ".slots.\"$SLOT_ID\".port" "$REGISTRY")
    EXPECTED_STRATEGY=$(jq -r ".slots.\"$SLOT_ID\".strategy" "$REGISTRY")
    EXPECTED_STATUS=$(jq -r ".slots.\"$SLOT_ID\".status" "$REGISTRY")
    
    # 檢查 process 是否存在
    ACTUAL_RUNNING=false
    ACTUAL_STRATEGY=""
    
    PID=$(pgrep -f "freqtrade.*slot_${SLOT_ID}.json" 2>/dev/null || true)
    if [[ -n "$PID" ]]; then
        ACTUAL_RUNNING=true
        # 從 cmdline 提取策略名稱
        CMDLINE=$(cat /proc/$PID/cmdline 2>/dev/null | tr '\0' ' ' || true)
        ACTUAL_STRATEGY=$(echo "$CMDLINE" | grep -oP '(?<=--strategy\s)\S+' || true)
    fi
    
    # 檢查漂移
    DRIFTED=false
    
    # 狀態漂移
    if [[ "$EXPECTED_STATUS" == "running" ]] && ! $ACTUAL_RUNNING; then
        echo "⚠️  Slot $SLOT_ID ($NAME): registry=running, actual=stopped"
        DRIFTED=true
        DRIFT_COUNT=$((DRIFT_COUNT + 1))
        
        if $APPLY; then
            TEMP=$(mktemp)
            jq ".slots.\"$SLOT_ID\".status = \"stopped\"" "$REGISTRY" > "$TEMP"
            mv "$TEMP" "$REGISTRY"
            echo "   → 已更新 registry: status=stopped"
        fi
    elif [[ "$EXPECTED_STATUS" == "stopped" ]] && $ACTUAL_RUNNING; then
        echo "⚠️  Slot $SLOT_ID ($NAME): registry=stopped, actual=running"
        DRIFTED=true
        DRIFT_COUNT=$((DRIFT_COUNT + 1))
        
        if $APPLY; then
            TEMP=$(mktemp)
            jq ".slots.\"$SLOT_ID\".status = \"running\"" "$REGISTRY" > "$TEMP"
            mv "$TEMP" "$REGISTRY"
            echo "   → 已更新 registry: status=running"
        fi
    elif [[ "$EXPECTED_STATUS" == "error" ]] && $ACTUAL_RUNNING; then
        echo "⚠️  Slot $SLOT_ID ($NAME): registry=error, actual=running"
        DRIFTED=true
        DRIFT_COUNT=$((DRIFT_COUNT + 1))
        
        if $APPLY; then
            TEMP=$(mktemp)
            jq ".slots.\"$SLOT_ID\".status = \"running\"" "$REGISTRY" > "$TEMP"
            mv "$TEMP" "$REGISTRY"
            echo "   → 已更新 registry: status=running"
        fi
    fi
    
    # 策略漂移
    if $ACTUAL_RUNNING && [[ -n "$ACTUAL_STRATEGY" ]] && [[ "$ACTUAL_STRATEGY" != "$EXPECTED_STRATEGY" ]]; then
        echo "⚠️  Slot $SLOT_ID ($NAME): registry=$EXPECTED_STRATEGY, actual=$ACTUAL_STRATEGY"
        DRIFTED=true
        DRIFT_COUNT=$((DRIFT_COUNT + 1))
        
        if $APPLY; then
            TEMP=$(mktemp)
            jq ".slots.\"$SLOT_ID\".strategy = \"$ACTUAL_STRATEGY\"" "$REGISTRY" > "$TEMP"
            mv "$TEMP" "$REGISTRY"
            echo "   → 已更新 registry: strategy=$ACTUAL_STRATEGY"
        fi
    fi
    
    # 正常狀態
    if ! $DRIFTED; then
        if $ACTUAL_RUNNING; then
            echo "✅ Slot $SLOT_ID ($NAME): running, strategy=$EXPECTED_STRATEGY"
        else
            echo "⏸️  Slot $SLOT_ID ($NAME): stopped"
        fi
    fi
done

echo ""
echo "=== 總結 ==="
if [[ $DRIFT_COUNT -eq 0 ]]; then
    echo "✅ 無漂移，registry 與實際狀態一致"
else
    echo "⚠️  偵測到 $DRIFT_COUNT 處漂移"
    if ! $APPLY; then
        echo ""
        echo "執行 \`bash reconcile.sh --apply\` 以實際狀態為準更新 registry"
    else
        # 更新 last_reconciled
        TEMP=$(mktemp)
        jq ".last_reconciled = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" "$REGISTRY" > "$TEMP"
        mv "$TEMP" "$REGISTRY"
        
        # Git commit
        cd "$BASE_DIR"
        git add user_data/config/prod/registry.json
        git commit --no-verify -m "auto(prod): reconcile registry @ $(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
        echo "✅ Registry 已同步並 commit"
    fi
fi
