#!/bin/bash
# ==============================================
# 下載合約歷史資料（分批避免 API 限制）
# ==============================================

cd /home/brian/freqtrade
source .venv/bin/activate

LOGFILE="user_data/logs/futures_history_download.log"
mkdir -p user_data/logs

echo "========================================" | tee -a "$LOGFILE"
echo "Futures History Download started at $(date)" | tee -a "$LOGFILE"
echo "========================================" | tee -a "$LOGFILE"

# 主要幣種
PAIRS=(
  "BTC/USDT:USDT"
  "ETH/USDT:USDT"
  "SOL/USDT:USDT"
  "XRP/USDT:USDT"
  "BNB/USDT:USDT"
)

# 分批下載（每批 1 個月）
MONTHS=(
  "20240101-20240131"
  "20240201-20240229"
  "20240301-20240331"
  "20240401-20240430"
  "20240501-20240531"
  "20240601-20240630"
  "20240701-20240731"
  "20240801-20240831"
  "20240901-20240930"
  "20241001-20241031"
  "20241101-20241130"
  "20241201-20241231"
  "20250101-20250131"
  "20250201-20250228"
  "20250301-20250331"
  "20250401-20250430"
  "20250501-20250531"
)

for pair in "${PAIRS[@]}"; do
  echo "Downloading $pair..." | tee -a "$LOGFILE"

  for month_range in "${MONTHS[@]}"; do
    echo "  Range: $month_range" | tee -a "$LOGFILE"

    freqtrade download-data \
      --exchange bybit \
      --trading-mode futures \
      --pairs "$pair" \
      --timerange "$month_range" \
      --timeframe 5m \
      --data-format-ohlcv feather \
      --prepend \
      2>&1 | tail -3 | tee -a "$LOGFILE"

    sleep 3
  done
done

echo "========================================" | tee -a "$LOGFILE"
echo "Download completed at $(date)" | tee -a "$LOGFILE"

# 驗證
for pair in "${PAIRS[@]}"; do
  filename="user_data/data/bybit/${pair//\//_}-5m.feather"
  if [[ -f "$filename" ]]; then
    python3 << PYEOF
import pandas as pd
df = pd.read_feather('$filename')
print(f"$pair: {len(df)} rows, {df.iloc[0]['date']} ~ {df.iloc[-1]['date']}")
PYEOF
  fi
done

echo "========================================" | tee -a "$LOGFILE"
