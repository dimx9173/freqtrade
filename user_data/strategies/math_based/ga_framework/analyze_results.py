#!/usr/bin/env python3
"""
數學策略 GA 迭代結果分析器 v2.0

使用 `freqtrade hyperopt-show --best --print-json` 解析 hyperopt 結果，
自動提取關鍵指標並 append 到 iteration_tracker.md。

使用方式:
    python3 analyze_results.py --strategy=PolyReg_Adaptive_v2
    python3 analyze_results.py --strategy=nsgaii_bb_rpb_tsl_bi --compare
    python3 analyze_results.py --strategy=nsgaii_bb_rpb_tsl_bi --hyperopt-filename=my_results.fthypt
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ---- 路徑設定 ----
# 基於 script 位置的相對路徑（不再硬編碼 HOME）
SCRIPT_DIR = Path(__file__).resolve().parent           # .../math_based/ga_framework
MATH_BASED_DIR = SCRIPT_DIR.parent                      # .../math_based
USER_DATA_DIR = MATH_BASED_DIR.parent.parent if MATH_BASED_DIR.name == "math_based" else None
FREQTRADE_ROOT = USER_DATA_DIR.parent if USER_DATA_DIR else None

# 自動推導 freqtrade binary（優先找 .venv，否則用 PATH 上的）
_venv_bin = FREQTRADE_ROOT / ".venv/bin/freqtrade" if FREQTRADE_ROOT else None
FREQTRADE_BIN = str(_venv_bin) if _venv_bin and _venv_bin.exists() else "freqtrade"

STRATEGY_PATH = str(MATH_BASED_DIR) if MATH_BASED_DIR.exists() else str(
    Path(os.environ.get("HOME", "/home/brian")) / "freqtrade/user_data/strategies/math_based"
)
GA_FRAMEWORK_DIR = SCRIPT_DIR
TRACKER_FILE = GA_FRAMEWORK_DIR / "iteration_tracker.md"

# hyperopt_results 目錄
_home = Path(os.environ.get("HOME", "/home/brian"))
HYPEROPT_RESULTS_DIR = (
    USER_DATA_DIR / "hyperopt_results" if USER_DATA_DIR and (USER_DATA_DIR / "hyperopt_results").exists()
    else _home / "freqtrade/user_data/hyperopt_results"
)


def run_hyperopt_show(strategy, hyperopt_filename=None, best=True, print_json=True):
    """執行 freqtrade hyperopt-show 並返回 JSON 輸出"""
    cmd = [
        FREQTRADE_BIN, "hyperopt-show",
        "--strategy-path", STRATEGY_PATH,
    ]

    if best:
        cmd.append("--best")
    if print_json:
        cmd.append("--print-json")
    if hyperopt_filename:
        cmd.append("--hyperopt-filename")
        cmd.append(hyperopt_filename)

    # 嘗試使用 --strategy (某些版本的 freqtrade 需要)
    # 如果不需要就省略，hyperopt-show 會自動從結果檔偵測

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(FREQTRADE_ROOT) if FREQTRADE_ROOT else str(_home / "freqtrade"),
        )

        if result.returncode != 0:
            # 嘗試加上 --strategy
            cmd2 = cmd + ["--strategy", strategy]
            result = subprocess.run(
                cmd2,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(FREQTRADE_ROOT) if FREQTRADE_ROOT else str(_home / "freqtrade"),
            )

        if result.returncode != 0:
            print(f"⚠️  hyperopt-show 失敗: {result.stderr[:500]}", file=sys.stderr)
            return None

        # 過濾 stderr 中的 warning，只取 stdout JSON
        output = result.stdout.strip()
        if not output:
            return None

        return json.loads(output)

    except subprocess.TimeoutExpired:
        print("⚠️  hyperopt-show 超時", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析失敗: {e}", file=sys.stderr)
        print(f"   stdout 前 500 字元: {result.stdout[:500]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"⚠️  錯誤: {e}", file=sys.stderr)
        return None


def find_latest_hyperopt_file(strategy_name):
    """尋找最新的 hyperopt 結果檔案"""
    if not HYPEROPT_RESULTS_DIR.exists():
        return None

    # 尋找符合策略名稱的 .fthypt 檔案
    files = list(HYPEROPT_RESULTS_DIR.glob(f"*{strategy_name}*.fthypt"))
    if not files:
        # 嘗試更寬鬆的匹配
        files = list(HYPEROPT_RESULTS_DIR.glob("*.fthypt"))

    if not files:
        return None

    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files[0]


def extract_metrics_from_json(data):
    """從 hyperopt-show JSON 輸出中提取關鍵指標"""
    metrics = {
        "total_profit_pct": None,
        "total_profit_abs": None,
        "trades": None,
        "win_rate": None,
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "max_drawdown": None,
        "profit_factor": None,
        "objective": None,
        "best_parameters": {},
    }

    if not data:
        return metrics

    # hyperopt-show --best --print-json 輸出格式各版本不同
    # 常見格式: 單一 epoch 物件或 epochs 陣列

    epoch = data
    if isinstance(data, dict):
        # 可能是 {"epochs": [...]} 或直接是 epoch dict
        if "epochs" in data and isinstance(data["epochs"], list) and len(data["epochs"]) > 0:
            epoch = data["epochs"][0]
        elif "best" in data and isinstance(data["best"], dict):
            # 某些版本用 "best" key
            epoch = data["best"]

    if not isinstance(epoch, dict):
        return metrics

    # 提取結果
    results = epoch.get("results", epoch.get("result", {}))
    if isinstance(results, dict):
        metrics["total_profit_pct"] = results.get("profit_total_pct", results.get("profit_total"))
        metrics["total_profit_abs"] = results.get("profit_total_abs")
        metrics["trades"] = results.get("total_trades", results.get("trades"))
        metrics["win_rate"] = results.get("winrate", results.get("win_rate"))
        metrics["max_drawdown"] = results.get("max_drawdown", results.get("max_drawdown_account"))
        metrics["profit_factor"] = results.get("profit_factor")

    # 提取損失/目標值
    metrics["objective"] = epoch.get("loss", epoch.get("objective"))

    # 提取最佳參數
    params = epoch.get("params", epoch.get("params_details", {}))
    if isinstance(params, dict):
        # params_details 是 {key: {value: ...}} 格式
        for k, v in params.items():
            if isinstance(v, dict) and "value" in v:
                metrics["best_parameters"][k] = v["value"]
            elif isinstance(v, (int, float, str)):
                metrics["best_parameters"][k] = v
        if not metrics["best_parameters"]:
            # 嘗試直接從 epoch 取得
            for k, v in epoch.items():
                if k not in ("results", "result", "loss", "objective", "params", "params_details",
                             "epoch", "is_initial_point", "is_best"):
                    if isinstance(v, (int, float, str)):
                        metrics["best_parameters"][k] = v

    # 嘗試從 trades 陣列計算 Sharpe/Sortino
    trades_list = epoch.get("trades", [])
    if not trades_list:
        trades_list = results.get("trades", []) if isinstance(results, dict) else []

    if isinstance(trades_list, list) and len(trades_list) > 0:
        # 從 trades 計算
        profits = []
        for t in trades_list:
            if isinstance(t, dict):
                p = t.get("profit_ratio", t.get("profit", 0))
                if p is not None:
                    profits.append(float(p))

        if profits:
            import statistics
            import math

            mean_p = statistics.mean(profits) if len(profits) > 0 else 0
            std_p = statistics.stdev(profits) if len(profits) > 1 else 1e-10

            if std_p > 0:
                metrics["sharpe_ratio"] = mean_p / std_p * math.sqrt(len(profits))

            # Sortino: 只算負收益的標準差
            negative = [p for p in profits if p < 0]
            if negative and len(negative) > 1:
                downside_std = statistics.stdev(negative)
                if downside_std > 0:
                    metrics["sortino_ratio"] = mean_p / downside_std * math.sqrt(len(profits))
            elif negative:
                metrics["sortino_ratio"] = 0.0

    return metrics


def format_metric(value, fmt=".2%", default="N/A"):
    """格式化指標值"""
    if value is None:
        return default
    if fmt == "d":
        # 'd' format only works with integers — convert floats safely
        return f"{int(value):d}"
    if isinstance(value, float):
        return f"{value * 100:.2f}%" if fmt.endswith("%") else f"{value:{fmt}}"
    if isinstance(value, int):
        return f"{value:{fmt}}"
    return str(value)


def append_to_tracker(strategy, metrics, compare_mode=False):
    """將分析結果 append 到 iteration_tracker.md"""
    if not TRACKER_FILE.exists():
        print(f"⚠️  找不到 tracker: {TRACKER_FILE}", file=sys.stderr)
        return

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    entry = f"""
### {strategy} - Analysis @ {date_str}
- **日期**: {date_str}
- **分析時間**: {now.strftime('%H:%M:%S')}
- **結果**:
  - 總利潤: {format_metric(metrics.get('total_profit_pct'), '.2%')}
  - 交易數: {format_metric(metrics.get('trades'), 'd', 'N/A')}
  - 勝率: {format_metric(metrics.get('win_rate'), '.1%')}
  - 最大回撤: {format_metric(metrics.get('max_drawdown'), '.2%')}
  - Sharpe: {format_metric(metrics.get('sharpe_ratio'), '.3f')}
  - Sortino: {format_metric(metrics.get('sortino_ratio'), '.3f')}
  - Profit Factor: {format_metric(metrics.get('profit_factor'), '.3f')}
  - Objective: {format_metric(metrics.get('objective'), '.5f')}
"""

    if metrics.get("best_parameters"):
        entry += "- **最佳參數**:\n"
        for k, v in metrics["best_parameters"].items():
            entry += f"  - {k}: {v}\n"

    entry += "- **狀態**: ✅ 已分析\n"

    if compare_mode:
        entry += "- **比較模式**: 已啟用 (跨迭代比較)\n"

    # Append to tracker
    with open(TRACKER_FILE, "a") as f:
        f.write(entry)

    print(f"✅ 已 append 到 {TRACKER_FILE}")


def print_report(strategy, metrics, compare_mode=False):
    """列印分析報告"""
    print()
    print("=" * 60)
    print(f"  GA 迭代分析報告: {strategy}")
    print("=" * 60)
    print(f"  總利潤:         {format_metric(metrics.get('total_profit_pct'), '.2%')}")
    print(f"  絕對利潤:       {format_metric(metrics.get('total_profit_abs'), '.4f')}")
    print(f"  交易數:         {format_metric(metrics.get('trades'), 'd')}")
    print(f"  勝率:           {format_metric(metrics.get('win_rate'), '.1%')}")
    print(f"  最大回撤:       {format_metric(metrics.get('max_drawdown'), '.2%')}")
    print(f"  Sharpe Ratio:   {format_metric(metrics.get('sharpe_ratio'), '.3f')}")
    print(f"  Sortino Ratio:  {format_metric(metrics.get('sortino_ratio'), '.3f')}")
    print(f"  Profit Factor:  {format_metric(metrics.get('profit_factor'), '.3f')}")
    print(f"  Objective:      {format_metric(metrics.get('objective'), '.5f')}")
    print("-" * 60)

    if metrics.get("best_parameters"):
        print("  最佳參數:")
        for k, v in metrics["best_parameters"].items():
            print(f"    {k}: {v}")
        print("-" * 60)

    if compare_mode:
        print("  🔍 比較模式已啟用 — 可與先前迭代對比")
        print("-" * 60)

    print()


def main():
    parser = argparse.ArgumentParser(
        description="數學策略 GA 迭代結果分析器 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python3 analyze_results.py --strategy=PolyReg_Adaptive_v2
  python3 analyze_results.py --strategy=nsgaii_bb_rpb_tsl_bi --compare
  python3 analyze_results.py --strategy=PolyReg_Adaptive_v2 --hyperopt-filename=results.fthypt
        """,
    )

    parser.add_argument(
        "--strategy", "-s",
        type=str,
        required=True,
        help="策略名稱 (如 PolyReg_Adaptive_v2)",
    )
    parser.add_argument(
        "--compare", "-c",
        action="store_true",
        help="啟用跨迭代比較模式",
    )
    parser.add_argument(
        "--hyperopt-filename",
        type=str,
        default=None,
        help="指定 hyperopt 檔案路徑 (預設: 自動尋找最新)",
    )
    parser.add_argument(
        "--no-append",
        action="store_true",
        help="不 append 到 iteration_tracker.md",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式輸出結果",
    )

    args = parser.parse_args()
    strategy = args.strategy

    # 尋找 hyperopt 檔案
    hyperopt_file = args.hyperopt_filename
    if not hyperopt_file:
        latest = find_latest_hyperopt_file(strategy)
        if latest:
            hyperopt_file = str(latest)
            print(f"📁 使用最新結果: {hyperopt_file}")
        else:
            print(f"⚠️  找不到 {strategy} 的 hyperopt 結果檔案")
            print(f"   搜尋目錄: {HYPEROPT_RESULTS_DIR}")
            print(f"   提示: 先執行 GA 迭代產生結果，或使用 --hyperopt-filename 指定檔案")
            sys.exit(1)
    else:
        # 如果是相對路徑，嘗試在使用者目錄找
        if not os.path.isabs(hyperopt_file):
            candidate = HYPEROPT_RESULTS_DIR / hyperopt_file
            if candidate.exists():
                hyperopt_file = str(candidate)
            else:
                print(f"⚠️  找不到指定檔案: {hyperopt_file}")
                sys.exit(1)

    print(f"🔍 分析策略: {strategy}")
    print(f"📄 Hyperopt 檔案: {hyperopt_file}")

    # 執行 hyperopt-show
    print("⏳ 執行 hyperopt-show --best --print-json ...")
    data = run_hyperopt_show(strategy, hyperopt_filename=hyperopt_file)

    if data is None:
        print("❌ 無法取得 hyperopt 結果")
        print("   請確認 freqtrade 可正常執行且超參數結果檔案存在")
        sys.exit(1)

    # 提取指標
    metrics = extract_metrics_from_json(data)

    if args.json:
        print(json.dumps(metrics, indent=2, default=str))
    else:
        print_report(strategy, metrics, compare_mode=args.compare)

    # Append to tracker
    if not args.no_append:
        append_to_tracker(strategy, metrics, compare_mode=args.compare)


if __name__ == "__main__":
    main()
