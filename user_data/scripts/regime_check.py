#!/usr/bin/env python3
"""
Market Regime Analyzer - CLI Tool
=================================
Quick command-line tool to check current market regime for any pair.

Usage:
    python3 regime_check.py                    # Check all 5 pairs
    python3 regime_check.py BTC               # Check specific pair
    python3 regime_check.py --live            # Show live regime with latest data

Author: Brian's Trading System
Date: 2026-04-28
"""

import pandas as pd
import numpy as np
import talib.abstract as ta
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Configuration
DATA_PATH = Path("/home/brian/freqtrade/user_data/data/bybit")
PAIRS = ["BTC", "ETH", "SOL", "XRP", "BNB"]
TIMEFRAME = "15m"

# Regime Detection Parameters
PARAMS = {
    "adx_period": 14,
    "adx_strong_threshold": 25,
    "adx_very_strong_threshold": 35,
    "bb_period": 20,
    "bb_std": 2.0,
    "bb_width_low": 0.01,
    "bb_width_high": 0.04,
    "ma_short": 20,
    "ma_medium": 50,
    "ma_long": 200,
    "atr_period": 14,
    "atr_vol_threshold": 1.2,
    "rsi_period": 14,
}


def detect_current_regime(df: pd.DataFrame) -> dict:
    """Detect current regime from latest candles"""
    if len(df) < 20:
        return {"regime": "UNKNOWN", "reason": "Insufficient data"}

    # Get latest data
    latest = df.iloc[-1]
    prev5 = df.tail(5)
    prev20 = df.tail(20)

    # Calculate values
    adx = latest["adx"]
    bb_width = latest["bb_width"]
    atr_ratio = latest["atr_ratio"]
    bb_position = latest["bb_position"]
    di_cross = latest["di_cross"]
    rsi = latest["rsi"]
    bb_width_roc = latest["bb_width_roc"]
    atr_roc = latest["atr_roc"]

    regime_scores = {"TREND": 0, "VOLATILE": 0, "BREAKOUT": 0}

    # BREAKOUT Detection
    if not pd.isna(bb_width_roc) and bb_width_roc > 0.15:
        regime_scores["BREAKOUT"] += 2
    if not pd.isna(atr_roc) and atr_roc > 0.1:
        regime_scores["BREAKOUT"] += 2
    if bb_position < 0.2 or bb_position > 0.8:
        regime_scores["BREAKOUT"] += 2
    if 20 <= adx <= 35 and regime_scores["BREAKOUT"] >= 2:
        regime_scores["BREAKOUT"] += 1

    # TREND Detection
    if adx >= 35:
        regime_scores["TREND"] += 3
    elif adx >= 25:
        regime_scores["TREND"] += 2
    if abs(di_cross) > 5:
        regime_scores["TREND"] += 2
    if abs(latest["price_to_ma_long"]) > 0.02:
        regime_scores["TREND"] += 1
    if 0.015 <= bb_width <= 0.04:
        regime_scores["TREND"] += 1

    # VOLATILE Detection (high volatility, no clear trend)
    if adx >= 20 and adx < 25:
        regime_scores["VOLATILE"] += 1
    if bb_width > 0.025:
        regime_scores["VOLATILE"] += 2
    if rsi < 40 or rsi > 60:
        regime_scores["VOLATILE"] += 2
    if abs(latest["price_to_ma_medium"]) < 0.01:
        regime_scores["VOLATILE"] += 1

    # Determine regime
    max_score = max(regime_scores.values())

    # Override: if ADX < 20, default to VOLATILE
    if adx < 20:
        detected_regime = "VOLATILE"
    elif regime_scores["BREAKOUT"] >= 4:
        detected_regime = "BREAKOUT"
    elif regime_scores["TREND"] >= 4 and adx >= 25:
        detected_regime = "TREND"
    else:
        detected_regime = "VOLATILE"

    return {
        "regime": detected_regime,
        "adx": round(adx, 2) if not pd.isna(adx) else None,
        "bb_width": round(bb_width, 4) if not pd.isna(bb_width) else None,
        "atr_ratio": round(atr_ratio, 2) if not pd.isna(atr_ratio) else None,
        "rsi": round(rsi, 2) if not pd.isna(rsi) else None,
        "di_cross": round(di_cross, 2) if not pd.isna(di_cross) else None,
        "scores": regime_scores,
        "bb_position": round(bb_position, 2) if not pd.isna(bb_position) else None,
    }


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all regime indicators"""
    df = df.copy()

    # ADX and Directional Indicators
    df["adx"] = ta.ADX(df, timeperiod=PARAMS["adx_period"])
    df["plus_di"] = ta.PLUS_DI(df, timeperiod=PARAMS["adx_period"])
    df["minus_di"] = ta.MINUS_DI(df, timeperiod=PARAMS["adx_period"])

    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = ta.BBANDS(
        df["close"],
        timeperiod=PARAMS["bb_period"],
        nbdevup=PARAMS["bb_std"],
        nbdevdn=PARAMS["bb_std"],
    )
    df["bb_upper"] = bb_upper
    df["bb_middle"] = bb_middle
    df["bb_lower"] = bb_lower
    df["bb_width"] = (bb_upper - bb_lower) / bb_middle

    # Moving Averages
    df["ma_short"] = ta.EMA(df, timeperiod=PARAMS["ma_short"])
    df["ma_medium"] = ta.EMA(df, timeperiod=PARAMS["ma_medium"])
    df["ma_long"] = ta.EMA(df, timeperiod=PARAMS["ma_long"])

    # Price position relative to MAs
    df["price_to_ma_short"] = (df["close"] - df["ma_short"]) / df["ma_short"]
    df["price_to_ma_medium"] = (df["close"] - df["ma_medium"]) / df["ma_medium"]
    df["price_to_ma_long"] = (df["close"] - df["ma_long"]) / df["ma_long"]

    # ATR and volatility
    df["atr"] = ta.ATR(df, timeperiod=PARAMS["atr_period"])
    df["atr_ma"] = df["atr"].rolling(window=20).mean()
    df["atr_ratio"] = df["atr"] / df["atr_ma"]

    # RSI
    df["rsi"] = ta.RSI(df, timeperiod=PARAMS["rsi_period"])

    # Bollinger Band Width rate of change
    df["bb_width_roc"] = df["bb_width"].pct_change(periods=10)
    df["bb_width_roc"] = df["bb_width_roc"].rolling(window=5).mean()

    # ATR rate of change
    df["atr_roc"] = df["atr"].pct_change(periods=10)
    df["atr_roc"] = df["atr_roc"].rolling(window=5).mean()

    # BB position
    df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    df["bb_position"] = df["bb_position"].fillna(0.5)

    # DI cross
    df["di_cross"] = df["plus_di"] - df["minus_di"]

    return df


def analyze_pair(pair: str, lookback_candles: int = 100) -> dict:
    """Analyze a single pair and return current regime info"""
    file_path = DATA_PATH / f"{pair}_USDT-{TIMEFRAME}.feather"

    if not file_path.exists():
        return {"error": f"{file_path} not found"}

    # Load data
    df = pd.read_feather(file_path)
    df["date"] = pd.to_datetime(df["date"])

    if len(df) < 50:
        return {"error": "Insufficient data"}

    # Calculate indicators
    df = calculate_indicators(df)

    # Get regime info
    latest_time = df["date"].iloc[-1]

    # Get last N candles for recent regime
    recent = df.tail(lookback_candles)
    regime_counts = (
        recent["regime_confirmed"].value_counts()
        if "regime_confirmed" in df.columns
        else {"UNKNOWN": lookback_candles}
    )

    # Get current regime
    current_regime = detect_current_regime(df)

    # Calculate historical distribution
    hist_regime = (
        df["regime_confirmed"].value_counts().to_dict() if "regime_confirmed" in df.columns else {}
    )

    return {
        "pair": pair,
        "latest_time": str(latest_time),
        "latest_price": df["close"].iloc[-1],
        "current_regime": current_regime["regime"],
        "adx": current_regime["adx"],
        "bb_width": current_regime["bb_width"],
        "atr_ratio": current_regime["atr_ratio"],
        "rsi": current_regime["rsi"],
        "di_cross": current_regime["di_cross"],
        "bb_position": current_regime["bb_position"],
        "scores": current_regime["scores"],
    }


def print_regime_table(results: list):
    """Print regime analysis in a nice table format"""
    # Header
    print()
    print(
        "╔══════════════════════════════════════════════════════════════════════════════════════════╗"
    )
    print(
        "║                         MARKET REGIME STATUS - 15m TIMEFRAME                            ║"
    )
    print(
        "╠════════════════╦════════╦════════╦════════╦════════╦════════╦════════╦════════════════╣"
    )
    print(
        "║     PAIR       ║ REGIME ║  ADX   ║ BB-W   ║ ATR    ║  RSI   ║ DI-Sep ║ Recommendation  ║"
    )
    print(
        "╠════════════════╬════════╬════════╬════════╬════════╬════════╬════════╬════════════════╣"
    )

    for r in results:
        if "error" in r:
            print(f"║ {r['pair']:12} ║  ERROR: {r['error'][:30]:30}                              ║")
            continue

        regime = r["current_regime"]
        adx = r["adx"] if r["adx"] else 0
        bb = r["bb_width"] if r["bb_width"] else 0
        atr = r["atr_ratio"] if r["atr_ratio"] else 0
        rsi = r["rsi"] if r["rsi"] else 50
        di = r["di_cross"] if r["di_cross"] else 0

        # Recommendation based on regime
        if regime == "TREND":
            rec = "Follow trend"
        elif regime == "BREAKOUT":
            rec = "Volatility play"
        else:
            rec = "Stay selective"

        # Regime emoji/indicator
        regime_icon = {"TREND": "📈", "VOLATILE": "📊", "BREAKOUT": "💥", "UNKNOWN": "❓"}.get(
            regime, "?"
        )

        print(
            f"║ {r['pair']:12} ║ {regime_icon} {regime:6} ║ {adx:6.1f} ║ {bb:.4f} ║ {atr:.2f}  ║ {rsi:6.1f} ║ {di:+6.1f} ║ {rec:16} ║"
        )

    print(
        "╚════════════════╩════════╩════════╩════════╩════════╩════════╩════════╩════════════════╝"
    )
    print()

    # Legend
    print("Legend:")
    print(
        "  REGIME: TREND=Strong directional move | VOLATILE=High波动/No clear trend | BREAKOUT=突破"
    )
    print("  ADX: >25 = Strong trend, <20 = No trend")
    print("  BB-W: Bollinger Band Width (volatility measure)")
    print("  ATR: Current/Avg ATR ratio (>1.0 = expanding)")
    print("  RSI: 30-70 normal range")
    print("  DI-Sep: +DI minus -DI (positive = bullish bias)")
    print()


def print_pair_detail(pair: str):
    """Print detailed info for a single pair"""
    result = analyze_pair(pair)

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print(f"\n{'=' * 60}")
    print(f"  {pair}/USDT - Market Regime Analysis")
    print(f"{'=' * 60}")
    print(f"  Latest Price:    {result['latest_price']:.2f}")
    print(f"  Latest Time:     {result['latest_time']}")
    print()
    print(f"  CURRENT REGIME: {result['current_regime']}")
    print(f"  ────────────────────────────────────────")
    print(
        f"  ADX (14):       {result['adx']:.2f}  {'(Strong trend)' if result['adx'] > 25 else '(Weak trend)'}"
    )
    print(
        f"  BB Width:       {result['bb_width']:.4f}  {'(High volatility)' if result['bb_width'] > 0.025 else '(Low volatility)'}"
    )
    print(
        f"  ATR Ratio:      {result['atr_ratio']:.2f}  {'(Expanding)' if result['atr_ratio'] > 1.0 else '(Contracting)'}"
    )
    print(f"  RSI (14):       {result['rsi']:.2f}")
    print(
        f"  DI Separation:  {result['di_cross']:+.2f}  {'(Bullish)' if result['di_cross'] > 0 else '(Bearish)'}"
    )
    print(
        f"  BB Position:    {result['bb_position']:.2f}  {'(Near upper band)' if result['bb_position'] > 0.8 else '(Near lower band)' if result['bb_position'] < 0.2 else '(Middle)'}"
    )
    print()
    print(
        f"  Regime Scores: TREND={result['scores']['TREND']}, VOLATILE={result['scores']['VOLATILE']}, BREAKOUT={result['scores']['BREAKOUT']}"
    )
    print()

    # Strategy recommendations
    regime = result["current_regime"]
    print(f"  STRATEGY RECOMMENDATION:")
    if regime == "TREND":
        print("  ├─ Preferred: Trend-following entries on pullbacks")
        print("  ├─ Use wider stops, trail profits")
        print("  ├─ PSV1_ATR_Filter: Should perform well")
        print("  └─ Consider higher position size")
    elif regime == "BREAKOUT":
        print("  ├─ Preferred: Volatility breakouts")
        print("  ├─ Quick entries, wide stops")
        print("  ├─ PSV1_ATR_Filter: Excellent fit (ATR filter aligns)")
        print("  └─ Can use higher leverage")
    elif regime == "VOLATILE":
        print("  ├─ Preferred: Mean reversion, range trading")
        print("  ├─ Tight stops, shorter targets")
        print("  ├─ PSV1_ATR_Filter: Be selective, increase ATR threshold")
        print("  └─ Reduce position size")
    print()


def main():
    """Main CLI entry point"""
    print()
    print("=" * 70)
    print("  MARKET REGIME ANALYZER - 15m Timeframe")
    print("=" * 70)

    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print(__doc__)
            return

        # Analyze specific pair
        pair = sys.argv[1].upper()
        if pair in PAIRS or pair == "BTCUSDT":
            pair = pair.replace("USDT", "").replace("_", "")
            print_pair_detail(pair)
        else:
            print(f"Unknown pair: {pair}")
            print(f"Available: {', '.join(PAIRS)}")
        return

    # Analyze all pairs
    results = []
    for pair in PAIRS:
        result = analyze_pair(pair)
        results.append(result)

    print_regime_table(results)

    # Quick summary
    regime_summary = {}
    for r in results:
        if "error" not in r:
            regime = r["current_regime"]
            regime_summary[regime] = regime_summary.get(regime, 0) + 1

    print("Quick Summary:")
    for regime, count in sorted(regime_summary.items()):
        print(f"  {regime}: {count}/5 pairs")


if __name__ == "__main__":
    main()
