#!/usr/bin/env python3
"""
parse_regime_results.py — 通用 regime results parser
Usage: python parse_regime_results.py <REGIME_DIR> <REGIME_NAME> <TIMERANGE> [OUTPUT_JSON]
"""

import json
import re
import sys
from pathlib import Path

STRATEGIES = [
    "BB_RPB_TSL_BI",
    "ElliotV5_SMA_ninja",
    "NASOSv4",
    "NASOSv5_mod3",
    "SMAOffsetProtectOptV1",
]

METRIC_PATTERNS = {
    "trades": r"Total/Daily Avg Trades\s*│\s*(\d+)\s*/\s*([\d.]+)",
    "starting": r"Starting balance\s*│\s*([\d.]+) USDT",
    "final": r"Final balance\s*│\s*([\d.]+) USDT",
    "profit_usdt": r"Absolute profit\s*│\s*(-?[\d.]+) USDT",
    "profit_pct": r"Total profit %\s*│\s*(-?[\d.]+)%",
    "cagr": r"CAGR %\s*│\s*(-?[\d.]+)%",
    "sortino": r"Sortino\s*│\s*(-?[\d.]+)",
    "sharpe": r"Sharpe\s*│\s*(-?[\d.]+)",
    "calmar": r"Calmar\s*│\s*(-?[\d.]+)",
    "sqn": r"SQN\s*│\s*(-?[\d.]+)",
    "profit_factor": r"Profit factor\s*│\s*(-?[\d.]+)",
    "expectancy": r"Expectancy \(Ratio\)\s*│\s*(-?[\d.]+)\s*\((-?[\d.]+)\)",
    "max_open": r"Max open trades\s*│\s*(\d+)",
    "win_pct": r"Win\s+Draw\s+Loss\s+Win%\s*│\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)",
    "dd_abs": r"Absolute drawdown\s*│\s*(-?[\d.]+) USDT\s*\((-?[\d.]+)%\)",
    "dd_dur": r"Drawdown duration\s*│\s*([^\│]+?)\s{2,}",
    "market_chg": r"Market change\s*│\s*(-?[\d.]+)%",
    "best_day": r"Best day\s*│\s*(-?[\d.]+) USDT",
    "worst_day": r"Worst day\s*│\s*(-?[\d.]+) USDT",
}


def parse_log(path):
    text = Path(path).read_text(errors="replace")
    m = {}
    sm_start = text.find("SUMMARY METRICS")
    sm_end = text.find("Backtested", sm_start)
    if sm_start == -1 or sm_end == -1:
        return m
    block = text[sm_start:sm_end]
    ss_start = text.find("STRATEGY SUMMARY")
    ss_block = text[ss_start:] if ss_start != -1 else ""

    win_m = re.search(r"\u2502\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s*\u2502", ss_block)
    if win_m:
        m["wins"] = int(win_m.group(1))
        m["draws"] = int(win_m.group(2))
        m["losses"] = int(win_m.group(3))
        m["win_pct"] = float(win_m.group(4))

    for key, pat in METRIC_PATTERNS.items():
        if key == "win_pct":
            continue
        match = re.search(pat, block)
        if match:
            if key == "trades":
                m["trades"] = int(match.group(1))
                m["trades_per_day"] = float(match.group(2))
            elif key == "expectancy":
                m["expectancy_pct"] = float(match.group(1))
                m["expectancy_ratio"] = float(match.group(2))
            elif key == "dd_abs":
                m["dd_usdt"] = float(match.group(1))
                m["dd_pct"] = float(match.group(2))
            else:
                val = match.group(1).replace(",", "")
                try:
                    m[key] = float(val) if "." in val or "-" in val else int(val)
                except ValueError:
                    m[key] = val.strip()
    return m


def fmt(v, w, p=False):
    if isinstance(v, (int, float)):
        return f"{v:>{w}.2f}" if p else f"{v:>{w}}"
    return f"{'-':>{w}}"


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    regime_dir = Path(sys.argv[1])
    regime_name = sys.argv[2]
    timerange = sys.argv[3]
    output_json = sys.argv[4] if len(sys.argv) > 4 else str(regime_dir / "comparison_summary.json")

    all_data = {
        "meta": {
            "timerange": timerange,
            "regime": regime_name,
            "exchange": "bybit (isolated futures, leverage 1x)",
            "starting_capital": 10000,
            "fee": 0.06,
            "config": "user_data/config/backtest_futures_standard.json",
            "data_source": "user_data/data/bybit/*-5m-futures.feather",
        },
        "results": {},
    }

    for s in STRATEGIES:
        log = regime_dir / s / "backtest.log"
        if not log.exists():
            print(f"WARN: {s}: missing log")
            continue
        parsed = parse_log(log)
        all_data["results"][s] = parsed
        if parsed:
            print(
                f"  ok {s}: profit={parsed.get('profit_pct', '?')}%  sharpe={parsed.get('sharpe', '?')}  trades={parsed.get('trades', '?')}"
            )

    Path(output_json).write_text(json.dumps(all_data, indent=2, ensure_ascii=False))
    print(f"\nWrote {output_json}")

    print(f"\n=== {regime_name} Summary ===")
    print(
        f"{'Strategy':<22} {'Trades':>7} {'Profit%':>8} {'Sharpe':>7} {'Sortino':>8} {'Calmar':>8} {'Win%':>6} {'DD%':>6} {'PF':>6}"
    )
    print("-" * 90)
    for s in STRATEGIES:
        d = all_data["results"].get(s, {})
        if not d:
            print(f"{s:<22}  (no data)")
            continue
        line = (
            f"{s:<22} "
            f"{fmt(d.get('trades', 0), 7)} "
            f"{fmt(d.get('profit_pct'), 8, p=True)}% "
            f"{fmt(d.get('sharpe'), 7, p=True)} "
            f"{fmt(d.get('sortino'), 8, p=True)} "
            f"{fmt(d.get('calmar'), 8, p=True)} "
            f"{fmt(d.get('win_pct'), 6, p=True)} "
            f"{fmt(d.get('dd_pct'), 6, p=True)} "
            f"{fmt(d.get('profit_factor'), 6, p=True)}"
        )
        print(line)


if __name__ == "__main__":
    main()
