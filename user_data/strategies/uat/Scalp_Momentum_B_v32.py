"""
Scalp_Momentum_B_v32 - Pure Spread Scalping Strategy
=====================================================
v32 Concept: Trade bid-ask spread, NOT trend direction.
- NO EMA for trend
- NO RSI for momentum
- BB for mean reversion
- Wick/body ratio for institutional activity
- Volume spike for confirmation
- 5-min hard exit

Key differences from v28/v31:
1. Completely ignores EMA crossover as trend signal
2. Uses Bollinger Bands for mean-reversion entries
3. Uses wick/body ratio (≥3.0) for rejection detection
4. Hard 5-minute time exit
5. Short side uses same logic (symmetric BB)
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v32(IStrategy):
    # ========== Core Parameters ==========
    stoploss = -0.005  # -0.5% hard stop (was -0.15%, too tight)
    leverage = 5
    futures_leverage = True
    timeframe = "5m"  # Changed from 1m to 5m (1m noise too high)
    process_only_new_candles = True

    # Time exit (15 minutes = 900 seconds, was 300)
    max_holding_seconds = 900

    # ========== Minimal ROI (adjusted for 5m) ==========
    minimal_roi = {
        "0": 0.005,  # 0.5% immediate
        "5": 0.008,  # 0.8% after 5 min
        "10": 0.012,  # 1.2% after 10 min
        "15": 0.015,  # 1.5% after 15 min (max)
    }

    # ========== Trailing Stop ==========
    trailing_stop = True
    trailing_stop_positive = 0.003  # 0.3% (was 0.2%)
    trailing_stop_positive_offset = 0.006  # 0.6% (was 0.4%)
    trailing_only_offset_is_reached = True

    # ========== Bollinger Bands Parameters ==========
    bb_period = 20
    bb_std = 1.5  # Tighter than default 2.0 for more signals

    # ========== Wick Rejection Parameters ==========
    wick_body_ratio = 3.0  # Wick must be 3x body (strong rejection)
    wick_dominance = True  # Wick must dominate the other side

    # ========== Volume Parameters ==========
    volume_sma_period = 20
    volume_ratio_min = 1.5  # Volume must be 1.5x average

    # ========== ATR/Volatility Filter ==========
    atr_period = 14
    max_atr_pct = 0.008  # 0.8% max - skip if too volatile

    # ========== Spread Filter ==========
    max_spread_pct = 0.004  # 0.4% max spread (slippage protection)

    # ========== Risk Management ==========
    max_open_trades = 2
    trade_cooldown = 60  # seconds between trades on same pair
    daily_max_loss_pct = 0.015  # 1.5% daily loss limit
    max_drawdown_pct = 0.02  # 2% drawdown circuit breaker

    # ========== Exit Tags ==========
    exit_tag_time = "time_exit"
    exit_tag_trailing = "trailing_exit"

    # ========== Track States ==========
    trade_start_times = {}  # pair -> entry time
    daily_pnl = 0.0
    last_reset_date = None

    # ========== Indicators ==========
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ---- Bollinger Bands ----
        bbands = ta.BBANDS(
            dataframe, timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        dataframe["bb_upper"] = bbands["upperband"]
        dataframe["bb_middle"] = bbands["middleband"]
        dataframe["bb_lower"] = bbands["lowerband"]

        # ---- Wick Metrics ----
        body = abs(dataframe["close"] - dataframe["open"])
        dataframe["body"] = body

        upper_wick = dataframe["high"] - dataframe[["close", "open"]].max(axis=1)
        lower_wick = dataframe[["close", "open"]].min(axis=1) - dataframe["low"]

        dataframe["upper_wick"] = upper_wick
        dataframe["lower_wick"] = lower_wick

        # Wick/body ratio (for rejection strength)
        dataframe["wick_body_ratio"] = dataframe[["upper_wick", "lower_wick"]].max(
            axis=1
        ) / dataframe["body"].replace(0, np.nan)

        # Wick dominance (which side wins)
        dataframe["upper_dominates"] = upper_wick > lower_wick
        dataframe["lower_dominates"] = lower_wick > upper_wick

        # ---- Volume ----
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=self.volume_sma_period)
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_sma"].replace(0, np.nan)

        # ---- ATR ----
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # ---- Spread ----
        dataframe["spread"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]

        # ---- BB Position (%b) ----
        # 0 = at lower BB, 1 = at upper BB
        bb_range = dataframe["bb_upper"] - dataframe["bb_lower"]
        dataframe["bb_position"] = (dataframe["close"] - dataframe["bb_lower"]) / bb_range.replace(
            0, np.nan
        )

        return dataframe

    # ========== Entry Logic ==========
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ---- LONG: Price at lower BB + strong lower wick + volume ----
        # RELAXED conditions for 5m timeframe:
        # 1. Price near lower BB (bb_position <= 0.2, was 0.1)
        # 2. Lower wick > body (was > 2x body)
        # 3. Volume spike (volume_ratio >= 1.2, was 1.5)
        # 4. ATR filter (not too volatile)
        # 5. Spread filter (not too wide)
        # 6. Wick/body ratio >= 2.0 (was 3.0)

        cond_bb_lower = dataframe["bb_position"] <= 0.2  # Near lower BB (relaxed)
        cond_wick_reject = dataframe["lower_wick"] > dataframe["body"]  # Lower wick > body
        cond_wick_bull = dataframe["lower_dominates"]  # Lower wick wins
        cond_volume = dataframe["volume_ratio"] >= 1.2  # Relaxed from 1.5
        cond_atr = dataframe["atr_pct"] <= self.max_atr_pct
        cond_spread = dataframe["spread"] <= self.max_spread_pct
        cond_wick_ratio = dataframe["wick_body_ratio"] >= 2.0  # Relaxed from 3.0

        # All conditions must be true
        dataframe["enter_long"] = (
            cond_bb_lower
            & cond_wick_reject
            & cond_wick_bull
            & cond_volume
            & cond_atr
            & cond_spread
            & cond_wick_ratio
        ).astype(int)

        # ---- SHORT: Price at upper BB + strong upper wick + volume ----
        # Mirror of long conditions

        cond_bb_upper = dataframe["bb_position"] >= 0.8  # Near upper BB (relaxed from 0.9)
        cond_wick_reject_bear = dataframe["upper_wick"] > dataframe["body"]  # Upper wick > body
        cond_wick_bear = dataframe["upper_dominates"]  # Upper wick wins

        dataframe["enter_short"] = (
            cond_bb_upper
            & cond_wick_reject_bear
            & cond_wick_bear
            & cond_volume
            & cond_atr
            & cond_spread
            & cond_wick_ratio
        ).astype(int)

        return dataframe

    # ========== Exit Logic ==========
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No discrete exit signals - handled by custom_exit
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        """
        Exit logic:
        1. Time-based exit (5 min hard cap)
        2. Trailing stop (activates at +0.05%)
        """
        # ---- Time-based exit (5 minutes) ----
        if trade is not None and hasattr(trade, "open_date"):
            holding_seconds = (current_time - trade.open_date).total_seconds()
            if holding_seconds >= self.max_holding_seconds:
                return self.exit_tag_time

        # ---- Trailing stop is handled by Freqtrade ----
        # But we can add early profit take here
        if current_profit >= 0.0010:  # 0.10% take profit if fast move (<2 min)
            if trade is not None and hasattr(trade, "open_date"):
                holding_seconds = (current_time - trade.open_date).total_seconds()
                if holding_seconds < 120:  # < 2 minutes
                    return "fast_profit_take"

        return None

    # ========== Entry Confirmation (Filters) ==========
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

        # 1. ATR filter (not too volatile)
        atr_pct = last_candle["atr_pct"]
        if atr_pct > self.max_atr_pct:
            return False

        # 2. Spread filter (not too wide)
        spread_pct = last_candle["spread"]
        if spread_pct > self.max_spread_pct:
            return False

        # 3. Volume filter (must have participation)
        volume_ratio = last_candle["volume_ratio"]
        if volume_ratio < self.volume_ratio_min:
            return False

        # 4. Wick rejection must be present
        wick_body_ratio = last_candle.get("wick_body_ratio", 0)
        if wick_body_ratio < self.wick_body_ratio:
            return False

        return True

    # ========== Slippage Protection ==========
    @property
    def confirm_trade_entry_timeout(self) -> int:
        """Order timeout in seconds"""
        return 60

    # ========== Pair Lock (Cooldown) ==========
    def _get_pair_lock_time(self, pair: str) -> int:
        """Return cooldown in seconds for a pair"""
        return self.trade_cooldown

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
        """
        Return stop loss value relative to current rate.
        -0.0015 = -0.15% from entry
        """
        return self.stoploss

    # ========== Info Logging ==========
    def inform(
        self, pair: str, current_time, current_rate: float, current_profit: float, trade: "Trade"
    ):
        """Log trade info for debugging"""
        if trade is not None:
            holding = (current_time - trade.open_date).total_seconds()
            logger.info(
                f"[{pair}] Profit: {current_profit:.4f}, "
                f"Holding: {holding:.0f}s, "
                f"Entry: {trade.enter_rate:.6f}, "
                f"Current: {current_rate:.6f}"
            )
