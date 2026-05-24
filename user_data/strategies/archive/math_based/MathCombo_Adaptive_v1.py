from freqtrade.strategy import IStrategy, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
from scipy import stats


class MathCombo_Adaptive_v1(IStrategy):
    """
    數學理論組合策略

    結合多種數學理論:
    1. 線性迴歸 (趨勢方向)
    2. 標準差通道 (波動率)
    3. Z-Score (均值回歸強度)
    4. 凱利公式 (倉位管理)
    5. 期望值計算 (進場確認)
    6. ADX (趨勢強度過濾)
    """

    minimal_roi = {"0": 0.03, "30": 0.02, "60": 0.01}
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    timeframe = "1h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 200
    use_exit_signal = True

    # 參數
    window = DecimalParameter(50, 300, default=100, space="buy")
    dev_mult = DecimalParameter(1.5, 4.0, default=2.5, space="buy")
    zscore_threshold = DecimalParameter(1.0, 3.0, default=2.0, space="buy")
    adx_min = DecimalParameter(15, 30, default=20, space="buy")
    adx_max = DecimalParameter(25, 50, default=40, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        window = int(self.window.value)
        dev_mult = self.dev_mult.value
        z_thresh = self.zscore_threshold.value

        close_arr = dataframe["close"].values
        n = len(close_arr)

        # 1. 線性迴歸
        pred_arr = np.full(n, np.nan)
        upper_arr = np.full(n, np.nan)
        lower_arr = np.full(n, np.nan)
        slope_arr = np.full(n, np.nan)

        # 2. Z-Score
        zscore_arr = np.full(n, np.nan)

        # 3. 期望值計算用陣列
        win_rate_arr = np.full(n, np.nan)
        expectancy_arr = np.full(n, np.nan)

        for i in range(window - 1, n):
            y = close_arr[i - window + 1 : i + 1]
            x = np.arange(window)

            try:
                # 線性迴歸
                slope, intercept = np.polyfit(x, y, 1)
                pred = slope * (window - 1) + intercept
                fitted = slope * x + intercept
                residuals = y - fitted
                std_dev = np.std(residuals, ddof=1)

                pred_arr[i] = pred
                upper_arr[i] = pred + dev_mult * std_dev
                lower_arr[i] = pred - dev_mult * std_dev
                slope_arr[i] = slope

                # Z-Score: (價格 - 預測) / 標準差
                zscore = (close_arr[i] - pred) / std_dev if std_dev > 0 else 0
                zscore_arr[i] = zscore

                # 計算近期勝率 (模擬回測)
                recent_returns = np.diff(y) / y[:-1]
                wins = np.sum(recent_returns > 0)
                total = len(recent_returns)
                win_rate = wins / total if total > 0 else 0.5
                win_rate_arr[i] = win_rate

                # 期望值 = 勝率 * 平均獲利 - (1-勝率) * 平均虧損
                avg_win = (
                    np.mean(recent_returns[recent_returns > 0])
                    if np.any(recent_returns > 0)
                    else 0.01
                )
                avg_loss = (
                    abs(np.mean(recent_returns[recent_returns <= 0]))
                    if np.any(recent_returns <= 0)
                    else 0.01
                )
                expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
                expectancy_arr[i] = expectancy

            except Exception:
                continue

        dataframe["poly_pred"] = pred_arr
        dataframe["poly_upper"] = upper_arr
        dataframe["poly_lower"] = lower_arr
        dataframe["poly_slope"] = slope_arr
        dataframe["zscore"] = zscore_arr
        dataframe["win_rate"] = win_rate_arr
        dataframe["expectancy"] = expectancy_arr

        # 4. ADX (趨勢強度)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # 5. RSI (確認超買超賣)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # 6. ATR (波動率)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        atr_mean = dataframe["atr"].rolling(window=window).mean()
        dataframe["atr_ok"] = dataframe["atr"] < atr_mean * 1.5  # 波動率不過高

        # 組合進場條件
        # 條件1: Z-Score 顯示超賣 (價格遠低於迴歸線)
        # 條件2: 期望值 > 0 (統計上有優勢)
        # 條件3: ADX 在合理範圍 (有趨勢但不過強)
        # 條件4: RSI 確認超賣
        # 條件5: 波動率不過高

        dataframe["long_condition"] = (
            (dataframe["zscore"] < -z_thresh)  # Z-Score 顯示超賣
            & (dataframe["expectancy"] > 0)  # 期望值為正
            & (dataframe["adx"] > self.adx_min.value)  # 有趨勢
            & (dataframe["adx"] < self.adx_max.value)  # 趨勢不過強
            & (dataframe["rsi"] < 40)  # RSI 確認超賣
            & (dataframe["atr_ok"])  # 波動率正常
            & (dataframe["poly_slope"] > 0)  # 趨勢向上
        )

        # 出場條件: Z-Score 回到正常範圍或期望值轉負
        dataframe["exit_condition"] = (
            (dataframe["zscore"] > 0)  # 回到中軌上方
            | (dataframe["expectancy"] < 0)  # 期望值轉負
            | (dataframe["rsi"] > 60)  # RSI 進入超買
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["long_condition"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["exit_condition"], "exit_long"] = 1
        return dataframe

    def custom_stake_amount(
        self, pair: str, current_time, current_rate, proposed_stake, min_stake, max_stake, **kwargs
    ) -> float:
        """
        凱利公式動態倉位管理
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if len(dataframe) < 2:
            return proposed_stake

        last_candle = dataframe.iloc[-1]

        # 取得勝率和盈虧比
        win_rate = last_candle["win_rate"]

        if np.isnan(win_rate) or win_rate <= 0:
            return proposed_stake * 0.5  # 保守倉位

        # 簡化凱利公式: f* = 2p - 1 (假設盈虧比為1)
        kelly_fraction = 2 * win_rate - 1

        # 分數凱利 (更保守)
        fraction = 0.25 * kelly_fraction

        # 限制範圍
        fraction = max(0.1, min(0.5, fraction))

        return proposed_stake * fraction
