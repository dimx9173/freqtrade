#!/bin/bash
# Phase 1 驗證腳本
# 用法: bash verify_phase1.sh
# 檢查 OpenCode 實作產出是否符合規格

set -e

FREQTRADE_DIR="/home/brian/freqtrade"
TARGET_DIR="$FREQTRADE_DIR/user_data/strategies/math_based/ga_framework"
SMOKE_TEST="$TARGET_DIR/pre_flight_smoke_test.py"
RUN_GA="$TARGET_DIR/run_ga.sh"

echo "=========================================="
echo "🔍 Phase 1 驗證"
echo "=========================================="

# 1. 檔案存在
echo ""
echo "1️⃣  檔案存在檢查"
[ -f "$SMOKE_TEST" ] && echo "  ✅ pre_flight_smoke_test.py 存在 ($(wc -l < $SMOKE_TEST) lines)" || { echo "  ❌ pre_flight_smoke_test.py 缺失"; exit 1; }
[ -f "$RUN_GA" ] && echo "  ✅ run_ga.sh 存在 ($(wc -l < $RUN_GA) lines)" || { echo "  ❌ run_ga.sh 缺失"; exit 1; }

# 2. Python 語法
echo ""
echo "2️⃣  Python 語法檢查"
python3 -c "import ast; ast.parse(open('$SMOKE_TEST').read())" && echo "  ✅ Python 語法 OK" || { echo "  ❌ Python 語法錯誤"; exit 1; }

# 3. Bash 語法
echo ""
echo "3️⃣  Bash 語法檢查"
bash -n "$RUN_GA" && echo "  ✅ Bash 語法 OK" || { echo "  ❌ Bash 語法錯誤"; exit 1; }

# 4. CLI help 測試
echo ""
echo "4️⃣  CLI Help 測試"
python3 "$SMOKE_TEST" --help 2>&1 | head -20

# 5. 4 個月預設檢查
echo ""
echo "5️⃣  4 個月預設檢查（看 run_ga.sh 是否有 --months 邏輯）"
if grep -q "months" "$RUN_GA"; then
  echo "  ✅ 找到 months 邏輯"
  grep -n "months" "$RUN_GA" | head -5
else
  echo "  ❌ 沒找到 months 邏輯"
  exit 1
fi

if grep -q "allow-short-window" "$RUN_GA"; then
  echo "  ✅ 找到 --allow-short-window 邏輯"
else
  echo "  ⚠️  沒找到 --allow-short-window flag"
fi

# 6. Negative KB 檢查
echo ""
echo "6️⃣  Negative KB 內建檢查（看 pre_flight_smoke_test.py 是否含 known pitfalls）"
for pitfall in "rsi" "trailing_stop" "shift" "leverage" "exit_trend"; do
  if grep -qi "$pitfall" "$SMOKE_TEST"; then
    echo "  ✅ 涵蓋 $pitfall"
  else
    echo "  ⚠️  缺少 $pitfall 檢查"
  fi
done

# 7. 可執行權限
echo ""
echo "7️⃣  可執行權限"
chmod +x "$SMOKE_TEST" 2>/dev/null
chmod +x "$RUN_GA" 2>/dev/null
[ -x "$SMOKE_TEST" ] && echo "  ✅ pre_flight_smoke_test.py 可執行" || echo "  ⚠️  pre_flight_smoke_test.py 不可執行"
[ -x "$RUN_GA" ] && echo "  ✅ run_ga.sh 可執行" || echo "  ⚠️  run_ga.sh 不可執行"

echo ""
echo "=========================================="
echo "✅ Phase 1 驗證完成"
echo "=========================================="
