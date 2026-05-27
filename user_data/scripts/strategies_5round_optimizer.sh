#!/bin/bash
# ============================================================
# 5-Round Multi-Dimensional Strategy Optimizer
# 對 Freqtrade 策略進行 5 輪多維度優化
# ============================================================

set -e

STRATEGY=$1
CONFIG=$2
TIMERANGE=${3:-"20250601-20260413"}
FEE=${4:-"0.0004"}
FREQ="/home/brian/freqtrade/.venv/bin/freqtrade"
STRAT_DIR="/home/brian/freqtrade/user_data/strategies/test"
OPT_DIR="/home/brian/freqtrade/user_data/scripts/optimization"

if [[ -z "$STRATEGY" ]]; then
    echo "用法: $0 <策略名稱> [config] [timerange] [fee]"
    exit 1
fi

STRATEGY_FILE="$STRAT_DIR/${STRATEGY}.py"
echo "===== 5-Round Optimizer: $STRATEGY ====="

if [[ ! -f "$STRATEGY_FILE" ]]; then
    echo "策略檔案不存在: $STRATEGY_FILE"
    exit 1
fi

# -----------------------------------------------
# Round 1: 標準時間框架測試（1h vs 4h vs 1d）
# -----------------------------------------------
echo "[Round 1] 時間框架測試..."

for tf in "1h" "4h" "1d"; do
    echo "  測試 $tf..."
    cd /home/brian/freqtrade
    $FREQ backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --fee "$FEE" \
        --timeframe "$tf" 2>/dev/null | \
    python3 -c "
import sys, re
output = sys.stdin.read()
match = re.search(r'Result:\s*\n(.*?)\$\$\$', output, re.DOTALL)
if match:
    lines = match.group(1).strip().split('\n')
    profit = re.search(r'(-?[\d.]+)%', lines[-1]) if lines else None
    trades = re.search(r'(\d+)\s*trades', output)
    print(f'  {tf}: profit={profit.group(0) if profit else \"N/A\"}, trades={trades.group(1) if trades else \"N/A\"}')
else:
    print(f'  {tf}: FAILED')
" 2>/dev/null || echo "  $tf: FAILED"
done

# -----------------------------------------------
# Round 2: 止損參數掃描（1%, 2%, 3%, 5%）
# -----------------------------------------------
echo "[Round 2] 止損參數掃描..."

for sl in "0.01" "0.02" "0.03" "0.05"; do
    echo "  測試 stoploss=$sl..."
    cd /home/brian/freqtrade
    $FREQ backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --fee "$FEE" \
        --stoploss "$sl" 2>/dev/null | \
    grep -E "({}|Profit)" | tail -3 || echo "  stoploss=$sl: FAILED"
done

# -----------------------------------------------
# Round 3: ROI 參數測試（短線 vs 長線）
# -----------------------------------------------
echo "[Round 3] ROI 參數測試..."

ROI_CONFIGS=(
    "short:0.01,30|medium:0.02,60|long:0.03,120"
    "short:0.02,15|medium:0.03,30|long:0.05,60"
    "short:0.005,20|medium:0.01,40|long:0.02,80"
)

for i in "${!ROI_CONFIGS[@]}"; do
    roi="${ROI_CONFIGS[$i]}"
    echo "  測試 ROI 配置 $((i+1))..."
    cd /home/brian/freqtrade
    $FREQ backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --fee "$FEE" \
        --roi "$roi" 2>/dev/null | \
    grep -E "Profit|trades" | tail -2 || echo "  ROI config $((i+1)): FAILED"
done

# -----------------------------------------------
# Round 4: 市場 conditions 篩選（只做多 / 多空）
# -----------------------------------------------
echo "[Round 4] 交易方向測試..."

for side in "long" "short" "both"; do
    echo "  測試 direction=$side..."
    cd /home/brian/freqtrade
    $FREQ backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG" \
        --timerange "$TIMERANGE" \
        --fee "$FEE" \
        --direction "$side" 2>/dev/null | \
    grep -E "Profit|trades" | tail -2 || echo "  direction=$side: FAILED"
done

# -----------------------------------------------
# Round 5: 最佳組合回測
# -----------------------------------------------
echo "[Round 5] 最佳參數組合回測..."

# 根據前面四輪結果，選擇最佳參數組合
# 這裡使用 AI 來決定最佳組合
cd /home/brian/freqtrade

# 先跑一次標準回測取得基準
STANDARD_BT=$($FREQ backtesting \
    --strategy "$STRATEGY" \
    --config "$CONFIG" \
    --timerange "$TIMERANGE" \
    --fee "$FEE" \
    --output-format json 2>/dev/null)

STANDARD_PROFIT=$(echo "$STANDARD_BT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    if results:
        print(results[0].get('profit_abs', 0))
    else:
        print(0)
except: print(0)
" 2>/dev/null || echo "0")

echo "  標準回測 profit: $STANDARD_PROFIT USDT"

# -----------------------------------------------
# 生成優化報告
# -----------------------------------------------
REPORT_FILE="$OPT_DIR/${STRATEGY}_optimization_report.md"
mkdir -p "$OPT_DIR"

cat > "$REPORT_FILE" << EOF
# $STRATEGY 優化報告

## 5 輪優化結果

### Round 1: 時間框架測試
| 時間框架 | 結果 |
|---------|------|
| 1h | 待填入 |
| 4h | 待填入 |
| 1d | 待填入 |

### Round 2: 止損參數
| 止損 | 結果 |
|------|------|
| 1% | 待填入 |
| 2% | 待填入 |
| 3% | 待填入 |
| 5% | 待填入 |

### Round 3: ROI 參數
| 配置 | 結果 |
|------|------|
| Config 1 (短線) | 待填入 |
| Config 2 (中線) | 待填入 |
| Config 3 (長線) | 待填入 |

### Round 4: 交易方向
| 方向 | 結果 |
|------|------|
| Long | 待填入 |
| Short | 待填入 |
| Both | 待填入 |

### Round 5: 最佳組合
- 標準回測 Profit: $STANDARD_PROFIT USDT

## 結論
- 最佳時間框架: 待確認
- 最佳止損: 待確認
- 最佳 ROI: 待確認
- 最佳方向: 待確認

EOF

echo "  報告已生成: $REPORT_FILE"
echo "===== 5-Round Optimizer 完成 ====="
