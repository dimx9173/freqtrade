#!/usr/bin/env python3
"""
精煉工坊核心引擎 (The Refinery Engine)
功能：Hyperopt 參數優化、停損優化、績效評估
"""

import json
import subprocess
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from refinery_config import RefineryConfig as Config

# 配置日誌
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL), format=Config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class RefineryEngine:
    """精煉工坊核心引擎"""

    def __init__(self):
        self.config = Config()

        # 驗證配置
        if not self.config.validate_config():
            raise RuntimeError("配置驗證失敗")

    def get_candidate_strategies(self):
        """獲取候選池中的所有策略"""
        candidates = []

        for candidate_dir in Config.CANDIDATE_POOL_DIR.glob("candidate_*"):
            if candidate_dir.is_dir():
                metadata_file = candidate_dir / "metadata.json"
                strategy_files = list(candidate_dir.glob("gen_strategy_*.py"))

                if metadata_file.exists() and strategy_files:
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)

                    candidates.append(
                        {
                            "dir": candidate_dir,
                            "strategy_file": strategy_files[0],
                            "metadata": metadata,
                        }
                    )

        return candidates

    def run_hyperopt(self, strategy_file, strategy_name):
        """執行 Hyperopt 優化"""
        # 計算時間範圍
        end_date = datetime.now()
        start_date = end_date - timedelta(days=Config.HYPEROPT_TIMERANGE_DAYS)
        timerange = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"

        # 構建命令
        cmd = [
            str(Config.FREQTRADE_BIN),
            "hyperopt",
            "--strategy-path",
            str(strategy_file.parent),
            "--strategy",
            strategy_name,
            "--hyperopt-loss",
            Config.HYPEROPT_LOSS,
            "--spaces",
            *Config.HYPEROPT_SPACES,
            "--epochs",
            str(Config.HYPEROPT_EPOCHS),
            "--timerange",
            timerange,
            "--datadir",
            str(Config.DATA_DIR),
            "--config",
            str(Config.FREQTRADE_CONFIG),
        ]

        logger.info(f"🔧 執行 Hyperopt 優化: {strategy_name}")
        logger.info(f"   輪數: {Config.HYPEROPT_EPOCHS}, 目標: {Config.HYPEROPT_LOSS}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1小時超時
                cwd=str(Config.BASE_DIR),
            )

            if result.returncode == 0:
                logger.info("✅ Hyperopt 優化完成")
                return self.parse_hyperopt_results(result.stdout)
            else:
                logger.error(f"❌ Hyperopt 失敗: {result.stderr[-500:]}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("⏳ Hyperopt 超時")
            return None
        except Exception as e:
            logger.error(f"❌ Hyperopt 異常: {e}")
            return None

    def parse_hyperopt_results(self, output):
        """解析 Hyperopt 輸出結果"""
        try:
            # 從輸出中提取最佳結果（簡化版）
            # 實際實現需要更複雜的解析邏輯
            best_result = {"sharpe": 0, "profit": 0, "params": {}}

            # TODO: 實現完整的結果解析
            # 可以從 hyperopt_results.pickle 或 JSON 輸出中讀取

            return best_result

        except Exception as e:
            logger.error(f"解析 Hyperopt 結果失敗: {e}")
            return None

    def compare_performance(self, original_kpis, optimized_kpis):
        """比較優化前後的性能"""
        if not original_kpis or not optimized_kpis:
            return False, {}

        original_sharpe = original_kpis.get("sharpe_ratio", 0)
        optimized_sharpe = optimized_kpis.get("sharpe_ratio", 0)

        original_profit = original_kpis.get("profit_total_pct", 0)
        optimized_profit = optimized_kpis.get("profit_total_pct", 0)

        sharpe_improvement = (
            (optimized_sharpe - original_sharpe) / original_sharpe if original_sharpe > 0 else 0
        )
        profit_improvement = (
            (optimized_profit - original_profit) / abs(original_profit)
            if original_profit != 0
            else 0
        )

        # 檢查是否達到改進標準
        criteria = Config.REFINEMENT_CRITERIA
        significant_improvement = (
            sharpe_improvement >= criteria["sharpe_improvement"]
            or profit_improvement >= criteria["profit_improvement"]
        ) and optimized_sharpe >= criteria["min_sharpe_after_opt"]

        comparison = {
            "sharpe_before": original_sharpe,
            "sharpe_after": optimized_sharpe,
            "sharpe_improvement": sharpe_improvement,
            "profit_before": original_profit,
            "profit_after": optimized_profit,
            "profit_improvement": profit_improvement,
            "significant": significant_improvement,
        }

        return significant_improvement, comparison

    def promote_to_optimized(self, candidate, optimized_params, comparison):
        """將優化後的策略晉升到優化候選池"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy_name = candidate["strategy_file"].stem

        # 創建優化策略目錄
        optimized_dir = Config.OPTIMIZED_DIR / f"optimized_{timestamp}_{strategy_name}"
        optimized_dir.mkdir(parents=True, exist_ok=True)

        # 複製策略文件
        shutil.copy(candidate["strategy_file"], optimized_dir)

        # 保存優化參數和比較結果
        optimization_data = {
            "timestamp": timestamp,
            "original_metadata": candidate["metadata"],
            "optimized_params": optimized_params,
            "performance_comparison": comparison,
            "optimized_at": datetime.now().isoformat(),
        }

        with open(optimized_dir / "optimization_report.json", "w") as f:
            json.dump(optimization_data, f, indent=2, default=str)

        logger.info(f"🎉 策略已晉升至優化池: {optimized_dir.name}")

        # Git 整合
        if Config.ENABLE_GIT_INTEGRATION:
            self.git_commit_optimized_strategy(optimized_dir, comparison)

        return optimized_dir

    def git_commit_optimized_strategy(self, optimized_dir, comparison):
        """將優化後的策略提交到 Git"""
        try:
            commit_message = Config.GIT_COMMIT_MESSAGE_TEMPLATE.format(
                strategy_name=optimized_dir.name,
                sharpe_before=comparison["sharpe_before"],
                sharpe_after=comparison["sharpe_after"],
            )

            subprocess.run(
                ["git", "add", str(optimized_dir)],
                cwd=str(Config.STRATEGIES_GENERATE_DIR),
                check=False,
            )
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=str(Config.STRATEGIES_GENERATE_DIR),
                check=False,
            )

            logger.info(f"📦 已提交到 Git: {commit_message}")

        except Exception as e:
            logger.warning(f"⚠️  Git 提交失敗: {e}")

    def refine_strategy(self, candidate):
        """精煉單個策略"""
        strategy_name = candidate["strategy_file"].stem
        logger.info(f"🔧 開始精煉策略: {strategy_name}")

        # 1. 執行 Hyperopt 優化
        optimized_params = self.run_hyperopt(candidate["strategy_file"], strategy_name)

        if not optimized_params:
            logger.warning(f"⚠️  策略 {strategy_name} 優化失敗")
            return False

        # 2. 比較優化前後性能
        # 從候選元數據獲取原始 KPI
        original_kpis = candidate["metadata"].get("kpis", {}).get("3m", {})

        # TODO: 使用優化後的參數重新回測，獲取新的 KPI
        optimized_kpis = {}  # 需要實現回測邏輯

        significant, comparison = self.compare_performance(original_kpis, optimized_kpis)

        # 3. 如果有顯著提升，晉升到優化池
        if significant:
            logger.info(f"✅ 策略顯著改進！")
            logger.info(
                f"   夏普比率: {comparison['sharpe_before']:.2f} → "
                f"{comparison['sharpe_after']:.2f} "
                f"({comparison['sharpe_improvement']:.1%})"
            )

            self.promote_to_optimized(candidate, optimized_params, comparison)
            return True
        else:
            logger.info(f"💔 策略改進不顯著，未晉升")
            return False

    def run_refinery_batch(self, max_strategies=None):
        """批次精煉候選策略"""
        logger.info("=" * 70)
        logger.info("🔧 精煉工坊啟動")
        logger.info("=" * 70)

        # 獲取候選策略
        candidates = self.get_candidate_strategies()

        if not candidates:
            logger.warning("⚠️  候選池中無策略可優化")
            return

        logger.info(f"📊 找到 {len(candidates)} 個候選策略")

        # 限制處理數量
        if max_strategies:
            candidates = candidates[:max_strategies]
            logger.info(f"🎯 本次處理前 {max_strategies} 個策略")

        # 逐個精煉
        success_count = 0
        for i, candidate in enumerate(candidates, 1):
            logger.info(f"\n{'=' * 70}")
            logger.info(f"處理策略 {i}/{len(candidates)}")
            logger.info(f"{'=' * 70}")

            if self.refine_strategy(candidate):
                success_count += 1

        # 總結
        logger.info("")
        logger.info("=" * 70)
        logger.info("🏁 精煉工坊完成")
        logger.info("=" * 70)
        logger.info(f"   總處理: {len(candidates)}")
        logger.info(f"   ✅ 成功晉升: {success_count}")
        logger.info(f"   ❌ 未通過: {len(candidates) - success_count}")
        logger.info("=" * 70)


def main():
    """主函數：批次優化候選策略"""
    engine = RefineryEngine()

    # 執行批次精煉（可設置最大處理數量）
    engine.run_refinery_batch(max_strategies=5)


if __name__ == "__main__":
    main()
