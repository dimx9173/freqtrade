# pragma pylint: disable=invalid-name
"""
FreqAI ML Strategy V84 — Hybrid: V70 Regime Detection + V83 ML Prediction
Pairs: BTC/USDT only
Timeframe: 5m (from V83)
Features: 5 max (from V83)
FreqAI mode: Regression (XGBoostRegressor)
Target: raw 12-bar forward return % (1 hour ahead for 5m data)
Entry: prediction > 70th percentile (LONG), < 30th percentile (SHORT)
Regime Filter: V70 regime detection added to filter entries

CHANGE from V83:
- Add V70-style regime detection (uptrend, downtrend, sideways, volatile)
- LONG entry: regime is NOT downtrend AND prediction > 70th percentile
- SHORT entry: regime IS downtrend AND prediction < 30th percentile
- V70 indicators added: adx, bb_position, volume_ratio, ema_distance
"""

import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import IStrategy


class FreqAI_ML_Strategy_v84(IStrategy):
    """
    FreqAI Regression Strategy V84 - Hybrid with V70 Regime Detection.
    Predicts raw 12-bar forward return % using 5 features.
    Regime detection filters entries to improve quality.
    """

    # ===========================================
    # TIMEFRAME & STOPLOSS
    # ===========================================
    timeframe = "5m"
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
    # REGIME DETECTION PARAMETERS (from V70)
    # ===========================================
    regime_lookback_period = 100
    regime_adx_period = 14
    uptrend_adx_min = 25
    downtrend_adx_min = 20

    # ===========================================
    # populate_indicators
    # ===========================================
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Traditional indicators + regime detection (V70 style).
        """

        # --- Basic indicators (from V83) ---
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
        dataframe["bb_upper"] = bb_upper
        dataframe["bb_lower"] = bb_lower
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

        # --- V70 Regime Detection Indicators ---
        # EMA system
        dataframe["ema_fast"] = close.ewm(span=12, adjust=False).mean()
        dataframe["ema_slow"] = close.ewm(span=26, adjust=False).mean()
        dataframe["ema_medium"] = ema_50

        # ADX
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # Volatility
        dataframe["atr"] = atr
        dataframe["atr_percentile"] = (
            dataframe["atr"]
            .rolling(100)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
        )
        dataframe["realized_volatility"] = close.rolling(20).std()
        dataframe["volatility_ratio"] = dataframe["atr"] / (
            dataframe["realized_volatility"] + 1e-10
        )

        # VWAP
        dataframe["vwap"] = self.calc_vwap(dataframe)

        # --- Calculate market regime (V70 logic) ---
        dataframe = self.detect_market_regime(dataframe)

        # --- Extra indicators for regime confirmation ---
        dataframe["ema_trend_strength"] = (
            dataframe["ema_fast"] - dataframe["ema_slow"]
        ) / dataframe["ema_slow"]
        dataframe["ema_convergence"] = (
            np.abs(dataframe["ema_fast"] - dataframe["ema_slow"]) / dataframe["ema_slow"]
        )

        # FREQAI REQUIRED CALL - must be last in this method
        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    def calc_vwap(self, dataframe: pd.DataFrame) -> pd.Series:
        """Calculate VWAP."""
        typical = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3
        cum_vol = dataframe["volume"].cumsum()
        return (typical * dataframe["volume"]).cumsum() / cum_vol.replace(0, np.nan)

    def detect_market_regime(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        V70-style Multi-Factor Market Regime Detection.
        Regimes: uptrend, downtrend, sideways, volatile
        """
        lookback = self.regime_lookback_period

        # EMA Trend
        dataframe["ema_trend_strength"] = (
            dataframe["ema_fast"] - dataframe["ema_slow"]
        ) / dataframe["ema_slow"]
        dataframe["ema_convergence"] = (
            np.abs(dataframe["ema_fast"] - dataframe["ema_slow"]) / dataframe["ema_slow"]
        )

        # Price vs EMAs
        dataframe["price_vs_ema_medium"] = (
            dataframe["close"] - dataframe["ema_medium"]
        ) / dataframe["ema_medium"]

        # ADX-based trend strength
        dataframe["adx_strong"] = dataframe["adx"] > self.uptrend_adx_min

        # DI-based direction
        dataframe["di_bullish"] = dataframe["plus_di"] > dataframe["minus_di"]
        dataframe["di_bearish"] = dataframe["minus_di"] > dataframe["plus_di"]

        # Volatility percentile
        dataframe["volatility_percentile"] = (
            dataframe["volatility_ratio"]
            .rolling(lookback)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5, raw=False)
        )

        # High volatility flag
        dataframe["high_volatility"] = dataframe["volatility_ratio"] > dataframe[
            "volatility_ratio"
        ].rolling(50).quantile(0.80)

        # ---- Regime Classification ----
        dataframe["market_regime"] = "neutral"

        # SIDEWAYS (low ADX, EMAs converging)
        sideways_condition = (
            (dataframe["adx"] < 20)
            & (dataframe["ema_convergence"] < 0.01)
            & (dataframe["volatility_percentile"] < 0.7)
        )
        dataframe.loc[sideways_condition, "market_regime"] = "sideways"

        # HIGH VOLATILITY
        high_vol_condition = (dataframe["volatility_percentile"] > 0.90) | (
            dataframe["high_volatility"]
        )
        dataframe.loc[high_vol_condition, "market_regime"] = "volatile"

        # UPTREND
        uptrend_condition = (
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["close"] > dataframe["ema_medium"])
            & (dataframe["adx"] >= self.uptrend_adx_min)
            & (dataframe["di_bullish"])
        )
        dataframe.loc[uptrend_condition, "market_regime"] = "uptrend"

        # DOWNTREND
        downtrend_condition = (
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["close"] < dataframe["ema_medium"])
            & (dataframe["adx"] >= self.downtrend_adx_min)
            & (dataframe["di_bearish"])
        )
        dataframe.loc[downtrend_condition, "market_regime"] = "downtrend"

        # Override with high volatility if present
        high_vol_override = (
            dataframe["market_regime"].isin(["uptrend", "downtrend", "sideways"])
            & high_vol_condition
        )
        dataframe.loc[high_vol_override, "market_regime"] = "volatile"

        # Regime indicators
        dataframe["regime_is_uptrend"] = (dataframe["market_regime"] == "uptrend").astype(int)
        dataframe["regime_is_downtrend"] = (dataframe["market_regime"] == "downtrend").astype(int)
        dataframe["regime_is_sideways"] = (dataframe["market_regime"] == "sideways").astype(int)
        dataframe["regime_is_volatile"] = (dataframe["market_regime"] == "volatile").astype(int)

        return dataframe

    # ===========================================
    # set_freqai_targets
    # ===========================================
    def set_freqai_targets(self, dataframe: pd.DataFrame, metadata: dict, **kwargs) -> pd.DataFrame:
        """
        REQUIRED by FreqAI.
        Defines the target: raw 12-bar forward return % (same as V83).
        """
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
        Same 5 features as V83:
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
    # populate_entry_trend - V84 HYBRID LOGIC
    # ===========================================
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        V84 Hybrid Entry: V70 regime filter + V83 ML prediction.

        Entry Rules:
        - LONG: regime is NOT downtrend AND prediction > 70th percentile
        - SHORT: regime IS downtrend AND prediction < 30th percentile

        This filters out bad entries:
        - No LONG in downtrend (catch the falling knife)
        - No SHORT in uptrend (fight the trend)
        """
        prediction = dataframe.get("&-ml_return", 0)
        do_predict = dataframe.get("do_predict", 1)

        valid = do_predict == 1

        # Get regime (V70 style)
        regime = dataframe["market_regime"]

        # Compute percentile thresholds dynamically from predictions (same as V83)
        pred_valid = prediction[valid & prediction.notna()]
        if len(pred_valid) > 0:
            p30 = pred_valid.quantile(0.30)
            p70 = pred_valid.quantile(0.70)
        else:
            p30 = -0.001
            p70 = 0.001

        # V84 regime filter conditions
        regime_allows_long = regime != "downtrend"
        regime_allows_short = regime == "downtrend"

        # LONG: regime is NOT downtrend AND prediction > 70th percentile
        long_cond = valid & regime_allows_long & (prediction > p70)

        # SHORT: regime IS downtrend AND prediction < 30th percentile
        short_cond = valid & regime_allows_short & (prediction < p30)

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
