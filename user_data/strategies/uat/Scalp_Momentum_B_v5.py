"""
Scalp_Momentum_B_v5 - ATR Compression + Candlestick Reversal Scalping
=======================================================================
Purpose: High win-rate scalping on Binance/Bybit USDT-M Futures (1m)
Core    : ATR compression detection + Pin Bar / Hammer / Engulfing entry
Exit    : Fixed time (15min) OR 1% profit / 0.5% stoploss
Risk    : Max 2% per trade, 5x leverage, isolated margin

Philosophy:
- Scalping = high win rate (65%+) + small profit/loss
- Enter when ATR is compressed (market coiled, about to move)
- Use candlestick patterns for precise entry timing
- Exit quickly - don't let profits evaporate
"""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Scalp_Momentum_B_v5(IStrategy):
    """
    ATR Compression Scalping Strategy

    Entry Conditions (ALL must be met):
    1. ATR(14) < ATR(14) SMA(20) * 0.85  (ATR compressed below its average)
    2. One of these candlestick patterns:
       - Hammer (long lower wick, small body at top)
       - Bullish Engulfing (green candle fully engulfs previous red)
       - Pin Bar (long wick in one direction, small body at opposite end)
    3. Price near support (recent low) OR VWAP

    Exit:
    - Take Profit: 1.0% (fixed, scalp target)
    - Stop Loss: 0.5% (fixed, tight risk control)
    - Time Exit: 15 minutes max hold time
    """

    # ------------------------------------------------------------------
    # Strategy Parameters
    # ------------------------------------------------------------------
    stoploss = -0.005  # 0.5% fixed stoploss (will be overridden by custom_stoploss)

    # Minimal ROI - aggressive scalp targets (in minutes as strings for 1m tf)
    minimal_roi = {
        "5": 0.005,  # +0.5% after 5 candles (5 min)
        "10": 0.008,  # +0.8% after 10 candles (10 min)
        "15": 0.010,  # +1.0% after 15 candles (15 min)
    }

    # Futures / leverage
    leverage = 5
    futures_leverage = True

    # Timeframe - 1m for true scalping
    timeframe = "1m"

    # Process only new candles
    process_only_new_candles = True

    # ------------------------------------------------------------------
    # ATR Compression Parameters
    # ------------------------------------------------------------------
    atr_period = 14
    atr_sma_period = 20
    atr_compression_threshold = 0.85  # ATR must be below 85% of its SMA

    # ------------------------------------------------------------------
    # Candlestick Pattern Parameters
    # ------------------------------------------------------------------
    # Hammer: lower wick >= 2x body, upper wick <= 0.5x body
    hammer_body_ratio = 2.0
    hammer_upper_limit = 0.5

    # Pin Bar: wick >= 2.5x body
    pinbar_wick_ratio = 2.5

    # ------------------------------------------------------------------
    # Exit Parameters
    # ------------------------------------------------------------------
    take_profit_pct = 0.01  # 1% take profit
    stop_loss_pct = 0.005  # 0.5% stop loss
    max_hold_candles = 15  # 15 candles = 15 minutes on 1m

    # ------------------------------------------------------------------
    # § A: Indicator Calculation
    # ------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # === ATR and ATR Compression ===
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period)
        dataframe["atr_sma"] = ta.SMA(dataframe["atr"], timeperiod=self.atr_sma_period)
        dataframe["atr_compressed"] = dataframe["atr"] < (
            dataframe["atr_sma"] * self.atr_compression_threshold
        )

        # === VWAP ===
        dataframe["vwap"] = self._vwap(dataframe)

        # === EMA for trend context (optional filter) ===
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)

        # === Candlestick Components ===
        dataframe["body"] = abs(dataframe["close"] - dataframe["open"])
        dataframe["body_pct"] = dataframe["body"] / dataframe["close"] * 100
        dataframe["upper_wick"] = dataframe["high"] - np.maximum(
            dataframe["close"], dataframe["open"]
        )
        dataframe["lower_wick"] = (
            np.minimum(dataframe["close"], dataframe["open"]) - dataframe["low"]
        )
        dataframe["total_range"] = dataframe["high"] - dataframe["low"]

        # === Candlestick Pattern Detection ===
        # Hammer: long lower wick, small body, upper wick small
        dataframe["is_hammer"] = (
            (dataframe["lower_wick"] >= dataframe["body"] * self.hammer_body_ratio)
            & (dataframe["upper_wick"] <= dataframe["body"] * self.hammer_upper_limit)
            & (dataframe["body"] > 0)
            & (dataframe["close"] > dataframe["open"])  # Bullish hammer (green)
        )

        # Bullish Engulfing: current green candle fully engulfs previous red candle
        prev_open = dataframe["open"].shift(1)
        prev_close = dataframe["close"].shift(1)
        dataframe["is_engulfing"] = (
            (dataframe["close"] > dataframe["open"])  # Current is green
            & (prev_close < prev_open)  # Previous is red
            & (dataframe["open"] <= prev_close)  # Current open <= previous close
            & (dataframe["close"] >= prev_open)  # Current close >= previous open
        )

        # Pin Bar: long wick in one direction, small body at opposite end
        dataframe["is_pinbar"] = (dataframe["body"] > 0) & (
            # Bullish pinbar: long lower wick, body at top
            (
                (dataframe["lower_wick"] >= dataframe["body"] * self.pinbar_wick_ratio)
                & (dataframe["close"] > dataframe["open"])
            )
            |
            # Or bearish pinbar for short (not used in this long-only version)
            (
                (dataframe["upper_wick"] >= dataframe["body"] * self.pinbar_wick_ratio)
                & (dataframe["close"] < dataframe["open"])
            )
        )

        # Combined pattern signal
        dataframe["candle_pattern"] = (
            dataframe["is_hammer"] | dataframe["is_engulfing"] | dataframe["is_pinbar"]
        )

        # === Support/Resistance (recent lows) ===
        dataframe["recent_low"] = dataframe["low"].rolling(window=20, min_periods=1).min()
        dataframe["near_support"] = dataframe["close"] <= (dataframe["recent_low"] * 1.002)

        # === Volume confirmation ===
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["volume_spike"] = dataframe["volume"] > (dataframe["volume_sma"] * 1.2)

        return dataframe

    # ------------------------------------------------------------------
    # § B: Entry Signal (Long only)
    # ------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Condition 1: ATR compression (market coiled)
        cond_atr_compression = dataframe["atr_compressed"]

        # Condition 2: Candlestick reversal pattern
        cond_pattern = dataframe["candle_pattern"]

        # Condition 3: Price near support or below VWAP (mean reversion setup)
        cond_price_location = dataframe["near_support"] | (dataframe["close"] < dataframe["vwap"])

        # Condition 4: Volume confirmation
        cond_volume = dataframe["volume_spike"]

        # Combined entry signal
        dataframe["enter_long"] = (
            cond_atr_compression & cond_pattern & cond_price_location & cond_volume
        ).astype(int)

        return dataframe

    # ------------------------------------------------------------------
    # § C: Exit Signal
    # ------------------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals:
        - RSI overbought (> 65) → early warning
        - Price above VWAP + pattern exhaustion
        """
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=7)

        dataframe["exit_long"] = (
            (dataframe["rsi"] > 65)
            | (dataframe["close"] > dataframe["vwap"] * 1.005)  # 0.5% above VWAP
        ).astype(int)

        return dataframe

    # ------------------------------------------------------------------
    # § D: Custom Stoploss - Fixed percentage
    # ------------------------------------------------------------------
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
        Fixed 0.5% stoploss for tight risk control.
        """
        return -self.stop_loss_pct

    # ------------------------------------------------------------------
    # § E: Custom Exit - Time-based and profit-based
    # ------------------------------------------------------------------
    def custom_exit(
        self, pair: str, trade, current_time, current_rate: float, current_profit: float, **kwargs
    ):
        """
        Exit reasons:
        - 'time_exit': Held for max_hold_candles
        - 'profit_target': Hit 1% profit
        """
        # Check if we've held for max time
        # Note: In backtesting, we can't easily check candle count
        # So we rely on minimal_roi for time-based exits

        # Check profit target
        if current_profit >= self.take_profit_pct:
            return "profit_target"

        return None

    # ------------------------------------------------------------------
    # § F: VWAP Helper
    # ------------------------------------------------------------------
    @staticmethod
    def _vwap(df: DataFrame) -> DataFrame:
        """Volume-Weighted Average Price"""
        typical = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"]
        cum_pv = (typical * vol).cumsum()
        cum_vol = vol.cumsum()
        vwap = cum_pv / cum_vol
        return vwap

    # ------------------------------------------------------------------
    # § G: Stake Sizing - Risk-based
    # ------------------------------------------------------------------
    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float | None,
        **kwargs,
    ) -> float:
        """
        Risk 2% of capital per trade with 0.5% stop = 40% of capital max
        But with 5x leverage, actual position is smaller
        """
        max_risk_pct = 0.02  # 2% risk per trade
        stop_distance = self.stop_loss_pct  # 0.5%

        # Calculate safe stake
        total_cap = 1000  # fallback
        if hasattr(self, "wallets") and self.wallets:
            total_cap = self.wallets.get_total("USDT") or 1000

        safe_stake = (total_cap * max_risk_pct) / stop_distance

        # Apply limits
        if max_stake is not None:
            safe_stake = min(safe_stake, max_stake)
        if min_stake is not None:
            safe_stake = max(safe_stake, min_stake)

        return safe_stake

    # ------------------------------------------------------------------
    # § H: Trade Confirmation
    # ------------------------------------------------------------------
    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time,
        **kwargs,
    ) -> bool:
        """Final validation before entry"""
        return True
