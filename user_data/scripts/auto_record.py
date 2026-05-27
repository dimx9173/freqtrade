#!/usr/bin/env python3
"""
Auto-Record Hook for Freqtrade Backtest Results
自動記錄回測結果鉤子

功能：
- 讀取 backtest 結果 (JSON)
- 自動判斷是 17天還是 112天回測
- 自動調用 StrategyLearner.save_result()
- 自動評估是否合格

用法：
    python auto_record.py [meta_json_path]

示例：
    python auto_record.py backtest_results/backtest-result-2026-04-22_10-43-12.meta.json
    python auto_record.py  # 自動讀取最新的 .last_result.json
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from strategy_learner import StrategyLearner

# ============================================================================
# 配置
# ============================================================================
DB_PATH = "/home/brian/freqtrade/user_data/strategy_tracker.db"
BACKTEST_RESULTS_DIR = "/home/brian/freqtrade/user_data/backtest_results"


# ============================================================================
# 工具函數
# ============================================================================


def detect_timerange(meta_info: Dict[str, Any]) -> str:
    """
    自動判斷回測時間範圍是 17天還是 112天
    通過 backtest_start_ts 和 backtest_end_ts 計算
    """
    # meta_info 已經是 inner dict (from parse_backtest_result)
    start_ts = meta_info.get("backtest_start_ts", 0)
    end_ts = meta_info.get("backtest_end_ts", 0)

    if not start_ts or not end_ts:
        # 嘗試從 strategy name 推斷
        return "17d" if "test" in str(meta_info.get("run_id", "")).lower() else "112d"

    days = (end_ts - start_ts) / 86400  # 轉換為天數

    if days <= 20:
        return "17d"
    elif days >= 100:
        return "112d"
    else:
        return "17d"  # 預設為短回測


def parse_backtest_result(meta_path: Path) -> tuple:
    """
    解析 backtest meta.json 和結果
    返回: (strategy_name, result_data)
    """
    with open(meta_path, "r") as f:
        meta_json = json.load(f)

    strategy_name = list(meta_json.keys())[0]
    meta_info = meta_json[strategy_name]

    # Construct zip path from meta path (replace .meta.json with .zip)
    zip_path = meta_path.with_name(meta_path.stem.replace(".meta", "") + ".zip")
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip file not found: {zip_path}")

    # 解壓並讀取 JSON
    import zipfile

    json_name = zip_path.stem + ".json"

    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open(json_name) as f:
            backtest_data = json.load(f)

    # 解析結果
    return strategy_name, backtest_data, meta_info


def extract_metrics(backtest_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    從 backtest JSON 中提取關鍵指標
    支援多種數據結構
    """
    metrics = {"profit": 0.0, "trades": 0, "winrate": 0.0}

    # 嘗試從 strategy.{name}.results_per_pair[0] 提取 (新版格式)
    # 結構: {"strategy": {"TestTV_xxx": {...}}}
    strategy_data = backtest_data.get("strategy", {})

    for strat_name, strat_value in strategy_data.items():
        if isinstance(strat_value, dict):
            # 從 results_per_pair 提取
            results_per_pair = strat_value.get("results_per_pair", [])
            if results_per_pair and len(results_per_pair) > 0:
                total_data = results_per_pair[-1]  # 最後一個是 TOTAL
                if total_data.get("key") == "TOTAL" and len(results_per_pair) > 1:
                    total_data = results_per_pair[-2]  # 倒數第二個是實際的最後一個交易對

                metrics["profit"] = float(total_data.get("profit_total_abs", 0.0))
                metrics["trades"] = int(total_data.get("trades", 0))
                metrics["winrate"] = float(total_data.get("winrate", 0.0))
                return metrics

    # 嘗試從 results_per_pair 直接提取
    results_per_pair = backtest_data.get("results_per_pair", [])
    if results_per_pair:
        for rp in results_per_pair:
            if rp.get("key") == "TOTAL":
                continue
            metrics["profit"] = float(rp.get("profit_total_abs", 0.0))
            metrics["trades"] = int(rp.get("trades", 0))
            metrics["winrate"] = float(rp.get("winrate", 0.0))
            return metrics

    # 嘗試直接從 backtest_data 提取頂層欄位
    if "profit_total_abs" in backtest_data:
        metrics["profit"] = float(backtest_data.get("profit_total_abs", 0.0))
        metrics["trades"] = int(backtest_data.get("total_trades", 0))
        metrics["winrate"] = float(backtest_data.get("winrate", 0.0))
        return metrics

    # 嘗試從 results.{name} 提取
    results = backtest_data.get("results", {})
    for key, value in results.items():
        if isinstance(value, dict):
            metrics["profit"] = float(value.get("profit_total_abs", value.get("profit", 0.0)))
            metrics["trades"] = int(value.get("trades", 0))
            metrics["winrate"] = float(value.get("winrate", 0.0))
            return metrics

    return metrics


def get_script_hash(strategy_name: str) -> str:
    """從策略名稱提取 script hash"""
    # 格式: TestTV_HASH
    if "TestTV_" in strategy_name:
        return strategy_name.split("TestTV_")[-1]
    return "unknown"


def determine_market_regime(market_change: float) -> tuple:
    """根據市場變化判斷市場狀態"""
    if market_change > 5:
        return "trending_up", market_change
    elif market_change < -5:
        return "trending_down", market_change
    else:
        return "ranging", market_change


def init_short_results_cache(db_path: str):
    """初始化 short_results_cache 表"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_results_cache (
            strategy_name TEXT PRIMARY KEY,
            script_hash TEXT,
            timeframe TEXT,
            profit REAL,
            trades INTEGER,
            winrate REAL,
            created_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# ============================================================================
# 主類
# ============================================================================


class AutoRecordHook:
    """自動記錄回測結果鉤子"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.learner = StrategyLearner(db_path)
        init_short_results_cache(db_path)

    def process_backtest(self, meta_path: Path) -> Dict[str, Any]:
        """
        處理單個回測結果
        返回評估結果
        """
        print(f"[AutoRecord] Processing: {meta_path}")

        try:
            strategy_name, backtest_data, meta_info = parse_backtest_result(meta_path)
        except FileNotFoundError as e:
            print(f"[AutoRecord] Error: {e}")
            return {"success": False, "error": str(e)}

        # 檢測時間範圍
        timerange = detect_timerange(meta_info)
        print(f"[AutoRecord] Detected timerange: {timerange}")

        # 提取指標
        metrics = extract_metrics(backtest_data)
        print(f"[AutoRecord] Metrics: {metrics}")

        # 根據時間範圍保存
        script_hash = get_script_hash(strategy_name)

        if timerange == "17d":
            # 17天回測 - 暫存，等待 112天結果
            self._save_short_result(strategy_name, script_hash, metrics, meta_info)
            return {
                "success": True,
                "strategy_name": strategy_name,
                "timerange": "17d",
                "message": "Short backtest recorded, waiting for 112d result",
            }
        else:
            # 112天回測 - 嘗試獲取 17天結果並評估
            result_17d = self._get_short_result(strategy_name)
            result_112d = metrics

            # 評估策略
            market_change = meta_info.get("market_change", 0.0)
            market_regime, _ = determine_market_regime(market_change)

            evaluation = self.learner.evaluate_strategy(
                strategy_name, result_17d, result_112d, market_regime, market_change
            )

            # 保存完整結果
            self.learner.save_result(
                strategy_name=strategy_name,
                script_hash=script_hash,
                timeframe=meta_info.get("timeframe", "1h"),
                result_17d=result_17d,
                result_112d=result_112d,
                market_regime=market_regime,
                market_change=market_change,
                evaluation=evaluation,
                notes=f"Auto-recorded from {meta_path.name}",
            )

            # 清理暫存
            self._clear_short_result(strategy_name)

            return {
                "success": True,
                "strategy_name": strategy_name,
                "timerange": "112d",
                "evaluation": evaluation,
            }

    def _save_short_result(
        self,
        strategy_name: str,
        script_hash: str,
        metrics: Dict[str, Any],
        meta_info: Dict[str, Any],
    ):
        """保存 17天回測結果到暫存表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO short_results_cache
            (strategy_name, script_hash, timeframe, profit, trades, winrate, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                strategy_name,
                script_hash,
                meta_info.get("timeframe", "1h"),
                metrics["profit"],
                metrics["trades"],
                metrics["winrate"],
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()
        print(f"[AutoRecord] Saved 17d cache for {strategy_name}")

    def _get_short_result(self, strategy_name: str) -> Dict[str, Any]:
        """獲取暫存的 17天結果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT profit, trades, winrate FROM short_results_cache
            WHERE strategy_name = ?
        """,
            (strategy_name,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {"profit": row[0], "trades": row[1], "winrate": row[2]}
        else:
            # 如果沒有 17天結果，使用預設值
            return {"profit": 0.0, "trades": 0, "winrate": 0.0}

    def _clear_short_result(self, strategy_name: str):
        """清理暫存結果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM short_results_cache WHERE strategy_name = ?", (strategy_name,))
        conn.commit()
        conn.close()


# ============================================================================
# 主程序
# ============================================================================


def main():
    """主程序入口"""
    print("=" * 60)
    print("[AutoRecord] Freqtrade Backtest Auto-Record Hook")
    print("=" * 60)

    # 解析參數
    if len(sys.argv) > 1:
        meta_path = Path(sys.argv[1])
    else:
        # 讀取最新的 backtest result
        last_result_path = Path(BACKTEST_RESULTS_DIR) / ".last_result.json"
        if last_result_path.exists():
            with open(last_result_path, "r") as f:
                last_data = json.load(f)
            latest = last_data.get("latest_backtest", "")
            if latest.endswith(".zip"):
                latest = latest.replace(".zip", ".meta.json")
            meta_path = Path(BACKTEST_RESULTS_DIR) / latest
        else:
            # 獲取最新的 meta.json
            meta_files = sorted(Path(BACKTEST_RESULTS_DIR).glob("backtest-result-*.meta.json"))
            if meta_files:
                meta_path = meta_files[-1]
            else:
                print("[AutoRecord] Error: No backtest results found")
                sys.exit(1)

    if not meta_path.exists():
        print(f"[AutoRecord] Error: File not found: {meta_path}")
        sys.exit(1)

    # 執行處理
    hook = AutoRecordHook()
    result = hook.process_backtest(meta_path)

    # 輸出結果
    print("")
    print("=" * 60)
    if result["success"]:
        print(f"[AutoRecord] ✅ Success: {result['strategy_name']}")
        print(f"[AutoRecord] Timerange: {result['timerange']}")
        if "evaluation" in result:
            eval_result = result["evaluation"]
            print(f"[AutoRecord] Qualified: {eval_result['qualified']}")
            print(
                f"[AutoRecord] Score: {eval_result['score']} (threshold: {eval_result['threshold']})"
            )
            print(f"[AutoRecord] Reason: {eval_result['reason']}")
    else:
        print(f"[AutoRecord] ❌ Failed: {result.get('error', 'Unknown error')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
