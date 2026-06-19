"""
FreqAI_ML_Strategy_v97 - Hybrid: Regime Detection + Pure Technical Entry
========================================================================

Core Design:
- Regime detection (V70): Uptrend/Downtrend/Sideways/Volatile
- Pure technical entry (D3e style): EMA21<EMA50 + ADX>=25 + DI->DI+
- Short only when Downtrend/HighVol
- Target: positive return in bear market

Architecture:
1. populate_indicators() → RSI, ADX, DI, EMA, BB
2. detect_regime() → classify market state
3. populate_entry_trend() → short only when regime confirms

Author: Hermes Agent for Brian
"""

import numpy as np
import pandas as pd
from freqtrade.strategy.interface import IStrategy
from freqtrade.exchange import timeframe_to_minutes
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class FreqAI_ML_Strategy_v97(IStrategy):
    version = "v97.0"
    INTERFACE_VERSION = 4

    # Stoploss / ROI
    stoploss = -0.03
    trailing_stop = False
    trailing_stop_positive = 0.0
    trailing_stop_positive_offset = 0.0
    minimal_roi = {
        "0": 0.015,  # 1.5% immediate
        "60": 0.01,  # 1% after 60 bars (5h)
        "180": 0.005,  # 0.5% after 180 bars (15h)
    }
    timeframe = "5m"

    # Backtest settings
    process_only_new_candles = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # ===========================================
    # REGIME DETECTION PARAMETERS
    # ===========================================
    adx_threshold = 25
    ema_fast = 21
    ema_slow = 50

    # ===========================================
    # POPULATE INDICATORS
    # ===========================================
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ADX
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # +DI / -DI
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # EMA
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.ema_fast)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.ema_slow)

        # Bollinger Bands (manual to avoid TALib string issue)
        sma20 = dataframe["close"].rolling(window=20).mean()
        std20 = dataframe["close"].rolling(window=20).std()
        dataframe["bb_middle"] = sma20
        dataframe["bb_upper"] = sma20 + (2.0 * std20)
        dataframe["bb_lower"] = sma20 - (2.0 * std20)
        dataframe["bb_pct"] = (
            (dataframe["close"] - dataframe["bb_lower"])
            / (dataframe["bb_upper"] - dataframe["bb_lower"]).replace(0, np.nan)
        ).clip(0, 1)

        # Regime detection
        dataframe = self.detect_regime(dataframe)

        return dataframe

    # ===========================================
    # REGIME DETECTION (V70 style)
    # ===========================================
    def detect_regime(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Classify market into 4 regimes:
        - UPTREND: EMA21 > EMA50 AND ADX > 25 AND +DI > -DI
        - DOWNTREND: EMA21 < EMA50 AND ADX > 25 AND -DI > +DI
        - SIDEWAYS: ADX < 25
        - VOLATILE: ADX > 40 AND +DI > 30 AND -DI > 30
        """
        ema_fast = dataframe["ema_fast"]
        ema_slow = dataframe["ema_slow"]
        adx = dataframe["adx"]
        plus_di = dataframe["plus_di"]
        minus_di = dataframe["minus_di"]

        # Default: Sideways
        dataframe["regime"] = "sideways"

        # Downtrend: EMA fast below slow AND ADX confirms AND -DI leads
        downtrend = (ema_fast < ema_slow) & (adx > self.adx_threshold) & (minus_di > plus_di)
        dataframe.loc[downtrend, "regime"] = "downtrend"

        # Uptrend: EMA fast above slow AND ADX confirms AND +DI leads
        uptrend = (ema_fast > ema_slow) & (adx > self.adx_threshold) & (plus_di > minus_di)
        dataframe.loc[uptrend, "regime"] = "uptrend"

        # Volatile: ADX very high with both DI elevated
        volatile = (adx > 40) & (plus_di > 30) & (minus_di > 30)
        dataframe.loc[volatile, "regime"] = "volatile"

        # Sideways: ADX low
        dataframe.loc[adx < self.adx_threshold, "regime"] = "sideways"

        # Encode as integers for freqtrade
        regime_map = {"sideways": 0, "uptrend": 1, "downtrend": 2, "volatile": 3}
        dataframe["regime_encoded"] = dataframe["regime"].map(regime_map).fillna(0).astype(int)

        return dataframe

    # ===========================================
    # ENTRY LOGIC - SHORT ONLY in Downtrend/Volatile
    # ===========================================
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Short entry when:
        - Regime is DOWNTREND or VOLATILE
        - EMA21 < EMA50 (confirmed downtrend)
        - ADX >= 25 (trend has strength)
        - -DI > +DI (downward momentum)
        - RSI in 32-72 range (not oversold/overbought)
        """
        regime = dataframe["regime"]
        ema_fast = dataframe["ema_fast"]
        ema_slow = dataframe["ema_slow"]
        adx = dataframe["adx"]
        plus_di = dataframe["plus_di"]
        minus_di = dataframe["minus_di"]
        rsi = dataframe["rsi"]

        # Short conditions
        short_cond = (
            ((regime == "downtrend") | (regime == "volatile"))
            & (ema_fast < ema_slow)
            & (adx >= self.adx_threshold)
            & (minus_di > plus_di)
            & (rsi > 32)
            & (rsi < 72)
        )

        dataframe["enter_short"] = short_cond.astype(int)
        dataframe["enter_long"] = 0  # No long entries

        return dataframe

    # ===========================================
    # EXIT LOGIC
    # ===========================================
    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Exit when:
        - RSI hits 30 (oversold - take profit)
        - OR regime changes to UPTREND/SIDEWAYS
        """
        regime = dataframe["regime"]
        rsi = dataframe["rsi"]
        adx = dataframe["adx"]

        # Exit short when RSI oversold or trend reversal
        exit_short = (rsi < 32) | ((regime == "uptrend") & (adx > 25))
        dataframe["exit_short"] = exit_short.astype(int)
        dataframe["exit_long"] = 0

        return dataframe
