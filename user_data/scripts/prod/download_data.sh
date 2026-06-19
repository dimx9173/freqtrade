#!/bin/bash
# ==============================================
# download_data.sh v2
# 統一 futures 資料下載 (含 flock + 完整性檢查)
#
# 用法:
#   bash download_data.sh              # 下載最近 7 天
#   bash download_data.sh --days 14    # 下載最近 14 天
#   bash download_data.sh --full       # 下載完整歷史
# ==============================================

set -e

BASE_DIR="/home/brian/freqtrade"
REGISTRY="$BASE_DIR/user_data/config/prod/registry.json"
DATADIR="$BASE_DIR/user_data/data/bybit/futures"
LOCK_FILE="/tmp/freqtrade_download.lock"
FREQTRADE_BIN="$BASE_DIR/.venv/bin/freqtrade"
VALIDATE_SCRIPT="$BASE_DIR/user_data/scripts/prod/validate_data.py"

# === 參數解析 ===

DAYS=7
FULL_HISTORY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --days)
            DAYS="$2"
            shift 2
            ;;
        --full)
            FULL_HISTORY=true
            shift
            ;;
        *)
            echo "未知選項: $1"
            exit 1
            ;;
    esac
done

# === 排程鎖 (防 cron 與手動同時執行) ===

exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "❌ 另一個下載任務正在執行"
    exit 1
fi

cleanup() {
    flock -u 200 2>/dev/null || true
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

echo "=== 統一 Futures 資料下載 ==="
echo "目錄: $DATADIR"

# === 從 registry 收集 pairs + timeframes ===

PAIRS=$(jq -r '.slots[].pairs[]?' "$REGISTRY" 2>/dev/null | sort -u | tr '\n' ' ')
TIMEFRAMES=$(jq -r '.slots[].timeframes[]?' "$REGISTRY" 2>/dev/null | sort -u | tr '\n' ' ')

# 如果 registry 沒有 pairs/timeframes，使用預設值
if [[ -z "$PAIRS" ]]; then
    echo "⚠️  Registry 沒有 pairs，使用預設值"
    PAIRS="BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT XRP/USDT:USDT BNB/USDT:USDT"
fi

if [[ -z "$TIMEFRAMES" ]]; then
    echo "⚠️  Registry 沒有 timeframes，使用預設值"
    TIMEFRAMES="5m"
fi

echo "交易對: $PAIRS"
echo "時間週期: $TIMEFRAMES"

# === 計算時間範圍 ===

if $FULL_HISTORY; then
    echo "模式: 完整歷史"
    TIMERANGE="20200101-$(date +%Y%m%d)"
else
    END_DATE=$(date +%Y%m%d)
    START_DATE=$(date -d "$DAYS days ago" +%Y%m%d)
    TIMERANGE="${START_DATE}-${END_DATE}"
    echo "模式: 最近 $DAYS 天 ($TIMERANGE)"
fi

# === 建立資料目錄 ===

mkdir -p "$DATADIR"

# === 下載資料 (失敗重試 3 次) ===

MAX_RETRIES=3
DOWNLOAD_SUCCESS=false

for attempt in $(seq 1 $MAX_RETRIES); do
    echo ""
    echo "--- 下載嘗試 $attempt/$MAX_RETRIES ---"
    
    if $FREQTRADE_BIN download-data \
        --pairs $PAIRS \
        --timeframes $TIMEFRAMES \
        --trading-mode futures \
        --timerange "$TIMERANGE" \
        --datadir "$DATADIR" \
        --prepend \
        --exchange bybit; then
        DOWNLOAD_SUCCESS=true
        break
    else
        echo "⚠️  下載失敗，等待 10 秒後重試..."
        sleep 10
    fi
done

if ! $DOWNLOAD_SUCCESS; then
    echo "❌ 下載失敗，已嘗試 $MAX_RETRIES 次"
    exit 1
fi

echo ""
echo "✅ 下載完成"

# === 移動可能寫到子目錄的檔案 ===

if [ -d "$DATADIR/futures" ]; then
    echo "🔄 移動子目錄資料..."
    for f in "$DATADIR/futures"/*-futures.feather; do
        if [ -f "$f" ]; then
            basename=$(basename "$f")
            mv "$f" "$DATADIR/$basename"
            echo "  移動: $basename"
        fi
    done
    rmdir "$DATADIR/futures" 2>/dev/null || true
fi

# === 完整性檢查 ===

echo ""
echo "=== 完整性驗證 ==="

# 提取 pair 名稱 (BTC/USDT:USDT → BTC)
PAIR_NAMES=$(echo "$PAIRS" | tr ' ' '\n' | sed 's|/.*||' | tr '\n' ' ')

python3 "$VALIDATE_SCRIPT" \
    --datadir "$DATADIR" \
    --pairs $PAIR_NAMES \
    --timeframes $TIMEFRAMES \
    --min-rows-per-day 288

VALIDATE_RC=$?

if [ $VALIDATE_RC -ne 0 ]; then
    echo ""
    echo "⚠️  完整性驗證失敗，部分資料可能不完整"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ 下載並驗證完成！"
echo "=========================================="
