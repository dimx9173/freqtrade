"""
Scalp_RSI_Reversal - RSI 超賣反彈策略
=====================================
反向操作策略：進場超賣市場，出場反彈恢復

進場條件：RSI < 30（超賣區域，預期反彈）
出場條件：RSI > 60（復甦）或 +1% 止盈
止損：-0.5%

Timeframe: 5m
Leverage: 5x
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class Scalp_RSI_Reversal(IStrategy):
    # === 基本參數 ===
    stoploss = -0.005
    minimal_roi = {
        "0": 0.01,  # +1% 止盈（0分鐘即生效）
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # === 禁用 Trailing Stop ===
    trailing_stop = False
    position_adjustment_enable = False

    # === RSI 參數 ===
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought_exit = 60

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場：RSI < 30（超賣區域）
        """
        cond_rsi_oversold = dataframe["rsi"] < self.rsi_oversold

        dataframe["enter_long"] = cond_rsi_oversold.astype(int)
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        標準 exit_long 不用，讓 custom_exit 處理所有出場邏輯
        """
        dataframe["exit_long"] = 0
        return dataframe

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ) -> str | None:
        """
        智能出場邏輯：
        1. RSI > 60 → 指標出場（動量恢復）
        2. Profit >= +1% → 止盈出场
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1]

        rsi = last_candle["rsi"]

        # 條件1：RSI 回升到 60 以上（超賣反彈完成）
        if rsi > self.rsi_overbought_exit:
            return "rsi_recovery"

        # 條件2：+1% 止盈
        if current_profit >= 0.01:
            return "profit_target_1pct"

        return None

    def custom_stoploss(
        self,
        pair: str,
        trade,
        entry: float,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        固定止損：-0.5%
        """
        return -0.005
