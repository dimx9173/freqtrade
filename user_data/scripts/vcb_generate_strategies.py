#!/usr/bin/env python3
"""
VCB Grid Search - Strategy File Generator
Generates individual strategy files for all parameter combinations.
"""

import itertools
import os

# Grid parameters
ATR_VALUES = [0.25, 0.30, 0.35, 0.40]
VRANK_VALUES = [0.05, 0.10, 0.15, 0.20]
TP_VALUES = [0.03, 0.04, 0.05, 0.06, 0.08]
SL_VALUES = [0.005, 0.008, 0.010, 0.015]


def format_strategy_name(atr, vrank, tp, sl):
    """Generate strategy name from parameters."""
    return f"VCB_grid_1h_A{int(atr * 100)}_V{int(vrank * 100)}_TP{int(tp * 100)}_SL{int(sl * 1000)}"


STRATEGY_TEMPLATE = '''"""
{strategy_name} - Grid Search Parameter Set
======================================================================
ATR threshold: {atr}
Vrank threshold: {vrank}
TP: {tp}%
SL: {sl}%
"""

import talib.abstract as ta
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from typing import Optional


class {strategy_class}(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"

    can_short = False
    can_long = True

    stoploss = -{sl_pct}
    minimal_roi = {{"0": {tp_pct}, "1440": 0.01}}
    max_exit_age = 24
    exit_profit_only = False
    use_exit_signal = True
    trailing_stop = False
    trailing_stop_positive = 0.0
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False
    startup_candle_count = 200
    process_only_new_candles = False

    atr_compression_threshold = {atr}
    vrank_threshold = {vrank}
    atr_period = 14
    atr_ma_period = 200
    vrank_period = 48

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["atr_pct"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"] * 100.0
        dataframe["atr_pct_ma"] = dataframe["atr_pct"].rolling(window=self.atr_ma_period).mean()
        dataframe["vrank"] = (
            dataframe["volume"]
            .rolling(window=self.vrank_period)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        )
        dataframe["atr_filter"] = (
            dataframe["atr_pct"] < dataframe["atr_pct_ma"] * self.atr_compression_threshold
        )
        dataframe["vrank_filter"] = dataframe["vrank"] < self.vrank_threshold
        dataframe["vcb_entry"] = dataframe["atr_filter"] & dataframe["vrank_filter"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["vcb_entry"], "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["force_exit"] = 0
        return dataframe

    def leverage(
        self, pair: str, current_time: "datetime", current_rate: float,
        proposed_leverage: float, max_leverage: float, entry_tag: str,
        side: str, **kwargs
    ) -> float:
        return 2.0
'''


def generate_strategies():
    """Generate all strategy files."""
    output_dir = "/home/brian/freqtrade/user_data/strategies/test"

    count = 0
    for atr, vrank, tp, sl in itertools.product(ATR_VALUES, VRANK_VALUES, TP_VALUES, SL_VALUES):
        # Use same format for both file name and class name
        name = format_strategy_name(atr, vrank, tp, sl)

        content = STRATEGY_TEMPLATE.format(
            strategy_name=name,
            strategy_class=name,  # Same as filename
            atr=atr,
            vrank=vrank,
            tp=tp,
            sl=sl,
            tp_pct=tp / 100.0,
            sl_pct=sl / 100.0,
        )

        filepath = os.path.join(output_dir, f"{name}.py")
        with open(filepath, "w") as f:
            f.write(content)
        count += 1

    print(f"Generated {count} strategy files")


if __name__ == "__main__":
    generate_strategies()
