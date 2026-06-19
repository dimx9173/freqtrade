# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib
import datetime
from technical.util import resample_to_interval, resampled_merge
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    stoploss_from_open,
    merge_informative_pair,
    DecimalParameter,
    IntParameter,
    CategoricalParameter,
)
import technical.indicators as ftt


def EWO(dataframe, ema_length=5, ema2_length=35):
    df = dataframe.copy()
    ema1 = ta.EMA(df, timeperiod=ema_length)
    ema2 = ta.EMA(df, timeperiod=ema2_length)
    emadif = (ema1 - ema2) / df["close"] * 100
    return emadif


class SMAOffsetProtectOptV1(IStrategy):
    INTERFACE_VERSION = 3

    # Buy hyperspace params:
    buy_params = {
        "base_nb_candles_buy": 13,
        "ewo_high": 5.835,
        "ewo_low": -19.909,
        "low_offset": 0.978,
        "rsi_buy": 55,
    }
    # Sell hyperspace params:
    sell_params = {
        "base_nb_candles_sell": 18,
        "high_offset": 1.012,
        "pHSL": -0.08,
        "pPF_1": 0.016,
        "pPF_2": 0.080,
        "pSL_1": 0.011,
        "pSL_2": 0.040,
    }

    # and disable roi:
    # ROI table:
    minimal_roi = {"0": 100.0}

    # Stoploss:
    stoploss = -0.1  # stop loss 10%

    protections = [
        # 	{
        # 		"method": "StoplossGuard",
        # 		"lookback_period_candles": 12,
        # 		"trade_limit": 1,
        # 		"stop_duration_candles": 6,
        # 		"only_per_pair": True
        # 	},
        # 	{
        # 		"method": "StoplossGuard",
        # 		"lookback_period_candles": 12,
        # 		"trade_limit": 2,
        # 		"stop_duration_candles": 6,
        # 		"only_per_pair": False
        # 	},
        {
            "method": "LowProfitPairs",
            "lookback_period_candles": 60,
            "trade_limit": 1,
            "stop_duration": 60,
            "required_profit": -0.05,
        },
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
    ]

    # SMAOffset
    base_nb_candles_buy = IntParameter(
        5, 80, default=buy_params["base_nb_candles_buy"], space="buy", optimize=True
    )
    base_nb_candles_sell = IntParameter(
        5, 80, default=sell_params["base_nb_candles_sell"], space="sell", optimize=True
    )
    low_offset = DecimalParameter(
        0.9, 0.99, default=buy_params["low_offset"], space="buy", optimize=True
    )
    high_offset = DecimalParameter(
        0.99, 1.1, default=sell_params["high_offset"], space="sell", optimize=True
    )

    # Protection
    fast_ewo = 50
    slow_ewo = 200
    ewo_low = DecimalParameter(
        -20.0, -8.0, default=buy_params["ewo_low"], space="buy", optimize=True
    )
    ewo_high = DecimalParameter(
        2.0, 12.0, default=buy_params["ewo_high"], space="buy", optimize=True
    )
    rsi_buy = IntParameter(30, 70, default=buy_params["rsi_buy"], space="buy", optimize=True)

    # Trailing stop:
    trailing_stop = False
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True

    # Sell signal
    use_exit_signal = True
    sell_profit_only = False
    sell_profit_offset = 0.01
    ignore_roi_if_buy_signal = True

    # Optimal timeframe for the strategy
    timeframe = "5m"
    informative_timeframe = "1h"

    process_only_new_candles = True
    startup_candle_count = 30

    plot_config = {
        "main_plot": {
            "ma_buy": {"color": "orange"},
            "ma_sell": {"color": "orange"},
        },
    }

    # Custom stoploss
    use_custom_stoploss = True
    # [Custom stoploss] hard stoploss profit
    pHSL = DecimalParameter(
        -0.100, -0.030, default=-0.08, decimals=3, space="sell", load=True
    )  # hard stop loss 8%
    # [Custom stoploss] profit threshold 1, trigger point, SL_1 is used
    pPF_1 = DecimalParameter(0.008, 0.020, default=0.016, decimals=3, space="sell", load=True)
    pSL_1 = DecimalParameter(0.008, 0.020, default=0.011, decimals=3, space="sell", load=True)

    # [Custom stoploss] profit threshold 2, SL_2 is used
    pPF_2 = DecimalParameter(0.040, 0.100, default=0.080, decimals=3, space="sell", load=True)
    pSL_2 = DecimalParameter(0.020, 0.070, default=0.040, decimals=3, space="sell", load=True)

    def informative_pairs(self):

        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.informative_timeframe) for pair in pairs]

        return informative_pairs

    def get_informative_indicators(self, metadata: dict):

        dataframe = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe=self.informative_timeframe
        )

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        if self.config["runmode"].value == "hyperopt":
            # Calculate all ma_buy values
            for val in self.base_nb_candles_buy.range:
                dataframe[f"ma_{val}"] = ta.EMA(dataframe, timeperiod=val)
        else:
            dataframe[f"ma_{self.base_nb_candles_buy.value}"] = ta.EMA(
                dataframe, timeperiod=self.base_nb_candles_buy.value
            )
            dataframe[f"ma_{self.base_nb_candles_sell.value}"] = ta.EMA(
                dataframe, timeperiod=self.base_nb_candles_sell.value
            )

        # Elliot
        dataframe["EWO"] = EWO(dataframe, self.fast_ewo, self.slow_ewo)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append(
            (
                (
                    dataframe["close"]
                    < (dataframe[f"ma_{self.base_nb_candles_buy.value}"] * self.low_offset.value)
                )
                & (dataframe["EWO"] > self.ewo_high.value)
                & (dataframe["rsi"] < self.rsi_buy.value)
                & (dataframe["volume"] > 0)
            )
        )

        conditions.append(
            (
                (
                    dataframe["close"]
                    < (dataframe[f"ma_{self.base_nb_candles_buy.value}"] * self.low_offset.value)
                )
                & (dataframe["EWO"] < self.ewo_low.value)
                & (dataframe["volume"] > 0)
            )
        )

        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        conditions.append(
            (
                (
                    dataframe["close"]
                    > (dataframe[f"ma_{self.base_nb_candles_sell.value}"] * self.high_offset.value)
                )
                & (dataframe["volume"] > 0)
            )
        )

        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), "exit_long"] = 1

        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:

        # hard stoploss profit
        HSL = self.pHSL.value
        PF_1 = self.pPF_1.value
        SL_1 = self.pSL_1.value
        PF_2 = self.pPF_2.value
        SL_2 = self.pSL_2.value

        # For profits between PF_1 and PF_2 the stoploss (sl_profit) used is linearly interpolated
        # between the values of SL_1 and SL_2. For all profits above PL_2 the sl_profit value
        # rises linearly with current profit, for profits below PF_1 the hard stoploss profit is used.

        if current_profit > PF_2:
            sl_profit = SL_2 + (current_profit - PF_2)
        elif current_profit > PF_1:
            sl_profit = SL_1 + ((current_profit - PF_1) * (SL_2 - SL_1) / (PF_2 - PF_1))
        else:
            sl_profit = HSL

        # Only for hyperopt invalid return
        if sl_profit >= current_profit:
            return -0.99

        return stoploss_from_open(sl_profit, current_profit)
