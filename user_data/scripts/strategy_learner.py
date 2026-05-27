import sqlite3
from datetime import datetime
from typing import Optional


class StrategyLearner:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.threshold = 15.0  # 初始門檻
        self.recent_failures = 0
        self._init_db()

    def _init_db(self):
        """確保數據庫表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 檢查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='strategy_results'
        """)
        if not cursor.fetchone():
            # 重建表（基本 schema 已在初始化時創建）
            pass

        conn.commit()
        conn.close()

    def evaluate_strategy(
        self,
        name: str,
        result_17d: dict,
        result_112d: dict,
        market_regime: str = "ranging",
        market_change: float = 0.0,
    ) -> dict:
        """
        評估策略是否合格
        返回: {'qualified': bool, 'score': float, 'reason': str}
        """
        # 1. 計算穩定性分數 (17天 vs 112天差異)
        stability = 1 - abs(result_17d["profit"] - result_112d["profit"])

        # 2. 勝率穩定性
        winrate_stability = 1 - abs(result_17d["winrate"] - result_112d["winrate"])

        # 3. 基礎分數
        base_score = result_17d["profit"]

        # 4. 失敗懲罰
        fail_penalty = self.recent_failures * 0.1

        # 5. 最終分數
        final_score = base_score + (stability * 2) + (winrate_stability * 1) - fail_penalty

        # 6. 自動調整門檻
        if self.recent_failures > 3:
            self.threshold = 20.0
        elif self.recent_failures > 6:
            self.threshold = 25.0

        qualified = final_score >= self.threshold

        if not qualified:
            self.recent_failures += 1

        return {
            "qualified": qualified,
            "score": round(final_score, 2),
            "threshold": self.threshold,
            "stability": round(stability, 2),
            "winrate_stability": round(winrate_stability, 2),
            "base_score": round(base_score, 2),
            "fail_penalty": round(fail_penalty, 2),
            "reason": "passed"
            if qualified
            else f"score {final_score:.2f} < threshold {self.threshold}",
        }

    def save_result(
        self,
        strategy_name: str,
        script_hash: str,
        timeframe: str,
        result_17d: dict,
        result_112d: dict,
        market_regime: str,
        market_change: float,
        evaluation: dict,
        notes: str = "",
    ):
        """保存結果到數據庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO strategy_results (
                strategy_name, script_hash, timeframe, created_at,
                profit_17d, trades_17d, winrate_17d,
                profit_112d, trades_112d, winrate_112d,
                market_regime, market_change,
                is_qualified, failure_reason, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                strategy_name,
                script_hash,
                timeframe,
                datetime.now().isoformat(),
                result_17d["profit"],
                result_17d["trades"],
                result_17d["winrate"],
                result_112d["profit"],
                result_112d["trades"],
                result_112d["winrate"],
                market_regime,
                market_change,
                evaluation["qualified"],
                evaluation["reason"],
                notes,
            ),
        )

        conn.commit()
        conn.close()

    def get_learning_stats(self) -> dict:
        """獲取學習統計"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 總體統計
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_qualified = 1 THEN 1 ELSE 0 END) as qualified,
                SUM(CASE WHEN is_qualified = 0 THEN 1 ELSE 0 END) as failed,
                AVG(score) as avg_score
            FROM (
                SELECT strategy_name,
                       MAX(is_qualified) as is_qualified,
                       MAX(score) as score
                FROM (
                    SELECT strategy_name, is_qualified,
                           CAST(is_qualified AS REAL) +
                           (SELECT 1 - abs(profit_17d - profit_112d) FROM strategy_results sr2
                            WHERE sr2.strategy_name = strategy_results.strategy_name LIMIT 1) * 2 as score
                    FROM strategy_results
                ) sub
                GROUP BY strategy_name
            )
        """)

        row = cursor.fetchone()
        total, qualified, failed, avg_score = row if row else (0, 0, 0, 0.0)

        conn.close()

        return {
            "total_strategies": total,
            "qualified_count": qualified,
            "failed_count": failed,
            "avg_stability_score": round(avg_score, 2) if avg_score else 0.0,
            "current_threshold": self.threshold,
        }

    def get_recent_results(self, limit: int = 10) -> list:
        """獲取最近的策略評估結果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT strategy_name, profit_17d, profit_112d, is_qualified, created_at
            FROM strategy_results
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "strategy_name": row[0],
                    "profit_17d": row[1],
                    "profit_112d": row[2],
                    "is_qualified": bool(row[3]),
                    "created_at": row[4],
                }
            )

        conn.close()
        return results

    def update_learning_stats(self):
        """更新學習統計表"""
        stats = self.get_learning_stats()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO learning_stats (
                date, total_strategies, qualified_count, failed_count,
                avg_stability_score, current_threshold
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.now().isoformat(),
                stats["total_strategies"],
                stats["qualified_count"],
                stats["failed_count"],
                stats["avg_stability_score"],
                stats["current_threshold"],
            ),
        )

        conn.commit()
        conn.close()


# 測試功能
if __name__ == "__main__":
    db_path = "/home/brian/freqtrade/user_data/strategy_tracker.db"
    learner = StrategyLearner(db_path)

    # 測試評估
    result_17d = {"profit": 8.5, "trades": 45, "winrate": 0.55}
    result_112d = {"profit": 7.2, "trades": 312, "winrate": 0.52}

    evaluation = learner.evaluate_strategy("TestStrategy", result_17d, result_112d)
    print("評估結果:", evaluation)

    # 保存測試
    learner.save_result(
        strategy_name="TestStrategy",
        script_hash="abc123",
        timeframe="1h",
        result_17d=result_17d,
        result_112d=result_112d,
        market_regime="trending_up",
        market_change=5.2,
        evaluation=evaluation,
        notes="Test run",
    )
    print("已保存測試結果")

    # 獲取統計
    stats = learner.get_learning_stats()
    print("學習統計:", stats)

    # 獲取最近結果
    recent = learner.get_recent_results()
    print("最近結果:", recent)
