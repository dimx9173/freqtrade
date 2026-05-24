from freqtrade.strategy import IStrategy, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import PolynomialFeatures


class PolyReg_Adaptive_v1(IStrategy):
    """
    自適應多項式迴歸策略

    改進點:
    1. 加權迴歸 (近期資料權重較高)
    2. Ridge 正則化防止過擬合
    3. 動態階數選擇 (根據市場狀態)
    4. ATR 波動率過濾
    5. 趨勢確認 (ADX)
    """

    # 基本設定
    minimal_roi = {"0": 0.04, "30": 0.03, "60": 0.02}
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    timeframe = "1h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 300
    use_exit_signal = True

    # 參數
    window = DecimalParameter(50, 300, default=200, space="buy")
    degree = DecimalParameter(1, 4, default=2, space="buy")
    alpha = DecimalParameter(0.1, 10.0, default=1.0, space="buy")
    weight_decay = DecimalParameter(0.9, 0.99, default=0.95, space="buy")
    dev_mult = DecimalParameter(2.0, 5.0, default=3.0, space="buy")
    atr_period = DecimalParameter(10, 20, default=14, space="buy")
    adx_threshold = DecimalParameter(20, 40, default=30, space="buy")

    def weighted_polyfit(self, x, y, degree, alpha, decay):
        """
        加權多項式迴歸 (Ridge 正則化)

        Parameters:
        - x: 時間序列
        - y: 價格序列
        - degree: 多項式階數
        - alpha: Ridge 正則化強度
        - decay: 權重衰減率 (近期資料權重較高)

        Returns:
        - model: 訓練好的模型
        - poly_features: 多項式特徵轉換器
        """
        # 生成權重 (指數衰減)
        n = len(y)
        weights = np.power(decay, np.arange(n)[::-1])
        weights = weights / np.sum(weights) * n  # 正規化

        # 多項式特徵
        poly_features = PolynomialFeatures(degree=degree, include_bias=False)
        X_poly = poly_features.fit_transform(x.reshape(-1, 1))

        # Ridge 迴歸 (帶樣本權重)
        model = Ridge(alpha=alpha, fit_intercept=True)
        model.fit(X_poly, y, sample_weight=weights)

        return model, poly_features

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ATR
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=int(self.atr_period.value))

        # ADX
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # ATR 過濾範圍
        atr_low = dataframe["atr"].rolling(window=int(self.window.value)).quantile(0.3)
        atr_high = dataframe["atr"].rolling(window=int(self.window.value)).quantile(0.7)
        dataframe["atr_ok"] = (dataframe["atr"] > atr_low) & (dataframe["atr"] < atr_high)

        # 多項式迴歸
        window = int(self.window.value)
        degree = int(self.degree.value)
        alpha = self.alpha.value
        decay = self.weight_decay.value
        dev_mult = self.dev_mult.value

        close_arr = dataframe["close"].values
        n = len(close_arr)

        # 初始化
        pred_arr = np.full(n, np.nan)
        upper_arr = np.full(n, np.nan)
        lower_arr = np.full(n, np.nan)
        slope_arr = np.full(n, np.nan)

        for i in range(window - 1, n):
            # 取得窗口資料
            y = close_arr[i - window + 1 : i + 1]
            x = np.arange(window)

            try:
                # 加權多項式迴歸
                model, poly_features = self.weighted_polyfit(x, y, degree, alpha, decay)

                # 預測當前點 (x = window - 1)
                x_current = poly_features.transform([[window - 1]])
                pred = model.predict(x_current)[0]

                # 計算殘差標準差
                X_poly = poly_features.transform(x.reshape(-1, 1))
                y_pred = model.predict(X_poly)
                residuals = y - y_pred
                std_dev = np.std(residuals, ddof=1)

                # 計算斜率 (一階導數)
                if degree >= 1:
                    # 對於多項式，斜率在 x 處的導數
                    coeffs = np.polyfit(x, y, degree)
                    # 導數係數
                    deriv_coeffs = np.polyder(coeffs)
                    slope = np.polyval(deriv_coeffs, window - 1)
                else:
                    slope = 0

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

        # 進場條件
        # 均值回歸: 價格觸及通道後反彈
        dataframe["long_condition"] = (
            dataframe["atr_ok"]
            & (dataframe["adx"] < self.adx_threshold.value)  # 盤整市場
            & (dataframe["low"].shift(1) < dataframe["poly_lower"].shift(1))
            & (dataframe["close"] > dataframe["poly_lower"])
        )

        dataframe["short_condition"] = (
            dataframe["atr_ok"]
            & (dataframe["adx"] < self.adx_threshold.value)
            & (dataframe["high"].shift(1) > dataframe["poly_upper"].shift(1))
            & (dataframe["close"] < dataframe["poly_upper"])
        )

        # 趨勢跟隨: 斜率確認
        dataframe["trend_long"] = (
            (dataframe["adx"] >= self.adx_threshold.value)
            & (dataframe["poly_slope"] > 0)
            & (dataframe["close"] > dataframe["poly_pred"])
        )

        dataframe["trend_short"] = (
            (dataframe["adx"] >= self.adx_threshold.value)
            & (dataframe["poly_slope"] < 0)
            & (dataframe["close"] < dataframe["poly_pred"])
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 均值回歸進場
        dataframe.loc[dataframe["long_condition"], "enter_long"] = 1
        dataframe.loc[dataframe["short_condition"], "enter_short"] = 1

        # 趨勢跟隨進場 (可選)
        # dataframe.loc[dataframe['trend_long'], 'enter_long'] = 1
        # dataframe.loc[dataframe['trend_short'], 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 出場條件: 價格回到迴歸線
        dataframe.loc[
            (dataframe["close"] > dataframe["poly_pred"])
            & (dataframe["close"].shift(1) <= dataframe["poly_pred"].shift(1)),
            "exit_long",
        ] = 1

        dataframe.loc[
            (dataframe["close"] < dataframe["poly_pred"])
            & (dataframe["close"].shift(1) >= dataframe["poly_pred"].shift(1)),
            "exit_short",
        ] = 1

        return dataframe
