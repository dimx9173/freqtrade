#!/usr/bin/env python3
"""
Hybrid_v3_tight_trail — Hybrid_v3 with tighter trailing stop parameters

Diagnosis (2026-06-06 1y backtest):
  - 93% trades are weak_trend (regime=1 transition)
  - WR 64.5% on 769 trades but avg_win 0.35% << avg_loss 2.76%
  - trailing stop is the loss source: 178 trades × -2.76% = -233.85 USDT
  - Original: trailing_stop_positive=0.107 (10.7% trigger), offset=0.12 (12% from peak)

Design hypothesis:
  - Tighter trailing stop will cut losses earlier, reducing avg_loss
  - Trade-off: may reduce avg_win too, but avg_loss reduction should dominate
  - Try: trigger 5% (half of 10.7%), offset 6% (half of 12%)

Backtest plan: 1y (2025-05-01 ~ 2026-05-24), 9 pairs (excl BTC), Hybrid_v3_tight_trail vs Hybrid_v3
"""
import logging

from Hybrid_v3 import Hybrid_v3

logger = logging.getLogger(__name__)


class Hybrid_v3_tight_trail(Hybrid_v3):
    """
    Hybrid_v3 with tighter trailing stop (5% trigger / 6% offset instead of 10.7% / 12%).

    Goal: cut avg_loss by triggering trailing stop earlier in 178 loss trades.
    Expected: avg_loss 2.76% → ~1.4%, with 64.5% WR preserved.
    """

    # Tighter trailing (vs parent 10.7% / 12%)
    # Original: trailing_stop_positive=0.107, trailing_stop_positive_offset=0.12
    # Tighter:  trigger 5% (half), offset 6% (half)
    trailing_stop_positive: float = 0.05      # 5% trigger (was 10.7%)
    trailing_stop_positive_offset: float = 0.06  # 6% from peak (was 12%)
    # Keep all other params from Hybrid_v3 (ROI, stoploss, regime thresholds, etc.)
