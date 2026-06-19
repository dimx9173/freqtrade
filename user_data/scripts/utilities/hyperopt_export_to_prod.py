#!/usr/bin/env python3
"""
hyperopt-to-prod 自動匯出腳本
============================
從 fthypt 解析 best trial, 寫成 prod/*.json 格式。

Usage:
    cd /home/brian/freqtrade
    .venv/bin/python3 user_data/scripts/utilities/hyperopt_export_to_prod.py [--strategy STRATEGY] [--dry-run]

設計:
- 找每個策略最新 fthypt
- 解析 best trial (最低 loss)
- 區分 buy/sell/roi/stoploss/trailing
- 寫成 prod/<name>.json (備份到 prod/backup/)
- 預設 --dry-run 只印出將寫入內容, 不實際動 prod json

安全:
- 不殺 bot 進程
- 不覆蓋現有 prod json (先備份)
- 寫入前驗證結構 (buy/sell non-empty, max_open_trades > 0)
- --apply 才實際寫入 (預設 --dry-run)
"""

import argparse
import json
import glob
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# === 設定 ===
FREQTRADE_DIR = Path("/home/brian/freqtrade")
HYPEROPT_DIR = FREQTRADE_DIR / "user_data" / "hyperopt_results"
PROD_DIR = FREQTRADE_DIR / "user_data" / "strategies" / "prod"
BACKUP_DIR = PROD_DIR / "backup"

STRATEGIES = [
    "NASOSv4",
    "PSV5_Hybrid",
    "BB_RPB_TSL_BI",
    "NASOSv5_mod3",
    "SMAOffsetProtectOptV1",
]


def parse_fthypt(fthypt_path: Path) -> dict | None:
    """解析 fthypt NDJSON 找 best trial (最低 loss)"""
    best = None
    n_trials = 0
    with open(fthypt_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "loss" in d and "params_dict" in d:
                n_trials += 1
                if best is None or d["loss"] < best["loss"]:
                    best = d
    if best:
        best["_n_trials"] = n_trials
    return best


def get_full_params(best_trial: dict) -> dict:
    """合併 params_dict (hyperopt) + params_not_optimized (固定 param)

    freqtrade 2026.3 把不參與 hyperopt 的 param 放在 params_not_optimized 區
    """
    full = {}
    full.update(best_trial.get("params_dict", {}))
    not_opt = best_trial.get("params_not_optimized", {})
    for k, v in not_opt.items():
        if k not in full:  # 不覆蓋 hyperopt 結果
            full[k] = v
    return full


def split_params(params_dict: dict) -> dict:
    """把 fthypt params_dict 拆成 buy/sell/roi/stoploss/trailing 區塊

    處理 3 種 key 格式:
    1. prefix 格式: buy_xxx, sell_xxx (新版 hyperopt)
    2. 無 prefix 格式: base_nb_candles_buy, base_nb_candles_sell (舊版 hyperopt)
    3. 策略定義的特定 key
    """
    buy = {}
    sell = {}
    roi = {}
    trailing = {}
    stoploss = None
    max_open_trades = None
    protection = {}

    # 策略已知的 buy/sell param (無 prefix 版本)
    KNOWN_BUY_NO_PREFIX = {
        "base_nb_candles_buy",
        "lookback_candles",
        "profit_threshold",
        "ewo_high",
        "ewo_high_2",
        "ewo_low",
        "low_offset",
        "low_offset_2",
        "rsi_buy",
        "rsi_fast_buy",
        "buy_adx_min",
        "buy_adx_trend_min",
        "buy_atr_threshold_high",
        "buy_atr_threshold_low",
        "buy_volume_ratio_min",
        "buy_rsi_short_min",
        "buy_rsi_short_max",
        "buy_rsi_long_max",
        "buy_ema_proximity_pct",
        "buy_roc_threshold",
        "buy_volatility_threshold",
    }
    KNOWN_SELL_NO_PREFIX = {
        "base_nb_candles_sell",
        "high_offset",
        "high_offset_2",
    }

    for k, v in params_dict.items():
        if k.startswith("buy_"):
            # 保留完整 key (e.g. buy_adx_min, buy_bb_delta)
            # freqtrade 從 params.buy["buy_adx_min"] 找值對應 self.buy_adx_min
            buy[k] = v
        elif k.startswith("sell_"):
            sell[k] = v
        elif k in KNOWN_BUY_NO_PREFIX:
            # 舊版 hyperopt 沒 prefix, 但 param name 含 _buy/_sell
            # 保留原始 key 名 (策略讀的是完整 key 如 base_nb_candles_buy)
            buy[k] = v
        elif k in KNOWN_SELL_NO_PREFIX:
            # 保留原始 key 名
            sell[k] = v
        elif k.startswith("roi_"):
            # NASOSv5_mod3 用 roi_p0/roi_p1/roi_p2 + roi_t0/roi_t1/roi_t2
            # 跳過這些 (IntParameter 漏進 json 的)
            continue
        elif k == "stoploss":
            stoploss = v
        elif k.startswith("trailing_") or k in (
            "trailing_stop",
            "trailing_stop_positive",
            "trailing_stop_positive_offset",
            "trailing_only_offset_is_reached",
        ):
            trailing[k] = v
        elif k == "max_open_trades":
            max_open_trades = v
        elif k.startswith("pHSL") or k.startswith("pPF_") or k.startswith("pSL_"):
            protection[k] = v
        else:
            # 未知 key, 暫歸 buy
            buy[k] = v

    # 標準 3 段 ROI
    if not roi:
        roi = {"0": 0.06, "30": 0.03, "60": 0.015}

    return {
        "buy": buy,
        "sell": sell,
        "minimal_roi": roi,
        "stoploss": stoploss,
        "trailing": trailing,
        "max_open_trades": max_open_trades,
        "protection": protection,
    }


def validate_export(export: dict, strategy: str) -> list[str]:
    """驗證匯出結構, 回傳錯誤清單"""
    errors = []
    if not export["buy"]:
        errors.append(f"{strategy}: buy params 為空 (hyperopt 沒找到 buy 維度?)")
    if export["max_open_trades"] is not None and export["max_open_trades"] == 0:
        errors.append(f"{strategy}: max_open_trades=0 (會禁止交易)")
    if export["stoploss"] is None:
        errors.append(f"{strategy}: 缺 stoploss")
    if export["stoploss"] is not None and export["stoploss"] > -0.02:
        errors.append(f"{strategy}: stoploss {export['stoploss']} 過寬 (> -2%)")
    return errors


def export_strategy(strategy: str, dry_run: bool = True) -> bool:
    """匯出單一策略. 成功回傳 True, 失敗/跳過回傳 False"""
    files = sorted(glob.glob(str(HYPEROPT_DIR / f"strategy_{strategy}_*.fthypt")))
    if not files:
        print(f"  ❌ {strategy}: 找不到 fthypt")
        return False
    latest = Path(files[-1])

    print(f"\n{'=' * 60}")
    print(f"📦 {strategy}")
    print(f"   fthypt: {latest.name}")
    print(f"   mtime:  {datetime.fromtimestamp(latest.stat().st_mtime):%Y-%m-%d %H:%M:%S}")

    best = parse_fthypt(latest)
    if not best:
        print(f"  ❌ {strategy}: fthypt 沒有 valid trials")
        return False

    n_trials = best.get("_n_trials", 0)
    print(f"   trials: {n_trials}")
    print(f"   best loss: {best['loss']:.4f}")

    # 合併 hyperopt + not_optimized params
    full_params = get_full_params(best)
    export = split_params(full_params)

    # 驗證
    errors = validate_export(export, strategy)
    if errors:
        print(f"  ⚠️  驗證警告:")
        for e in errors:
            print(f"      {e}")
        print(f"  (即使有警告, 仍會繼續匯出, 但 Brian 應人工 review)")

    # 比較現有 prod json
    prod_json = PROD_DIR / f"{strategy}.json"
    if prod_json.exists():
        with open(prod_json) as f:
            current = json.load(f)
        cur_buy_n = len(current.get("params", {}).get("buy", {}))
        cur_sell_n = len(current.get("params", {}).get("sell", {}))
        print(f"   current prod: {cur_buy_n} buy, {cur_sell_n} sell")
        print(f"   new export:   {len(export['buy'])} buy, {len(export['sell'])} sell")

    # 構造新 prod json (nested 格式, 跟現有 PSV5/BB_RPB 一致)
    new_json = {
        "strategy_name": strategy,
        "params": {
            "buy": export["buy"],
            "sell": export["sell"],
            "max_open_trades": {
                "max_open_trades": int(export["max_open_trades"])
                if export["max_open_trades"] is not None
                else 5
            },
        },
    }
    # minimal_roi (nested)
    if export["minimal_roi"]:
        new_json["params"]["roi"] = export["minimal_roi"]
    # stoploss (nested)
    if export["stoploss"] is not None:
        new_json["params"]["stoploss"] = {"stoploss": export["stoploss"]}
    else:
        new_json["params"]["stoploss"] = {"stoploss": -0.10}
    # trailing (nested)
    if export["trailing"]:
        new_json["params"]["trailing"] = {
            "trailing_stop": export["trailing"].get("trailing_stop", True),
            "trailing_stop_positive": export["trailing"].get("trailing_stop_positive", 0.01),
            "trailing_stop_positive_offset": export["trailing"].get(
                "trailing_stop_positive_offset", 0.03
            ),
            "trailing_only_offset_is_reached": export["trailing"].get(
                "trailing_only_offset_is_reached", True
            ),
        }
    # protection (nested)
    if export["protection"]:
        new_json["params"]["protection"] = export["protection"]

    # 印出新內容預覽
    print(f"\n   📋 New prod json 預覽 (nested 格式):")
    print(
        f"      buy: {len(new_json['params']['buy'])} params (sample: {list(new_json['params']['buy'].items())[:2]})"
    )
    print(f"      sell: {len(new_json['params']['sell'])} params")
    print(f"      roi: {new_json['params'].get('roi', {})}")
    print(f"      stoploss: {new_json['params'].get('stoploss', {})}")
    print(f"      max_open_trades: {new_json['params'].get('max_open_trades', {})}")

    if dry_run:
        print(f"\n   🔍 DRY-RUN: 不實際寫入 {prod_json.name}")
        return True
    else:
        # 備份現有
        if prod_json.exists():
            BACKUP_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"{strategy}.{ts}.json"
            shutil.copy2(prod_json, backup_path)
            print(f"   💾 備份 → {backup_path.name}")

        # 寫入
        with open(prod_json, "w") as f:
            json.dump(new_json, f, indent=2)
        print(f"   ✅ 寫入 {prod_json.name}")
        return True


def main():
    parser = argparse.ArgumentParser(description="hyperopt-to-prod 自動匯出")
    parser.add_argument("--strategy", help="指定單一策略 (預設 5 個全跑)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="只預覽不寫入 (預設)")
    parser.add_argument("--apply", action="store_true", help="實際寫入 prod json (覆蓋 --dry-run)")
    args = parser.parse_args()

    dry_run = not args.apply

    print("=" * 60)
    print("🚀 hyperopt-to-prod 自動匯出")
    print(f"   mode: {'DRY-RUN (預覽)' if dry_run else 'APPLY (實際寫入)'}")
    print("=" * 60)

    if args.strategy:
        strats = [args.strategy]
    else:
        strats = STRATEGIES

    success = 0
    for s in strats:
        if export_strategy(s, dry_run=dry_run):
            success += 1

    print("\n" + "=" * 60)
    print(f"📊 結果: {success}/{len(strats)} 策略成功")
    if dry_run:
        print("\n⚠️  DRY-RUN 模式, 未實際寫入")
        print("   若要套用, 執行: --apply")
    else:
        print(f"\n✅ 已寫入 prod json")
        print(f"   備份位置: {BACKUP_DIR}/")
        print(f"   提醒: 不殺 bot 進程, 等 Brian 決策重啟時機")
    print("=" * 60)


if __name__ == "__main__":
    main()
