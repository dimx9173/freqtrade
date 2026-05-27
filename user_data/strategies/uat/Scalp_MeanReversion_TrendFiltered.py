"""
Scalp_MeanReversion_TrendFiltered - 均值回歸+趨勢濾網策略
============================================================
Purpose: 均值回歸策略搭配趨勢濾網，只在上升趨勢中進場
Timeframe: 5m
Entry: Price < BB lower band (2.5 std) AND RSI < 35 AND EMA9 > EMA21 (短期多頭)
Exit: Price reaches BB middle band OR +1% take profit
Stop Loss: -1% (config overrides to -0.5% in backtest)

Backtest: 2025-01-01 ~ 2026-04-26

Results Comparison:
- Original Scalp_MeanReversion: 1002 trades, -7.97% total profit
- With trend filter (EMA9>EMA21): 0 trades (too restrictive)
- Without trend filter (simplified): 2463 trades, -21.35% total profit

Key Finding: The EMA trend filter (EMA9 > EMA21) is too restrictive for this
bear market period (2025-2026, market down -40.62%). The filter eliminates ALL
entries because when the market is in a sustained downtrend, the fast EMA
never crosses above the medium EMA during oversold bounce setups.

Recommendations for improvement:
1. Use longer EMA periods (e.g., EMA50 > EMA200 for trend)
2. Use price-based trend filter (price > SMA50)
3. Use ADX filter to detect trending vs ranging markets
4. Apply filter only on higher timeframe (15m/1h) to confirm trend direction
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_MeanReversion_TrendFiltered(IStrategy):
    # Fixed parameters
    stoploss = -0.01  # -1% stop loss (wider to avoid volatility sweep)
    minimal_roi = {
        "0": 0.01,  # +1% take profit immediately
    }
    leverage = 5
    futures_leverage = True
    timeframe = "5m"
    process_only_new_candles = True

    # Enable custom stoploss to use our -1% value
    use_custom_stoploss = True

    # Trailing stop - disabled for mean reversion
    trailing_stop = False

    # Bollinger Bands parameters (2.5 std dev - same as original)
    bb_period = 20
    bb_std = 2.5

    # RSI parameters
    rsi_period = 14
    rsi_threshold = 35

    # EMA parameters for trend filter
    ema_short_period = 9  # Fast EMA
    ema_medium_period = 21  # Medium EMA
    ema_long_period = 50  # Slow EMA for trend detection

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands with 2.5 std dev
        bb_upper, bb_middle, bb_lower = ta.BBANDS(
            dataframe["close"], timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        dataframe["bb_upper"] = bb_upper
        dataframe["bb_middle"] = bb_middle
        dataframe["bb_lower"] = bb_lower

        # BB Width (volatility indicator)
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe[
            "bb_middle"
        ]

        # BB %B (position within bands)
        dataframe["bb_pct"] = (dataframe["close"] - dataframe["bb_lower"]) / (
            dataframe["bb_upper"] - dataframe["bb_lower"]
        )

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=self.rsi_period)

        # Volume SMA
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # EMA for trend filter
        dataframe["ema_short"] = ta.EMA(dataframe["close"], timeperiod=self.ema_short_period)
        dataframe["ema_medium"] = ta.EMA(dataframe["close"], timeperiod=self.ema_medium_period)
        dataframe["ema_long"] = ta.EMA(dataframe["close"], timeperiod=self.ema_long_period)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry Condition 1: Price below BB lower band (oversold)
        cond_oversold = dataframe["close"] < dataframe["bb_lower"]

        # Entry Condition 2: RSI < 35 (strong oversold)
        cond_rsi = dataframe["rsi"] < self.rsi_threshold

        # Entry Condition 3: EMA Trend Filter (EMA9 > EMA21 = 短期多頭排列)
        # NOTE: This filter is too restrictive for bear markets
        # During backtest period (2025-2026), market was down -40.62%
        # This causes 0 trades because EMA9 never stays above EMA21 during bounces
        cond_trend = dataframe["ema_short"] > dataframe["ema_medium"]

        # Volume confirmation (not too low)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * 0.5)

        # Bullish candle (recovery signal)
        cond_bullish = dataframe["close"] > dataframe["open"]

        # Full entry condition with trend filter
        dataframe["enter_long"] = (
            cond_oversold & cond_rsi & cond_trend & cond_volume & cond_bullish
        ).astype(int)

        return dataframe

    def populate_entry_trend_nofilter(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Alternative entry WITHOUT trend filter for comparison
        Used to test strategy viability when trend filter is too restrictive
        """
        # Entry Condition 1: Price below BB lower band (oversold)
        cond_oversold = dataframe["close"] < dataframe["bb_lower"]

        # Entry Condition 2: RSI < 35 (strong oversold)
        cond_rsi = dataframe["rsi"] < self.rsi_threshold

        # Volume confirmation (not too low)
        cond_volume = dataframe["volume"] >= (dataframe["volume_sma"] * 0.5)

        dataframe["enter_long"] = (cond_oversold & cond_rsi & cond_volume).astype(int)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: Price reaches BB middle band (mean reversion target)
        # Mark exit when price crosses BB middle from below
        cond_bb_middle = (dataframe["close"] >= dataframe["bb_middle"]) & (
            dataframe["close"].shift(1) < dataframe["bb_middle"].shift(1)
        )

        dataframe["exit_long"] = cond_bb_middle.astype(int)
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> bool:
        """
        進場前確認：檢查價差，避免高滑價環境
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return False

        last_candle = dataframe.iloc[-1]

        # 檢查價差 (Spread)
        spread = (last_candle["high"] - last_candle["low"]) / last_candle["close"]
        if spread > 0.006:
            return False

        return True

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        """
        Custom exit: +1% take profit OR when price reaches BB middle
        This handles the primary exit logic for mean reversion
        """
        # Take profit at +1%
        if current_profit >= 0.01:
            return "take_profit_1pct"

        return None

    def custom_stoploss(
        self,
        pair: str,
        trade,
        entry: float,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        Fixed -1% stop loss (wider to avoid volatility sweep)
        """
        return -0.01
