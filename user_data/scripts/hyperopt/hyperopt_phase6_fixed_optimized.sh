#!/bin/bash

# =====================================================
# FreqAI Phase 6: 三目標投票系統修復優化腳本
# 基於性能問題診斷的關鍵修復版本
# =====================================================

# 設定變量
STRATEGY="EnsembleStrategyPhase5_Voting"
CONFIG="user_data/config/config_ensemble_phase5_voting.json"
TIMERANGE="20240601-20250101"  # 充足數據範圍
EPOCHS=200                     # 增加優化輪數以找到更好的參數
JOBS=6                         # 穩定的並行數量

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${GREEN}=================================================="
echo -e "🎯 FreqAI Phase 6: 三目標投票系統修復優化"
echo -e "=================================================="
echo -e "策略: ${STRATEGY}"
echo -e "配置: ${CONFIG}"
echo -e "時間範圍: ${TIMERANGE}"
echo -e "優化輪數: ${EPOCHS}"
echo -e "並行任務: ${JOBS}"
echo -e "==================================================${NC}"

echo -e "${PURPLE}🔧 關鍵修復內容:${NC}"
echo -e "  ✅ 簡化為二層級進場系統(高品質+標準品質)"
echo -e "  ✅ 提高信心度門檻(60%-80%範圍)"
echo -e "  ✅ 現實化Kelly參數(勝率55%,槓桿12倍)"
echo -e "  ✅ 加權集成投票機制"
echo -e "  ✅ 增強數據預處理和特徵工程"

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

# 清理舊的優化結果和模型
echo -e "${YELLOW}🧹 清理舊的優化和模型數據...${NC}"
rm -rf user_data/hyperopt_results/*hyperopt_${STRATEGY}*
rm -rf user_data/models/three_target_voting*
rm -rf user_data/data/freqai_data/three_target_voting*

# 創建必要目錄
mkdir -p user_data/hyperopt_results
mkdir -p logs
mkdir -p user_data/models

# 設定日誌文件
LOG_FILE="logs/hyperopt_phase6_fixed_$(date +%Y%m%d_%H%M%S).log"

echo -e "${BLUE}🚀 開始Phase 6修復版三目標投票系統優化...${NC}"
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
    --min-trades 20 \
    --logfile "${LOG_FILE}" \
    -v

HYPEROPT_EXIT_CODE=$?

echo ""
echo -e "${BLUE}📊 優化結果分析...${NC}"

if [ $HYPEROPT_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Phase 6修復優化成功完成！${NC}"
    echo ""
    echo -e "${GREEN}🎉 三目標投票系統修復優化結果:${NC}"
    echo -e "${BLUE}核心修復成果:${NC}"
    echo -e "  🎯 二層級信號系統: 高品質(嚴格) + 標準品質(適中)"
    echo -e "  💪 提高信心度門檻: momentum(60%) + trend(65%) + volatility(55%)"
    echo -e "  📊 現實化Kelly參數: 勝率55%, 盈虧比2.3, 最大槓桿12倍"
    echo -e "  🤖 加權集成投票: LGB(40%) + XGB(40%) + DL(20%)"
    echo -e "  🔧 優化特徵工程: 更多滑動窗口 + 降低噪聲閾值"
    echo ""
    echo -e "${PURPLE}📈 預期性能改進:${NC}"
    echo -e "  勝率目標: 從26.1% 提升至 >50%"
    echo -e "  收益目標: 從-3.03% 改善至 >20% (年化)"
    echo -e "  信號品質: 大幅提升，減少假信號"
    echo -e "  風險控制: 更保守的倉位管理"
    echo ""
    echo -e "${YELLOW}📁 結果文件位置:${NC}"
    echo -e "  優化結果: user_data/hyperopt_results/"
    echo -e "  日誌文件: ${LOG_FILE}"
    echo -e "  模型文件: user_data/models/"

    # 顯示最佳結果
    echo ""
    echo -e "${BLUE}🏆 查看最佳優化結果...${NC}"
    if freqtrade hyperopt-show --config "${CONFIG}" --strategy "${STRATEGY}" -n 1 2>/dev/null; then
        echo -e "${GREEN}最佳參數已顯示在上方${NC}"
    else
        echo -e "${YELLOW}使用以下命令查看詳細結果:${NC}"
        echo -e "freqtrade hyperopt-show --config ${CONFIG} --strategy ${STRATEGY} -n 5"
    fi

else
    echo -e "${RED}❌ 優化失敗 (退出代碼: $HYPEROPT_EXIT_CODE)${NC}"
    echo -e "${YELLOW}請檢查日誌文件: ${LOG_FILE}${NC}"
    echo -e "${YELLOW}常見問題解決方案:${NC}"
    echo -e "  1. 檢查數據是否充足: freqtrade download-data --config ${CONFIG} --timerange ${TIMERANGE}"
    echo -e "  2. 檢查策略語法: python user_data/strategies/${STRATEGY}.py"
    echo -e "  3. 檢查依賴安裝: pip install lightgbm xgboost torch"
    exit 1
fi

echo ""
echo -e "${GREEN}🔥 FreqAI Phase 6 修復版三目標投票系統優化完成！🔥${NC}"
echo -e "${BLUE}後續驗證步驟:${NC}"
echo -e "  1. 運行回測驗證: freqtrade backtesting --config ${CONFIG} --strategy ${STRATEGY}"
echo -e "  2. 分析詳細結果: freqtrade backtesting-analysis --config ${CONFIG}"
echo -e "  3. 如滿意結果，可切換至實盤測試模式"
