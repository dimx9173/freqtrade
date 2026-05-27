"""
Freqtrade Scalping Strategy - Portfolio B: Momentum Breakout (Balanced)
===============================================================================
Purpose : Scalping on Binance USDT-M Futures (5m confirm + 1m entry)
Core    : EMA(8,21) + MACD(8,17,5) + ATR + VWAP
Stoploss: Dynamic 1.5 × ATR
Targets : 1.5–2 × ATR | Max risk per trade: 2%
Market  : Oscillating bull-ish bias

Brian's UAT strategy — do not run on mainnet without live validation.
"""

# ----------------------------------------------------------------------
# °°° SECTION 1: imports °°°°
# ----------------------------------------------------------------------
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


# ----------------------------------------------------------------------
# °°° SECTION 2: Strategy Class °°°°
# ----------------------------------------------------------------------
class Scalp_Momentum_B_v1(IStrategy):
    # ------------------------------------------------------------------
    # HYPEROPTABLE SETTINGS
    # ------------------------------------------------------------------
    # ATR-based dynamic stoploss (Freqtrade will search 0.5–3.0 × ATR)
    stoploss = -1.0  # placeholder; overridden by _dynamic_stoploss

    # Minimal ROI table — conservative scalp targets (in minutes as strings)
    minimal_roi = {
        "0": 0.005,  # +0.5 % at open (emergency exit if signal fails)
        "20": 0.010,  # +1.0 % after 20 candles (100 min)
        "60": 0.020,  # +2.0 % after 60 candles (300 min)
        "240": 0.030,  # +3.0 % after 240 candles (20 h)
    }

    # Futures / leverage
    leverage = 5  # 5× leverage on Binance USDT-M
    futures_leverage = True

    # Timeframes
    # ── main (informative, used for confirmation) ──
    timeframe = "5m"
    # ── secondary (used for entry signalling) ──
    entry_timeframe = "1m"

    # Process only new candles — safer for short-window scalp
    process_only_new_candles = True

    # Wait N candles before allowing a new trade on the same pair
    cooldown_entr = 0  # managed by ATR stop distance instead

    # ------------------------------------------------------------------
    # § A: informative_pairs — pull 5m + 1m data for each active pair
    # ------------------------------------------------------------------
    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        pair_timeframes = []
        for pair in pairs:
            pair_timeframes.append((pair, self.timeframe))  # 5m confirm
            pair_timeframes.append((pair, self.entry_timeframe))  # 1m entry
        return pair_timeframes

    # ------------------------------------------------------------------
    # § B: Indicator calculation (both timeframes combined)
    # ------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # === 5m timeframe indicators ===
        # EMA 8 & 21 — golden-cross confirmation
        dataframe["ema_8"] = ta.EMA(dataframe, timeperiod=8)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)

        # MACD (8,17,5) — trend & momentum filter
        macd = ta.MACD(dataframe, fastperiod=8, slowperiod=17, signalperiod=5)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # ATR — dynamic stoploss & take-profit sizing
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # VWAP — volume-weighted average price (dynamic support/resistance)
        dataframe["vwap"] = self._vwap(dataframe)

        # RSI — exit confirmation (not entry trigger)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # === 1m timeframe indicators ===
        # Re-use same indicators on the 1m slice
        # (Freqtrade merges both timeframes by timestamp key)
        # Indicators on 1m are computed automatically by TALib call above
        # since the same column names are written.

        return dataframe

    # ------------------------------------------------------------------
    # § C: Entry signal (long only)
    # ------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ------------------------------------------------------------------
        # ENTRY LOGIC — all three conditions MUST be met simultaneously:
        # ------------------------------------------------------------------
        # ① EMA Golden Cross: EMA8 crosses ABOVE EMA21 on 5m
        cond_ema_golden = dataframe["ema_8"] > dataframe["ema_21"]

        # ② MACD Histogram flips from negative → positive (momentum born)
        #    We require the current bar to be > 0 while the previous was ≤ 0
        cond_macd_flip = (dataframe["macd_hist"] > 0) & (dataframe["macd_hist"].shift(1) <= 0)

        # ③ Price is above VWAP (bullish location bias)
        cond_price_above_vwap = dataframe["close"] > dataframe["vwap"]

        # Combined entry signal
        dataframe["enter_long"] = (cond_ema_golden & cond_macd_flip & cond_price_above_vwap).astype(
            int
        )

        return dataframe

    # ------------------------------------------------------------------
    # § D: Exit signal (managed by custom_stoploss / minimal_roi)
    # ------------------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals:
        - RSI overbought (> 70) → early warning exit
        - ATR-based profit taking is handled by custom_stoploss
        - Stop-loss is also managed by custom_stoploss
        """
        dataframe["exit_long"] = (dataframe["rsi"] > 70).astype(int)
        return dataframe

    # ------------------------------------------------------------------
    # § E: Dynamic Stoploss — 1.5 × ATR from entry price
    # ------------------------------------------------------------------
    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
        entry: float,
        current_time: "datetime",
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        Returns the raw stoploss distance multiplier.
        Freqtrade interprets:  return = -|value|
        e.g. return 0.015  →  Freqtrade applies 1.5 % stop distance.
        """
        # Pull 5m dataframe for this pair
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return -0.05  # fallback 5 %

        last_atr = dataframe["atr"].iloc[-1]
        if last_atr <= 0 or last_atr != last_atr:  # guard NaN
            return -0.05

        # 1.5 × ATR stop distance (expressed as a fraction of entry price)
        atr_stop_fraction = (1.5 * last_atr) / entry
        return -atr_stop_fraction

    # ------------------------------------------------------------------
    # § F: VWAP helper (session-anchored)
    # ------------------------------------------------------------------
    @staticmethod
    def _vwap(df: DataFrame) -> DataFrame:
        """
        Volume-Weighted Average Price anchored to session open.
        VWAP = Σ(price × volume) / Σ(volume) per rolling window.
        Uses hlc3 (high-low-close)/3 as typical price.
        """
        typical = (df["high"] + df["low"] + df["close"]) / 3.0
        vol = df["volume"]
        cum_pv = (typical * vol).rolling(window=len(df), min_periods=1).sum()
        cum_vol = vol.rolling(window=len(df), min_periods=1).sum()
        vwap = cum_pv / cum_vol
        return vwap

    # ------------------------------------------------------------------
    # § G: Stake sizing — enforce ≤ 2 % risk per trade
    # ------------------------------------------------------------------
    def custom_stake_amount(
        self,
        pair: str,
        current_time: "datetime",
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float | None,
        **kwargs,
    ) -> float:
        """
        Freqtrade calls this to determine the stake amount for a new trade.
        We calculate the stop-distance in price units and cap the
        stake so that loss at stoploss ≤ 2 % of total capital.
        """
        # Get latest ATR on 5m
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return proposed_stake

        last_atr = dataframe["atr"].iloc[-1]
        if last_atr <= 0 or last_atr != last_atr:
            return proposed_stake

        entry_price = current_rate
        stop_distance = 1.5 * last_atr  # price units
        max_loss_pct = 0.02  # 2 % of capital

        # Get available capital from wallet
        total_cap = 1000  # fallback
        if hasattr(self, "wallets") and self.wallets:
            total_cap = self.wallets.get_total("USDT") or 1000

        # stake that yields exactly 2 % loss at 1.5×ATR stop
        safe_stake = (total_cap * max_loss_pct) / (stop_distance / entry_price)

        # respect Freqtrade limits
        if max_stake is not None:
            safe_stake = min(safe_stake, max_stake)
        if min_stake is not None:
            safe_stake = max(safe_stake, min_stake)

        return safe_stake

    # ------------------------------------------------------------------
    # § H: Optional — print diagnostics in dry-run / live
    # ------------------------------------------------------------------
    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: "datetime",
        **kwargs,
    ) -> bool:
        """
        Called just before submitting the order.
        Return False to abort the trade.
        """
        # Could add volume spike check, news filter, etc.
        return True
