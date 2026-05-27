#!/bin/bash
# 整理並整合文件

echo "📂 開始整理文件..."
echo ""

# 創建文檔目錄結構
mkdir -p docs/{guides,reports,technical}

echo "1. 移動使用指南..."
# 保持主要文檔在根目錄
cp README.md docs/guides/ 2>/dev/null || true
cp QUICK_START_v2.md docs/guides/ 2>/dev/null || true
echo "   ✅ 指南文檔已複製到 docs/guides/"

echo ""
echo "2. 移動技術文檔..."
mv GIT_INTEGRATION.md docs/technical/ 2>/dev/null || true
mv IMPLEMENTATION_CHECKLIST.md docs/technical/ 2>/dev/null || true
mv PROJECT_SUMMARY.md docs/technical/ 2>/dev/null || true
echo "   ✅ 技術文檔已移至 docs/technical/"

echo ""
echo "3. 移動報告文檔..."
mv BUGFIX_20251005.md docs/reports/ 2>/dev/null || true
mv BUGFIX_BACKTEST_20251006.md docs/reports/ 2>/dev/null || true
mv CLEANUP_REPORT_20251006.md docs/reports/ 2>/dev/null || true
echo "   ✅ 報告文檔已移至 docs/reports/"

echo ""
echo "4. 創建文檔索引..."
cat > docs/INDEX.md << 'INDEX'
# 📚 文檔索引

## 📖 使用指南 (guides/)

### 主要文檔
- **[README.md](../README.md)** - 系統總覽與完整文檔（保留在根目錄）
- **[QUICK_START_v2.md](../QUICK_START_v2.md)** - 快速啟動指南（保留在根目錄）

這兩份文檔保留在根目錄方便快速訪問。

---

## 🔧 技術文檔 (technical/)

### Git 與版本控制
- **[GIT_INTEGRATION.md](technical/GIT_INTEGRATION.md)** - Git 自動提交與手動操作指南
  - 自動提交機制
  - 手動 Git 操作
  - 查詢技巧
  - 最佳實踐

### 專案管理
- **[PROJECT_SUMMARY.md](technical/PROJECT_SUMMARY.md)** - 專案重構總結報告
  - 系統架構對比
  - 核心改進
  - 技術規格
  - 預期產出

- **[IMPLEMENTATION_CHECKLIST.md](technical/IMPLEMENTATION_CHECKLIST.md)** - 實施檢查清單
  - 完成度統計
  - 測試建議
  - 部署檢查

---

## 📊 報告文檔 (reports/)

### Bug 修復報告
- **[BUGFIX_20251005.md](reports/BUGFIX_20251005.md)** - v1.2 Bug 修復記錄
  - KPI 配置引用錯誤
  - list.split() 錯誤
  - unhashable list 錯誤
  - ROI None 值錯誤

- **[BUGFIX_BACKTEST_20251006.md](reports/BUGFIX_BACKTEST_20251006.md)** - v2.1 回測問題修復
  - 回測結果讀取優化
  - 錯誤處理增強
  - 日誌級別調整
  - 診斷工具

### 維護報告
- **[CLEANUP_REPORT_20251006.md](reports/CLEANUP_REPORT_20251006.md)** - 專案清理報告
  - 清理統計
  - 目錄結構優化
  - 性能改善
  - 維護建議

---

## 🗂️ 文檔結構

```
docs/
├── INDEX.md                        # 本文件
│
├── guides/                         # 使用指南（副本）
│   ├── README.md
│   └── QUICK_START_v2.md
│
├── technical/                      # 技術文檔
│   ├── GIT_INTEGRATION.md
│   ├── PROJECT_SUMMARY.md
│   └── IMPLEMENTATION_CHECKLIST.md
│
└── reports/                        # 報告文檔
    ├── BUGFIX_20251005.md
    ├── BUGFIX_BACKTEST_20251006.md
    └── CLEANUP_REPORT_20251006.md
```

---

## 📝 文檔使用建議

### 新用戶
1. 閱讀 **[README.md](../README.md)** 了解系統架構
2. 閱讀 **[QUICK_START_v2.md](../QUICK_START_v2.md)** 快速上手
3. 參考 **[GIT_INTEGRATION.md](technical/GIT_INTEGRATION.md)** 設置版本控制

### 開發者
1. 查看 **[PROJECT_SUMMARY.md](technical/PROJECT_SUMMARY.md)** 了解技術細節
2. 使用 **[IMPLEMENTATION_CHECKLIST.md](technical/IMPLEMENTATION_CHECKLIST.md)** 驗證部署
3. 參考 **reports/** 了解歷史問題與解決方案

### 維護者
1. 定期查看 **reports/** 中的修復記錄
2. 更新文檔索引
3. 歸檔舊版本報告

---

**最後更新**: 2025-10-06
**版本**: v2.1
INDEX

echo "   ✅ 已創建文檔索引"

echo ""
echo "5. 更新 .gitignore..."
cat >> .gitignore << 'GITIGNORE'

# 文檔備份
docs/guides/*.md
GITIGNORE

echo "   ✅ 已更新 .gitignore"

echo ""
echo "6. 創建根目錄 README 鏈接..."
cat > DOCS.md << 'DOCSLINK'
# 📚 文檔導航

完整的文檔索引請查看：[docs/INDEX.md](docs/INDEX.md)

## 快速鏈接

### 📖 使用指南
- [README.md](README.md) - 系統總覽
- [QUICK_START_v2.md](QUICK_START_v2.md) - 快速啟動

### 🔧 技術文檔
- [Git 整合說明](docs/technical/GIT_INTEGRATION.md)
- [專案總結](docs/technical/PROJECT_SUMMARY.md)
- [實施檢查清單](docs/technical/IMPLEMENTATION_CHECKLIST.md)

### 📊 報告
- [Bug 修復報告](docs/reports/)
- [清理報告](docs/reports/CLEANUP_REPORT_20251006.md)

---

**完整索引**: [docs/INDEX.md](docs/INDEX.md)
DOCSLINK

echo "   ✅ 已創建 DOCS.md 導航文件"

echo ""
echo "=" 70
echo "✅ 文件整理完成！"
echo "=" 70
echo ""
echo "文檔結構:"
tree docs/ -L 2 2>/dev/null || find docs/ -type f -o -type d | head -20
echo ""
echo "根目錄保留文件:"
ls -1 *.md 2>/dev/null | head -10
echo ""
echo "使用 'cat docs/INDEX.md' 查看完整文檔索引"
