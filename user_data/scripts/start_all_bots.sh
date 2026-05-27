#!/bin/bash
# ==============================================
# start_all_bots.sh
# 一鍵啟動 Freqtrade Bot（tmux 模式）
# 用法:
#   bash start_all_bots.sh        # 啟動全部 5 個 Bot
#   bash start_all_bots.sh 3      # 只啟動 Slot 3 (BB_RPB_TSL_BI)
#   bash start_all_bots.sh 1 3 5  # 只啟動 Slot 1, 3, 5
# ==============================================

SESSION="freqtrade_main"
BASE_DIR="$HOME/freqtrade"
STRATEGY_BASE="user_data/strategies/prod"   # 策略統一放在 prod/

# 定義任務列表 (ID|視窗名|設定檔|DB檔|Log檔|策略名|策略檔)
TASKS=(
    "1|NASOSv4|config_1.json|tradesv3_1.sqlite|freqtrade_1.log|NASOSv4|NASOSv4.py"
    "2|PSV5_Hybrid|config_2.json|tradesv3_uat.sqlite|freqtrade_uat_PSV5_Hybrid.log|PSV5_Hybrid|PSV5_Hybrid.py"
    "3|BB_RPB_TSL_BI|config_3.json|tradesv3_3.sqlite|freqtrade_3.log|BB_RPB_TSL_BI|BB_RPB_TSL_BI.py"
    "4|NASOSv5_mod3|config_4.json|tradesv3_4.sqlite|freqtrade_4.log|NASOSv5_mod3|NASOSv5_mod3.py"
    "5|SMAOffsetProtectOptV1|config_5.json|tradesv3_5.sqlite|freqtrade_5.log|SMAOffsetProtectOptV1|SMAOffsetProtectOptV1.py"
    "6|ElliotV5_SMA_ninja|config_6.json|tradesv3_6.sqlite|freqtrade_6.log|ElliotV5_SMA_ninja|ElliotV5_SMA_ninja.py"
)

FILTER_IDS=("$@")

# 建立 tmux session
tmux has-session -t "$SESSION" 2>/dev/null
if [[ $? != 0 ]]; then
    echo "建立新的 tmux session: $SESSION"
    tmux new-session -d -s "$SESSION" -n "base"
fi

for task in "${TASKS[@]}"; do
    IFS='|' read -r ID NAME CONFIG DB LOG STRAT STRATFILE <<< "$task"

    # 若有指定 filter，只處理清單內的 ID
    if [[ ${#FILTER_IDS[@]} -gt 0 ]]; then
        SKIP=1
        for fid in "${FILTER_IDS[@]}"; do
            if [[ "$fid" == "$ID" ]]; then
                SKIP=0
                break
            fi
        done
        [[ $SKIP -eq 1 ]] && continue
    fi

    # 檢查視窗是否存在，不存在則建立
    WINDOW_EXISTS=$(tmux list-windows -t "$SESSION" -F "#I" | grep -w "$ID")
    if [[ -z "$WINDOW_EXISTS" ]]; then
        echo "建立視窗 $ID ($NAME)..."
        tmux new-window -t "$SESSION:$ID" -n "$NAME"
    fi

    # 檢查進程是否已運行
    if pgrep -f "freqtrade.*$CONFIG" > /dev/null; then
        echo "[Bot $ID] $NAME — 已在運行中，跳過。"
    else
        echo "[Bot $ID] $NAME — 未運行，正在啟動..."
        ARGS="--config user_data/config/$CONFIG --db-url sqlite:///user_data/sqlite/$DB --logfile user_data/logs/$LOG --strategy-path $STRATEGY_BASE --strategy $STRAT"
        CMD="cd $BASE_DIR && source .venv/bin/activate && freqtrade --version && zsh user_data/scripts/utilities/monitor_run.sh \"freqtrade trade $ARGS\""
        tmux send-keys -t "$SESSION:$ID" C-c C-u "$CMD" C-m
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
echo "策略位置: $STRATEGY_BASE/"
ls "$BASE_DIR/$STRATEGY_BASE/" 2>/dev/null
