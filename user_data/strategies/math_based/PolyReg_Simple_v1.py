from freqtrade.strategy import IStrategy, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class PolyReg_Simple_v1(IStrategy):
    """
    簡化版多項式迴歸策略

    核心邏輯:
    1. 計算線性迴歸線
    2. 建立標準差通道
    3. 價格觸及下軌做多，觸及上軌做空
    4. 回到中軌出場
    """

    minimal_roi = {"0": 0.05}
    stoploss = -0.03
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    timeframe = "1h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 200
    use_exit_signal = True

    # 參數
    window = DecimalParameter(50, 300, default=100, space="buy")
    dev_mult = DecimalParameter(1.5, 4.0, default=2.5, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        window = int(self.window.value)
        dev_mult = self.dev_mult.value

        close_arr = dataframe["close"].values
        n = len(close_arr)

        # 初始化
        pred_arr = np.full(n, np.nan)
        upper_arr = np.full(n, np.nan)
        lower_arr = np.full(n, np.nan)
        slope_arr = np.full(n, np.nan)

        for i in range(window - 1, n):
            y = close_arr[i - window + 1 : i + 1]
            x = np.arange(window)

            try:
                # 線性迴歸
                slope, intercept = np.polyfit(x, y, 1)
                pred = slope * (window - 1) + intercept

                # 殘差標準差
                fitted = slope * x + intercept
                residuals = y - fitted
                std_dev = np.std(residuals, ddof=1)

                pred_arr[i] = pred
                upper_arr[i] = pred + dev_mult * std_dev
                lower_arr[i] = pred - dev_mult * std_dev
                slope_arr[i] = slope

            except Exception:
                continue

        dataframe["poly_pred"] = pred_arr
        dataframe["poly_upper"] = upper_arr
        dataframe["poly_lower"] = lower_arr
        dataframe["poly_slope"] = slope_arr

        # 進場條件: 價格觸及通道後反彈
        dataframe["long_condition"] = (
            dataframe["low"].shift(1) < dataframe["poly_lower"].shift(1)
        ) & (dataframe["close"] > dataframe["poly_lower"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["long_condition"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 出場: 價格回到迴歸線上方
        dataframe.loc[
            (dataframe["close"] > dataframe["poly_pred"])
            & (dataframe["close"].shift(1) <= dataframe["poly_pred"].shift(1)),
            "exit_long",
        ] = 1
        return dataframe
