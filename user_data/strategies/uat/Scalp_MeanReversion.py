"""
Scalp_MeanReversion - 均值回歸策略
===================================
Purpose: 均值回歸策略，價格觸及布林帶下軌且RSI超賣時進場
Timeframe: 5m
Entry: Price < BB lower band (2.5 std) AND RSI < 35
Exit: Price reaches BB middle band OR +1% take profit
Stop Loss: -0.5%

Backtest: 2025-01-01 ~ 2026-04-26
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_MeanReversion(IStrategy):
    # Fixed parameters
    stoploss = -0.005  # -0.5% stop loss
    minimal_roi = {
        "0": 0.01,  # +1% take profit immediately
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop - disabled for mean reversion
    trailing_stop = False

    # Bollinger Bands parameters (2.5 std dev for tighter bands)
    bb_period = 20
    bb_std = 2.0  # Wider bands - less extreme signals

    # RSI parameters
    rsi_period = 14
    rsi_threshold = 35

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands with 2.5 std dev
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

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # Volume SMA
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry Condition 1: Price below BB lower band (oversold)
        cond_oversold = dataframe["close"] < dataframe["bb_lower"]

        # Entry Condition 2: RSI < 35 (strong oversold)
        cond_rsi = dataframe["rsi"] < self.rsi_threshold

        # Volume confirmation (not too low)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * 0.5)

        # Bullish candle (recovery signal)
        cond_bullish = dataframe["close"] > dataframe["open"]

        dataframe["enter_long"] = (cond_oversold & cond_rsi & cond_volume & cond_bullish).astype(
            int
        )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: Price reaches BB middle band (mean reversion target)
        # OR use custom_exit for +1% take profit

        # Mark exit when price crosses BB middle from below
        cond_bb_middle = (dataframe["close"] >= dataframe["bb_middle"]) & (
            dataframe["close"].shift(1) < dataframe["bb_middle"].shift(1)
        )

        dataframe["exit_long"] = cond_bb_middle.astype(int)
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

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        """
        Custom exit: +1% take profit OR when price reaches BB middle
        This handles the primary exit logic for mean reversion
        """
        # Take profit at +1%
        if current_profit >= 0.01:
            return "take_profit_1pct"

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
        Fixed -0.5% stop loss
        """
        return -0.005
