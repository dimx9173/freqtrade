#!/usr/bin/env python3
"""
FreqTrade Strategy: RegimeAware_v1
Regime-adaptive bidirectional strategy

Market Analysis:
- Bull (BTC up): RSI oversold -> 55% win rate, +0.17% avg 24h return
- Bear (BTC down): RSI overbought -> 55% win rate, -0.17% avg 24h return

Strategy:
- Detect regime using 200 EMA of daily close
- Bull: Long when RSI < 30, exit when RSI > 55
- Bear: Short when RSI > 70, exit when RSI < 45
- 5m candles, but use daily EMA for regime
"""

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade


class RegimeAware_v1(IStrategy):
    timeframe = "5m"
    can_short = True

    minimal_roi = {
        "0": 0.01,  # 1% profit target (fast, capture quick moves)
        "60": 0.005,  # 0.5% after 1h
    }
    stoploss = -0.015  # -1.5% tight stop

    RSI_PERIOD = 14

    # Regime detection
    REGIME_EMA_PERIOD = 200  # Daily EMA for trend
    REGIME_BULL_THRESHOLD = 1.01  # Price 1% above EMA = bull
    REGIME_BEAR_THRESHOLD = 0.99  # Price 1% below EMA = bear

    default_stake_amount = 0.95
    startup_candle_count = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.RSI_PERIOD)

        # For regime: use a longer lookback
        # On 5m, use 200 EMA as short-term reference
        dataframe["ema_short"] = ta.EMA(dataframe, timeperiod=50)

        # Price relative to short EMA
        dataframe["price_vs_ema"] = (dataframe["close"] / dataframe["ema_short"] - 1) * 100

        # Regime: Bull if price > EMA and rising
        dataframe["ema_diff"] = dataframe["ema_short"].diff(12)  # 12*5m = 1h of diff
        dataframe["is_bull"] = (dataframe["price_vs_ema"] > 0.5) & (dataframe["ema_diff"] > 0)
        dataframe["is_bear"] = (dataframe["price_vs_ema"] < -0.5) & (dataframe["ema_diff"] < 0)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bull market: Long on RSI oversold
        bull_long = dataframe["is_bull"] & (dataframe["rsi"] < 30)

        # Bear market: Short on RSI overbought
        bear_short = dataframe["is_bear"] & (dataframe["rsi"] > 70)

        dataframe.loc[bull_long, "enter_long"] = 1
        dataframe.loc[bear_short, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit Long: RSI normalized in bull
        long_exit = dataframe["rsi"] > 55

        # Exit Short: RSI normalized in bear
        short_exit = dataframe["rsi"] < 45

        dataframe.loc[long_exit, "exit_long"] = 1
        dataframe.loc[short_exit, "exit_short"] = 1
        return dataframe

    def adjust_position_size(
        self,
        market,
        current_time,
        current_rate,
        propose_rate,
        current_balance,
        max_stake,
        open_trades,
        trade: Trade,
        entry_rate,
        current_time_since,
        current_dt,
        **kwargs,
    ) -> float:
        return self.default_stake_amount
