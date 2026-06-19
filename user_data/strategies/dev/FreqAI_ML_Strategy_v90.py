# pragma pylint: disable=invalid-name
"""
FreqAI ML Strategy V90 — Scalp Core (Regression)
Pairs: BTC/USDT, ETH/USDT
Timeframe: 5m
Features: 5 max (%-prefixed)
FreqAI mode: Regression (XGBoostRegressor)
Target: raw 6-bar forward return % (30 min ahead for 5m data)
Entry: prediction > 0.001 (LONG), < -0.001 (SHORT)
Exit: ROI 0.6%, stoploss -0.3%

CHANGE from V83:
- Pairs: BTC+ETH (not just BTC)
- Prediction horizon: 6 bars (30 min) instead of 12 bars (60 min)
- Stop loss: -0.3% (tight for scalp)
- ROI: 0.6% take profit (scalp target)
- Classification -> Regression (more stable for short horizons)
"""

import numpy as np
import pandas as pd

from freqtrade.strategy import IStrategy


class FreqAI_ML_Strategy_v90(IStrategy):
    """
    FreqAI Scalping Classification Strategy.
    Predicts direction of 3-bar forward return (UP=1, DOWN=0).
    """

    # ===========================================
    # TIMEFRAME & STOPLOSS
    # ===========================================
    timeframe = "1m"
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.01
    max_open_trades = 5
    stake_amount = 20.0

    # ===========================================
    # ROI
    # ===========================================
    minimal_roi = {"0": 0.005}

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
        gain = delta.where(delta > 0, 0).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands (manual, short window for scalping)
        close = dataframe["close"]
        sma10 = close.rolling(window=10).mean()
        std10 = close.rolling(window=10).std()
        bb_upper = sma10 + (2 * std10)
        bb_lower = sma10 - (2 * std10)
        dataframe["bb_percent"] = (
            (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
        ).clip(0, 1)

        # EMA distance (short EMA for scalping)
        ema_20 = close.ewm(span=20, adjust=False).mean()
        dataframe["ema_distance"] = ((close - ema_20) / close).clip(-0.05, 0.05)

        # Volume ratio
        volume_ma = dataframe["volume"].rolling(window=10).mean()
        dataframe["volume_ratio"] = (dataframe["volume"] / volume_ma.replace(0, np.nan)).clip(0, 3)

        # ATR percent (short window)
        high = dataframe["high"]
        low = dataframe["low"]
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=7).mean()
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
        Defines the target: raw 6-bar forward return % (30 min for 5m).
        Uses &-prefix so FreqAI recognizes it as a target.

        Regression is more stable than Classification for short horizons.
        """
        # 6-candle forward return (5m x 6 = 30 minutes ahead)
        dataframe["&ml_prediction"] = dataframe["close"].shift(-6) / dataframe["close"] - 1
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
        Features use `%-prefix. Max 5 features.
        Scalping-optimized: shorter windows, momentum-focused.
        """
        close = dataframe["close"]
        high = dataframe["high"]
        low = dataframe["low"]
        volume = dataframe["volume"]

        # --- RSI (short window) ---
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).clip(0, 100)

        # --- Bollinger Bands (short window) ---
        sma10 = close.rolling(window=10).mean()
        std10 = close.rolling(window=10).std()
        bb_upper = sma10 + (2 * std10)
        bb_lower = sma10 - (2 * std10)
        bb_pct = ((close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)).clip(0, 1)

        # --- EMA distance (short EMA) ---
        ema_20 = close.ewm(span=20, adjust=False).mean()
        ema_dist = ((close - ema_20) / close).clip(-0.05, 0.05)

        # --- Volume ratio ---
        volume_ma = volume.rolling(window=10).mean()
        vol_ratio = (volume / volume_ma.replace(0, np.nan)).clip(0, 3)

        # --- ATR volatility (short window) ---
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=7).mean()
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
        Entry based on FreqAI regression prediction (raw return %).
        Uses probability-weighted thresholds for scalp scalping.

        Entry conditions:
        - LONG: ml_prediction > 0.001 (0.1% predicted forward return) AND RSI < 70
        - SHORT: ml_prediction < -0.001 (0.1% predicted backward return) AND RSI > 30
        """
        ml_pred = dataframe.get("&ml_prediction", 0.0)
        rsi = dataframe.get("rsi", 50)

        # Long: positive prediction + not overbought
        long_cond = (ml_pred > 0.001) & (rsi < 70)

        # Short: negative prediction + not oversold
        short_cond = (ml_pred < -0.001) & (rsi > 30)

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
