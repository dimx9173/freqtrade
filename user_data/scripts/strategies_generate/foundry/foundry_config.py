"""
策略鑄造廠配置文件 (The Foundry Configuration)
階段一：全自動化生成與海選
"""

from pathlib import Path
from datetime import datetime, timedelta


class FoundryConfig:
    """鑄造廠核心配置"""

    # ==================== 路徑配置 ====================
    BASE_DIR = Path("/Users/carlos/pywork/freqtrade")
    USER_DATA_DIR = BASE_DIR / "user_data"
    STRATEGIES_GENERATE_DIR = USER_DATA_DIR / "scripts" / "strategies_generate"

    # Freqtrade 配置
    FREQTRADE_BIN = BASE_DIR / ".venv" / "bin" / "freqtrade"
    FREQTRADE_CONFIG = USER_DATA_DIR / "config" / "config_ScalpingStrategy.json"
    DATA_DIR = USER_DATA_DIR / "data" / "bybit"

    # 階段目錄
    FOUNDRY_DIR = STRATEGIES_GENERATE_DIR / "foundry"
    CANDIDATE_POOL_DIR = STRATEGIES_GENERATE_DIR / "successful_strategies" / "candidate_pool"
    TEMP_STRATEGIES_DIR = FOUNDRY_DIR / "temp_strategies"
    LOGS_DIR = FOUNDRY_DIR / "logs"

    # ==================== 技術指標庫 ====================
    INDICATOR_POOL = {
        "trend": [
            "EMA",  # 指數移動平均線
            "SMA",  # 簡單移動平均線
            "WMA",  # 加權移動平均線
            "DEMA",  # 雙指數移動平均線
            "TEMA",  # 三指數移動平均線
            "ADX",  # 平均趨向指數
            "MACD",  # 移動平均收斂發散
            "PSAR",  # 拋物線SAR
        ],
        "momentum": [
            "RSI",  # 相對強弱指數
            "Stochastic",  # 隨機指標
            "Stochastic_RSI",  # 隨機RSI
            "Williams_R",  # 威廉指標
            "CCI",  # 順勢指標
            "MOM",  # 動量指標
            "ROC",  # 變動率
        ],
        "volatility": [
            "ATR",  # 真實波動幅度
            "Bollinger_Bands",  # 布林帶
            "Keltner_Channel",  # 肯特納通道
        ],
        "volume": [
            "OBV",  # 能量潮
            "MFI",  # 資金流量指標
            "VWAP",  # 成交量加權平均價
        ],
    }

    # ==================== 篩選標準 (The Foundry KPIs) ====================
    # 第一階段：核心三項指標（簡化版）
    FOUNDRY_CRITERIA = {
        "max_drawdown": 0.05,  # < 5%
        "min_trades_per_month": 60,  # > 60 筆/月
        "min_win_rate": 0.60,  # > 60%
    }

    # ==================== 回測週期配置 ====================
    @staticmethod
    def get_backtest_periods():
        """獲取三個回測週期的時間範圍"""
        today = datetime.now()
        return {
            "3m": {
                "name": "3個月",
                "start": (today - timedelta(days=90)).strftime("%Y%m%d"),
                "end": today.strftime("%Y%m%d"),
                "days": 90,
            },
            "9m": {
                "name": "9個月",
                "start": (today - timedelta(days=270)).strftime("%Y%m%d"),
                "end": today.strftime("%Y%m%d"),
                "days": 270,
            },
            "18m": {
                "name": "18個月",
                "start": (today - timedelta(days=540)).strftime("%Y%m%d"),
                "end": today.strftime("%Y%m%d"),
                "days": 540,
            },
        }

    # ==================== Gemini CLI 配置 ====================
    GEMINI_CLI_PATH = "gemini"
    GEMINI_TIMEOUT = 300  # 5分鐘
    GEMINI_MAX_RETRIES = 3
    GEMINI_RETRY_DELAY = 5

    # ==================== 交易配置 ====================
    TIMEFRAME = "5m"
    MAX_OPEN_TRADES = 3
    STAKE_AMOUNT = 10
    TRADING_MODE = "futures"
    MARGIN_MODE = "isolated"

    # ==================== 運行配置 ====================
    CYCLE_INTERVAL = 300  # 每輪間隔秒數
    MAX_TEMP_STRATEGIES = 100  # 最多保留臨時策略數
    ENABLE_AUTO_CLEANUP = True  # 自動清理失敗策略

    # ==================== 日誌配置 ====================
    LOG_LEVEL = "DEBUG"  # 改為 DEBUG 以查看更多信息
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

    # ==================== Git 配置 ====================
    ENABLE_GIT_INTEGRATION = True
    GIT_AUTO_COMMIT = True
    GIT_COMMIT_MESSAGE_TEMPLATE = "🎯 Foundry: Add candidate strategy {strategy_name} | Win Rate: {win_rate}% | Sharpe: {sharpe}"

    @classmethod
    def validate_config(cls):
        """驗證配置正確性"""
        issues = []

        # 檢查 Freqtrade
        if not cls.FREQTRADE_BIN.exists():
            issues.append(f"❌ Freqtrade 執行檔不存在: {cls.FREQTRADE_BIN}")

        # 檢查數據目錄
        if not cls.DATA_DIR.exists():
            issues.append(f"❌ 數據目錄不存在: {cls.DATA_DIR}")

        # 檢查配置文件
        if not cls.FREQTRADE_CONFIG.exists():
            issues.append(f"⚠️  配置文件不存在: {cls.FREQTRADE_CONFIG}")

        # 創建必要目錄
        for directory in [
            cls.FOUNDRY_DIR,
            cls.CANDIDATE_POOL_DIR,
            cls.TEMP_STRATEGIES_DIR,
            cls.LOGS_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        if issues:
            print("\n配置驗證結果:")
            for issue in issues:
                print(f"  {issue}")
            return len([i for i in issues if "❌" in i]) == 0

        print("\n✅ 配置驗證通過")
        print(f"   - Freqtrade: {cls.FREQTRADE_BIN}")
        print(f"   - 數據目錄: {cls.DATA_DIR}")
        print(f"   - 候選池: {cls.CANDIDATE_POOL_DIR}")
        print(
            f"   - 篩選標準: Win Rate > {cls.FOUNDRY_CRITERIA['min_win_rate']:.0%}, "
            f"Drawdown < {cls.FOUNDRY_CRITERIA['max_drawdown']:.0%}"
        )
        return True

    @classmethod
    def get_strategy_prompt_template(cls):
        """獲取策略生成 Prompt 模板"""
        return """你是 Freqtrade 剝頭皮策略專家。

請撰寫一個完整的 Freqtrade 策略，使用以下技術指標：
{indicators}

**策略要求：**
1. **時間框架**: 5分鐘 (5m)
2. **交易模式**: Futures (永續合約)
3. **交易方向**: Long & Short (雙向交易)
4. **本金**: 1000 USDT, 單筆: 10 USDT
5. **槓桿**: 10x

**策略目標 (The Foundry 標準):**
- 最大回撤: < 7%
- 月均交易: > 60 筆
- 勝率: > 50%
- 利潤因子: > 1.2
- 夏普比率: > 1.0

**入場邏輯設計原則：**
1. ✅ 結合 2-3 個指標的確認信號
2. ✅ 包含趨勢過濾（例如 ADX > 20）
3. ✅ 使用適中的閾值（RSI: 35-65，避免過於極端）
4. ✅ 總條件數: 3-4 個（使用 AND 組合）
5. ❌ 禁止使用「評分制」系統
6. ❌ 禁止使用 qtpylib.crossed_above/below（信號不穩定）
7. ❌ 禁止使用 pandas_ta.tsi()（改用 talib 的 RSI/CCI/MFI）

**出場邏輯：**
1. 使用動態止損（ATR 基礎）
2. 設置合理的 ROI 目標
3. 包含反向信號出場

**技術要求：**
1. 類名必須唯一（例如: ScalpingStrategy_{indicators_hash}）
2. 設置 `can_short = True`
3. 設置 `timeframe = '5m'`
4. 完整實現 populate_indicators, populate_entry_trend, populate_exit_trend
5. 使用 'enter_long'/'exit_long' 和 'enter_short'/'exit_short'
6. 如使用 reduce 函數，必須導入: from functools import reduce
7. talib 參數類型: timeperiod=int, nbdevup=float
8. talib 返回值處理:
   - STOCH: slowk, slowd = ta.STOCH(...)
   - BBANDS: upper, mid, lower = ta.BBANDS(...)
   - MACD: macd, signal, hist = ta.MACD(...)

請生成完整的策略代碼，用 ```python ... ``` 包裹。"""


if __name__ == "__main__":
    config = FoundryConfig()
    config.validate_config()
