# pragma pylint: disable=invalid-name
"""
FreqAI ML Strategy V91 — Kelly Scalp (Fixed R:R)
Pairs: BTC/USDT, ETH/USDT
Timeframe: 5m
Features: 5 max (%-prefixed)
FreqAI mode: Regression (XGBoostRegressor)
Target: raw 6-bar forward return % (30 min ahead)
Entry: prediction > 0.001 (LONG), < -0.001 (SHORT)
Exit: ROI +0.3%, Stoploss -0.3% → 1:1 R:R (核心修復)

CHANGE from V90:
- Fixed R:R = 1:1 (target 0.3%, stop -0.3%) — V90 的 0.5%:1.88% 導致期望值為負
- Trailing stop disabled (剝头皮不需要)
- More aggressive entry (ml_pred > 0.0005, < -0.0005)
- ROI table: quick exits for scalp
- Futures mode: 2x leverage for enhanced returns
"""

import numpy as np
import pandas as pd

from freqtrade.strategy import IStrategy


class FreqAI_ML_Strategy_v91(IStrategy):
    """
    FreqAI Scalping Strategy with Fixed 1:1 R:R.
    Key fix: V90 had 0.27:1 R ratio (1.88% loss vs 0.50% win) → impossible to profit.
    V91 target: 1:1 R:R = 0.3% win / 0.3% loss.
    """

    # ===========================================
    # TIMEFRAME & STOPLOSS
    # ===========================================
    timeframe = "5m"
    stoploss = -0.003  # -0.3% (matches target = 1:1 R:R)
    trailing_stop = False  # Scalp: fast exits, no trailing
    max_open_trades = 3
    stake_amount = 50.0

    # ===========================================
    # ROI — 1:1 R:R scalp targets
    # ===========================================
    minimal_roi = {
        "0": 0.003,  # 0.3% take profit (1R)
        "30": 0.002,  # 0.2% after 150min
        "60": 0.001,  # 0.1% after 300min (time exit)
    }

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

        # Bollinger Bands (manual, window 20)
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

        # FREQAI REQUIRED CALL
        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    # ===========================================
    # set_freqai_targets
    # ===========================================
    def set_freqai_targets(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        """
        REQUIRED by FreqAI.
        Target: raw 6-bar forward return % (30 min for 5m).
        """
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
        5 features max (%-prefixed).
        """
        close = dataframe["close"]
        high = dataframe["high"]
        low = dataframe["low"]
        volume = dataframe["volume"]

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).clip(0, 100)

        # Bollinger Bands
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        bb_upper = sma20 + (2 * std20)
        bb_lower = sma20 - (2 * std20)
        bb_pct = ((close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)).clip(0, 1)

        # EMA distance
        ema_50 = close.ewm(span=50, adjust=False).mean()
        ema_dist = ((close - ema_50) / close).clip(-0.05, 0.05)

        # Volume ratio
        volume_ma = volume.rolling(window=20).mean()
        vol_ratio = (volume / volume_ma.replace(0, np.nan)).clip(0, 3)

        # ATR
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        atr_pct = (atr / close).clip(0, 0.05)

        # FEATURES
        dataframe["%-rsi"] = (rsi / 100.0).clip(0, 1)
        dataframe["%-bb_pct"] = bb_pct
        dataframe["%-ema_dist"] = (ema_dist * 20).clip(-1, 1)
        dataframe["%-vol_ratio"] = (vol_ratio / 3.0).clip(0, 1)
        dataframe["%-atr_vol"] = (atr_pct * 20).clip(0, 1)

        return dataframe

    # ===========================================
    # populate_entry_trend
    # ===========================================
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Entry based on FreqAI regression prediction.
        1:1 R:R requires:
        - Entry: ml_pred > 0 (direction correct)
        - Stop: -0.3% from entry
        - Target: +0.3% from entry

        Conditions:
        - LONG: ml_prediction > 0.0005 (0.05% predicted return)
        - SHORT: ml_prediction < -0.0005 (0.05% predicted return)
        """
        ml_pred = dataframe.get("&ml_prediction", 0.0)
        rsi = dataframe.get("rsi", 50)

        # More aggressive thresholds for higher trade frequency
        long_cond = (ml_pred > 0.0005) & (rsi < 75)
        short_cond = (ml_pred < -0.0005) & (rsi > 25)

        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    # ===========================================
    # populate_exit_trend
    # ===========================================
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Exit controlled by ROI table and stoploss."""
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
