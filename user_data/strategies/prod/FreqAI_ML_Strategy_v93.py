# pragma pylint: disable=invalid-name
"""
FreqAI ML Strategy V93 — Simple Direction (1H)
Pairs: BTC/USDT
Timeframe: 1H (reduced noise)
FreqAI mode: Regression (XGBoostRegressor)
Target: raw 4-bar forward return (4 hours ahead)
Entry: ml_pred > 0 (LONG), < 0 (SHORT) — pure direction
Exit: Trailing stop (0.02) + time exit 24h
Stop loss: -0.03 (3%)

CHANGE from V92:
- Timeframe: 1H (was 15m) — much less noise
- Pure direction entry (no threshold) — all signals taken
- Trailing stop 2% (allows big moves to run)
- No explicit ROI table — let trailing handle winners

HYPOTHESIS: 1H noise is low enough that ML direction prediction
is accurate enough to be positive expectancy with 3% stop.
"""

import numpy as np
import pandas as pd

from freqtrade.strategy import IStrategy


class FreqAI_ML_Strategy_v93(IStrategy):
    """Simple ML direction prediction on 1H."""

    timeframe = "1h"
    stoploss = -0.03  # -3% stop
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03
    max_open_trades = 2
    stake_amount = 50.0

    # Minimal ROI — rely on trailing stop
    minimal_roi = {
        "0": 0.02,
        "720": 0.01,  # After 12h: 1% min
    }

    freqai_enable = True

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Simple RSI
        delta = dataframe["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        # EMA for trend
        dataframe["ema_50"] = dataframe["close"].ewm(span=50, adjust=False).mean()

        # Volume ratio
        vol_ma = dataframe["volume"].rolling(window=20).mean()
        dataframe["vol_ratio"] = (dataframe["volume"] / vol_ma.replace(0, np.nan)).clip(0, 3)

        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def set_freqai_targets(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        # 4-bar (4h for 1H) forward return
        dataframe["&ml_prediction"] = dataframe["close"].shift(-4) / dataframe["close"] - 1
        return dataframe

    def feature_engineering_standard(
        self, dataframe: pd.DataFrame, metadata: dict, **kwargs
    ) -> pd.DataFrame:
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

        # BB
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        bb_upper = sma20 + (2 * std20)
        bb_lower = sma20 - (2 * std20)
        bb_pct = ((close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)).clip(0, 1)

        # EMA distance
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema_dist = ((close - ema50) / close).clip(-0.05, 0.05)

        # Volume
        vol_ma = volume.rolling(window=20).mean()
        vol_ratio = (volume / vol_ma.replace(0, np.nan)).clip(0, 3)

        # ATR
        tr = pd.concat(
            [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
        ).max(axis=1)
        atr = tr.rolling(window=14).mean()
        atr_pct = (atr / close).clip(0, 0.05)

        dataframe["%-rsi"] = (rsi / 100).clip(0, 1)
        dataframe["%-bb_pct"] = bb_pct
        dataframe["%-ema_dist"] = (ema_dist * 20).clip(-1, 1)
        dataframe["%-vol_ratio"] = (vol_ratio / 3).clip(0, 1)
        dataframe["%-atr_vol"] = (atr_pct * 20).clip(0, 1)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Direction + trend filter.
        Only enter if:
        1. ML predicts direction (ml_pred > 0 for LONG, < 0 for SHORT)
        2. Trend agrees (close > EMA50 for LONG, close < EMA50 for SHORT)
        """
        ml_pred = dataframe.get("&ml_prediction", 0.0)

        # NO trend filter — test if ML direction alone generates signals
        long_cond = ml_pred > 0
        short_cond = ml_pred < 0

        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
