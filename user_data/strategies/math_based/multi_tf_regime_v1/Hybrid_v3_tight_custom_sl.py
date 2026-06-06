#!/usr/bin/env python3
"""
Hybrid_v3_tight_custom_sl — Hybrid_v3 with TIGHTER custom_stoploss profit protection

Diagnosis (2026-06-06 1y backtest):
  - 178 trades exit with "trailing_stop_loss" but these are custom_stoploss triggers
  - max gain only 1-3% (never reached 5% trailing trigger)
  - custom_stoploss profit protection tiers (1.5% / 3% / 5%) trigger too late
  - avg loss -2.76% on these 178 trades

Hypothesis: tighter custom_stoploss will cut losses earlier
  - Old: profit ≥ 1.5% → -1.5% (protect 1.5%); profit ≥ 3% → +1% (lock 1%); profit ≥ 5% → +2% (lock 2%)
  - New: profit ≥ 0.5% → -0.5%; profit ≥ 1.5% → +0.5%; profit ≥ 3% → +1.5%

Expected: 178 trades avg_loss -2.76% → -1.4%
"""
import logging

from Hybrid_v3 import Hybrid_v3

logger = logging.getLogger(__name__)


class Hybrid_v3_tight_custom_sl(Hybrid_v3):
    """
    Hybrid_v3 with tighter custom_stoploss profit-protection tiers.

    Goal: protect profit earlier so avg_loss on 178 exit-by-stop trades drops.
    Trade-off: smaller avg_win (cuts winners earlier), but should net positive.
    """

    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float | None:
        # Keep parent class's -5% hard stop and floating zone unchanged
        if current_profit < -0.05:
            return -0.05  # 5% hard stop (unchanged)
        elif current_profit < 0:
            return -0.99  # let price float, no hard stop (unchanged)

        # NEW: Tighter profit protection tiers (was 1.5% / 3% / 5%)
        if current_profit >= 0.03:
            return +0.015   # lock 1.5% profit (was +0.01 = 1%)
        if current_profit >= 0.015:
            return +0.005   # lock 0.5% profit (was -0.015 = protect half)
        if current_profit >= 0.005:
            return -0.005   # allow up to -0.5% (was -0.05 = -5% from entry)

        # Default: allow up to -5% below entry for small profits
        return -0.05
