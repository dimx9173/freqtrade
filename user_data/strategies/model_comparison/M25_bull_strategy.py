"""
M25_bull_strategy - Q3 2025 BULL 環境原創策略 v2

設計理念：
- 強趨勢確認：只在明確上升趨勢中進場
- 簡化進場：價格突破 + RSI 支撐
- 簡化退出：主要靠 ROI，讓利潤奔跑

適用環境：Q3 2025 BULL (+78% 強勢市場)
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame, Series
import numpy as np
import pandas as pd
from talib import EMA, RSI, ATR, ADX, PLUS_DI, MINUS_DI


class M25_bull_strategy(IStrategy):
    """
    M25 BULL 策略 - 原創設計 v2
    """

    # === freqtrade 2026.3 規範 ===
    INTERFACE_VERSION = 3

    # === 策略參數 ===
    # 更激進的 ROI - 讓利潤奔跑
    minimal_roi = {
        "0": 0.10,  # 0-10%: 10% 獲利
        "60": 0.05,  # 1小時後: 5% 獲利
        "180": 0.03,  # 3小時後: 3% 獲利
    }

    stoploss = -0.03  # 3% 止損

    # 不使用 trailing，讓 ROI 控制
    trailing_stop = False
    trailing_stop_offset = 0.0
    trailing_only_offset = 0.0

    # === 進場參數 ===
    ema_short = 20
    ema_long = 50
    adx_threshold = 30  # 更嚴格的 ADX
    lookback_period = 24  # 24 * 5m = 2小時
    rsi_oversold = 40
    rsi_overbought = 65

    # === 適當時間框架 ===
    timeframe = "5m"
    informative_timeframe = "1h"

    # === 短倉處理 ===
    can_short = False  # BULL 環境不做空

    # === 進入條件 ===
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        添加指標
        """
        # === 5m 指標 ===
        close = dataframe["close"].values
        high = dataframe["high"].values
        low = dataframe["low"].values

        dataframe["ema_20"] = EMA(close, timeperiod=self.ema_short)
        dataframe["ema_50"] = EMA(close, timeperiod=self.ema_long)

        # RSI
        dataframe["rsi"] = RSI(close, timeperiod=14)

        # ATR
        dataframe["atr"] = ATR(high, low, close, timeperiod=14)

        # 最近高点 (lookback_period 内)
        dataframe["high_2h"] = dataframe["high"].rolling(window=self.lookback_period).max()

        # ADX (5m)
        dataframe["adx"] = ADX(high, low, close, timeperiod=14)
        dataframe["plus_di"] = PLUS_DI(high, low, close, timeperiod=14)
        dataframe["minus_di"] = MINUS_DI(high, low, close, timeperiod=14)

        # === 1h 趨勢指標 ===
        df_1h = dataframe.copy()
        df_1h["date"] = pd.to_datetime(df_1h["date"])
        df_1h = df_1h.set_index("date")
        df_1h = df_1h.resample("1h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        df_1h = df_1h.dropna().reset_index()

        if len(df_1h) > 0:
            close_1h = df_1h["close"].values
            high_1h = df_1h["high"].values
            low_1h = df_1h["low"].values

            # 1h EMA
            df_1h["ema_20_1h"] = EMA(close_1h, timeperiod=20)
            df_1h["ema_50_1h"] = EMA(close_1h, timeperiod=50)

            # 1h ADX
            df_1h["adx_1h"] = ADX(high_1h, low_1h, close_1h, timeperiod=14)

            # 合并 1h 指标到 5m
            df_1h_for_merge = df_1h[["date", "ema_20_1h", "ema_50_1h", "adx_1h"]]
            dataframe["date"] = pd.to_datetime(dataframe["date"])
            dataframe = pd.merge_asof(
                dataframe.sort_values("date"),
                df_1h_for_merge.sort_values("date"),
                on="date",
                direction="backward",
                tolerance=pd.Timedelta("2h"),
            )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進入信號邏輯 - 精簡化
        """
        # 確保必要列存在
        if "ema_20_1h" not in dataframe.columns or "adx_1h" not in dataframe.columns:
            dataframe["enter_long"] = 0
            return dataframe

        # 核心條件：強上升趨勢
        trend_up = dataframe["ema_20_1h"] > dataframe["ema_50_1h"]

        # ADX > 30 (強趨勢)
        strong_trend = dataframe["adx_1h"] > self.adx_threshold

        # 價格突破近期高點
        price_breakout = dataframe["close"] > dataframe["high_2h"].shift(1)

        # RSI 在合理範圍
        rsi_ok = (dataframe["rsi"] > self.rsi_oversold) & (dataframe["rsi"] < self.rsi_overbought)

        # 進入條件
        enter = trend_up & strong_trend & price_breakout & rsi_ok

        dataframe["enter_long"] = enter.astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出場信號邏輯 - 極簡化，幾乎不使用
        """
        # 確保必要列存在
        if "ema_20_1h" not in dataframe.columns:
            dataframe["exit_long"] = 0
            return dataframe

        # 只在趨勢逆轉時退出
        trend_reversal = dataframe["ema_20_1h"] < dataframe["ema_50_1h"]

        # 或 RSI 極度超買
        rsi_extreme = dataframe["rsi"] > 85

        # 退出
        exit_signal = trend_reversal | rsi_extreme

        dataframe["exit_long"] = exit_signal.astype(int)

        return dataframe

    # === 訂單類型 ===
    order_types = {
        "entry": "market",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_entry": "market",
    }

    # === 時間-force ===
    time_in_force = {"entry": "gtc", "exit": "ioc"}
