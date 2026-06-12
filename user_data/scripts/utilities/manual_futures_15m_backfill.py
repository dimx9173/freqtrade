#!/usr/bin/env python3
"""
手動補下載 bybit 合約 15m 缺失範圍
頻率: 一次性的, 當 download_futures_daily cron 漏跑時用

Usage:
    cd /home/brian/freqtrade
    ./.venv/bin/python3 user_data/scripts/utilities/manual_futures_15m_backfill.py

功能:
- 對 9 對 (ETH/SOL/BNB/XRP/DOGE/ADA/AVAX/TON/SUI) 補 15m 合約資料
- 從 file 現有最後時間到 2026-06-12 18:30 UTC
- 用 Bybit API `until` 參數往前翻頁 (ccxt bybit 不支援完整 paginate)
- 自動 dedup + sort + save

作者: MiniMax-M3 (2026-06-12)
"""

import ccxt
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import sys

EXCHANGE = ccxt.bybit({'options': {'defaultType': 'swap'}})
PAIRS = ['ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'TON', 'SUI']
TIMEFRAME = '15m'
DATA_DIR = Path('/home/brian/freqtrade/user_data/data/bybit/futures')
TARGET_END = pd.Timestamp('2026-06-12 18:30:00', tz='UTC')


def backfill_pair(pair: str) -> dict:
    symbol = f'{pair}/USDT:USDT'
    fpath = DATA_DIR / f'{pair}_USDT_USDT-15m-futures.feather'

    if not fpath.exists():
        return {'pair': pair, 'status': 'SKIP', 'reason': 'file not exist'}

    existing = pd.read_feather(fpath)
    existing['date'] = pd.to_datetime(existing['date'], utc=True)
    file_end = existing['date'].max()

    if file_end >= TARGET_END:
        return {'pair': pair, 'status': 'UP_TO_DATE', 'last': str(file_end)}

    print(f'\n=== {pair}: {file_end} -> {TARGET_END} ===')
    all_ohlcv = []
    until_ts = int(TARGET_END.timestamp() * 1000)
    start_ts = int(file_end.timestamp() * 1000) + 1
    batch = 0
    max_batches = 30

    while until_ts > start_ts and batch < max_batches:
        try:
            ohlcv = EXCHANGE.fetch_ohlcv(symbol, TIMEFRAME, limit=200, params={'until': until_ts})
        except Exception as e:
            print(f'  Error: {e}')
            break
        if not ohlcv:
            break
        all_ohlcv = ohlcv + all_ohlcv  # prepend
        last_ts = ohlcv[-1][0]
        first_ts = ohlcv[0][0]
        if last_ts <= start_ts:
            break
        until_ts = first_ts - 1
        batch += 1
        if len(ohlcv) < 200:
            break

    if not all_ohlcv:
        return {'pair': pair, 'status': 'NO_DATA', 'last': str(file_end)}

    new_df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    new_df['date'] = pd.to_datetime(new_df['timestamp'], unit='ms', utc=True)
    new_df = new_df[['date', 'open', 'high', 'low', 'close', 'volume']]
    new_df = new_df[new_df['date'] > file_end]

    if new_df.empty:
        return {'pair': pair, 'status': 'NO_NEW', 'last': str(file_end)}

    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset='date', keep='last')
    combined = combined.sort_values('date').reset_index(drop=True)
    combined = combined[['date', 'open', 'high', 'low', 'close', 'volume']]
    combined.to_feather(fpath)

    return {
        'pair': pair,
        'status': 'OK',
        'new_bars': len(new_df),
        'batches': batch,
        'new_range': f'{new_df.iloc[0]["date"]} ~ {new_df.iloc[-1]["date"]}',
        'file_total': len(combined),
        'file_range': f'{combined.iloc[0]["date"]} ~ {combined.iloc[-1]["date"]}',
    }


def main():
    print('=' * 70)
    print('Manual Bybit Futures 15m Backfill')
    print(f'Target: {TARGET_END}')
    print(f'Pairs: {PAIRS}')
    print('=' * 70)

    results = []
    for pair in PAIRS:
        result = backfill_pair(pair)
        results.append(result)
        print(f'  {result}')

    print('\n' + '=' * 70)
    print('SUMMARY')
    print('=' * 70)
    for r in results:
        print(f"  {r['pair']:<6} {r['status']:<12} {r.get('new_bars', '-')} bars | {r.get('file_range', r.get('last', '-'))}")


if __name__ == '__main__':
    main()
