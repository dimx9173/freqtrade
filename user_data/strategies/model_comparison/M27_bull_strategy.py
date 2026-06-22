# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

"""
M27_bull_strategy.py
M2.7 原創設計: Trend Snapshot Strategy (v5 - Pure Trend Following)
----------------------------------------------
設計理念: Q3 2025 BULL 環境, 順勢趨勢跟隨。
         進場: EMA 金叉 + ADX > 25 確認趨勢
         出場: 完全交給 ROI + Trailing Stop (不用 exit_signal)
         核心理念: 讓趨勢帶你離場, 不要猜頭底
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class M27_bull_strategy(IStrategy):
    """
    M2.7 Trend Snapshot Strategy
    適用: Q3 2025 BULL 環境 (2025-07-01 ~ 2025-09-30)
    """

    # === INTERFACE ===
    INTERFACE_VERSION = 3

    # === 時間框架 ===
    timeframe = "5m"
    inbound_timeframe = "5m"

    # === 盈虧設定 ===
    stoploss = -0.05

    # ROI 表 (讓利潤奔跑, BULL 波段大)
    roi = {
        "0": 0.06,
        "60": 0.04,
        "180": 0.025,
        "360": 0.01,
    }

    # Trailing Stop
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # === 倉位 ===
    max_open_trades = 3
    stake_amount = 50
    can_short = False

    # === 風險管理 ===
    # 使用 exit_profit_offset 讓利潤 > 3% 才允許 exit_signal
    exit_profit_offset = 0.03
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # === 訂單 ===
    order_time_in_force = {"entry": "gtc", "exit": "gtc"}
    entry_order_type = "market"
    exit_order_type = "market"

    # === 參數 ===
    ema_fast_len = 9
    ema_slow_len = 21
    adx_threshold = 25

    # === populate_indicators ===
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast_len)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow_len)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ADX
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # MACD
        macd = ta.MACD(dataframe, timeperiod=12, fastperiod=5, slowperiod=10)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]

        return dataframe

    # === populate_entry_trend ===
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        進場: EMA 多頭排列 + ADX 確認趨勢 + RSI 健康
        """
        dataframe.loc[
            (
                # EMA 金叉 (多頭排列)
                (dataframe["ema_fast"] > dataframe["ema_slow"])
                &
                # 價格在 EMA 慢線之上
                (dataframe["close"] > dataframe["ema_slow"])
                &
                # ADX 確認趨勢強度 > 25
                (dataframe["adx"] > self.adx_threshold)
                &
                # 多頭排列 (+DI > -DI)
                (dataframe["plus_di"] > dataframe["minus_di"])
                &
                # RSI 40-60 (非超買, 動能健康)
                (dataframe["rsi"] > 40)
                & (dataframe["rsi"] < 60)
                &
                # MACD 多頭
                (dataframe["macd"] > dataframe["macd_signal"])
                & (dataframe["macd"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    # === populate_exit_trend ===
    # 故意留空, 讓 exit_signal 完全不使用, 只靠 ROI 離場
    # 若需要離場信號, 只在極端的 EMA 死叉情況下
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出場: 故意留空, 完全交給 ROI + Trailing Stop 處理
        這樣可以避免 exit_signal 在趨勢市場中產生大量假信號
        """
        # 不產生任何 exit_long 信號
        return dataframe

    # === get_stoploss ===
    def get_stoploss(
        self, pair: str, trade, entry_time, current_time, current_rate: float, **kwargs
    ) -> float:
        return -self.stoploss
