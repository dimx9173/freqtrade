#!/bin/zsh
# ==============================================
# Auto Download Data - 每日自動下載 K 線資料
# 包含 Spot + Futures，保留歷史資料
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
echo "[1/5] Generating pairlist..." | tee -a "$LOGFILE"
python user_data/scripts/utilities/gen_pairlist.py 2>&1 | tee -a "$LOGFILE"
if [[ ${pipestatus[1]:-$?} -ne 0 ]]; then
    echo "ERROR: gen_pairlist.py failed!" | tee -a "$LOGFILE"
fi

# 2. 計算 timerange
# Spot: 2 個月
# Futures: 6 個月
SPOT_TIME_RANGE=$(zsh user_data/scripts/utilities/get_time_range.sh 2)
FUTURES_TIME_RANGE=$(zsh user_data/scripts/utilities/get_time_range.sh 6)
echo "[2/5] Spot Timerange: $SPOT_TIME_RANGE" | tee -a "$LOGFILE"
echo "[2/5] Futures Timerange: $FUTURES_TIME_RANGE" | tee -a "$LOGFILE"

# 3. 下載 spot 資料（使用 --prepend 保留歷史）
echo "[3/5] Downloading spot data..." | tee -a "$LOGFILE"
for tf in 5m 15m 30m 1h 4h 12h 1d; do
    echo "  Downloading spot $tf..." | tee -a "$LOGFILE"
    freqtrade download-data \
        --exchange bybit \
        --trading-mode spot \
        --pairs-file "$HOME/freqtrade/user_data/config/coinmarketcap-pairs.json" \
        --timerange "$SPOT_TIME_RANGE" \
        --timeframe "$tf" \
        --data-format-ohlcv feather \
        --prepend \
        2>&1 | tail -10 | tee -a "$LOGFILE"
    EXIT_CODE=${pipestatus[1]:-$?}
    if [[ $EXIT_CODE -ne 0 ]]; then
        echo "  WARNING: spot $tf download failed (exit: $EXIT_CODE)" | tee -a "$LOGFILE"
    fi
    sleep 3
done

# 4. 下載 futures 資料（使用 --prepend 保留歷史）
echo "[4/5] Downloading futures data..." | tee -a "$LOGFILE"
for tf in 5m 15m 30m 1h 4h 12h 1d; do
    echo "  Downloading futures $tf..." | tee -a "$LOGFILE"
    freqtrade download-data \
        --exchange bybit \
        --trading-mode futures \
        --pairs-file "$HOME/freqtrade/user_data/config/coinmarketcap-future-pairs.json" \
        --timerange "$FUTURES_TIME_RANGE" \
        --timeframe "$tf" \
        --data-format-ohlcv feather \
        --prepend \
        2>&1 | tail -10 | tee -a "$LOGFILE"
    EXIT_CODE=${pipestatus[1]:-$?}
    if [[ $EXIT_CODE -ne 0 ]]; then
        echo "  WARNING: futures $tf download failed (exit: $EXIT_CODE)" | tee -a "$LOGFILE"
    fi
    sleep 3
done

# 5. 驗證下載結果
echo "---" | tee -a "$LOGFILE"
echo "[5/5] Data verification:" | tee -a "$LOGFILE"
SPOT_COUNT=$(ls user_data/data/bybit/*_USDT-5m.feather 2>/dev/null | grep -v "futures" | wc -l)
FUTURES_COUNT=$(ls user_data/data/bybit/futures/*_USDT_USDT-5m-futures.feather 2>/dev/null | wc -l)
echo "  Spot 5m pairs: $SPOT_COUNT" | tee -a "$LOGFILE"
echo "  Futures 5m pairs: $FUTURES_COUNT" | tee -a "$LOGFILE"

# 顯示最舊和最新資料日期
OLDEST_SPOT=$(python3 -c "import pandas as pd; df=pd.read_feather('user_data/data/bybit/BTC_USDT-5m.feather'); print(df.iloc[0]['date'])" 2>/dev/null || echo "N/A")
NEWEST_SPOT=$(python3 -c "import pandas as pd; df=pd.read_feather('user_data/data/bybit/BTC_USDT-5m.feather'); print(df.iloc[-1]['date'])" 2>/dev/null || echo "N/A")
echo "  Spot BTC range: $OLDEST_SPOT ~ $NEWEST_SPOT" | tee -a "$LOGFILE"

if [[ "$FUTURES_COUNT" -lt 5 ]]; then
    echo "  WARNING: Futures data count low ($FUTURES_COUNT)" | tee -a "$LOGFILE"
fi

echo "auto_download_data finished at $(date)" | tee -a "$LOGFILE"
echo "-----------------------------" | tee -a "$LOGFILE"
