"""
Scalp_BB_Only - 單指標測試：布林帶波動策略
==========================================
Purpose: 純布林帶指標測試，隔離其他指標的影響
Timeframe: 5m
Entry: Price touches lower Bollinger Band in uptrend
Exit: Price touches upper Bollinger Band or trailing stop
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_BB_Only(IStrategy):
    # Fixed parameters
    stoploss = -0.03
    minimal_roi = {
        "1": 0.005,
        "2": 0.008,
        "4": 0.012,
        "8": 0.018,
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.006
    trailing_only_offset_is_reached = True

    # Bollinger Bands parameters
    bb_period = 20
    bb_std = 2.0

    # Trend confirmation (minimal - just EMA)
    ema_trend_period = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = ta.BBANDS(
            dataframe["close"], timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        dataframe["bb_upper"] = bb_upper
        dataframe["bb_middle"] = bb_middle
        dataframe["bb_lower"] = bb_lower

        # BB Width (volatility indicator)
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe[
            "bb_middle"
        ]

        # BB %B (position within bands)
        dataframe["bb_pct"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )

        # Trend EMA (simple, just to confirm direction)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend_period)

        # Volume SMA
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Trend: price above EMA50 (simple uptrend check)
        cond_trend = dataframe["close"] > dataframe["ema_trend"]

        # Entry: price touches or crosses lower BB (oversold)
        cond_oversold = dataframe["low"] <= dataframe["bb_lower"]

        # Volume confirmation
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * 0.8)

        # Bullish candle
        cond_bullish = dataframe["close"] > dataframe["open"]

        dataframe["enter_long"] = (cond_trend & cond_oversold & cond_volume & cond_bullish).astype(
            int
        )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: price touches upper BB (overbought)
        dataframe["exit_long"] = (dataframe["high"] >= dataframe["bb_upper"]).astype(int)
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
        進場前確認：檢查價差，避免高滑價環境
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return False

        last_candle = dataframe.iloc[-1]

        # 檢查價差 (Spread)
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > 0.006:
            return False

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
        return -0.03

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        if current_profit >= 0.018:
            return "profit_target"
        return None
