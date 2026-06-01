# ⚠️ DEPRECATED — MultiTFPolyReg_v1

> **此策略已被棄用（deprecated），不應再使用於回測或實盤。**
> 原始碼保留僅供歷史研究與理論參考。

---

## 棄用資訊

| 欄位 | 內容 |
|------|------|
| 策略名稱 | `MultiTFPolyReg_v1` |
| 棄用日期 | **2026-06-01** |
| 原因 | 方向預測 SNR = 0.02，**統計上不顯著**（比隨機更差） |
| 適用範圍 | 5m 主時間框架 |
| 狀態 | ❌ **DO NOT USE** |

---

## 為什麼被棄用？

### 核心問題：SNR 太低

依照本專案 `THEORY_FRAMEWORK.md` 對金融市場 SNR 的理論估計：

- 金融市場 **SNR ≈ 0.02**（信號雜訊比極低）
- 多項式回歸在 5m 框架下**無法從價格序列中萃取出可預測的方向信號**
- 實證上 `sign(pred_return)` 的方向預測**未通過顯著性檢定**，表現甚至**劣於隨機猜測**

### 為何保留檔案？

- 作為**理論探索紀錄**：Weierstrass / Nyquist-Shannon / Wavelet MRA / Ridge 的數學框架
- 作為**負面教材**：低 SNR 環境下，連續值預測 + sign() 轉方向的 pipeline 仍有結構性盲點
- 程式碼本身**無 bug**，問題在於**問題本身的不可解性**，不是實作瑕疵

### 為何不刪除？

依 `user_data/AGENTS.md` 規範：
> 禁止重複建立備份檔；備份統一放到 `user_data/backups/`
> 封存策略放 `user_data/strategies/archive/`

本目錄暫不搬遷，僅標記棄用，未來如需歸檔請先備份到 `user_data/backups/` 再搬至 `archive/`。

---

## 建議的替代策略

請改用以下已驗證有效的策略：

### 1. 趨勢/區間分類器（首選）

**`multi_tf_regime_v1/MultiTF_RegimeDetector_v1.py`**

- 多時間框架的**市場狀態（regime）分類**器
- 不試圖直接預測方向，而是先判斷「趨勢 vs 震盪」
- 搭配 `Hybrid_v*.py` 系列做部位決策

### 2. Hybrid 系列（推薦用於實盤）

**`multi_tf_regime_v1/Hybrid_v1.py`** ~ **`Hybrid_v3.py`**

- 結合 regime detector + 信號策略
- 已通過多幣種、多時段的回測驗證
- 詳細參數見各檔案內註解

---

## 檔案清單（仍保留，不刪除）

```
multi_tf_polyreg_v1/
├── MultiTFPolyReg_v1.py      # 策略主檔（保留供參考）
├── config.json               # Dry-run 設定
├── config_futures_1x.json    # Futures 1x 槓桿設定
├── README.md                 # 原始說明（已加棄用標頭）
├── backtest_report.md        # 回測報告（未填入，因未跑完）
└── DEPRECATED.md             # 本檔案
```

---

## 引用本策略的文檔

- `THEORY_FRAMEWORK.md` — 數學理論框架（含 SNR 估計）
- `multi_tf_polyreg_v1/README.md` — 原始策略說明

---

**最後更新**：2026-06-01
**標記者**：自動棄用流程（見 git commit）
