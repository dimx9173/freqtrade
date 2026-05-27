"""
Scalp_EMA_RSI_Optimized_v2 - 優化版策略 v2
===========================================
進化重點：
- ATR(14) * 1.5 動態止損（波動適應性）
- 固定止盈 +1.5%（5x槓桿 = +7.5% 本金回報）
- 移除 trailing stop

進場：EMA多頭排列(5>12>20) + RSI 35-65
Timeframe: 5m
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_EMA_RSI_Optimized_v2(IStrategy):
    # Fixed parameters
    stoploss = -0.02
    minimal_roi = {
        "0": 0.015,  # +1.5% fixed take profit (5x leverage = +7.5% per trade)
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Disable trailing stop (use fixed TP instead)
    trailing_stop = False

    # EMA parameters
    ema_fast = 5
    ema_slow = 12
    ema_trend = 20

    # RSI parameters (35-65 range for momentum confirmation)
    rsi_period = 7
    rsi_min = 35
    rsi_max = 65

    # ATR parameters for dynamic stoploss
    atr_period = 14
    atr_multiplier = 1.5

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA indicators
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)
        dataframe["ema_trend"] = ta.EMA(dataframe, timeperiod=self.ema_trend)

        # EMA slope (rising)
        dataframe["ema_rising"] = dataframe["ema_fast"] > dataframe["ema_fast"].shift(2)

        # RSI indicator
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # ATR indicator for dynamic stoploss
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA multi-timeframe alignment: fast > slow > trend
        cond_ema_trend = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["ema_slow"] > dataframe["ema_trend"])
            & dataframe["ema_rising"]
        )

        # RSI momentum confirmation: 35-65 range
        cond_rsi = (dataframe["rsi"] >= self.rsi_min) & (dataframe["rsi"] <= self.rsi_max)

        # Entry: EMA alignment AND RSI confirmation
        dataframe["enter_long"] = (cond_ema_trend & cond_rsi).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = False
        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time,
        current_rate,
        current_profit,
        after_open_rate,
        before_open_rate,
        current_entry_rate,
        current_exit_rate,
        **kwargs,
    ) -> float:
        """
        Custom stoploss using ATR dynamic adjustment.
        ATR-based stop gives wider stops in volatile markets, tighter in calm markets.
        """
        # Get dataframe for the pair
        dataframe, _ = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)

        if dataframe is None or len(dataframe) < self.atr_period:
            # Fall back to default stoploss
            return -0.02

        # Get the last candle's ATR
        last_candle = dataframe.iloc[-1]
        atr_value = last_candle["atr"]

        if atr_value is None or np.isnan(atr_value):
            return -0.02

        # Calculate dynamic stoploss as percentage
        # ATR * multiplier / current_rate = stoploss percentage
        atr_stop_pct = (atr_value * self.atr_multiplier) / current_rate

        # Cap the stoploss to reasonable bounds (between 0.5% and 5%)
        atr_stop_pct = max(0.005, min(0.05, atr_stop_pct))

        # Return negative value for stoploss
        return -atr_stop_pct
