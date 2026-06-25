# SPEC: 策略自動退場與替換機制 v2

> **版本**: 2.0 (Swarm 審閱修訂版)  
> **狀態**: 🟡 Pending Implementation  
> **建立日期**: 2026-06-25  
> **審閱者**: Alpha (效率) / Beta (安全) / Gamma (創意)  
> **最後更新**: 2026-06-25

---

## 1. Architecture Decision Record (ADR)

### 1.1 Context

Freqtrade 6-slot 生產系統（Bybit 期貨）缺乏策略整體績效監控：
- ✅ 有單筆交易 stoploss/trailing（策略內建）
- ✅ 有 bot 存活監控（`freqtrade_health_pnl.py`，每 5 小時）
- ✅ 有 P&L 報告（API 收集）
- ❌ 無策略整體退場機制（連續虧損、drawdown、idle 偵測）
- ❌ 無自動替換邏輯

**現狀問題案例**：
- SMAOffsetProtectOptV1: 106+ 天無新平倉，仍在運行
- PSV5_Hybrid: -17.72% 收益率，無預警機制

### 1.2 Decision

**核心原則：偵測 + 通知 → 觀察 2 週 → 再決定是否自動化**

| 項目 | 原設計 (v1) | 修訂後 (v2) | 理由 |
|------|-------------|-------------|------|
| 實作方式 | 新建 `strategy_guardian.py` | 擴展 `freqtrade_health_pnl.py` | Alpha：已有 80% 基礎設施 |
| 狀態管理 | 5 狀態狀態機 | 不加新狀態，加 `guardian_alert` 欄位 | Alpha：現有 running/swapping/error 已夠用 |
| 退場決策 | 二元（觸發/不觸發） | ICU Triage 5 級健康分數 | Gamma：非生即死太剛性 |
| 防禦機制 | 無 | Beta 4 個 CRITICAL 防禦 | Beta：防止系統癱瘓 |
| 自動化 | 可選自動 swap | MVP 只通知，人工決定 | 降低風險 |

### 1.3 被擊毀的備選方案

- ❌ **完整狀態機**（running → monitoring → retiring → retired → cooldown）  
  → Alpha 認為過度工程，現有 3 狀態已夠用
  
- ❌ **自動執行 swap**  
  → MVP 階段只通知，觀察 2 週確認準確率後再決定
  
- ❌ **二元退場閾值**（drawdown > 25% → 退場）  
  → Gamma 指出熊市所有策略都虧時會全部被殺

---

## 2. Implementation Specifications

### 2.1 Phase 1 MVP（本週，+60 行 Python）

**目標檔案**: `~/.hermes/scripts/freqtrade_health_pnl.py`

**新增邏輯**:

```python
# === 在 P&L 報告後追加 ===

# 1. Health Score 計算（ICU Triage 概念）
def compute_health_score(profit_data):
    """
    綜合健康分數 (0-100)
    結合所有 API 可取得的指標
    
    權重分配：
    - 30% 絕對報酬 (profit_all_percent)
    - 25% 盈虧比 (profit_factor)
    - 25% 最大回撤 (max_drawdown)
    - 20% 勝率 (win_rate)
    """
    profit_pct = profit_data.get('profit_all_percent', 0)
    win_rate = profit_data.get('win_rate', 0.5) * 100
    profit_factor = profit_data.get('profit_factor', 1.0)
    max_dd = abs(profit_data.get('max_drawdown', 0))
    
    # 各指標標準化到 0-100
    profit_score = max(0, min(100, (profit_pct + 10) * 5))  # -10%→0, +10%→100
    wr_score = win_rate
    pf_score = max(0, min(100, profit_factor * 33))  # PF 3.0 → 100
    dd_score = max(0, 100 - max_dd * 500)  # 20% DD → 0
    
    # 加權綜合
    health = (
        0.30 * profit_score +   # 絕對報酬
        0.25 * pf_score +       # 盈虧比
        0.25 * dd_score +       # 最大回撤
        0.20 * wr_score         # 勝率
    )
    
    return round(health, 1)

# 2. 分級通知（ICU Triage）
def get_triage_level(health_score):
    """
    5 級健康狀態
    
    🟢 Normal (≥60): 正常運行
    🟡 Watchful (40-60): 加強監控
    🟠 Degraded (20-40): 縮編觀察
    🔴 Critical (<20): 建議退場
    """
    if health_score >= 60: return ("🟢", "Normal")
    if health_score >= 40: return ("🟡", "Watchful")
    if health_score >= 20: return ("🟠", "Degraded")
    return ("🔴", "Critical")

# 3. Beta 防禦：API 錯誤區分
consecutive_api_failures = {}

def safe_evaluate_slot(slot, api_data):
    """區分 API 錯誤 vs 空結果，防止誤殺"""
    if api_data is None:
        consecutive_api_failures[slot] = consecutive_api_failures.get(slot, 0) + 1
        if consecutive_api_failures[slot] >= 3:
            return "API_DOWN_CRITICAL"  # 連續 3 次失敗，真正斷線
        return "API_ERROR_SKIP"  # 單次失敗，不評估，不退場
    
    consecutive_api_failures[slot] = 0  # 成功則重置
    return compute_health_score(api_data)

# 4. Beta 防禦：系統熔斷器
MAX_CONCURRENT_CRITICAL = 2  # 最多同時 2 個 slot 處於 Critical

def can_alert_critical(current_slot, all_triage_levels):
    """防止多 slot 同時退場導致系統癱瘓"""
    critical_count = sum(1 for s, level in all_triage_levels.items() 
                        if level == "Critical" and s != current_slot)
    if critical_count >= MAX_CONCURRENT_CRITICAL:
        return False  # 拒絕觸發，改為系統級警報
    return True
```

### 2.2 Beta 防禦措施（P0 必須）

| 風險 | 防禦 | 實作方式 |
|------|------|----------|
| **API 斷線誤殺** | 區分 API error vs 空結果 | `consecutive_api_failures` 計數器，連續 3 次失敗才警報 |
| **Race condition** | 原子寫入 | 先寫 `.tmp` 再 `os.rename()`（原子操作） |
| **多 slot 同時退場** | 系統熔斷器 | `MAX_CONCURRENT_CRITICAL = 2` |
| **Registry 損壞** | 寫入前備份 + fsync | `shutil.copy()` + `os.fsync()` |

**原子寫入範例**:
```python
import os
import shutil
import json

def write_registry_atomic(registry_path, registry_data):
    """原子寫入 registry，防止 crash 導致檔案損壞"""
    tmp_path = registry_path + '.tmp'
    backup_path = registry_path + '.bak'
    
    # 1. 備份當前檔案
    if os.path.exists(registry_path):
        shutil.copy(registry_path, backup_path)
    
    # 2. 寫入臨時檔
    with open(tmp_path, 'w') as f:
        json.dump(registry_data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())  # 確保寫入磁碟
    
    # 3. 原子替換（POSIX 系統保證原子性）
    os.rename(tmp_path, registry_path)
```

### 2.3 通知格式（Telegram）

```markdown
🤖 Freqtrade 策略健康報告
時間: 2026-06-25 05:00 (Wednesday)

📋 Slot 健康狀態 (ICU Triage)

| Slot | 策略 | Health | 分級 | 關鍵指標 |
|------|------|--------|------|----------|
| 1 | NASOSv4 | 72.3 | 🟢 Normal | Profit +5.2%, WR 58% |
| 2 | PSV5_Hybrid | 38.1 | 🟠 Degraded | DD -18%, WR 32% |
| 3 | BB_RPB_TSL_BI | 15.2 | 🔴 Critical | DD -25%, 0 trades 14d |
| 4 | NASOSv5_mod3 | 65.8 | 🟢 Normal | Profit +3.1%, WR 55% |
| 5 | SMAOffsetProtectOptV1 | 42.0 | 🟡 Watchful | 0 trades 106d |
| 6 | ElliotV5_SMA_ninja | 58.4 | 🟢 Normal | Profit -1.2%, WR 48% |

⚠️ 需要關注:
• Slot 3 (BB_RPB_TSL_BI): 🔴 Critical — 建議退場
• Slot 5 (SMAOffsetProtectOptV1): 🟡 Watchful — 106 天無交易

💡 建議動作:
• bash swap_strategy.sh 3 <replacement>
• 或手動檢查後決定
```

### 2.4 Health Score 權重說明

| 指標 | 權重 | 理由 |
|------|------|------|
| 絕對報酬 (profit_all_percent) | 30% | 最終目標是賺錢 |
| 盈虧比 (profit_factor) | 25% | 風險調整後的報酬品質 |
| 最大回撤 (max_drawdown) | 25% | 控制下行風險 |
| 勝率 (win_rate) | 20% | 策略穩定性指標 |

**標準化公式**:
- Profit: `(profit_pct + 10) * 5` → -10% 映射到 0，+10% 映射到 100
- Win Rate: `win_rate * 100` → 直接百分比
- Profit Factor: `pf * 33` → PF 3.0 映射到 100
- Drawdown: `100 - max_dd * 500` → 20% DD 映射到 0

---

## 3. Target Skill Requirement

### 3.1 Required Tools
- Python 3.12（Hermes 環境）
- Freqtrade API（已配置，user: carlos）
- Hermes cron（job_id: `d8d6aa6e99ca`，每 5 小時）

### 3.2 Required Capabilities
- 擴展 `freqtrade_health_pnl.py`（+60 行）
- 不改 registry schema（用 tmp 檔記錄 `consecutive_api_failures`）
- 更新 Hermes cron prompt（解釋 Health Score 含義）

### 3.3 不需要的工具
- ❌ 不新建 `strategy_guardian.py`
- ❌ 不改 registry.json schema
- ❌ 不自動執行 `swap_strategy.sh`（MVP 階段）

---

## 4. Execution Directive & Continuation

### 4.1 Phase 1: MVP（本週）

**目標**: 偵測 + 通知，不自動執行

- [ ] 在 `freqtrade_health_pnl.py` 加 Health Score 計算（+30 行）
- [ ] 加 ICU Triage 分級邏輯（+15 行）
- [ ] 加 Beta 防禦（API 錯誤區分 + 系統熔斷器）（+15 行）
- [ ] 更新 Hermes cron prompt（解釋 Health Score 含義）
- [ ] 測試：手動執行腳本，確認輸出正確
- [ ] 部署：觀察 2 週，收集 false positive 數據

**驗收標準**:
- Health Score 計算正確（與手動計算一致）
- ICU Triage 分級合理（🟢/🟡/🟠/🔴 分布符合直覺）
- Beta 防禦生效（API 斷線時不會誤觸發）
- 通知格式清晰（Telegram 可讀）

### 4.2 Phase 2: 驗證後決定（2 週後）

**目標**: 根據 Phase 1 數據決定下一步

- [ ] 分析通知準確率（false positive / false negative）
- [ ] 決定是否需要自動執行 swap
- [ ] 決定是否需要更精細的狀態機
- [ ] 考慮 Gamma 的 Tactical Withdrawal（regime-aware hibernation）

**決策標準**:
- False positive rate < 10% → 可考慮自動化
- False negative rate > 20% → 需調整 Health Score 權重
- 用戶反饋「通知太多」→ 提高閾值
- 用戶反饋「通知太少」→ 降低閾值

### 4.3 Phase 3: 長期（可選）

**目標**: 進階功能（視 Phase 2 結果決定）

- [ ] ELO Arena（策略相對排名）— Gamma 提案
- [ ] 生態學承載力（動態調整 bot 數量）— Gamma 提案
- [ ] 與 rolling-freqtrade-strategy 的 PerformanceRecord 整合
- [ ] Tactical Withdrawal（regime-aware hibernation）— Gamma 提案

### 4.4 Continuation State

Phase 1 可獨立完成，不依賴後續階段。若 Phase 1 成功，可繼續 Phase 2；若失敗，可回滾而不影響現有系統。

### 4.5 Directive Target

> **給執行代理**：讀取此 SPEC.md，擴展 `~/.hermes/scripts/freqtrade_health_pnl.py`，確保：
> 1. 不中斷現有 cron 排程（每 5 小時）
> 2. Health Score 計算正確（加權公式）
> 3. Beta 4 個 CRITICAL 防禦全部實作
> 4. 通知格式清晰（ICU Triage 分級）
> 5. 不自動執行任何 swap（只通知）
> 6. 加入 unit tests（至少 Health Score 計算）

---

## 5. Appendix

### 5.1 Swarm 審閱摘要

| 助理 | 核心洞察 | 採納程度 |
|------|---------|---------|
| **Alpha** (效率) | 「已有 80% 基礎設施，不要重複造輪子」 | ✅ 完全採納 |
| **Beta** (安全) | 「4 個 CRITICAL 可導致系統癱瘓」 | ✅ 全部納入防禦 |
| **Gamma** (創意) | 「退場不應該是二元的，策略可以冬眠」 | ✅ 採納 ICU Triage 概念 |

### 5.2 現有基礎設施盤點

| 組件 | 路徑 | 功能 | 狀態 |
|------|------|------|------|
| `freqtrade_health_pnl.py` | `~/.hermes/scripts/` | Ping + 重啟 + P&L 報告 | ✅ 每 5h cron |
| `check_bots.py` | `freqtrade/user_data/scripts/utilities/` | 健康檢查 + SQLite P&L | ✅ 可用 |
| `swap_strategy.sh` | `freqtrade/user_data/scripts/prod/` | 策略抽換 + rollback | ✅ 完整 |
| `registry.json` | `freqtrade/user_data/config/prod/` | Slot 狀態管理 | ✅ Schema 2.0 |
| Hermes cron | `d8d6aa6e99ca` | 每 5h 觸發健康檢查 | ✅ 已運行 348 次 |

### 5.3 風險評估

| 風險 | 嚴重度 | 發生概率 | 防禦措施 |
|------|--------|----------|----------|
| API 斷線誤殺 | CRITICAL | 高 | 連續 3 次失敗才行動 |
| Race condition | CRITICAL | 中 | 原子寫入 + flock |
| 多 slot 同時退場 | CRITICAL | 中 | 系統熔斷器 (MAX=2) |
| Registry 損壞 | CRITICAL | 低 | 寫入前備份 + fsync |
| Health Score 不準確 | HIGH | 中 | 觀察 2 週，收集數據 |

### 5.4 相關文件

- [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) — Freqtrade 系統設計
- [OPERATIONS.md](./OPERATIONS.md) — 維運手冊
- [ARCHITECTURE.md](./ARCHITECTURE.md) — 系統架構
- [SPEC_strategy_retirement_mechanism_v1.md](./SPEC_strategy_retirement_mechanism_v1.md) — 原設計（已棄用）

---

**文件維護者**: Brian Tseng (Speculari)  
**最後審閱**: 2026-06-25 (Swarm v2)  
**下次審閱**: Phase 2 完成後（預計 2026-07-09）
