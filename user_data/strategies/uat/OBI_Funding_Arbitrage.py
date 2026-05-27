"""
OBI_Funding_Arbitrage - Order Book Imbalance + Funding Rate Strategy
===================================================================
High-frequency mean reversion strategy using proxy indicators for order book imbalance.

Core Logic:
- Use Trend Pressure Index (TPI) as Order Book Imbalance proxy
- Use Volume Delta Z-Score as confirmation
- Use Funding Rate as market direction filter
- Target holding: 1-3 minutes
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
from functools import reduce


class OBI_Funding_Arbitrage(IStrategy):
    # ========== Core Parameters ==========
    timeframe = "1m"  # 1-minute for ultra-short holding
    leverage = 5
    futures_leverage = True

    # ========== Stoploss ==========
    stoploss = -0.004  # -0.4% hard stop

    # ========== Time Exit ==========
    max_holding_seconds = 180  # 3 minutes max

    # ========== Minimal ROI ==========
    minimal_roi = {
        "0": 0.003,  # 0.3% immediate
        "1": 0.005,  # 0.5% after 1 min
        "3": 0.008,  # 0.8% after 3 min
    }

    # ========== Trailing Stop ==========
    trailing_stop = True
    trailing_stop_positive = 0.002  # 0.2%
    trailing_stop_positive_offset = 0.004  # 0.4%
    trailing_only_offset_is_reached = True

    # ========== TPI Parameters ==========
    tpi_long_threshold = -0.7  # Extreme sell pressure
    tpi_short_threshold = 0.7  # Extreme buy pressure
    tpi_exit_threshold = 0.3  # TPI reversion level

    # ========== Volume Delta Parameters ==========
    vd_period = 20
    vd_zscore_threshold = 1.5

    # ========== Bollinger Bands (for price position) ==========
    bb_period = 20
    bb_std = 2.0
    bb_lower_entry = 0.15
    bb_upper_entry = 0.85

    # ========== Volatility Compression ==========
    compression_short = 3
    compression_long = 10
    compression_threshold = 0.6

    # ========== Risk Management ==========
    max_open_trades = 2
    trade_cooldown = 60  # seconds
    daily_max_loss_pct = 0.02  # 2%
    max_drawdown_pct = 0.03  # 3%

    # ========== Funding Rate Filter ==========
    funding_rate_pos_threshold = 0.0001  # 0.01% - positive bias
    funding_rate_neg_threshold = -0.0001  # -0.01% - negative bias

    # ========== State Tracking ==========
    daily_pnl = 0.0
    last_reset_date = None

    # ========== Indicators ==========
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ---- Trend Pressure Index (TPI) ----
        # Measures directional pressure: (close - open) / (high - low)
        range_ = dataframe["high"] - dataframe["low"]
        range_ = range_.replace(0, np.nan)
        dataframe["tpi"] = (dataframe["close"] - dataframe["open"]) / range_

        # ---- Volume Delta ----
        # Volume delta: positive for buy-dominant, negative for sell-dominant
        delta = np.where(
            dataframe["close"] > dataframe["open"], dataframe["volume"], -dataframe["volume"]
        )
        delta = np.where(dataframe["close"] == dataframe["open"], 0, delta)
        dataframe["volume_delta"] = delta

        # ---- Volume Delta Z-Score ----
        vd_sma = DataFrame(delta).rolling(self.vd_period).mean()[0]
        vd_std = DataFrame(delta).rolling(self.vd_period).std()[0]
        dataframe["vd_zscore"] = (delta - vd_sma) / vd_std.replace(0, np.nan)

        # ---- Volatility Compression Ratio ----
        short_range = (
            dataframe["high"].rolling(self.compression_short).max()
            - dataframe["low"].rolling(self.compression_short).min()
        )
        long_range = (
            dataframe["high"].rolling(self.compression_long).max()
            - dataframe["low"].rolling(self.compression_long).min()
        )
        dataframe["compression"] = short_range / long_range.replace(0, np.nan)

        # ---- Bollinger Bands ----
        bbands = ta.BBANDS(
            dataframe, timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        dataframe["bb_upper"] = bbands["upperband"]
        dataframe["bb_middle"] = bbands["middleband"]
        dataframe["bb_lower"] = bbands["lowerband"]

        # ---- BB Position (%B) ----
        bb_range = dataframe["bb_upper"] - dataframe["bb_lower"]
        dataframe["bb_position"] = (dataframe["close"] - dataframe["bb_lower"]) / bb_range.replace(
            0, np.nan
        )

        # ---- ATR for volatility check ----
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        return dataframe

    # ========== Entry Logic ==========
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ---- LONG: Sell pressure extreme + reversal incoming ----
        cond_tpi_long = dataframe["tpi"] < self.tpi_long_threshold
        cond_bb_lower = dataframe["bb_position"] < self.bb_lower_entry
        cond_vd_long = dataframe["vd_zscore"] < -self.vd_zscore_threshold
        cond_compression = dataframe["compression"] < self.compression_threshold

        # Funding rate filter (optional - if data available)
        # cond_funding_long = dataframe.get('funding_rate', 0) > self.funding_rate_neg_threshold

        dataframe["enter_long"] = (
            cond_tpi_long & cond_bb_lower & cond_vd_long & cond_compression
        ).astype(int)

        # ---- SHORT: Buy pressure extreme + reversal incoming ----
        cond_tpi_short = dataframe["tpi"] > self.tpi_short_threshold
        cond_bb_upper = dataframe["bb_position"] > self.bb_upper_entry
        cond_vd_short = dataframe["vd_zscore"] > self.vd_zscore_threshold

        # cond_funding_short = dataframe.get('funding_rate', 0) < self.funding_rate_pos_threshold

        dataframe["enter_short"] = (
            cond_tpi_short & cond_bb_upper & cond_vd_short & cond_compression
        ).astype(int)

        return dataframe

    # ========== Exit Logic ==========
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    # ========== Custom Exit ==========
    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        """
        Exit logic:
        1. Time-based exit (3 min hard cap)
        2. TPI reversion exit
        3. Volume Delta reversion exit
        """
        # ---- Time exit ----
        if trade is not None and hasattr(trade, "open_date"):
            holding_seconds = (current_time - trade.open_date).total_seconds()
            if holding_seconds >= self.max_holding_seconds:
                return "time_exit"

        # ---- TPI reversion exit ----
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is not None and len(dataframe) > 0:
            current_tpi = dataframe["tpi"].iloc[-1]
            current_vd = dataframe["vd_zscore"].iloc[-1]

            # Long exit: TPI reverted positive
            if trade and trade.enter_side == "long":
                if current_tpi > self.tpi_exit_threshold:
                    return "tpi_reversion_long"
                if current_vd > 0:
                    return "vd_reversion_long"

            # Short exit: TPI reverted negative
            if trade and trade.enter_side == "short":
                if current_tpi < -self.tpi_exit_threshold:
                    return "tpi_reversion_short"
                if current_vd < 0:
                    return "vd_reversion_short"

        return None

    # ========== Confirm Trade Entry ==========
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
        Final confirmation before order executes.
        Extra filters beyond entry signal.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) < 20:
            return False

        last_candle = dataframe.iloc[-1]

        # 1. Volatility check (not too volatile)
        atr_pct = last_candle["atr_pct"]
        if atr_pct > 0.01:  # > 1% ATR
            return False

        # 2. TPI must still be extreme (confirmation)
        if side == "long":
            if last_candle["tpi"] > self.tpi_long_threshold * 0.5:
                return False  # Already started reverting
        else:
            if last_candle["tpi"] < self.tpi_short_threshold * 0.5:
                return False

        # 3. Volume delta confirmation
        if abs(last_candle["vd_zscore"]) < 1.0:
            return False

        return True

    # ========== Slippage Protection ==========
    @property
    def confirm_trade_entry_timeout(self) -> int:
        return 30  # 30 seconds timeout

    # ========== Custom Stoploss ==========
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
        return self.stoploss

    # ========== Pair Lock ==========
    def _get_pair_lock_time(self, pair: str) -> int:
        return self.trade_cooldown
