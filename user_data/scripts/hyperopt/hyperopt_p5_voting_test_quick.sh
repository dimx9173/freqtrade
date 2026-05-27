#!/bin/bash

# =====================================================
# FreqAI Phase 6: 三目標投票系統快速優化測試腳本
# =====================================================

# 設定變量
STRATEGY="EnsembleStrategyPhase5_Voting"
CONFIG="user_data/config/config_ensemble_phase5_voting.json"
TIMERANGE="20240701-20250801"  # 一年數據：2024全年+2025上半年
EPOCHS=100                      # 快速測試：100次迭代
JOBS=8                          # 並行工作數

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=================================================="
echo -e "🎯 FreqAI Phase 6: 三目標投票系統優化"
echo -e "=================================================="
echo -e "策略: ${STRATEGY}"
echo -e "配置: ${CONFIG}"
echo -e "時間範圍: ${TIMERANGE}"
echo -e "優化輪數: ${EPOCHS}"
echo -e "並行任務: ${JOBS}"
echo -e "==================================================${NC}"

# 檢查必要文件
echo -e "${BLUE}📋 檢查必要文件...${NC}"

if [ ! -f "user_data/strategies/${STRATEGY}.py" ]; then
    echo -e "${RED}❌ 策略文件不存在: user_data/strategies/${STRATEGY}.py${NC}"
    exit 1
fi

if [ ! -f "${CONFIG}" ]; then
    echo -e "${RED}❌ 配置文件不存在: ${CONFIG}${NC}"
    exit 1
fi

if [ ! -f "user_data/freqaimodels/HybridEnsembleClassifier.py" ]; then
    echo -e "${RED}❌ 模型文件不存在: user_data/freqaimodels/HybridEnsembleClassifier.py${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 所有必要文件檢查完成${NC}"

# 清理舊的優化結果
echo -e "${YELLOW}🧹 清理舊的優化結果...${NC}"
rm -rf user_data/hyperopt_results/*hyperopt_${STRATEGY}*
rm -rf user_data/models/three_target_voting*

# 創建結果目錄
mkdir -p user_data/hyperopt_results
mkdir -p logs

# 設定日誌文件
LOG_FILE="logs/hyperopt_three_target_$(date +%Y%m%d_%H%M%S).log"

echo -e "${BLUE}🚀 開始三目標投票系統優化...${NC}"
echo -e "${BLUE}📄 日誌文件: ${LOG_FILE}${NC}"

# 執行Hyperopt優化
freqtrade hyperopt \
    --config "${CONFIG}" \
    --strategy "${STRATEGY}" \
    --freqaimodel HybridEnsembleClassifier \
    --timerange "${TIMERANGE}" \
    --epochs ${EPOCHS} \
    --spaces buy \
    -j ${JOBS} \
    --hyperopt-loss SharpeHyperOptLoss \
    --random-state 42 \
    --min-trades 10 \
    --logfile "${LOG_FILE}" \
    -v

HYPEROPT_EXIT_CODE=$?

echo ""
echo -e "${BLUE}📊 優化結果分析...${NC}"

if [ $HYPEROPT_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ 優化成功完成！${NC}"
    echo ""
    echo -e "${GREEN}🎉 三目標投票系統優化成功完成！${NC}"
    echo -e "${BLUE}核心改進:${NC}"
    echo -e "  📊 三個核心預測目標: momentum(5級) + trend(3級) + volatility(2級)"
    echo -e "  🎯 三重驗證投票機制: 嚴格信號品質控制"
    echo -e "  💰 Kelly公式動態倉位管理: 基於信號品質調整"
    echo -e "  📈 目標性能: 年化收益>100%, 最大回撤<8%, 勝率>60%"
    echo ""
    echo -e "${YELLOW}📁 結果文件位置:${NC}"
    echo -e "  優化結果: user_data/hyperopt_results/"
    echo -e "  日誌文件: ${LOG_FILE}"

else
    echo -e "${RED}❌ 優化失敗 (退出代碼: $HYPEROPT_EXIT_CODE)${NC}"
    echo -e "${YELLOW}請檢查日誌文件: ${LOG_FILE}${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🔥 FreqAI Phase 6 三目標投票系統優化完成！🔥${NC}"
