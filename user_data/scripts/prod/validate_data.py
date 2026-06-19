#!/usr/bin/env python3
"""
validate_data.py
驗證 futures feather 資料完整性

用法:
    python3 validate_data.py --datadir /path/to/data --pairs BTC ETH --timeframes 5m 1h
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("❌ 需要 pandas: pip install pandas pyarrow")
    sys.exit(1)


def validate_pair(datadir: str, pair: str, timeframe: str, min_rows_per_day: int = 288) -> dict:
    """驗證單一 pair 的資料完整性"""
    # 建構檔案路徑
    pair_clean = pair.replace("/", "_").replace(":", "_")
    filename = f"{pair_clean}-{timeframe}-futures.feather"
    filepath = os.path.join(datadir, filename)

    result = {
        "pair": pair,
        "timeframe": timeframe,
        "filepath": filepath,
        "exists": False,
        "rows": 0,
        "first_date": None,
        "last_date": None,
        "days_covered": 0,
        "avg_rows_per_day": 0,
        "status": "unknown",
        "error": None,
    }

    if not os.path.exists(filepath):
        result["status"] = "missing"
        result["error"] = f"檔案不存在: {filepath}"
        return result

    result["exists"] = True

    try:
        df = pd.read_feather(filepath)
        result["rows"] = len(df)

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], utc=True)
            result["first_date"] = df["date"].iloc[0].isoformat()
            result["last_date"] = df["date"].iloc[-1].isoformat()

            # 計算涵蓋天數
            time_span = df["date"].iloc[-1] - df["date"].iloc[0]
            result["days_covered"] = time_span.days + 1

            # 計算平均每日行數
            if result["days_covered"] > 0:
                result["avg_rows_per_day"] = result["rows"] / result["days_covered"]

            # 驗證完整性
            if result["avg_rows_per_day"] < min_rows_per_day * 0.9:
                result["status"] = "incomplete"
                result["error"] = (
                    f"資料不完整: 平均 {result['avg_rows_per_day']:.0f} rows/day, "
                    f"預期至少 {min_rows_per_day}"
                )
            else:
                result["status"] = "ok"
        else:
            result["status"] = "warning"
            result["error"] = "缺少 date 欄位"

    except Exception as e:
        result["status"] = "error"
        result["error"] = f"讀取失敗: {type(e).__name__}: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(description="驗證 futures feather 資料完整性")
    parser.add_argument("--datadir", required=True, help="資料目錄")
    parser.add_argument("--pairs", nargs="+", required=True, help="交易對列表")
    parser.add_argument("--timeframes", nargs="+", default=["5m"], help="時間週期列表")
    parser.add_argument(
        "--min-rows-per-day",
        type=int,
        default=288,
        help="每日最少行數 (5m=288, 1h=24)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.datadir):
        print(f"❌ 資料目錄不存在: {args.datadir}")
        sys.exit(1)

    print(f"=== 資料完整性驗證 ===")
    print(f"目錄: {args.datadir}")
    print(f"交易對: {', '.join(args.pairs)}")
    print(f"時間週期: {', '.join(args.timeframes)}")
    print(f"每日最少行數: {args.min_rows_per_day}")
    print()

    failed = 0
    results = []

    for pair in args.pairs:
        for tf in args.timeframes:
            result = validate_pair(args.datadir, pair, tf, args.min_rows_per_day)
            results.append(result)

            if result["status"] == "ok":
                print(
                    f"✅ {pair} ({tf}): {result['rows']} rows, "
                    f"{result['first_date']} ~ {result['last_date']}"
                )
            elif result["status"] == "missing":
                print(f"❌ {pair} ({tf}): 檔案不存在")
                failed += 1
            elif result["status"] == "incomplete":
                print(f"⚠️  {pair} ({tf}): {result['error']}")
                failed += 1
            else:
                print(f"⚠️  {pair} ({tf}): {result['error']}")
                failed += 1

    print()
    print(f"=== 總結 ===")
    print(f"總計: {len(results)} 個驗證")
    print(f"通過: {len(results) - failed}")
    print(f"失敗: {failed}")

    if failed > 0:
        sys.exit(1)
    else:
        print("✅ 所有資料完整")
        sys.exit(0)


if __name__ == "__main__":
    main()
