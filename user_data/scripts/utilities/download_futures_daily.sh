#!/bin/bash
# 每日下載合約資料（一週）
# 用法: bash user_data/scripts/utilities/download_futures_daily.sh

set -e

FREQTRADE_DIR="/home/brian/freqtrade"
CONFIG="$FREQTRADE_DIR/user_data/config/test/config_6.json"
DATADIR="$FREQTRADE_DIR/user_data/data/bybit/futures"
TIMEFRAMES="5m"
PAIRS="BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT XRP/USDT:USDT BNB/USDT:USDT"

# 計算一週前的日期
END_DATE=$(date +%Y%m%d)
START_DATE=$(date -d "7 days ago" +%Y%m%d)

echo "=========================================="
echo "📅 下載合約資料"
echo "⏰ 時間範圍: $START_DATE ~ $END_DATE"
echo "📊 Timeframe: $TIMEFRAMES"
echo "💱 幣種: $PAIRS"
echo "=========================================="

# 下載資料（不使用 --prepend，避免合併問題）
# 改為下載完整資料並覆蓋
freqtrade download-data \
  --config "$CONFIG" \
  --timeframes "$TIMEFRAMES" \
  --timerange "${START_DATE}-${END_DATE}" \
  --pairs $PAIRS \
  --trading-mode futures \
  --datadir "$DATADIR" \
  --erase

# 移動可能寫到子目錄的檔案
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

# 驗證資料
echo ""
echo "✅ 驗證資料:"
for pair in BTC ETH SOL XRP BNB; do
  FILE="$DATADIR/${pair}_USDT_USDT-5m-futures.feather"
  if [ -f "$FILE" ]; then
    python3 -c "
import pandas as pd
df = pd.read_feather('$FILE')
print(f'  {pair}: {len(df)} rows, {df.iloc[0][\"date\"]} ~ {df.iloc[-1][\"date\"]}')
" 2>/dev/null || echo "  $pair: 讀取失敗"
  else
    echo "  $pair: 檔案不存在"
  fi
done

echo ""
echo "=========================================="
echo "✅ 下載完成！"
echo "=========================================="
