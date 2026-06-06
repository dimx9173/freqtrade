#!/usr/bin/env python3
"""Analyze 1-year backtest results: enter tag, pair, exit reason distribution."""
import json
import sys
import zipfile
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python analyze_bt.py <backtest_zip>")
    sys.exit(1)

zf = zipfile.ZipFile(sys.argv[1])
json_name = [n for n in zf.namelist()
             if n.endswith('.json') and 'config' not in n
             and 'Hybrid' not in n and 'market' not in n][0]
data = json.loads(zf.read(json_name))
strat = data['strategy']['Hybrid_v3']

print(f"=== Backtest Window ===")
print(f"  Start: {strat['backtest_start']}, End: {strat['backtest_end']}")
print(f"  Days: {strat['backtest_days']}, Total trades: {strat['total_trades']}")
print(f"  Profit: {strat['profit_total_abs']:.4f} USDT ({strat.get('profit_total_pct', strat['profit_total_abs']/1000):.2%})")
print(f"  WR: {strat['winrate']:.1%}, Max DD: {strat['max_drawdown_account']*100:.2f}%")
print(f"  Market change: {strat['market_change']*100:.2f}%")

print(f"\n=== Enter Tag 分布 (by trade count) ===")
tags = [t for t in strat.get('results_per_enter_tag', []) if t['key'] != 'TOTAL']
tags.sort(key=lambda t: t['trades'], reverse=True)
for t in tags:
    print(f"  {t['key']:20s}: {t['trades']:4d} trades, {t['winrate']:>6.1%} WR, "
          f"profit={t['profit_total_abs']:>10.4f} USDT, "
          f"avg={t['profit_mean']*100:>7.3f}%")

print(f"\n=== Pair 分布 (by profit) ===")
pairs = [p for p in strat.get('results_per_pair', []) if p['key'] != 'TOTAL']
pairs.sort(key=lambda p: p['profit_total_abs'])
for p in pairs:
    print(f"  {p['key']:12s}: {p['trades']:4d} trades, {p['winrate']:>5.1%} WR, "
          f"profit={p['profit_total_abs']:>10.4f} USDT")

print(f"\n=== Exit Reason 分布 ===")
exits = [e for e in strat.get('exit_reason_summary', []) if e['key'] != 'TOTAL']
exits.sort(key=lambda e: e['trades'], reverse=True)
for e in exits:
    print(f"  {e['key']:25s}: {e['trades']:4d} trades, "
          f"avg={e.get('profit_mean', 0)*100:.3f}%, "
          f"total={e.get('profit_total_abs', 0):.4f} USDT")
