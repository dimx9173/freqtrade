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

- **[BUGFIX_ZIP_FORMAT_20251006.md](reports/BUGFIX_ZIP_FORMAT_20251006.md)** - v2.2 ZIP 格式修復
  - Freqtrade 結果格式變更
  - ZIP 文件自動解壓
  - 向後兼容性保證
  - 驗證測試通過

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
    ├── BUGFIX_ZIP_FORMAT_20251006.md
    ├── CLEANUP_REPORT_20251006.md
    └── ORGANIZATION_REPORT_20251006.md
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
**版本**: v2.2
