#!/bin/bash
# 每日下載合約資料（一週）
# 用法: bash user_data/scripts/utilities/download_futures_daily.sh

set -e

FREQTRADE_DIR="/home/brian/freqtrade"
# 明確指定 freqtrade venv 的 python：cron script 環境的 python3 是 /usr/bin/python3
# 沒有 pandas，會 ModuleNotFoundError，導致驗證區塊全部「讀取失敗」
FREQTRADE_VENV_PY="$FREQTRADE_DIR/.venv/bin/python3"
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

# 驗證資料（用 venv python，不要用 python3，cron 環境的 python3 沒有 pandas）
# 改寫: 把驗證邏輯做成獨立 script 避免 heredoc + bash 變數 expand + python f-string 衝突
echo ""
echo "✅ 驗證資料:"
if [ ! -x "$FREQTRADE_VENV_PY" ]; then
  echo "  ⚠️ 找不到 venv python: $FREQTRADE_VENV_PY"
  echo "  (PATH=$PATH)"
else
  # 除錯: 印出 venv python 跟 pandas 版本
  "$FREQTRADE_VENV_PY" -c "import sys,pandas,pyarrow; print(f'  [debug] py={sys.version.split()[0]} pandas={pandas.__version__} pyarrow={pyarrow.__version__}')" 2>&1 || true

  # 寫一個固定路徑的驗證 script（避免 mktemp 在 cron 環境的 /tmp 權限問題）
  VERIFY_SCRIPT="/tmp/verify_futures_feathers.py"
  cat > "$VERIFY_SCRIPT" <<'PYEOF'
"""Verify daily futures feather files for 5 pairs.
Usage: verify_futures_feathers.py <datadir> <pair1> <pair2> ...
Exits 0 if all readable, 1 if any failed.
"""
import sys
import os
import traceback

def main():
    if len(sys.argv) < 3:
        print(f"  [verify] usage error: {len(sys.argv)} args", file=sys.stderr)
        return 1
    datadir = sys.argv[1]
    pairs = sys.argv[2:]
    failed = 0
    for pair in pairs:
        filename = f"{pair}_USDT_USDT-5m-futures.feather"
        path = os.path.join(datadir, filename)
        try:
            import pandas as pd
            if not os.path.exists(path):
                print(f"  {pair}: 檔案不存在 ({path})")
                failed += 1
                continue
            df = pd.read_feather(path)
            first_date = df.iloc[0]['date'] if 'date' in df.columns else 'N/A'
            last_date = df.iloc[-1]['date'] if 'date' in df.columns else 'N/A'
            print(f"  {pair}: {len(df)} rows, {first_date} ~ {last_date}")
        except Exception as exc:
            print(f"  {pair}: 讀取失敗 ({type(exc).__name__}: {exc})", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            failed += 1
    if failed > 0:
        print(f"  [verify] {failed} pair(s) failed", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYEOF
  chmod +x "$VERIFY_SCRIPT"

  # Run verify script, separate stdout/stderr capture so hermes-cron can preserve
  # python tracebacks in stderr when delivered to the user.
  "$FREQTRADE_VENV_PY" "$VERIFY_SCRIPT" "$DATADIR" BTC ETH SOL XRP BNB
  VERIFY_RC=$?

  if [ $VERIFY_RC -ne 0 ]; then
    echo "  [verify] 整體失敗 (exit=$VERIFY_RC)"
  fi

  rm -f "$VERIFY_SCRIPT"
fi

echo ""
echo "=========================================="
echo "✅ 下載完成！"
echo "=========================================="
