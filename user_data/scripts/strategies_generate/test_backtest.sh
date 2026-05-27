#!/bin/bash
# 測試回測是否正常工作

echo "🔍 診斷回測問題..."
echo ""

# 檢查 Freqtrade
echo "1. 檢查 Freqtrade:"
FREQTRADE_BIN="/Users/carlos/pywork/freqtrade/.venv/bin/freqtrade"
if [ -f "$FREQTRADE_BIN" ]; then
    echo "   ✅ Freqtrade 存在: $FREQTRADE_BIN"
    $FREQTRADE_BIN --version
else
    echo "   ❌ Freqtrade 不存在: $FREQTRADE_BIN"
    exit 1
fi
echo ""

# 檢查配置文件
echo "2. 檢查配置文件:"
CONFIG_FILE="/Users/carlos/pywork/freqtrade/user_data/config/config_ScalpingStrategy.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "   ✅ 配置文件存在: $CONFIG_FILE"
else
    echo "   ❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi
echo ""

# 檢查數據目錄
echo "3. 檢查數據目錄:"
DATA_DIR="/Users/carlos/pywork/freqtrade/user_data/data/bybit"
if [ -d "$DATA_DIR" ]; then
    echo "   ✅ 數據目錄存在: $DATA_DIR"
    echo "   數據文件數量:"
    find "$DATA_DIR" -name "*.feather" | wc -l | xargs echo "      *.feather 文件:"
else
    echo "   ❌ 數據目錄不存在: $DATA_DIR"
    exit 1
fi
echo ""

# 檢查回測結果目錄
echo "4. 檢查回測結果目錄:"
RESULTS_DIR="/Users/carlos/pywork/freqtrade/user_data/backtest_results"
if [ -d "$RESULTS_DIR" ]; then
    echo "   ✅ 回測結果目錄存在: $RESULTS_DIR"
    echo "   現有結果文件數量: $(ls -1 $RESULTS_DIR/*.json 2>/dev/null | wc -l)"
else
    echo "   ⚠️  回測結果目錄不存在，創建中..."
    mkdir -p "$RESULTS_DIR"
fi
echo ""

# 檢查臨時策略目錄
echo "5. 檢查臨時策略:"
TEMP_DIR="/Users/carlos/pywork/freqtrade/user_data/scripts/strategies_generate/foundry/temp_strategies"
if [ -d "$TEMP_DIR" ]; then
    TEMP_COUNT=$(ls -1 $TEMP_DIR/*.py 2>/dev/null | wc -l)
    echo "   ✅ 臨時策略目錄存在"
    echo "   臨時策略數量: $TEMP_COUNT"

    if [ $TEMP_COUNT -gt 0 ]; then
        echo "   最新策略:"
        ls -lt $TEMP_DIR/*.py | head -3
    fi
else
    echo "   ❌ 臨時策略目錄不存在"
    exit 1
fi
echo ""

# 測試回測命令
echo "6. 測試回測命令:"
if [ $TEMP_COUNT -gt 0 ]; then
    LATEST_STRATEGY=$(ls -t $TEMP_DIR/*.py 2>/dev/null | head -1)
    STRATEGY_NAME=$(basename "$LATEST_STRATEGY" .py)

    echo "   使用策略: $STRATEGY_NAME"
    echo "   執行測試回測..."
    echo ""

    cd /Users/carlos/pywork/freqtrade

    $FREQTRADE_BIN backtesting \
        --strategy-path "$TEMP_DIR" \
        --strategy "$STRATEGY_NAME" \
        --datadir "$DATA_DIR" \
        --timerange 20250901-20251006 \
        --timeframe 5m \
        --config "$CONFIG_FILE" \
        --export trades \
        --cache none \
        --max-open-trades 3 \
        --stake-amount 10 2>&1 | tail -50

    EXIT_CODE=${PIPESTATUS[0]}
    echo ""

    if [ $EXIT_CODE -eq 0 ]; then
        echo "   ✅ 回測執行成功"
        echo "   檢查結果文件:"
        ls -lt "$RESULTS_DIR"/*.json 2>/dev/null | head -3
    else
        echo "   ❌ 回測執行失敗 (退出碼: $EXIT_CODE)"
    fi
else
    echo "   ⚠️  沒有臨時策略可測試"
    echo "   請先運行 Foundry 生成策略"
fi

echo ""
echo "診斷完成！"
