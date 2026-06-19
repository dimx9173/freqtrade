"""
VCB_MACD_1h_TP10_SL1.5 - VCB + MACD with Aggressive TP/SL
=========================================================
TOP VARIANT #1: TP=10%, SL=1.5% (R:R = 6.7:1)

Backtest Results (2025-05-01 to 2026-05-05):
- Win Rate: 33.3%
- Total Profit: 25.8%
- Annual Return: 25.5%
- Max Drawdown: -11.6%
- Sortino: 3.03

Filters: ATR < 0.30×MA200, Vrank < 0.10, MACD.hist > 0
"""

import talib.abstract as ta
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from typing import Optional


class VCB_MACD_1h_TP10_SL1_5(IStrategy):
    """
    VCB - Volatility Compression Breakout (TP10/SL1.5 variant)
    低波動壓縮後的方向突破進場 + MACD 零軸上方過濾
    激進 TP/SL: 10%/1.5% (R:R = 6.7:1)
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"

    # === 基本設定 ===
    can_short = False  # 僅做多
    can_long = True

    # SL: 1.5%
    stoploss = -0.015

    # TP: 10%
    minimal_roi = {
        "0": 0.10,
        "1440": 0.02,  # 24h 後降至 2%
    }

    # 最大持有: 24h = 24 根 1h K线
    max_exit_age = 24
    exit_profit_only = False

    # 退出signal
    use_exit_signal = True

    trailing_stop = False
    trailing_stop_positive = 0.0
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False

    # 启动等待
    startup_candle_count = 200
    process_only_new_candles = False

    # ========== 策略参数 ==========
    atr_compression_threshold = 0.30
    vrank_threshold = 0.10
    atr_period = 14
    atr_ma_period = 200
    vrank_period = 48

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算进场指标：
        1. ATR_pct: (H-L)/C * 100
        2. ATR_pct_ma200: 200日 ATR 均線
        3. Vrank_48: 成交量排名的百分位
        4. MACD: 快線慢線交叉
        """

        # === 1. ATR% (Python VCB 定義) ===
        dataframe["atr_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"] * 100.0

        # === 2. ATR% 200日均線 ===
        dataframe["atr_pct_ma"] = dataframe["atr_pct"].rolling(window=self.atr_ma_period).mean()

        # === 3. Vrank_48: 48根K线成交量排名的百分位 ===
        dataframe["vrank"] = (
            dataframe["volume"]
            .rolling(window=self.vrank_period)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        )

        # === 4. MACD (12, 26, 9) ===
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # === 5. 組合進場條件 ===
        dataframe["atr_filter"] = (
            dataframe["atr_pct"] < dataframe["atr_pct_ma"] * self.atr_compression_threshold
        )
        dataframe["vrank_filter"] = dataframe["vrank"] < self.vrank_threshold
        # MACD 過濾: histogram > 0 (在零軸上方)
        dataframe["macd_filter"] = dataframe["macd_hist"] > 0
        dataframe["vcb_entry"] = (
            dataframe["atr_filter"] & dataframe["vrank_filter"] & dataframe["macd_filter"]
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場信號: ATR 壓縮 + 低成交量 + MACD.histogram > 0
        只做多頭
        """
        dataframe.loc[dataframe["vcb_entry"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Freqtrade 的 custom_exit:
        當 exit_signal = 1 時，觸發 exit
        TP/SL 由 Freqtrade 內建邏輯處理
        24h 到期由 max_exit_age 控制
        """
        dataframe["force_exit"] = 0
        return dataframe

    def leverage(
        self,
        pair: str,
        current_time: "datetime",
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> float:
        """
        凱利杠桿：Full Kelly = 32.3%，保守建議 2x
        """
        return 2.0
