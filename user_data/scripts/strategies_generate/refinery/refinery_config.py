"""
精煉工坊配置文件 (The Refinery Configuration)
階段二：半自動化潛力優化
"""

from pathlib import Path


class RefineryConfig:
    """精煉工坊核心配置"""

    # ==================== 路徑配置 ====================
    BASE_DIR = Path("/Users/carlos/pywork/freqtrade")
    USER_DATA_DIR = BASE_DIR / "user_data"
    STRATEGIES_GENERATE_DIR = USER_DATA_DIR / "scripts" / "strategies_generate"

    # Freqtrade 配置
    FREQTRADE_BIN = BASE_DIR / ".venv" / "bin" / "freqtrade"
    FREQTRADE_CONFIG = USER_DATA_DIR / "config" / "config_ScalpingStrategy.json"
    DATA_DIR = USER_DATA_DIR / "data" / "bybit"

    # 階段目錄
    REFINERY_DIR = STRATEGIES_GENERATE_DIR / "refinery"
    CANDIDATE_POOL_DIR = STRATEGIES_GENERATE_DIR / "successful_strategies" / "candidate_pool"
    OPTIMIZED_DIR = STRATEGIES_GENERATE_DIR / "successful_strategies" / "optimized_candidates"
    LOGS_DIR = REFINERY_DIR / "logs"

    # ==================== Hyperopt 配置 ====================
    HYPEROPT_EPOCHS = 100  # 優化輪數
    HYPEROPT_LOSS = "SharpeHyperOptLoss"  # 優化目標：夏普比率
    HYPEROPT_SPACES = ["buy", "sell", "roi", "stoploss"]  # 優化空間
    HYPEROPT_TIMERANGE_DAYS = 365  # 使用過去12個月數據

    # ==================== 優化標準 ====================
    REFINEMENT_CRITERIA = {
        "sharpe_improvement": 0.20,  # 夏普比率提升 > 20%
        "profit_improvement": 0.15,  # 總利潤提升 > 15%
        "min_sharpe_after_opt": 1.2,  # 優化後夏普比率 > 1.2
    }

    # ==================== 優化參數範圍 ====================
    OPTIMIZATION_RANGES = {
        # ROI (Return on Investment)
        "roi": {
            "0": (0.01, 0.10),  # 即時止盈: 1%-10%
            "30": (0.005, 0.05),  # 30分鐘: 0.5%-5%
            "60": (0.002, 0.02),  # 60分鐘: 0.2%-2%
            "120": (0.001, 0.01),  # 120分鐘: 0.1%-1%
        },
        # 止損
        "stoploss": {
            "range": (-0.10, -0.02),  # -10% 到 -2%
        },
        # 買入/賣出指標參數（示例）
        "indicators": {
            "rsi_period": (7, 21),
            "ema_short": (5, 20),
            "ema_long": (20, 50),
            "bb_period": (15, 30),
            "bb_std": (1.5, 3.0),
        },
    }

    # ==================== 日誌配置 ====================
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

    # ==================== Git 配置 ====================
    ENABLE_GIT_INTEGRATION = True
    GIT_COMMIT_MESSAGE_TEMPLATE = (
        "🔧 Refinery: Optimized {strategy_name} | Sharpe: {sharpe_before:.2f} → {sharpe_after:.2f}"
    )

    @classmethod
    def validate_config(cls):
        """驗證配置正確性"""
        issues = []

        # 檢查 Freqtrade
        if not cls.FREQTRADE_BIN.exists():
            issues.append(f"❌ Freqtrade 執行檔不存在: {cls.FREQTRADE_BIN}")

        # 檢查候選池
        if not cls.CANDIDATE_POOL_DIR.exists():
            issues.append(f"⚠️  候選池目錄不存在: {cls.CANDIDATE_POOL_DIR}")

        # 創建必要目錄
        for directory in [cls.REFINERY_DIR, cls.OPTIMIZED_DIR, cls.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

        if issues:
            print("\n配置驗證結果:")
            for issue in issues:
                print(f"  {issue}")
            return len([i for i in issues if "❌" in i]) == 0

        print("\n✅ 精煉工坊配置驗證通過")
        print(f"   - Freqtrade: {cls.FREQTRADE_BIN}")
        print(f"   - 候選池: {cls.CANDIDATE_POOL_DIR}")
        print(f"   - 優化輪數: {cls.HYPEROPT_EPOCHS}")
        print(f"   - 優化目標: {cls.HYPEROPT_LOSS}")
        return True


if __name__ == "__main__":
    config = RefineryConfig()
    config.validate_config()
