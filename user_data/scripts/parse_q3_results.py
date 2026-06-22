#!/usr/bin/env python3
"""
parse_q3_results.py — 從 5 個 prod 策略的 backtest.log 抽取指標,輸出 JSON + Markdown
"""

import json
import re
from pathlib import Path

RESULTS_DIR = Path("user_data/reports/q3_2025_prod_comparison")
STRATEGIES = [
    "BB_RPB_TSL_BI",
    "ElliotV5_SMA_ninja",
    "NASOSv4",
    "NASOSv5_mod3",
    "SMAOffsetProtectOptV1",
]

# 從 SUMMARY METRICS 區塊精準抽取
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


def parse_log(path: Path) -> dict:
    text = path.read_text(errors="replace")
    m = {}
    # 只從 SUMMARY METRICS 區塊抽
    sm_start = text.find("SUMMARY METRICS")
    sm_end = text.find("Backtested", sm_start)
    if sm_start == -1 or sm_end == -1:
        return m
    block = text[sm_start:sm_end]
    # 還需要 STRATEGY SUMMARY 抽 trades summary
    ss_start = text.find("STRATEGY SUMMARY")
    ss_block = text[ss_start:] if ss_start != -1 else ""

    # win_pct — 從 STRATEGY SUMMARY 比較穩 (用 unicode \u2502 分隔)
    win_m = re.search(r"\u2502\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s*\u2502", ss_block)
    if win_m:
        m["wins"] = int(win_m.group(1))
        m["draws"] = int(win_m.group(2))
        m["losses"] = int(win_m.group(3))
        m["win_pct"] = float(win_m.group(4))

    # trades 從 SUMMARY
    for key, pat in METRIC_PATTERNS.items():
        if key in ("win_pct",):
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


def main():
    all_data = {
        "meta": {
            "timerange": "20250701-20250930",
            "regime": "BULL",
            "exchange": "bybit (isolated futures, leverage 1x)",
            "starting_capital": 10000,
            "fee": 0.05,
            "config": "user_data/config/config_6_futures_1x.json",
            "data_source": "user_data/data/bybit/*-5m-futures.feather",
        },
        "results": {},
    }

    for s in STRATEGIES:
        log = RESULTS_DIR / s / "backtest.log"
        if not log.exists():
            print(f"⚠ {s}: missing log")
            continue
        parsed = parse_log(log)
        all_data["results"][s] = parsed

    out_json = RESULTS_DIR / "comparison_summary.json"
    out_json.write_text(json.dumps(all_data, indent=2, ensure_ascii=False))
    print(f"✓ Wrote {out_json}")

    # 印摘要
    print("\n=== Summary Table ===")
    print(
        f"{'Strategy':<22} {'Trades':>7} {'Profit%':>8} {'Sharpe':>7} {'Sortino':>8} {'Calmar':>8} {'Win%':>6} {'DD%':>6} {'PF':>6}"
    )
    print("-" * 90)
    for s in STRATEGIES:
        d = all_data["results"].get(s, {})
        if not d:
            print(f"{s:<22}  (no data)")
            continue

        def fmt(v, w, p=False):
            if isinstance(v, (int, float)):
                return f"{v:>{w}.2f}" if p else f"{v:>{w}}"
            return f"{'-':>{w}}"

        print(
            f"{s:<22} {fmt(d.get('trades', 0), 7)} "
            f"{fmt(d.get('profit_pct'), 8, p=True)}% "
            f"{fmt(d.get('sharpe'), 7, p=True)} "
            f"{fmt(d.get('sortino'), 8, p=True)} "
            f"{fmt(d.get('calmar'), 8, p=True)} "
            f"{fmt(d.get('win_pct'), 6, p=True)} "
            f"{fmt(d.get('dd_pct'), 6, p=True)} "
            f"{fmt(d.get('profit_factor'), 6, p=True)}"
        )


if __name__ == "__main__":
    main()
