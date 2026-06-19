# pragma pylint: disable=invalid-name
"""
FreqAI ML Strategy V81 — Minimal Intraday 15m (test) → 5m (prod)
Pairs: BTC, ETH only
Features: 5 max
FreqAI mode: Classification
"""

import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, DecimalParameter


class FreqAI_ML_Strategy_v81(IStrategy):
    """
    FreqAI Classification Strategy.
    Predicts UP/DOWN using 5 simple features.
    """

    # ===========================================
    # TIMEFRAME & SToploss
    # ===========================================
    timeframe = "15m"  # Test with 15m (data exists). Switch to 5m for production.
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

    # ===========================================
    # ENTRY THRESHOLDS
    # ===========================================
    entry_up_threshold = DecimalParameter(0.50, 0.65, default=0.55, decimals=2, space="buy")
    entry_down_threshold = DecimalParameter(0.35, 0.50, default=0.45, decimals=2, space="sell")

    freqai_enable = True

    # ===========================================
    # populate_indicators
    # ===========================================
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        REQUIRED: call freqai.start() to trigger FreqAI training and prediction.
        Traditional indicators added here for additional filtering (not as ML features).
        """
        # RSI
        delta = dataframe["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands (manual - don't rely on auto-indicators)
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
        Defines the target: `&-s_direction` = 1 if price goes UP >0.5% in 3 candles, else 0.
        Uses `&-` prefix so FreqAI recognizes it as a target.
        """
        # 3-candle forward return (15min × 3 = 45min ahead)
        forward_return = dataframe["close"].shift(-3) / dataframe["close"] - 1
        # Classification: 1 = up > 0.5%, 0 = not up
        dataframe["&-s_direction"] = (forward_return > 0.005).astype(int)
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
        Features use `%-` prefix. Max 5 features.
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
        Entry based on FreqAI classification predictions.
        Classification output:
        - &-s_direction: predicted class ('0' or '1')
        - '1': probability of predicting class 1 (confidence for LONG)
        - '0': probability of predicting class 0 (confidence for SHORT)
        - do_predict: 1 = valid prediction
        """
        direction = dataframe.get("&-s_direction", "0")
        prob_up = (
            dataframe["1"] if "1" in dataframe.columns else pd.Series(0, index=dataframe.index)
        )
        prob_down = (
            dataframe["0"] if "0" in dataframe.columns else pd.Series(0, index=dataframe.index)
        )
        do_predict = dataframe.get("do_predict", 1)

        valid = do_predict == 1

        # Convert direction to numeric
        direction_val = pd.to_numeric(direction, errors="coerce").fillna(0)

        # LONG: predict UP (direction == 1) with confidence >= threshold
        long_cond = valid & (direction_val == 1) & (prob_up >= self.entry_up_threshold.value)

        # SHORT: predict DOWN (direction == 0) with confidence >= threshold
        short_cond = valid & (direction_val == 0) & (prob_down >= self.entry_down_threshold.value)

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
