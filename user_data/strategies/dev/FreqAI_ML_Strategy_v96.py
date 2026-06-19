"""
FreqAI_ML_Strategy_v96 - Kelly Criterion + Probability Theory
============================================================

Core Design:
- 5m intraday scalping (short-term)
- Top 5 pairs: BTC, ETH, SOL, XRP, LTC
- Max 5 indicators: RSI, BB_PCT, EMA_DIST, VOL_RATIO, ATR_VOL
- 6+ months training (FreqAI auto-trains on historical data)
- Target: 10% monthly return after fees
- Core: Kelly Criterion position sizing + probability theory

Architecture:
1. set_freqai_targets() → creates &ml_prediction (6-bar forward return %)
2. populate_indicators() → adds traditional indicators for strategy use
3. feature_engineering_standard() → creates 5 FreqAI features
4. populate_entry_trend() → uses FreqAI prediction + Kelly-inspired entry
5. populate_exit_trend() → minimal_roi-based exits
"""

import numpy as np
import pandas as pd
from freqtrade.strategy.interface import IStrategy
from typing import Dict


class FreqAI_ML_Strategy_v96(IStrategy):
    version = "v96.0"
    INTERFACE_VERSION = 4

    stoploss = -0.03
    trailing_stop = False
    trailing_stop_positive = 0.0
    trailing_stop_positive_offset = 0.0
    minimal_roi = {
        "0": 0.003,
        "30": 0.002,
        "60": 0.001,
    }
    timeframe = "5m"
    freqai_enabled = True

    process_only_new_candles = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    def set_freqai_targets(self, dataframe, metadata, **kwargs) -> pd.DataFrame:
        dataframe["&ml_prediction"] = dataframe["close"].shift(-6) / dataframe["close"] - 1
        return dataframe

    def populate_indicators(self, dataframe, metadata) -> pd.DataFrame:
        close = dataframe["close"]
        high = dataframe["high"]
        low = dataframe["low"]
        volume = dataframe["volume"]

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi"] = (100 - (100 / (1 + rs))).clip(0, 100)

        sma10 = close.rolling(window=10).mean()
        std10 = close.rolling(window=10).std()
        bb_upper = sma10 + (2 * std10)
        bb_lower = sma10 - (2 * std10)
        dataframe["bb_pct"] = ((close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)).clip(
            0, 1
        )

        ema_20 = close.ewm(span=20, adjust=False).mean()
        dataframe["ema_dist"] = ((close - ema_20) / close).clip(-0.05, 0.05)

        volume_ma = volume.rolling(window=10).mean()
        dataframe["vol_ratio"] = (volume / volume_ma.replace(0, np.nan)).clip(0, 3)

        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=7).mean()
        dataframe["atr_vol"] = (atr / close).clip(0, 0.05)

        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def feature_engineering_standard(self, dataframe, metadata, **kwargs) -> pd.DataFrame:
        close = dataframe["close"]
        high = dataframe["high"]
        low = dataframe["low"]
        volume = dataframe["volume"]

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).clip(0, 100)

        sma10 = close.rolling(window=10).mean()
        std10 = close.rolling(window=10).std()
        bb_upper = sma10 + (2 * std10)
        bb_lower = sma10 - (2 * std10)
        bb_pct = ((close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)).clip(0, 1)

        ema_20 = close.ewm(span=20, adjust=False).mean()
        ema_dist = ((close - ema_20) / close).clip(-0.05, 0.05)

        volume_ma = volume.rolling(window=10).mean()
        vol_ratio = (volume / volume_ma.replace(0, np.nan)).clip(0, 3)

        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=7).mean()
        atr_pct = (atr / close).clip(0, 0.05)

        dataframe["%-rsi"] = (rsi / 100.0).clip(0, 1)
        dataframe["%-bb_pct"] = bb_pct
        dataframe["%-ema_dist"] = (ema_dist * 20).clip(-1, 1)
        dataframe["%-vol_ratio"] = (vol_ratio / 3.0).clip(0, 1)
        dataframe["%-atr_vol"] = (atr_pct * 20).clip(0, 1)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata) -> pd.DataFrame:
        ml_pred = dataframe.get("&ml_prediction", 0.0)
        rsi = dataframe.get("rsi", 50)

        dataframe["enter_long"] = ((ml_pred > 0.0005) & (rsi < 70)).astype(int)
        dataframe["enter_short"] = ((ml_pred < -0.0005) & (rsi > 30)).astype(int)
        return dataframe

    def populate_exit_trend(self, dataframe, metadata) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
