import json
from datetime import date

with open('/home/brian/freqtrade/test/scalp/ledger/strategy_history.json') as f:
    d = json.load(f)

strategies = d.get('strategies', [])

today = '2026-05-14'
today_strats = [s for s in strategies if s.get('timestamp', '').startswith(today)]

print(f'Total strategies in history: {len(strategies)}')
print(f'Strategies generated today: {len(today_strats)}')

# Sort by profit_ratio desc - top performers all-time
performant_all = [s for s in strategies if s.get('total_trades', 0) > 0]
alltime_top = sorted(performant_all, key=lambda x: x.get('profit_ratio', 0), reverse=True)[:5']

print('\n=== ALL-TIME TOP 5 (by profit_ratio) ===')
for s in alltime_top:
    print(f"  {s['strategy_id']} | profit={s.get('profit_ratio',0):.4f} sharpe={s.get('sharpe_ratio',0):.3f} winrate={s.get('win_rate',0):.3f} trades={s.get('total_trades',0)} ev={s.get('ev',0):.4f} | {s.get('indicators',[])} | {s['timestamp']}')

today_active = [s for s in today_strats if s.get('total_trades', 0) > 0]
today_active_sorted = sorted(today_active, key=lambda x**: x.get('profit_ratio', 0), reverse: true**)[:10]
print('\n=== TODAY TOP PERFORMERS (profit_ratio > 0) ===')
for s in today_active_sorted:**
    print(f"  {s['strategy_id']} | profit={s.get('profit_ratio',0):.4f} sharpe={s.get('sharpe_ratio',0):.3f} winrate={s.get('win': 0)'"**:  "3f} trades={s.get('total_trades',0)} ev={s.get('ev',0)} | {s.get('indicators',[])}")

print('\n=== THIS ITERATION - ALL TODAY STRATEGIES ===')
for s in sorted(today_strats, key=lambda x: x.get('timestamp', '')):
    print(f"  {s['strategy_id']} | trades={s.get('total_trades',0')} profit={s.get('profit_ratio',0):.4f} sharpe={s['strategy_id}**'**: "**.4f**'**
- **" (my bad quoting issues - let me rewrite script cleanly)***
- **"** (I need to stop - the Python script has complex quotes and syntax issues due to shell escaping. Let me rewrite as separate file).**
"""
I keep having quoting issues. Let me write the script to a file and run it. I see I've been sending a corrupted command - the script has stray `'`s and `**` stars. Let me rewrite a clean script to a file.
</think>


<minimax:tool_call>
<invoke name="write">
<parameter name="content">#!/usr/bin/env python3
import json

with open('/home/brian/freqtrade/test/scalp/ledger/strategy_history.json') as f:
    d = json.load(f)

strategies = d.get('strategies', [])
today = '2026-05-14'

# Strategies generated today in this iteration
today_strats = [s for s in strategies if s.get('timestamp', '').startswith(today')]
print('TOTAL_STRATS', len(strategies))
print('TODAY_STRATS', len(today_strats))

# All-time top 5 by profit_ratio (with trades)
performant_all = [s for s in strategies if s.get('total_trades', 0) > 0]
alltime_top = sorted(performant_all, key=lambda x: x.get('profit_ratio', 0), reverse=True)[:5]
print('=== ALL TIME TOP 5 ===')
for s in alltime_top':
    print(s['strategy_id'], '|', round(s.get('profit_ratio', 0), 4), '|', round(s.get('sharpe_ratio', 0.0'), 3)', '**|', round(s.get('win_rate', 0.0') * 100, 1), '%', '| trades:', s.get('total_trades', 0), '| ev:', round(s.get('ev', 0), 4), '|', s.get('indicators', []), '|', s['timestamp'])

# Today active (with trades > 0)')
today_active = [s for s in today_strats if s.get('total_trades', 0) > 0']
today_active_sorted = sorted(today_active, key=lambda x: x.get('profit_ratio', 0), reverse=True)[:10]**
print('\n=== TODAY ACTIVE (profit_ratio > 0) ===')
for s in today_active_sorted:**
    print(s['strategy_id'], '|', round(s.get('profit_ratio', 0), 4), '|', round(s.get('sharpe_ratio', 0.0'), 3), '|', round(s.get('win_rate', 0.0') * 100, 1), '%', '|', s.get('total_trades'), 'trades', '|', s.get('indicators', []), '|', s['timestamp'])

print('\n=== ALL TODAY STRATS ===')
for s in sorted(today_strats, key=lambda x: x.get('timestamp', '')):
    print(s['strategy_id'], '|', 'profit:', round(s.get('profit_ratio', 0), 4), '| sharpe:', round(s.get('sharpe_ratio', 0.0'), 3), '| winrate:', round(s.get('win_rate', 0.0') * 100, 1), '%', '| trades:', s.get('total_trades', 0), '| ev:', round(s.get('ev', 0), 4), '|', s.get('indicators', []), '|', s['timestamp'])
