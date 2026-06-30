#!/bin/zsh
# start_all_bots.sh
# 啟動所有 freqtrade bots
# 用法: zsh start_all_bots.sh

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
FREQTRADE_DIR=$(dirname $(dirname $(dirname "$SCRIPT_DIR")))
MONITOR="$SCRIPT_DIR/monitor_run.sh"
LOG_DIR="$FREQTRADE_DIR/user_data/logs"

cd "$FREQTRADE_DIR"
source .venv/bin/activate

# Load slot-bound secrets (rollstr integration 2026-06-30)
if [[ -f "$FREQTRADE_DIR/.env" ]]; then
    set -a
    source "$FREQTRADE_DIR/.env"
    set +a
    echo "✅ Secrets loaded from .env"
else
    echo "⚠️  No .env at $FREQTRADE_DIR/.env - bot will fail to authenticate"
fi

start_bot() {
    local config=$1
    local strategy=$2
    local db=$3
    local log_name=$4

    local cmd="freqtrade trade --config user_data/config/$config --strategy $strategy --strategy-path user_data/strategies/prod --db-url sqlite:///user_data/sqlite/$db --logfile user_data/logs/freqtrade_$log_name.log"

    echo "Starting bot: $strategy ($config, $db)"
    nohup zsh "$MONITOR" "$cmd" >> "$LOG_DIR/startup_$log_name.log" 2>&1 &
}

#  Bot 1: NASOSv4
start_bot "config_1.tmpl.json" "NASOSv4" "tradesv3_1.sqlite" "NASOSv4"


#  Bot 3: BB_RPB_TSL_BI
start_bot "config_3.tmpl.json" "BB_RPB_TSL_BI" "tradesv3_3.sqlite" "BB_RPB_TSL_BI"

#  Bot 4: NASOSv5_mod3
start_bot "config_4.tmpl.json" "NASOSv5_mod3" "tradesv3_4.sqlite" "NASOSv5_mod3"

#  Bot 5: SMAOffsetProtectOptV1
start_bot "config_5.tmpl.json" "SMAOffsetProtectOptV1" "tradesv3_5.sqlite" "SMAOffsetProtectOptV1"

#  Bot 6: ElliotV5_SMA_ninja
start_bot "config_6.tmpl.json" "ElliotV5_SMA_ninja" "tradesv3_6.sqlite" "ElliotV5_SMA_ninja"

#  Bot 2: PSV5_Hybrid — DORMANT (Brian 2026-06-30: 缺好策略前不上)
#  Template + secrets 已就位,等決定策略再加
# start_bot "config_2.tmpl.json" "PSV5_Hybrid" "tradesv3_uat.sqlite" "PSV5_Hybrid"

#  Bot 7: PLACEHOLDER - strategy TBD; uncomment when finalized
# start_bot "config_7.tmpl.json" "PLACEHOLDER_STRATEGY" "tradesv3_7.sqlite" "PLACEHOLDER"

echo "All bots started. Check logs in $LOG_DIR/"
