# pragma pylint: disable=invalid-name
"""
FreqAI ML Strategy V82 — Regression (raw return %)
Pairs: BTC/USDT only
Timeframe: 15m
Features: 5 max (%-prefixed)
FreqAI mode: Regression (XGBoostRegressor)
Target: raw 12-bar forward return % (3 hours ahead for 15m data)
Entry: prediction > 70th percentile (LONG), < 30th percentile (SHORT)

CHANGE from V81R:
- Prediction horizon: 12 bars instead of 3 bars
- Entry thresholds: 70/30 percentile instead of 65/35
"""

import numpy as np
import pandas as pd

from freqtrade.strategy import IStrategy


class FreqAI_ML_Strategy_v82(IStrategy):
    """
    FreqAI Regression Strategy.
    Predicts raw 12-bar forward return % using 5 simple features.
    """

    # ===========================================
    # TIMEFRAME & STOPLOSS
    # ===========================================
    timeframe = "15m"
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.025
    max_open_trades = 3
    stake_amount = 50.0

    # ===========================================
    # ROI
    # ===========================================
    minimal_roi = {"0": 0.10}

    freqai_enable = True

    # ===========================================
    # populate_indicators
    # ===========================================
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Traditional indicators for additional context (not ML features).
        """
        # RSI
        delta = dataframe["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands (manual)
        close = dataframe["close"]
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        bb_upper = sma20 + (2 * std20)
        bb_lower = sma20 - (2 * std20)
        dataframe["bb_percent"] = (
            (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
        ).clip(0, 1)

        # EMA distance
        ema_50 = close.ewm(span=50, adjust=False).mean()
        dataframe["ema_distance"] = ((close - ema_50) / close).clip(-0.05, 0.05)

        # Volume ratio
        volume_ma = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = (dataframe["volume"] / volume_ma.replace(0, np.nan)).clip(0, 3)

        # ATR percent
        high = dataframe["high"]
        low = dataframe["low"]
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        dataframe["atr_pct"] = (atr / close).clip(0, 0.05)

        # FREQAI REQUIRED CALL - must be last in this method
        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    # ===========================================
    # set_freqai_targets
    # ===========================================
    def set_freqai_targets(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        """
        REQUIRED by FreqAI.
        Defines the target: raw 12-bar forward return % (not classification).
        Uses `&`-prefix so FreqAI recognizes it as a target.

        CHANGED from V81R: shift(-3) -> shift(-12)
        """
        # 12-candle forward return (15min x 12 = 3 hours ahead)
        # Raw return in decimal form (e.g., 0.01 = 1% return)
        forward_return = dataframe["close"].shift(-12) / dataframe["close"] - 1
        dataframe["&-ml_return"] = forward_return
        return dataframe

    # ===========================================
    # feature_engineering_standard
    # ===========================================
    def feature_engineering_standard(
        self, dataframe: pd.DataFrame, metadata: dict, **kwargs
    ) -> pd.DataFrame:
        """
        REQUIRED by FreqAI.
        Only OHLCV columns are available here. Compute ALL indicators from scratch.
        Features use `%-prefix`. Max 5 features.
        """
        close = dataframe["close"]
        high = dataframe["high"]
        low = dataframe["low"]
        volume = dataframe["volume"]

        # --- RSI ---
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).clip(0, 100)

        # --- Bollinger Bands ---
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        bb_upper = sma20 + (2 * std20)
        bb_lower = sma20 - (2 * std20)
        bb_pct = ((close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)).clip(0, 1)

        # --- EMA distance ---
        ema_50 = close.ewm(span=50, adjust=False).mean()
        ema_dist = ((close - ema_50) / close).clip(-0.05, 0.05)

        # --- Volume ratio ---
        volume_ma = volume.rolling(window=20).mean()
        vol_ratio = (volume / volume_ma.replace(0, np.nan)).clip(0, 3)

        # --- ATR ---
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        atr_pct = (atr / close).clip(0, 0.05)

        # FEATURE 1: RSI (0-1)
        dataframe["%-rsi"] = (rsi / 100.0).clip(0, 1)

        # FEATURE 2: BB position (0-1)
        dataframe["%-bb_pct"] = bb_pct

        # FEATURE 3: EMA distance (-1 to 1)
        dataframe["%-ema_dist"] = (ema_dist * 20).clip(-1, 1)

        # FEATURE 4: Volume ratio (0-1)
        dataframe["%-vol_ratio"] = (vol_ratio / 3.0).clip(0, 1)

        # FEATURE 5: ATR volatility (0-1)
        dataframe["%-atr_vol"] = (atr_pct * 20).clip(0, 1)

        return dataframe

    # ===========================================
    # populate_entry_trend
    # ===========================================
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Entry based on FreqAI regression prediction.
        Uses percentile-based thresholds tied to prediction distribution:
        - LONG: prediction > 70th percentile of predictions
        - SHORT: prediction < 30th percentile of predictions
        This adapts to the actual prediction scale rather than using fixed decimals.
        """
        prediction = dataframe.get("&-ml_return", 0)
        do_predict = dataframe.get("do_predict", 1)

        valid = do_predict == 1

        # Compute percentile thresholds dynamically from predictions
        pred_valid = prediction[valid & prediction.notna()]
        if len(pred_valid) > 0:
            p30 = pred_valid.quantile(0.30)
            p70 = pred_valid.quantile(0.70)
        else:
            p30 = -0.001
            p70 = 0.001

        # LONG: prediction > 70th percentile (above-average prediction)
        long_cond = valid & (prediction > p70)

        # SHORT: prediction < 30th percentile (below-average prediction)
        short_cond = valid & (prediction < p30)

        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    # ===========================================
    # populate_exit_trend
    # ===========================================
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """No separate exit signal - rely on trailing stop / stoploss."""
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
