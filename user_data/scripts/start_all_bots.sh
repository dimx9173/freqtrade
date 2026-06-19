#!/bin/bash
# ==============================================
# start_all_bots.sh v2
# 一鍵啟動 Freqtrade Bot（tmux 模式）
# 讀取 registry.json 作為 single source of truth
#
# 用法:
#   bash start_all_bots.sh        # 啟動全部 6 個 Bot
#   bash start_all_bots.sh 3      # 只啟動 Slot 3
#   bash start_all_bots.sh 1 3 5  # 只啟動 Slot 1, 3, 5
# ==============================================

set -e

SESSION="freqtrade_main"
BASE_DIR="$HOME/freqtrade"
REGISTRY="$BASE_DIR/user_data/config/prod/registry.json"
STRATEGY_BASE="user_data/strategies/prod"

# 檢查 registry.json 是否存在
if [[ ! -f "$REGISTRY" ]]; then
    echo "❌ 找不到 registry.json: $REGISTRY"
    exit 1
fi

# 從 registry.json 讀取 slots
SLOTS=$(jq -r '.slots | keys[]' "$REGISTRY" | sort -n)
FILTER_IDS=("$@")

# 建立 tmux session
tmux has-session -t "$SESSION" 2>/dev/null
if [[ $? != 0 ]]; then
    echo "建立新的 tmux session: $SESSION"
    tmux new-session -d -s "$SESSION" -n "base"
fi

for SLOT_ID in $SLOTS; do
    # 從 registry 讀取 slot 資訊
    NAME=$(jq -r ".slots.\"$SLOT_ID\".name" "$REGISTRY")
    PORT=$(jq -r ".slots.\"$SLOT_ID\".port" "$REGISTRY")
    DB=$(jq -r ".slots.\"$SLOT_ID\".db" "$REGISTRY")
    LOG=$(jq -r ".slots.\"$SLOT_ID\".log" "$REGISTRY")
    STRATEGY=$(jq -r ".slots.\"$SLOT_ID\".strategy" "$REGISTRY")
    CONFIG="slot_${SLOT_ID}.json"
    PARAMS=$(jq -r ".slots.\"$SLOT_ID\".params // empty" "$REGISTRY")

    # 若有指定 filter，只處理清單內的 ID
    if [[ ${#FILTER_IDS[@]} -gt 0 ]]; then
        SKIP=1
        for fid in "${FILTER_IDS[@]}"; do
            if [[ "$fid" == "$SLOT_ID" ]]; then
                SKIP=0
                break
            fi
        done
        [[ $SKIP -eq 1 ]] && continue
    fi

    # 檢查視窗是否存在，不存在則建立
    WINDOW_EXISTS=$(tmux list-windows -t "$SESSION" -F "#I" | grep -w "$SLOT_ID" || true)
    if [[ -z "$WINDOW_EXISTS" ]]; then
        echo "建立視窗 $SLOT_ID ($NAME)..."
        tmux new-window -t "$SESSION:$SLOT_ID" -n "$NAME"
    fi

    # 檢查進程是否已運行 (用 port 檢查更準確)
    if pgrep -f "freqtrade.*--config.*slot_${SLOT_ID}.json" > /dev/null; then
        echo "[Bot $SLOT_ID] $NAME — 已在運行中，跳過。"
    else
        echo "[Bot $SLOT_ID] $NAME — 未運行，正在啟動..."
        
        # 載入 prod/{strategy}.json (hyperopt 產出) 作為第二個 -c config
        PARAMS_FILE="$STRATEGY_BASE/$PARAMS"
        PARAMS_CONFIG=""
        if [[ -n "$PARAMS" && -f "$PARAMS_FILE" ]]; then
            PARAMS_CONFIG="-c $PARAMS_FILE"
            echo "[Bot $SLOT_ID] $NAME — 載入 hyperopt params: $PARAMS_FILE"
        elif [[ -n "$PARAMS" ]]; then
            echo "[Bot $SLOT_ID] $NAME — WARN: 無 $PARAMS_FILE, 將使用 .py defaults"
        fi
        
        # 組合啟動參數
        ARGS="--config user_data/config/prod/$CONFIG $PARAMS_CONFIG --db-url sqlite:///user_data/sqlite/$DB --logfile user_data/logs/$LOG --strategy-path $STRATEGY_BASE --strategy $STRATEGY"
        CMD="cd $BASE_DIR && source .venv/bin/activate && freqtrade --version && zsh user_data/scripts/utilities/monitor_run.sh \"freqtrade trade $ARGS\""
        tmux send-keys -t "$SESSION:$SLOT_ID" C-c C-u "$CMD" C-m
    fi
done

echo "---------------------------------------"
if [[ ${#FILTER_IDS[@]} -gt 0 ]]; then
    echo "已處理指定 Slots: ${FILTER_IDS[*]}"
else
    echo "已處理全部 Slots"
fi
echo "查看 tmux: tmux attach -t $SESSION"
echo ""
echo "Registry: $REGISTRY"
echo "策略位置: $BASE_DIR/$STRATEGY_BASE/"
