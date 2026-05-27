#!/usr/bin/env python3
"""
策略鑄造廠核心引擎 (The Foundry Engine)
功能：AI 策略生成、多週期回測、嚴格篩選
"""

import json
import subprocess
import random
import re
import time
import logging
import hashlib
from datetime import datetime
import shutil

from foundry_config import FoundryConfig as Config

# 配置日誌
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL), format=Config.LOG_FORMAT)
logger = logging.getLogger(__name__)


class FoundryEngine:
    """策略鑄造廠核心引擎"""

    def __init__(self):
        self.config = Config()

        # 驗證配置
        if not self.config.validate_config():
            raise RuntimeError("配置驗證失敗")

        # 統計數據
        self.stats = {
            "total_generated": 0,
            "total_passed": 0,
            "total_failed": 0,
            "start_time": datetime.now(),
        }

    def generate_indicator_combination(self):
        """生成隨機指標組合 (2-3個)"""
        num_indicators = random.randint(2, 3)
        combination = []

        # 確保包含不同類型的指標
        categories = list(Config.INDICATOR_POOL.keys())
        random.shuffle(categories)

        for category in categories[:num_indicators]:
            indicator = random.choice(Config.INDICATOR_POOL[category])
            combination.append(indicator)

        return combination

    def generate_strategy_code(self, indicators):
        """調用 Gemini CLI 生成策略代碼"""
        # 生成唯一策略名稱
        indicator_str = "_".join(indicators)
        strategy_hash = hashlib.md5(indicator_str.encode()).hexdigest()[:8]

        # 構建 Prompt
        prompt = Config.get_strategy_prompt_template().format(
            indicators=", ".join(indicators), indicators_hash=strategy_hash
        )

        # 調用 Gemini CLI
        for attempt in range(1, Config.GEMINI_MAX_RETRIES + 1):
            try:
                logger.info(
                    f"🤖 調用 Gemini CLI 生成策略 (嘗試 {attempt}/{Config.GEMINI_MAX_RETRIES})"
                )

                result = subprocess.run(
                    [Config.GEMINI_CLI_PATH],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=Config.GEMINI_TIMEOUT,
                )

                if result.returncode == 0 and "```python" in result.stdout:
                    # 提取代碼
                    parts = result.stdout.split("```python")
                    if len(parts) > 1:
                        code = parts[1].split("```")[0].strip()

                        # 自動修復常見問題
                        code = self.fix_code_issues(code)

                        logger.info("✅ 策略代碼生成成功")
                        return code, strategy_hash

                logger.warning(f"⚠️  Gemini 輸出無效，重試...")

            except subprocess.TimeoutExpired:
                logger.warning(f"⏳ Gemini CLI 超時 ({Config.GEMINI_TIMEOUT}s)，重試...")

            except Exception as e:
                logger.error(f"❌ Gemini CLI 錯誤: {e}")

            if attempt < Config.GEMINI_MAX_RETRIES:
                time.sleep(Config.GEMINI_RETRY_DELAY)

        logger.error("❌ 策略生成最終失敗")
        return None, None

    def fix_code_issues(self, code):
        """自動修復常見代碼問題"""
        fixes_applied = []

        # 1. 修復 STOCHRSI 返回值（最常見的錯誤）
        if "ta.STOCHRSI(" in code and ("stoch_rsi['fast" in code or "stochrsi['fast" in code):
            # 查找變量名
            stochrsi_var_match = re.search(r"(\w+)\s*=\s*ta\.STOCHRSI\(", code)
            if stochrsi_var_match:
                var_name = stochrsi_var_match.group(1)
                code = code.replace(
                    f"{var_name} = ta.STOCHRSI(", "stoch_rsi_k, stoch_rsi_d = ta.STOCHRSI("
                )
                code = code.replace(f"{var_name}['fastk']", "stoch_rsi_k")
                code = code.replace(f"{var_name}['fastd']", "stoch_rsi_d")
                code = code.replace(f"['{var_name}']['fastk']", "['stoch_rsi_k']")
                code = code.replace(f"['{var_name}']['fastd']", "['stoch_rsi_d']")
                fixes_applied.append("STOCHRSI")

        # 2. 修復 STOCH 返回值
        if "ta.STOCH(" in code and "stoch['slow" in code:
            code = code.replace("stoch = ta.STOCH(", "slowk, slowd = ta.STOCH(")
            code = code.replace("stoch['slowk']", "slowk")
            code = code.replace("stoch['slowd']", "slowd")
            fixes_applied.append("STOCH")

        # 3. 修復 BBANDS 返回值
        if "ta.BBANDS(" in code and "bbands['" in code:
            code = code.replace(
                "bbands = ta.BBANDS(", "upperband, middleband, lowerband = ta.BBANDS("
            )
            code = code.replace("bbands['upperband']", "upperband")
            code = code.replace("bbands['middleband']", "middleband")
            code = code.replace("bbands['lowerband']", "lowerband")
            fixes_applied.append("BBANDS")

        # 4. 修復 MACD 返回值
        if "ta.MACD(" in code and ("macd_result['" in code or "macd['" in code):
            code = re.sub(r"(\w+)\s*=\s*ta\.MACD\(", "macd, macdsignal, macdhist = ta.MACD(", code)
            code = code.replace("macd_result['macd']", "macd")
            code = code.replace("macd_result['macdsignal']", "macdsignal")
            code = code.replace("macd_result['macdhist']", "macdhist")
            fixes_applied.append("MACD")

        # 5. 修復 talib 參數類型
        if re.search(r"(nbdevup|nbdevdn)=(\d+)([,\)])", code):
            code = re.sub(r"(nbdevup|nbdevdn)=(\d+)([,\)])", r"\1=\2.0\3", code)
            fixes_applied.append("參數類型")

        # 6. 修復 ROI None 值
        if ": None" in code:
            code = re.sub(r":\s*None", ": 0.005", code)
            fixes_applied.append("ROI None")

        if fixes_applied:
            logger.info(f"🔧 自動修復: {', '.join(fixes_applied)}")

        return code

    def save_strategy_file(self, code, strategy_hash):
        """保存策略文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gen_strategy_{timestamp}_{strategy_hash}.py"
        filepath = Config.TEMP_STRATEGIES_DIR / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        logger.info(f"💾 策略已保存: {filename}")
        return filepath, filename.replace(".py", "")

    def extract_strategy_class_name(self, code):
        """從代碼中提取策略類名"""
        match = re.search(r"class\s+(\w+)\s*\(.*IStrategy.*\):", code)
        if match:
            return match.group(1)
        return None

    def run_backtest(self, strategy_path, strategy_name, period_key):
        """執行單次回測"""
        periods = Config.get_backtest_periods()
        period = periods[period_key]
        timerange = f"{period['start']}-{period['end']}"

        # 構建回測命令
        cmd = [
            str(Config.FREQTRADE_BIN),
            "backtesting",
            "--strategy-path",
            str(Config.TEMP_STRATEGIES_DIR),
            "--strategy",
            strategy_name,
            "--datadir",
            str(Config.DATA_DIR),
            "--timerange",
            timerange,
            "--timeframe",
            Config.TIMEFRAME,
            "--export",
            "trades",
            "--cache",
            "none",
            "--max-open-trades",
            str(Config.MAX_OPEN_TRADES),
            "--stake-amount",
            str(Config.STAKE_AMOUNT),
        ]

        # 必須添加配置文件
        if Config.FREQTRADE_CONFIG.exists():
            cmd.extend(["--config", str(Config.FREQTRADE_CONFIG)])
        else:
            logger.error(f"❌ 配置文件不存在: {Config.FREQTRADE_CONFIG}")
            return None

        logger.info(f"📈 執行 {period['name']} 回測: {timerange}")
        logger.debug(f"回測命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, cwd=str(Config.BASE_DIR)
            )

            if result.returncode != 0:
                logger.error(f"❌ {period['name']} 回測失敗")
                logger.error(f"錯誤輸出 (stderr):\n{result.stderr}")
                # 顯示標準輸出的最後部分（通常包含錯誤詳情）
                if result.stdout:
                    logger.error(f"標準輸出 (stdout 最後 2000 字符):\n{result.stdout[-2000:]}")
                return None

            # 尋找結果文件 - 改進邏輯
            backtest_results_dir = Config.USER_DATA_DIR / "backtest_results"

            if not backtest_results_dir.exists():
                logger.error(f"❌ 回測結果目錄不存在: {backtest_results_dir}")
                return None

            # 找最新的結果文件（zip 或 json）
            import time

            current_time = time.time()
            result_files = []

            # 查找 zip 和 json 文件（優先 zip）
            for pattern in ["*.zip", "*.json"]:
                for result_file in backtest_results_dir.glob(pattern):
                    # 排除 meta.json 文件
                    if result_file.name.endswith(".meta.json"):
                        continue
                    # 只檢查最近15秒內創建的文件
                    if current_time - result_file.stat().st_mtime < 15:
                        result_files.append(result_file)

            if not result_files:
                logger.error(f"❌ 找不到最近的回測結果文件")
                logger.info(f"檢查目錄: {backtest_results_dir}")
                logger.info(f"標準輸出: {result.stdout[-500:]}")
                return None

            # 按修改時間排序，取最新的
            result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            for result_file in result_files[:3]:
                try:
                    logger.debug(f"嘗試讀取: {result_file}")

                    # 處理 zip 文件
                    if result_file.suffix == ".zip":
                        import zipfile

                        with zipfile.ZipFile(result_file, "r") as zip_ref:
                            # 尋找 JSON 文件（通常是 backtest-result-*.json）
                            json_files = [
                                f
                                for f in zip_ref.namelist()
                                if f.endswith(".json") and not f.endswith(".meta.json")
                            ]

                            if not json_files:
                                logger.warning(f"ZIP 文件 {result_file.name} 中沒有 JSON 結果")
                                continue

                            # 讀取第一個 JSON 文件
                            json_filename = json_files[0]
                            with zip_ref.open(json_filename) as json_file:
                                data = json.load(json_file)
                    else:
                        # 處理 JSON 文件
                        with open(result_file, "r") as f:
                            data = json.load(f)

                    # 驗證數據結構
                    if "strategy" in data and data["strategy"]:
                        logger.info(f"✅ {period['name']} 回測成功")
                        logger.debug(f"使用結果文件: {result_file.name}")
                        return data
                    else:
                        logger.warning(f"文件 {result_file.name} 沒有策略數據")

                except zipfile.BadZipFile as e:
                    logger.warning(f"ZIP 文件損壞 {result_file.name}: {e}")
                    continue
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON 解析錯誤 {result_file.name}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"讀取文件錯誤 {result_file.name}: {e}")
                    continue

            logger.error(f"❌ 所有結果文件都無效")
            return None

        except subprocess.TimeoutExpired:
            logger.error(f"⏳ {period['name']} 回測超時")
            return None

        except Exception as e:
            logger.error(f"❌ {period['name']} 回測異常: {e}", exc_info=True)
            return None

    def evaluate_backtest_result(self, backtest_data, period_days):
        """評估回測結果是否通過篩選標準"""
        if not backtest_data:
            return False, {}

        try:
            strategy_data = backtest_data.get("strategy", {})
            if not strategy_data:
                return False, {}

            # 獲取策略結果
            strategy_name = list(strategy_data.keys())[0]
            results = strategy_data[strategy_name]
            results_per_pair = results.get("results_per_pair", [])

            # 找到 TOTAL 數據
            total_data = None
            for item in results_per_pair:
                if item.get("key") == "TOTAL":
                    total_data = item
                    break

            if not total_data:
                return False, {}

            # 提取關鍵指標
            total_trades = total_data.get("trades", 0)
            wins = total_data.get("wins", 0)
            profit_total_pct = total_data.get("profit_total_pct", 0)
            max_drawdown = abs(total_data.get("max_drawdown_account", 1.0))

            # 計算指標
            win_rate = wins / total_trades if total_trades > 0 else 0
            trades_per_month = total_trades * (30 / period_days) if period_days > 0 else 0

            # 計算利潤因子和夏普比率（從完整結果中提取）
            profit_factor = results.get("profit_factor", 0)
            sharpe_ratio = results.get("sharpe", 0)

            # 組織 KPIs
            kpis = {
                "win_rate": win_rate,
                "trades_per_month": trades_per_month,
                "max_drawdown": max_drawdown,
                "profit_factor": profit_factor,
                "sharpe_ratio": sharpe_ratio,
                "total_trades": total_trades,
                "profit_total_pct": profit_total_pct,
            }

            # 檢查是否通過所有標準（核心三項）
            criteria = Config.FOUNDRY_CRITERIA
            passed = (
                max_drawdown < criteria["max_drawdown"]
                and trades_per_month > criteria["min_trades_per_month"]
                and win_rate > criteria["min_win_rate"]
            )

            return passed, kpis

        except Exception as e:
            logger.error(f"評估結果時發生錯誤: {e}")
            return False, {}

    def run_multi_period_backtest(self, strategy_path, strategy_name):
        """執行三個週期的回測並評估"""
        periods = ["3m", "9m", "18m"]
        all_passed = True
        all_kpis = {}

        for period_key in periods:
            # 執行回測
            backtest_data = self.run_backtest(strategy_path, strategy_name, period_key)

            # 評估結果
            period_days = Config.get_backtest_periods()[period_key]["days"]
            passed, kpis = self.evaluate_backtest_result(backtest_data, period_days)

            all_kpis[period_key] = kpis

            # 記錄結果
            if passed:
                logger.info(f"✅ {period_key} 通過篩選")
                logger.info(
                    f"   勝率: {kpis['win_rate']:.1%} | "
                    f"月交易: {kpis['trades_per_month']:.0f} | "
                    f"回撤: {kpis['max_drawdown']:.1%} | "
                    f"夏普: {kpis['sharpe_ratio']:.2f}"
                )
            else:
                logger.warning(f"❌ {period_key} 未通過篩選")
                logger.warning(
                    f"   勝率: {kpis.get('win_rate', 0):.1%} | "
                    f"月交易: {kpis.get('trades_per_month', 0):.0f} | "
                    f"回撤: {kpis.get('max_drawdown', 0):.1%}"
                )
                logger.warning(
                    f"   利潤因子: {kpis.get('profit_factor', 0):.2f} | "
                    f"夏普比率: {kpis.get('sharpe_ratio', 0):.2f}"
                )

                # 顯示未通過的具體標準（核心三項）
                criteria = Config.FOUNDRY_CRITERIA
                failures = []
                if kpis.get("max_drawdown", 1) >= criteria["max_drawdown"]:
                    failures.append(
                        f"回撤 {kpis.get('max_drawdown', 0):.1%} >= {criteria['max_drawdown']:.1%}"
                    )
                if kpis.get("trades_per_month", 0) <= criteria["min_trades_per_month"]:
                    failures.append(
                        f"月交易 {kpis.get('trades_per_month', 0):.0f} <= {criteria['min_trades_per_month']}"
                    )
                if kpis.get("win_rate", 0) <= criteria["min_win_rate"]:
                    failures.append(
                        f"勝率 {kpis.get('win_rate', 0):.1%} <= {criteria['min_win_rate']:.1%}"
                    )

                if failures:
                    logger.warning(f"   未通過原因: {'; '.join(failures)}")

                all_passed = False
                break  # 快速失敗

        return all_passed, all_kpis

    def promote_to_candidate_pool(self, strategy_path, indicators, kpis):
        """將通過篩選的策略晉升到候選池"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        indicator_str = "_".join(indicators)

        # 創建候選策略目錄
        candidate_dir = Config.CANDIDATE_POOL_DIR / f"candidate_{timestamp}"
        candidate_dir.mkdir(parents=True, exist_ok=True)

        # 複製策略文件
        new_strategy_path = candidate_dir / strategy_path.name
        shutil.copy(strategy_path, new_strategy_path)

        # 保存元數據
        metadata = {
            "timestamp": timestamp,
            "indicators": indicators,
            "kpis": {k: {period: v for period, v in kpis.items()} for k, v in kpis.items()},
            "foundry_passed": True,
            "promoted_at": datetime.now().isoformat(),
        }

        with open(candidate_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info(f"🎉 策略已晉升至候選池: {candidate_dir.name}")

        # Git 整合
        if Config.ENABLE_GIT_INTEGRATION:
            self.git_commit_strategy(new_strategy_path, metadata)

        return candidate_dir

    def git_commit_strategy(self, strategy_path, metadata):
        """將策略提交到 Git"""
        try:
            # 獲取 KPI 數據
            kpis_3m = metadata["kpis"].get("3m", {})
            win_rate = kpis_3m.get("win_rate", 0) * 100
            sharpe = kpis_3m.get("sharpe_ratio", 0)

            commit_message = Config.GIT_COMMIT_MESSAGE_TEMPLATE.format(
                strategy_name=strategy_path.stem, win_rate=f"{win_rate:.1f}", sharpe=f"{sharpe:.2f}"
            )

            subprocess.run(
                ["git", "add", str(strategy_path)],
                cwd=str(Config.STRATEGIES_GENERATE_DIR),
                check=False,
            )
            subprocess.run(
                ["git", "add", str(strategy_path.parent / "metadata.json")],
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

    def cleanup_failed_strategy(self, strategy_path):
        """清理失敗的策略文件"""
        if Config.ENABLE_AUTO_CLEANUP and strategy_path.exists():
            strategy_path.unlink()
            logger.info(f"🗑️  已清理失敗策略: {strategy_path.name}")

    def run_foundry_cycle(self):
        """執行一個完整的鑄造廠週期"""
        logger.info("=" * 70)
        logger.info("🏭 開始新一輪策略鑄造...")
        logger.info("=" * 70)

        self.stats["total_generated"] += 1

        # 1. 生成指標組合
        indicators = self.generate_indicator_combination()
        logger.info(f"🧬 指標組合: {', '.join(indicators)}")

        # 2. 生成策略代碼
        code, strategy_hash = self.generate_strategy_code(indicators)
        if not code:
            logger.error("❌ 策略生成失敗，終止本輪")
            self.stats["total_failed"] += 1
            return False

        # 3. 保存策略文件
        strategy_path, strategy_module = self.save_strategy_file(code, strategy_hash)
        strategy_class = self.extract_strategy_class_name(code)

        if not strategy_class:
            logger.error("❌ 無法提取策略類名，終止本輪")
            self.cleanup_failed_strategy(strategy_path)
            self.stats["total_failed"] += 1
            return False

        # 4. 執行多週期回測
        passed, kpis = self.run_multi_period_backtest(strategy_path, strategy_class)

        # 5. 處理結果
        if passed:
            logger.info("🎊 恭喜！策略通過所有篩選標準！")
            self.promote_to_candidate_pool(strategy_path, indicators, kpis)
            self.stats["total_passed"] += 1

            # 清理臨時文件（可選）
            # self.cleanup_failed_strategy(strategy_path)

            return True
        else:
            logger.info("💔 策略未通過篩選標準")
            self.cleanup_failed_strategy(strategy_path)
            self.stats["total_failed"] += 1
            return False

    def print_stats(self):
        """打印統計信息"""
        runtime = datetime.now() - self.stats["start_time"]
        success_rate = (
            self.stats["total_passed"] / self.stats["total_generated"] * 100
            if self.stats["total_generated"] > 0
            else 0
        )

        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 鑄造廠運行統計")
        logger.info("=" * 70)
        logger.info(f"   總生成數: {self.stats['total_generated']}")
        logger.info(f"   ✅ 通過: {self.stats['total_passed']}")
        logger.info(f"   ❌ 失敗: {self.stats['total_failed']}")
        logger.info(f"   🎯 成功率: {success_rate:.1f}%")
        logger.info(f"   ⏱️  運行時間: {runtime}")
        logger.info("=" * 70)
        logger.info("")


def main():
    """主函數：7x24 持續運行"""
    engine = FoundryEngine()

    logger.info("🏭 策略鑄造廠啟動成功")
    logger.info(
        f"⚙️  篩選標準 (核心三項): Win Rate > {Config.FOUNDRY_CRITERIA['min_win_rate']:.0%}, "
        f"Trades/Month > {Config.FOUNDRY_CRITERIA['min_trades_per_month']}, "
        f"Drawdown < {Config.FOUNDRY_CRITERIA['max_drawdown']:.0%}"
    )
    logger.info("")

    cycle_count = 0

    try:
        while True:
            cycle_count += 1
            logger.info(f"🔄 ===== 第 {cycle_count} 輪鑄造開始 =====")

            try:
                engine.run_foundry_cycle()
            except Exception as e:
                logger.error(f"❌ 本輪發生錯誤: {e}", exc_info=True)

            logger.info(f"🔄 ===== 第 {cycle_count} 輪鑄造完成 =====")

            # 每10輪打印統計
            if cycle_count % 10 == 0:
                engine.print_stats()

            # 等待下一輪
            logger.info(f"⏱️  等待 {Config.CYCLE_INTERVAL} 秒後開始下一輪...")
            time.sleep(Config.CYCLE_INTERVAL)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("⚠️  接收到中斷信號，正在安全退出...")
        engine.print_stats()
        logger.info("👋 鑄造廠已停止")


if __name__ == "__main__":
    main()
