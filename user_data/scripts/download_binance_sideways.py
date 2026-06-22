#!/usr/bin/env python3
"""
download_binance_sideways.py — 從 Binance 下載 SIDEWAYS 期間 5m 歷史資料
Bybit 僅保留 ~1 年 5m 歷史,Binance 保留較長
下載後存到 user_data/data/bybit/ 並用 bybit 命名格式,以便 backtest 直接使用
"""

import ccxt
import pandas as pd
import os
from pathlib import Path
from datetime import datetime, timezone
import time
import json

# 25 個合約幣對 (與 coinmarketcap-futures-pairlist.json 對齊,但排除 LEO/GRAM/USDG/SHIB/CC/M 等無 Binance 5m 資料的幣)
PAIRS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "SOL/USDT:USDT",
    "TRX/USDT:USDT",
    "DOGE/USDT:USDT",
    "ZEC/USDT:USDT",
    "XLM/USDT:USDT",
    "XMR/USDT:USDT",
    "ADA/USDT:USDT",
    "LINK/USDT:USDT",
    "BCH/USDT:USDT",
    "HBAR/USDT:USDT",
    "LTC/USDT:USDT",
    "SUI/USDT:USDT",
    "AVAX/USDT:USDT",
    "TON/USDT:USDT",
    "NEAR/USDT:USDT",
    "HYPE/USDT:USDT",
    "USD1/USDT:USDT",
    "WLFI/USDT:USDT",
    "TAO/USDT:USDT",
]

# SIDEWAYS 期間
START_MS = int(datetime(2025, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)
END_MS = int(datetime(2025, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)  # 包含 6/30


# Bybit 命名: BTC_USDT-5m-futures.feather (單 USDT,不是 USDT_USDT)
def bybit_name(ccxt_pair: str) -> str:
    base, _, _ = ccxt_pair.partition("/")
    return f"{base}_USDT-5m-futures.feather"


OUT_DIR = Path("user_data/data/bybit")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Binance SIDEWAYS 5m download started")
    print(
        f"Pairs: {len(PAIRS)}, period: 2025-03-01 to 2025-07-01 (covers SIDEWAYS 20250301-20250630)"
    )
    ex = ccxt.binance(
        {
            "options": {"defaultType": "future"},
            "enableRateLimit": True,
        }
    )
    ex.load_markets()

    summary = {}
    for ccxt_pair in PAIRS:
        out_path = OUT_DIR / bybit_name(ccxt_pair)
        # Skip if already has full coverage
        if out_path.exists():
            try:
                existing = pd.read_feather(out_path)
                if len(existing) > 0 and "date" in existing.columns:
                    ex_d0 = pd.to_datetime(existing["date"].iloc[0], utc=True)
                    ex_d1 = pd.to_datetime(existing["date"].iloc[-1], utc=True)
                    if ex_d0 <= pd.Timestamp("2025-03-01", tz="UTC") and ex_d1 >= pd.Timestamp(
                        "2025-06-30 23:59:59", tz="UTC"
                    ):
                        print(
                            f"  ✓ {ccxt_pair}: already covered ({ex_d0.date()} → {ex_d1.date()}, {len(existing)} rows)"
                        )
                        summary[ccxt_pair] = {"status": "skipped", "rows": len(existing)}
                        continue
            except Exception:
                pass

        # Fetch 5m candles from Binance
        print(
            f"  ↓ {ccxt_pair}: downloading from {datetime.fromtimestamp(START_MS / 1000, tz=timezone.utc).date()} to {datetime.fromtimestamp(END_MS / 1000, tz=timezone.utc).date()}",
            end=" ",
            flush=True,
        )
        all_candles = []
        since = START_MS
        batch_count = 0
        try:
            while since < END_MS:
                candles = ex.fetch_ohlcv(ccxt_pair, "5m", since=since, limit=1000)
                if not candles:
                    break
                all_candles.extend(candles)
                since = candles[-1][0] + 5 * 60 * 1000  # next 5m
                batch_count += 1
                if batch_count % 5 == 0:
                    print(".", end="", flush=True)
                if batch_count > 200:  # safety: 200 × 1000 × 5m = ~70 days
                    print(" [cap reached]", end="", flush=True)
                    break
            if not all_candles:
                print(f" NO DATA")
                summary[ccxt_pair] = {"status": "empty"}
                continue
            df = pd.DataFrame(
                all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df[["date", "open", "high", "low", "close", "volume"]]
            # 合併到既有檔案 (如有)
            if out_path.exists():
                try:
                    existing = pd.read_feather(out_path)
                    if len(existing) > 0 and "date" in existing.columns:
                        existing["date"] = pd.to_datetime(existing["date"], utc=True)
                        df = (
                            pd.concat([existing, df])
                            .drop_duplicates(subset="date")
                            .sort_values("date")
                            .reset_index(drop=True)
                        )
                except Exception as e:
                    print(f" [merge failed: {e}]", end="")
            df.to_feather(out_path)
            d0 = df["date"].iloc[0]
            d1 = df["date"].iloc[-1]
            print(f" ✓ {len(df)} rows ({d0.date()} → {d1.date()})")
            summary[ccxt_pair] = {
                "status": "downloaded",
                "rows": len(df),
                "range": [str(d0.date()), str(d1.date())],
            }
        except Exception as e:
            print(f" ERROR: {e}")
            summary[ccxt_pair] = {"status": "error", "error": str(e)}
        time.sleep(0.2)  # gentle rate limiting

    log_path = Path("/tmp/binance_sideways_download.json")
    log_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    ok = sum(1 for v in summary.values() if v.get("status") in ("downloaded", "skipped"))
    print(f"\n✓ Done: {ok}/{len(PAIRS)} pairs OK. Log: {log_path}")


if __name__ == "__main__":
    main()
