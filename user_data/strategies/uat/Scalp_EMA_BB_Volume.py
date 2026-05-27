"""
Scalp_EMA_BB_Volume - 三指標組合測試：EMA + BB + Volume
========================================================
Purpose: 測試 EMA多頭排列 + BB觸及下軌 + Volume > 1.2x均量 組合策略
Timeframe: 5m
Backtest: 12 months

Entry Conditions:
  1. EMA多頭排列: EMA5 > EMA10 > EMA20 (短期上升趨勢確認)
  2. BB觸及下軌: 低價接觸或穿越布林帶下軌 (超賣信号)
  3. Volume > 1.2x均量: 成交量放大確認

Exit Conditions:
  - BB觸及上軌 或 trailing stop
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_EMA_BB_Volume(IStrategy):
    # ============ Fixed Parameters ============
    stoploss = -0.03
    minimal_roi = {
        "1": 0.005,
        "2": 0.008,
        "4": 0.012,
        "8": 0.018,
    }
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.003
    trailing_stop_positive_offset = 0.006
    trailing_only_offset_is_reached = True

    # ============ Leverage Method ============
    def leverage(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        return 5

    # ============ EMA Parameters (多頭排列) ============
    ema_short_period = 5  # 短期 EMA
    ema_mid_period = 10  # 中期 EMA
    ema_long_period = 20  # 長期 EMA (趨勢確認)

    # ============ Bollinger Bands Parameters ============
    bb_period = 20
    bb_std = 2.0

    # ============ Volume Parameters ============
    volume_sma_period = 20
    volume_multiplier = 1.2  # Volume must be > 1.2x average ( loosened from 1.5x)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ============ EMA Calculations ============
        # 三條EMA用於多頭排列判斷
        dataframe["ema5"] = ta.EMA(dataframe, timeperiod=self.ema_short_period)
        dataframe["ema10"] = ta.EMA(dataframe, timeperiod=self.ema_mid_period)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=self.ema_long_period)

        # EMA多頭排列條件: EMA5 > EMA10 > EMA20
        dataframe["ema_bull_alignment"] = (
            (dataframe["ema5"] > dataframe["ema10"]) & (dataframe["ema10"] > dataframe["ema20"])
        ).astype(int)

        # EMA slope (趨勢強度)
        dataframe["ema5_slope"] = dataframe["ema5"].pct_change(periods=3)
        dataframe["ema10_slope"] = dataframe["ema10"].pct_change(periods=3)

        # ============ Bollinger Bands ============
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

        # BB %B (position within bands, 0 = at lower band, 1 = at upper band)
        dataframe["bb_pct"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )

        # ============ Volume Indicators ============
        # Volume SMA
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=self.volume_sma_period)

        # Volume ratio (current volume / average volume)
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"]

        # Volume spike confirmation
        dataframe["volume_spike"] = (dataframe["volume_ratio"] >= self.volume_multiplier).astype(
            int
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ============ Entry Conditions ============

        # 條件1: EMA多頭排列 (短期 > 中期 > 長期)
        cond_ema_bull = (dataframe["ema5"] > dataframe["ema10"]) & (
            dataframe["ema10"] > dataframe["ema20"]
        )

        # 條件2: BB觸及下軌 (低價接觸或穿越下軌 = 超賣)
        cond_bb_oversold = dataframe["low"] <= dataframe["bb_lower"]

        # 條件3: Volume > 1.2x 均量確認
        cond_volume = dataframe["volume_ratio"] >= self.volume_multiplier

        # 牛市蠟燭確認
        cond_bullish = dataframe["close"] > dataframe["open"]

        # 結合所有進場條件
        dataframe["enter_long"] = np.where(
            cond_ema_bull & cond_bb_oversold & cond_volume & cond_bullish, 1, 0
        )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ============ Exit Conditions ============

        # 條件1: BB觸及上軌 (超買 = 止盈信號)
        cond_bb_overbought = dataframe["high"] >= dataframe["bb_upper"]

        # 條件2: EMA多頭排列結束 (EMA5 < EMA10)
        cond_ema_bear = dataframe["ema5"] < dataframe["ema10"]

        dataframe["exit_long"] = (cond_bb_overbought | cond_ema_bear).astype(int)

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

        # 檢查價差 (Spread) - 放寬至 1% 允許更大波動
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > 0.01:
            return False

        # 額外確認: BB寬度不能太小 (市場要有波動)
        if last_candle.get("bb_width", 0) < 0.005:
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
        """
        自定義止損: 3% 止損
        """
        return -0.03

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        """
        自定義出场: 目標利潤
        """
        if current_profit >= 0.018:
            return "profit_target_1.8pct"
        if current_profit >= 0.012:
            return "profit_target_1.2pct"
        return None
