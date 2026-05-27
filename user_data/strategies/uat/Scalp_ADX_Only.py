"""
Scalp_ADX_Only - 單指標測試：ADX趨勢強度策略
============================================
目的：隔離測試 ADX 指標的有效性
進場邏輯：僅使用 ADX > threshold 判斷趨勢強度
退出：標準 trailing stop + ATR stop
時間框架：5m
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_ADX_Only(IStrategy):
    # Fixed parameters
    stoploss = -0.02
    minimal_roi = {
        "1": 0.004,
        "2": 0.007,
        "4": 0.010,
        "8": 0.015,
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.002
    trailing_stop_positive_offset = 0.004
    trailing_only_offset_is_reached = True

    # ADX parameters - 單指標測試
    adx_period = 14
    adx_threshold = 25  # ADX > 25 表示趨勢強度足夠

    # 進場輔助：避免過度震盪
    adx_period_fast = 5
    adx_threshold_fast = 30  # 快 ADX 確認趨勢

    # Slippage protection thresholds
    max_spread_pct = 0.005  # 0.5% max spread
    max_atr_pct = 0.01  # 1% max ATR

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ADX 主指標
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=self.adx_period)
        dataframe["adx_fast"] = ta.ADX(dataframe, timeperiod=self.adx_period_fast)

        # 輔助：Directional Movement
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=self.adx_period)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=self.adx_period)

        # ATR for volatility check
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 單指標進場條件：ADX 突破閾值
        cond_adx_strong = dataframe["adx"] > self.adx_threshold
        cond_adx_fast = dataframe["adx_fast"] > self.adx_threshold_fast

        # 趨勢方向：+DI > -DI 表示多頭趨勢
        cond_uptrend = dataframe["plus_di"] > dataframe["minus_di"]

        # 快 ADX 確認不是在盤整結束即將反轉
        cond_adx_rising = dataframe["adx_fast"] > dataframe["adx_fast"].shift(1)

        # 進場條件组合
        dataframe["enter_long"] = (
            cond_adx_strong & cond_adx_fast & cond_uptrend & cond_adx_rising
        ).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 不使用 exit signal，讓 trailing stop 自然運作
        dataframe["exit_long"] = False
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> bool:
        """
        進場前確認：檢查價差和波動率，避免高滑價環境
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return False

        last_candle = dataframe.iloc[-1]

        # 1. 檢查價差 (Spread)
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > self.max_spread_pct:
            return False  # 價差太大，跳過

        # 2. 檢查波動率 (ATR)
        atr_pct = last_candle["atr"] / last_candle["close"]
        if atr_pct > self.max_atr_pct:
            return False  # 波動太大，跳過

        return True

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
        return -0.02

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.015:
            return "profit_target"
        return None
