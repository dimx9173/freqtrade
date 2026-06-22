# M3_bull_trend.py
# Q3 2025 BULL Regime Strategy - designed by MiniMax-M3
# Method: Multi-timeframe EMA + ADX trend strength + ATR dynamic stop
# =============================================================================
# BULL 環境特性 (Q3 2025):
#   - BTC 從 ~108K → 118K (+9.3%)
#   - 多幣跟漲, 強趨勢
#   - 短暫回調 < 5% 即恢復
#   - 波動率高 (ATR 大)
# 策略設計:
#   - 用 1h 趨勢過濾, 5m 進場
#   - 進場: 1h EMA20 上 + 5m 突破前高 + 量能確認
#   - 出場: ATR 動態追蹤止損 + RSI 超買
#   - 嚴格 ADX > 20 過濾震盪
# =============================================================================

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np


class M3_bull_trend(IStrategy):
    INTERFACE_VERSION = 3

    # 策略本身 ROI 較低, 標準 config 會 override
    minimal_roi = {"0": 0.04, "30": 0.025, "60": 0.012, "120": 0.005}
    stoploss = -0.08

    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    timeframe = "5m"
    startup_candle_count = 200

    # 可調參數 (不用 hyperopt, 直接寫死合理 BULL 值)
    adx_threshold = IntParameter(15, 35, default=20, space="buy", optimize=False)
    ema_fast = IntParameter(5, 20, default=9, space="buy", optimize=False)
    ema_slow = IntParameter(20, 60, default=21, space="buy", optimize=False)
    ema_trend_1h = IntParameter(20, 100, default=50, space="buy", optimize=False)
    breakout_lookback = IntParameter(10, 50, default=20, space="buy", optimize=False)
    volume_mult = DecimalParameter(1.0, 3.0, default=1.5, space="buy", optimize=False)
    rsi_max = IntParameter(60, 85, default=75, space="buy", optimize=False)

    order_types = {
        "entry": "market",
        "exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def informative_pairs(self):
        return [("BTC/USDT:USDT", "1h")]

    def _add_informative(self, dataframe, metadata):
        # 1h BTC 趨勢作為市場 regime 過濾
        btc_1h = self.dp.get_pair_dataframe("BTC/USDT:USDT", "1h")
        if not btc_1h.empty:
            btc_1h[f"ema_{self.ema_trend_1h.value}"] = ta.EMA(
                btc_1h, timeperiod=self.ema_trend_1h.value
            )
            btc_1h["btc_trend_up"] = (
                btc_1h["close"] > btc_1h[f"ema_{self.ema_trend_1h.value}"]
            ).astype(int)
            btc_1h = btc_1h[["date", "btc_trend_up"]].rename(
                columns={"btc_trend_up": "btc_1h_bull"}
            )
            dataframe = dataframe.merge(btc_1h, on="date", how="left")
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 5m 指標
        dataframe[f"ema_{self.ema_fast.value}"] = ta.EMA(dataframe, timeperiod=self.ema_fast.value)
        dataframe[f"ema_{self.ema_slow.value}"] = ta.EMA(dataframe, timeperiod=self.ema_slow.value)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["volume_mean_20"] = dataframe["volume"].rolling(20).mean()
        dataframe["high_breakout"] = (
            dataframe["high"].rolling(self.breakout_lookback.value).max().shift(1)
        )
        dataframe["low_breakout"] = (
            dataframe["low"].rolling(self.breakout_lookback.value).min().shift(1)
        )
        # 趨勢方向
        dataframe["ema_cross"] = (
            dataframe[f"ema_{self.ema_fast.value}"] > dataframe[f"ema_{self.ema_slow.value}"]
        ).astype(int)
        # 合併 1h BTC 趨勢
        dataframe = self._add_informative(dataframe, metadata)
        dataframe["btc_1h_bull"] = dataframe["btc_1h_bull"].fillna(0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 多進場: 趨勢 + 突破 + 量能 + BTC 大勢向上
        long_cond = (
            (dataframe["btc_1h_bull"] == 1)  # 1h BTC 趨勢向上
            & (dataframe["ema_cross"] == 1)  # 5m 快 EMA 在慢 EMA 之上
            & (dataframe["adx"] > self.adx_threshold.value)  # 趨勢強度夠
            & (dataframe["close"] > dataframe["high_breakout"])  # 突破前高
            & (
                dataframe["volume"] > dataframe["volume_mean_20"] * self.volume_mult.value
            )  # 量能放大
            & (dataframe["rsi"] < self.rsi_max.value)  # 沒過熱
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[long_cond, "enter_tag"] = "bull_breakout"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 出場: EMA 反轉 或 ADX 轉弱 或跌破動態支撐
        exit_cond = (
            ((dataframe["ema_cross"] == 0) & (dataframe["rsi"] > 50))
            | (dataframe["adx"] < 15)
            | (dataframe["close"] < dataframe["low_breakout"])
        )
        dataframe.loc[exit_cond, "exit_long"] = 1
        dataframe.loc[exit_cond, "exit_tag"] = "trend_fade"
        return dataframe
