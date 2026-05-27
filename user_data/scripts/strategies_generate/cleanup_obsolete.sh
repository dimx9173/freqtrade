#!/bin/bash
# 清理過時文件和代碼

echo "🧹 開始清理過時文件..."
echo ""

# 創建備份目錄
BACKUP_DIR="archive_old/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "1. 清理過時的舊系統文件..."

# 移動舊的 run_factory.sh (被 run_foundry.sh 取代)
if [ -f "run_factory.sh" ]; then
    echo "   移動: run_factory.sh → $BACKUP_DIR/"
    mv run_factory.sh "$BACKUP_DIR/"
fi

# 移動舊的 QUICK_START.md (被 QUICK_START_v2.md 取代)
if [ -f "QUICK_START.md" ]; then
    echo "   移動: QUICK_START.md → $BACKUP_DIR/"
    mv QUICK_START.md "$BACKUP_DIR/"
fi

# 移動舊的 cleanup.sh (功能已整合到各階段)
if [ -f "cleanup.sh" ]; then
    echo "   移動: cleanup.sh → $BACKUP_DIR/"
    mv cleanup.sh "$BACKUP_DIR/"
fi

echo ""
echo "2. 清理臨時和過時文檔..."

# 移動過時的文檔
OBSOLETE_DOCS=(
    "DIRECTORY_STRUCTURE.md"
    "FUTURES_MODE_UPDATE.md"
    "INTELLIGENT_OPTIMIZATION.md"
    "KPI_TARGETS_UPDATE.md"
    "MONITORING_SUMMARY.md"
    "OPTIMIZATION_FIXES.md"
    "CLEANUP_LOG.md"
)

for doc in "${OBSOLETE_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo "   移動: $doc → $BACKUP_DIR/"
        mv "$doc" "$BACKUP_DIR/"
    fi
done

echo ""
echo "3. 清理 __pycache__ 和編譯文件..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo "   ✅ 已清理 Python 編譯文件"

echo ""
echo "4. 清理舊的策略目錄 (strategies/)..."
if [ -d "strategies" ]; then
    STRATEGY_COUNT=$(find strategies -maxdepth 1 -type d | wc -l)
    echo "   發現 $STRATEGY_COUNT 個舊策略目錄"
    echo "   移動: strategies/ → $BACKUP_DIR/"
    mv strategies "$BACKUP_DIR/"
    echo "   ✅ 已移動舊策略目錄"
fi

echo ""
echo "5. 清理舊的 logs 目錄..."
if [ -d "logs" ]; then
    echo "   移動: logs/ → $BACKUP_DIR/"
    mv logs "$BACKUP_DIR/"
    echo "   ✅ 已移動舊日誌目錄"
fi

echo ""
echo "6. 清理 user_data 重複目錄..."
if [ -d "user_data" ]; then
    echo "   移動: user_data/ → $BACKUP_DIR/"
    mv user_data "$BACKUP_DIR/"
    echo "   ✅ 已移動重複的 user_data 目錄"
fi

echo ""
echo "7. 清理大文件..."
if [ -f "PROJECT_STRUCTURE.txt" ]; then
    SIZE=$(ls -lh PROJECT_STRUCTURE.txt | awk '{print $5}')
    echo "   刪除: PROJECT_STRUCTURE.txt ($SIZE)"
    rm PROJECT_STRUCTURE.txt
fi

echo ""
echo "8. 整理備份目錄..."

# 合併 archive 和 archive_old
if [ -d "archive" ]; then
    echo "   合併 archive/ 到 archive_old/"
    cp -r archive/* "$BACKUP_DIR/" 2>/dev/null || true
    rm -rf archive
fi

echo ""
echo "9. 創建 .gitignore..."
cat > .gitignore << 'GITIGNORE'
# Python
__pycache__/
*.py[cod]
*.so
*.egg
*.egg-info/
dist/
build/

# 日誌
*.log
logs/
*.pid

# 臨時文件
temp_strategies/
*.tmp
*.bak

# 大文件
*.zip
backtest_results/
*.json.gz

# 舊備份
archive_old/
strategies/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
GITIGNORE

echo "   ✅ 已創建 .gitignore"

echo ""
echo "=" 70
echo "✅ 清理完成！"
echo "=" 70
echo ""
echo "備份位置: $BACKUP_DIR"
echo ""
echo "當前目錄結構:"
ls -1 | grep -E "^(foundry|refinery|war_room|successful_strategies|run_|README|QUICK_START|GIT_|PROJECT_|IMPLEMENTATION_|BUGFIX_|test_)"

echo ""
echo "已清理的文件類型:"
echo "  • 舊系統文件 (run_factory.sh, cleanup.sh)"
echo "  • 過時文檔 (7個)"
echo "  • Python 編譯文件"
echo "  • 舊策略目錄 (strategies/)"
echo "  • 舊日誌目錄 (logs/)"
echo "  • 重複目錄 (user_data/)"
echo "  • 大文件 (PROJECT_STRUCTURE.txt)"
echo ""
echo "保留的核心文件:"
echo "  • 三階段目錄 (foundry/, refinery/, war_room/)"
echo "  • 啟動腳本 (run_foundry.sh, run_refinery.sh)"
echo "  • 核心文檔 (README.md, QUICK_START_v2.md, 等)"
echo "  • 成功策略 (successful_strategies/)"
echo "  • 診斷工具 (test_backtest.sh)"
echo ""
