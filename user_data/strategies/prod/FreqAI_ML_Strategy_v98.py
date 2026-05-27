# pragma pylint: disable=missing-docstring,invalid-name
"""
FreqAI_ML_Strategy_v98 - Regime Detection + Wide Stoploss + Aggressive ROI
============================================================================

Key insight from V70 success:
- Stoploss: -12% (NOT -3%/-4% which got immediately stopped out)
- ROI: 10% immediate + 5% in 60min
- Regime-adaptive: Short in downtrend/volatile, Long in sideways/uptrend
- Max duration exits per regime
- Custom exit logic from V70

This is the PURE TECHNICAL version (no FreqAI) based on V70 architecture.
"""

import numpy as np
from freqtrade.strategy import IStrategy
import talib.abstract as ta
from pandas import DataFrame


class FreqAI_ML_Strategy_v98(IStrategy):
    version = "v98.0"
    INTERFACE_VERSION = 4

    # === STOPLOSS — MUST BE WIDE for volatile bear markets ===
    stoploss = -0.12
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.015

    # === TIMEFRAME ===
    timeframe = "5m"

    # === ROI — Take profit aggressively ===
    minimal_roi = {
        "0": 0.10,
        "60": 0.05,
        "120": 0.03,
        "240": 0.02,
    }

    # === MAX OPEN TRADES ===
    max_open_trades = 2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMAs
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=50)

        # ADX + Directional Indicators
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

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

        # Volume
        dataframe["volume"] = dataframe["volume"]

        # Regime detection (V70 logic, simplified)
        dataframe["regime"] = "sideways"
        dataframe.loc[
            (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["adx"] > 25)
            & (dataframe["minus_di"] > dataframe["plus_di"]),
            "regime",
        ] = "downtrend"
        dataframe.loc[
            (dataframe["ema_fast"] > dataframe["ema_slow"])
            & (dataframe["adx"] > 25)
            & (dataframe["plus_di"] > dataframe["minus_di"]),
            "regime",
        ] = "uptrend"
        dataframe.loc[dataframe["adx"] > 40, "regime"] = "volatile"
        dataframe.loc[dataframe["adx"] < 20, "regime"] = "sideways"

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = "none"

        # === DOWNTREND: Short when EMA bearish + ADX confirms + RSI mid/high ===
        # Key fix: RSI > 50 means NOT oversold — we're fading the bounce
        downtrend_short = (
            (dataframe["regime"] == "downtrend")
            & (dataframe["ema_fast"] < dataframe["ema_slow"])
            & (dataframe["adx"] >= 25)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["rsi"] > 50)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[downtrend_short, "enter_short"] = 1
        dataframe.loc[downtrend_short, "enter_tag"] = "dntrend_short"

        # === VOLATILE: Short when strong ADX + DI- leading ===
        volatile_short = (
            (dataframe["regime"] == "volatile")
            & (dataframe["adx"] >= 30)
            & (dataframe["minus_di"] > dataframe["plus_di"])
            & (dataframe["rsi"] > 60)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[volatile_short, "enter_short"] = 1
        dataframe.loc[volatile_short, "enter_tag"] = "volatile_short"

        # === SIDEWAYS: Long mean-reversion at lower BB ===
        sideways_long = (
            (dataframe["regime"] == "sideways")
            & (dataframe["bb_pct"] < 0.25)
            & (dataframe["rsi"] < 45)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[sideways_long, "enter_long"] = 1
        dataframe.loc[sideways_long, "enter_tag"] = "sideways_long"

        # === UPTREND: Long at pullbacks (RSI < 40 = oversold territory) ===
        uptrend_long = (
            (dataframe["regime"] == "uptrend")
            & (dataframe["bb_pct"] < 0.20)
            & (dataframe["rsi"] < 40)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[uptrend_long, "enter_long"] = 1
        dataframe.loc[uptrend_long, "enter_tag"] = "uptrend_long"

        return dataframe

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ) -> str:
        """Force exit after max duration per regime."""
        dataframe, _ = self.strategy_resolution(pair)
        if dataframe is None:
            return ""

        regime = self._get_regime_at_time(dataframe, current_time)
        max_minutes = {
            "downtrend": 120,
            "volatile": 60,
            "sideways": 90,
            "uptrend": 240,
        }.get(regime, 120)

        open_minutes = (current_time - trade.open_date).total_seconds() / 60
        if open_minutes > max_minutes:
            return "max_duration"
        if current_profit < -0.10:
            return "hard_stop"
        return ""

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Exit signals per regime."""
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0

        # Long exit: RSI overbought OR price at upper BB
        long_exit = (dataframe["rsi"] > 65) | (dataframe["close"] >= dataframe["bb_upper"] * 0.99)
        dataframe.loc[long_exit, "exit_long"] = 1

        # Short exit: RSI oversold OR price at lower BB
        short_exit = (dataframe["rsi"] < 35) | (dataframe["close"] <= dataframe["bb_lower"] * 1.01)
        dataframe.loc[short_exit, "exit_short"] = 1

        return dataframe

    def _get_regime_at_time(self, dataframe: DataFrame, current_time) -> str:
        try:
            idx = dataframe["date"].searchsorted(current_time)
            idx = min(idx, len(dataframe) - 1)
            return dataframe.iloc[idx]["regime"]
        except Exception:
            return "sideways"
