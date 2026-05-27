#!/usr/bin/env python3
"""
Auto-Learn Script for Freqtrade Strategy Learning
自動學習腳本

功能：
- 讀取所有未評估的策略
- 對有 112天結果的策略執行 evaluate_strategy()
- 自動調整門檻
- 生成學習報告

用法：
    python auto_learn.py [--stats] [--evaluate-all]

Crontab 整合：
    0 * * * * /home/brian/freqtrade/user_data/scripts/auto_learn.py >> /home/brian/freqtrade/user_data/logs/auto_learn.log 2>&1
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from strategy_learner import StrategyLearner

# ============================================================================
# 配置
# ============================================================================
DB_PATH = "/home/brian/freqtrade/user_data/strategy_tracker.db"
BACKTEST_RESULTS_DIR = "/home/brian/freqtrade/user_data/backtest_results"
REPORT_FILE = "/home/brian/freqtrade/user_data/docs/LEARNING_REPORT.md"


# ============================================================================
# 工具函數
# ============================================================================


def print_section(title: str):
    """打印分區標題"""
    print("")
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_dict(data: Dict[str, Any], indent: int = 2):
    """打印字典（美化輸出）"""
    for key, value in data.items():
        print(f"{' ' * indent}{key}: {value}")


def get_unevaluated_strategies(conn: sqlite3.Connection) -> List[str]:
    """獲取有 112天結果但未評估的策略"""
    cursor = conn.cursor()

    # 找出有 profit_112d 但沒有評估記錄的策略
    cursor.execute("""
        SELECT DISTINCT strategy_name
        FROM strategy_results
        WHERE profit_112d IS NOT NULL
        AND profit_112d != 0
        AND (is_qualified IS NULL OR is_qualified = '')
        ORDER BY created_at DESC
    """)

    return [row[0] for row in cursor.fetchall()]


def get_pending_17d_strategies(conn: sqlite3.Connection) -> List[str]:
    """獲取只有 17天結果待評估的策略"""
    cursor = conn.cursor()

    # 從 short_results_cache 中獲取待處理的策略
    cursor.execute("""
        SELECT strategy_name FROM short_results_cache
        WHERE strategy_name NOT IN (
            SELECT DISTINCT strategy_name FROM strategy_results
            WHERE profit_112d IS NOT NULL AND profit_112d != 0
        )
    """)

    return [row[0] for row in cursor.fetchall()]


def get_all_strategies_summary(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """獲取所有策略的摘要"""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            strategy_name,
            timeframe,
            profit_17d,
            profit_112d,
            trades_17d,
            trades_112d,
            winrate_17d,
            winrate_112d,
            is_qualified,
            score,
            created_at
        FROM strategy_results
        ORDER BY created_at DESC
    """)

    results = []
    for row in cursor.fetchall():
        results.append(
            {
                "strategy_name": row[0],
                "timeframe": row[1],
                "profit_17d": row[2],
                "profit_112d": row[3],
                "trades_17d": row[4],
                "trades_112d": row[5],
                "winrate_17d": row[6],
                "winrate_112d": row[7],
                "is_qualified": bool(row[8]) if row[8] is not None else None,
                "score": row[9],
                "created_at": row[10],
            }
        )

    return results


def evaluate_pending_strategies(
    learner: StrategyLearner, conn: sqlite3.Connection
) -> Dict[str, Any]:
    """評估所有待評估的策略"""
    print_section("評估待處理策略")

    cursor = conn.cursor()

    # 獲取有 112d 結果但未評估的策略
    cursor.execute("""
        SELECT DISTINCT strategy_name
        FROM strategy_results
        WHERE profit_112d IS NOT NULL
        AND profit_112d != 0
        AND (is_qualified IS NULL OR is_qualified = '')
    """)

    pending = [row[0] for row in cursor.fetchall()]

    if not pending:
        print("  ✅ 沒有待評估的策略")
        return {"evaluated": 0, "qualified": 0, "failed": 0}

    print(f"  📋 找到 {len(pending)} 個待評估策略:")
    for name in pending:
        print(f"     - {name}")

    evaluated = 0
    qualified = 0
    failed = 0

    for strategy_name in pending:
        # 獲取該策略的所有記錄
        cursor.execute(
            """
            SELECT script_hash, timeframe,
                   profit_17d, trades_17d, winrate_17d,
                   profit_112d, trades_112d, winrate_112d,
                   market_regime, market_change
            FROM strategy_results
            WHERE strategy_name = ?
            ORDER BY created_at DESC
            LIMIT 1
        """,
            (strategy_name,),
        )

        row = cursor.fetchone()
        if not row:
            continue

        result_17d = {"profit": row[2] or 0.0, "trades": row[3] or 0, "winrate": row[4] or 0.0}
        result_112d = {"profit": row[5] or 0.0, "trades": row[6] or 0, "winrate": row[7] or 0.0}

        market_regime = row[8] or "ranging"
        market_change = row[9] or 0.0

        # 評估
        evaluation = learner.evaluate_strategy(
            strategy_name, result_17d, result_112d, market_regime, market_change
        )

        # 更新記錄
        cursor.execute(
            """
            UPDATE strategy_results
            SET is_qualified = ?, failure_reason = ?
            WHERE strategy_name = ?
            AND (is_qualified IS NULL OR is_qualified = '')
        """,
            (evaluation["qualified"], evaluation["reason"], strategy_name),
        )

        evaluated += 1
        if evaluation["qualified"]:
            qualified += 1
        else:
            failed += 1

        status = "✅ 合格" if evaluation["qualified"] else "❌ 不合格"
        print(
            f"  {status} {strategy_name}: score={evaluation['score']}, threshold={evaluation['threshold']}"
        )

    conn.commit()

    return {"evaluated": evaluated, "qualified": qualified, "failed": failed}


def adjust_thresholds(learner: StrategyLearner, conn: sqlite3.Connection) -> Dict[str, Any]:
    """根據學習結果自動調整門檻"""
    print_section("自動調整門檻")

    cursor = conn.cursor()

    # 統計過去的失敗率
    cursor.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN is_qualified = 1 THEN 1 ELSE 0 END) as qualified
        FROM strategy_results
        WHERE created_at >= datetime('now', '-7 days')
    """)

    row = cursor.fetchone()
    total = row[0] if row else 0
    qualified = row[1] if row else 0

    if total == 0:
        print("  ℹ️  最近 7 天沒有評估數據")
        return {"current_threshold": learner.threshold, "adjusted": False}

    fail_rate = (total - qualified) / total if total > 0 else 0

    print(f"  最近 7 天統計:")
    print(f"     總評估數: {total}")
    print(f"     合格數: {qualified}")
    print(f"     失敗率: {fail_rate * 100:.1f}%")
    print(f"     當前門檻: {learner.threshold}")

    # 根據失敗率調整
    old_threshold = learner.threshold

    if fail_rate > 0.8:
        # 80%+ 失敗率 - 放寬門檻
        learner.threshold = max(5.0, learner.threshold - 2.0)
        print(f"  📉 失敗率過高 ({fail_rate * 100:.1f}%)，降低門檻")
    elif fail_rate < 0.2:
        # <20% 失敗率 - 收紧門檻
        learner.threshold = min(30.0, learner.threshold + 1.0)
        print(f"  📈 失敗率過低 ({fail_rate * 100:.1f}%)，提高門檻")
    else:
        print(f"  ✅ 失敗率正常，保持門檻")

    if old_threshold != learner.threshold:
        print(f"  🔧 門檻調整: {old_threshold} → {learner.threshold}")
        return {"current_threshold": learner.threshold, "adjusted": True, "old": old_threshold}
    else:
        return {"current_threshold": learner.threshold, "adjusted": False}


def generate_learning_report(learner: StrategyLearner, conn: sqlite3.Connection) -> str:
    """生成學習報告"""
    print_section("生成學習報告")

    # 獲取統計數據
    stats = learner.get_learning_stats()

    cursor = conn.cursor()

    # 最近的評估結果
    cursor.execute("""
        SELECT strategy_name, profit_17d, profit_112d, is_qualified, score, created_at
        FROM strategy_results
        WHERE is_qualified IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
    """)

    recent_results = []
    for row in cursor.fetchall():
        recent_results.append(
            {
                "strategy_name": row[0],
                "profit_17d": row[1],
                "profit_112d": row[2],
                "is_qualified": bool(row[3]),
                "score": row[4],
                "created_at": row[5],
            }
        )

    # 構建報告
    report = f"""# Freqtrade 策略學習報告

## 生成時間
{datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}

## 學習統計

| 指標 | 數值 |
|------|------|
| 總策略數 | {stats["total_strategies"]} |
| 合格策略數 | {stats["qualified_count"]} |
| 不合格策略數 | {stats["failed_count"]} |
| 平均穩定性分數 | {stats["avg_stability_score"]} |
| 當前門檻 | {stats["current_threshold"]} |

## 最近的評估結果

| 策略名稱 | 17天profit | 112天profit | 結果 | 分數 |
|----------|------------|-------------|------|------|
"""

    for r in recent_results:
        status = "✅" if r["is_qualified"] else "❌"
        report += f"| {r['strategy_name']} | {r['profit_17d']:.2f}% | {r['profit_112d']:.2f}% | {status} | {r['score']} |\n"

    report += """
## 門檻調整歷史

門檻會根據失敗率自動調整：
- 失敗率 > 80%：降低門檻 2.0
- 失敗率 < 20%：提高門檻 1.0
- 否則：保持不變

"""

    return report


def save_report(report: str):
    """保存報告到文件"""
    report_path = Path(REPORT_FILE)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"  📄 報告已保存: {report_path}")


# ============================================================================
# 主程序
# ============================================================================


def main():
    """主程序入口"""
    print("")
    print("=" * 60)
    print("  [Auto-Learn] Freqtrade 自動學習系統")
    print(f"  時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # 解析參數
    show_stats = "--stats" in sys.argv
    evaluate_all = "--evaluate-all" in sys.argv

    # 連接數據庫
    conn = sqlite3.connect(DB_PATH)
    learner = StrategyLearner(DB_PATH)

    # 1. 評估待處理策略
    if evaluate_all:
        eval_result = evaluate_pending_strategies(learner, conn)
        print(f"\n  📊 評估結果: 評估了 {eval_result['evaluated']} 個策略")
        print(f"            合格: {eval_result['qualified']} 個")
        print(f"            不合格: {eval_result['failed']} 個")

    # 2. 自動調整門檻
    threshold_result = adjust_thresholds(learner, conn)

    # 3. 顯示學習統計
    if show_stats:
        print_section("學習統計")
        stats = learner.get_learning_stats()
        print_dict(stats)

    # 4. 顯示待處理的 17d 結果
    print_section("待處理項目")
    pending_17d = get_pending_17d_strategies(conn)
    if pending_17d:
        print(f"  ⏳ 有 {len(pending_17d)} 個策略僅有 17 天結果:")
        for name in pending_17d[:5]:
            print(f"     - {name}")
        if len(pending_17d) > 5:
            print(f"     ... 還有 {len(pending_17d) - 5} 個")
    else:
        print("  ✅ 沒有待處理的 17 天結果")

    # 5. 生成並保存報告
    report = generate_learning_report(learner, conn)
    save_report(report)

    conn.close()

    print_section("完成")
    print(f"  ✅ 自動學習完成")
    print(f"  📊 當前門檻: {learner.threshold}")
    print(f"  📄 報告: {REPORT_FILE}")


if __name__ == "__main__":
    main()
