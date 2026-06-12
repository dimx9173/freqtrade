#!/bin/bash
# ==============================================
# 分批下載合約歷史資料（避免 API 限制）
# ==============================================

cd /home/brian/freqtrade
source .venv/bin/activate

PAIR=${1:-"ETH/USDT:USDT"}
TIMEFRAME=${2:-"5m"}
LOGFILE="user_data/logs/futures_batch_download.log"
mkdir -p user_data/logs

echo "========================================" | tee -a "$LOGFILE"
echo "Batch download: $PAIR $TIMEFRAME" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# 分批下載（每批 3 個月）
START_DATES=("20240101" "20240401" "20240701" "20241001" "20250101")
END_DATES=("20240331" "20240630" "20240930" "20241231" "20260525")

for i in "${!START_DATES[@]}"; do
    START=${START_DATES[$i]}
    END=${END_DATES[$i]}

    echo "Downloading $START to $END..." | tee -a "$LOGFILE"

    freqtrade download-data \
        --exchange bybit \
        --trading-mode futures \
        --pairs "$PAIR" \
        --timerange "${START}-${END}" \
        --timeframe "$TIMEFRAME" \
        --data-format-ohlcv feather \
        --prepend \
        2>&1 | tail -5 | tee -a "$LOGFILE"

    sleep 5
done

echo "========================================" | tee -a "$LOGFILE"
echo "Batch download completed" | tee -a "$LOGFILE"

# 驗證
python3 << PYEOF
import pandas as pd
import glob

files = glob.glob(f'user_data/data/bybit/{PAIR.replace("/", "_")}-{TIMEFRAME}.feather')
if files:
    df = pd.read_feather(files[0])
    print(f"{PAIR} {TIMEFRAME}: {len(df)} rows")
    print(f"From: {df.iloc[0]['date']}")
    print(f"To: {df.iloc[-1]['date']}")
PYEOF

echo "========================================" | tee -a "$LOGFILE"
