# pragma pylint: disable=invalid-name
"""
FreqAI ML Strategy V92A — Wide R:R Scalp (5:1)
Pairs: BTC/USDT, ETH/USDT
Timeframe: 15m (reduced noise vs 5m)
Features: 5 max (%-prefixed)
FreqAI mode: Regression (XGBoostRegressor)
Target: raw 12-bar forward return % (3 hours ahead)
Entry: prediction > 0.002 (LONG), < -0.002 (SHORT)
Exit: ROI +3%, Stoploss -1% → 3:1 R:R

CHANGE from V91:
- Timeframe: 15m (was 5m) — less noise, better ML signal
- R:R = 3:1 (target 3%, stop -1%) — 39.6% win rate CAN be positive here
- Target horizon: 12 bars (3 hours for 15m)
- Entry threshold: 0.002 (same as V90 which had good win rate)

KEY INSIGHT: 1:1 R:R failed because 39.6% win rate < 59.3% break-even.
3:1 R:R only needs 25% win rate to break even. Our 39.6% WIN RATE becomes powerful.
"""

import numpy as np
import pandas as pd

from freqtrade.strategy import IStrategy


class FreqAI_ML_Strategy_v92A(IStrategy):
    """
    FreqAI Scalping with 3:1 R:R.
    V91: 0.3%/0.3% → needed 59.3% win rate → had 39.6% → FAIL
    V92: 1.0%/3.0% → needs 25.0% win rate → have 39.6% → SHOULD WORK
    """

    # ===========================================
    # TIMEFRAME & STOPLOSS
    # ===========================================
    timeframe = "15m"
    stoploss = -0.01  # -1% (1R for 3:1 R:R)
    trailing_stop = False  # Scalp: fast exits
    max_open_trades = 3
    stake_amount = 50.0

    # ===========================================
    # ROI — 3:1 R:R scalp targets
    # ===========================================
    minimal_roi = {
        "0": 0.05,  # 5% take profit (5R)
        "60": 0.03,  # 3% after 1h
        "180": 0.02,  # 2% after 3h (time exit)
    }

    freqai_enable = True

    # ===========================================
    # populate_indicators
    # ===========================================
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Traditional indicators.
        """
        # RSI
        delta = dataframe["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands (window 20)
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
        Target: raw 12-bar forward return % (3 hours for 15m).
        Changed from V91's 6-bar (30 min) to reduce noise.
        """
        dataframe["&ml_prediction"] = dataframe["close"].shift(-12) / dataframe["close"] - 1
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
        3:1 R:R: 1% risk, 3% reward per trade.

        Conditions:
        - LONG: ml_prediction > 0.002 (0.2% predicted 3h return)
        - SHORT: ml_prediction < -0.002 (0.2% predicted 3h return)
        """
        ml_pred = dataframe.get("&ml_prediction", 0.0)
        rsi = dataframe.get("rsi", 50)

        # Entry threshold: 0.002 (same as V90's successful 0.001 but slightly higher)
        long_cond = (ml_pred > 0.001) & (rsi < 80)
        short_cond = (ml_pred < -0.001) & (rsi > 20)

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
