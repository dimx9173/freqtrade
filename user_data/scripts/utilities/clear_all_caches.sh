#!/bin/bash
# clear_all_caches.sh — 清除 FreqAI 所有緩存
# 用法: ./clear_all_caches.sh [identifier_prefix]

cd ~/freqtrade

# 清除 FreqAI 模型緩存
if [ -n "$1" ]; then
    echo "清除 FreqAI 模型: user_data/models/${1}*"
    rm -rf user_data/models/${1}*
else
    echo "清除所有 FreqAI 模型"
    rm -rf user_data/models/*
fi

# 清除 backtest 結果
echo "清除 backtest 結果"
rm -rf user_data/backtest_results/*

# 清除 freqai 歷史預測
echo "清除 freqai 歷史預測"
rm -rf user_data/freqai/*

# 清除 Python pycache
echo "清除 Python pycache"
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

echo "✅ 所有緩存已清除"
