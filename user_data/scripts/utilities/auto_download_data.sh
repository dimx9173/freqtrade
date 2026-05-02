#!/bin/zsh
# ==============================================
# Auto Download Data - 每日自動下載 K 線資料
# 用法: zsh auto_download_data.sh
# ==============================================

HOME=/home/brian
cd $HOME/freqtrade
source .venv/bin/activate

LOGFILE="user_data/logs/auto_crontab.log"
mkdir -p user_data/logs

echo "========================================" | tee -a "$LOGFILE"
echo "auto_download_data start at $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# 1. 生成最新 pairlist
echo "[1/4] Generating pairlist..." | tee -a "$LOGFILE"
python user_data/scripts/utilities/gen_pairlist.py 2>&1 | tee -a "$LOGFILE"
if [[ ${pipestatus[1]:-$?} -ne 0 ]]; then
    echo "ERROR: gen_pairlist.py failed!" | tee -a "$LOGFILE"
fi

# 2. 計算 timerange（2 個月，避免 Bybit 歷史上限）
TIME_RANGE=$(zsh user_data/scripts/utilities/get_time_range.sh)
echo "[2/4] Timerange: $TIME_RANGE" | tee -a "$LOGFILE"

# 3. 逐個 timeframe 下載 spot 資料（避免 rate limit）
# 注意：config.json 有 defaultType: swap，所以必須明確指定 --trade-mode spot
echo "[3/4] Downloading spot data..." | tee -a "$LOGFILE"
for tf in 5m 15m 30m 1h 4h 12h 1d; do
    echo "  Downloading spot $tf..." | tee -a "$LOGFILE"
    freqtrade download-data \
        --exchange bybit \
        --trading-mode spot \
        --pairs-file "$HOME/freqtrade/user_data/config/coinmarketcap-pairs.json" \
        --timerange "$TIME_RANGE" \
        --timeframe "$tf" \
        --data-format-ohlcv feather \
        2>&1 | tail -10 | tee -a "$LOGFILE"
    EXIT_CODE=${pipestatus[1]:-$?}
    if [[ $EXIT_CODE -ne 0 ]]; then
        echo "  WARNING: spot $tf download failed (exit: $EXIT_CODE)" | tee -a "$LOGFILE"
    fi
    sleep 3  # 避免 rate limit
done

# 4. 逐個 timeframe 下載 futures 資料（不含 funding_rate，避免混淆）
echo "[4/4] Downloading futures data..." | tee -a "$LOGFILE"
for tf in 5m 15m 30m 1h 4h 12h 1d; do
    echo "  Downloading futures $tf..." | tee -a "$LOGFILE"
    freqtrade download-data \
        --exchange bybit \
        --trading-mode futures \
        --pairs-file "$HOME/freqtrade/user_data/config/coinmarketcap-future-pairs.json" \
        --timerange "$TIME_RANGE" \
        --timeframe "$tf" \
        --data-format-ohlcv feather \
        2>&1 | tail -10 | tee -a "$LOGFILE"

    EXIT_CODE=${pipestatus[1]:-$?}
    if [[ $EXIT_CODE -ne 0 ]]; then
        echo "  WARNING: futures $tf download failed (exit: $EXIT_CODE)" | tee -a "$LOGFILE"
    fi
    sleep 3
done

# 5. 驗證下載結果
echo "---" | tee -a "$LOGFILE"
echo "Data verification:" | tee -a "$LOGFILE"
LATEST_5M=$(ls -lt user_data/data/bybit/*5m.feather 2>/dev/null | head -1 | awk '{print $6, $7, $8}')
LATEST_15M=$(ls -lt user_data/data/bybit/*15m.feather 2>/dev/null | head -1 | awk '{print $6, $7, $8}')
echo "  Latest 5m data: $LATEST_5M" | tee -a "$LOGFILE"
echo "  Latest 15m data: $LATEST_15M" | tee -a "$LOGFILE"

if [[ -z "$LATEST_5M" ]]; then
    echo "  ERROR: No 5m data found!" | tee -a "$LOGFILE"
elif [[ "$LATEST_5M" != *"Apr"* ]] && [[ "$LATEST_5M" != *"May"* ]]; then
    echo "  WARNING: 5m data may be stale!" | tee -a "$LOGFILE"
fi

echo "auto_download_data finished at $(date)" | tee -a "$LOGFILE"
echo "-----------------------------" | tee -a "$LOGFILE"
