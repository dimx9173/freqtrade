#!/usr/bin/env python3
"""
數學約束驗證器 v1.0

根據數學驗證結果 (SNR≈0.02、degree≤2、Ridge、預測收益率非方向、BIC、滾動窗口、多TF)
檢查策略程式碼是否遵守這些數學鐵律。

使用方式:
    python3 constraint_validator.py --strategy=MultiTFPolyReg_v1
    python3 constraint_validator.py --strategy=PolyReg_Adaptive_v2
    python3 constraint_validator.py --strategy=Adaptive_Scalp_v2 --verbose
    python3 constraint_validator.py --list  # 列出所有策略並驗證
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path


# ---- 路徑設定 ----
HOME = Path(os.environ.get("HOME", "/home/brian"))
MATH_BASED_DIR = HOME / "freqtrade/user_data/strategies/math_based"


# ---- 數學鐵律定義 ----
CONSTRAINTS = {
    "degree_le_2": {
        "id": "LAW-01",
        "name": "degree ≤ 2",
        "severity": "HARD",
        "description": "多項式 degree 必須 ≤ 2。高次多項式在 SNR≈0.02 下必然 overfit。",
        "check": "check_degree_le_2",
    },
    "use_ridge": {
        "id": "LAW-02",
        "name": "使用 Ridge 正則化",
        "severity": "HARD",
        "description": "必須使用 Ridge (L2) 而非 Lasso (L1)。Lasso 在極低 SNR 下會錯誤地將係數歸零。",
        "check": "check_use_ridge",
    },
    "predict_returns": {
        "id": "LAW-03",
        "name": "預測收益率 (連續值)",
        "severity": "SOFT",
        "description": "預測目標應為連續收益率，非二元方向分類。方向分類損失資訊。",
        "check": "check_predict_returns",
    },
    "use_rolling_window": {
        "id": "LAW-04",
        "name": "使用滾動窗口訓練",
        "severity": "SOFT",
        "description": "應使用滾動窗口而非全局擬合 (expand)。金融時間序列非平穩。",
        "check": "check_use_rolling_window",
    },
    "multi_tf": {
        "id": "LAW-05",
        "name": "多 TF 多元編碼",
        "severity": "SOFT",
        "description": "應使用多時間框架特徵。Wavelet MRA 正交分解保證獨立性。",
        "check": "check_multi_tf",
    },
    "snr_aware_bounds": {
        "id": "LAW-06",
        "name": "SNR-aware 預期邊界",
        "severity": "SOFT",
        "description": "基於 SNR≈0.02，預期 Sharpe ≤ 0.4，超過則可能 overfit。",
        "check": "check_snr_aware_bounds",
    },
}


def find_strategy_file(strategy_name):
    """尋找策略檔案"""
    # 先在子目錄找
    for subdir in MATH_BASED_DIR.iterdir():
        if subdir.is_dir() and subdir.name not in ("ga_framework", "__pycache__"):
            candidate = subdir / f"{strategy_name}.py"
            if candidate.exists():
                return candidate

    # 再在頂層找
    candidate = MATH_BASED_DIR / f"{strategy_name}.py"
    if candidate.exists():
        return candidate

    return None


def list_all_strategies():
    """列出所有策略"""
    strategies = []

    # 子目錄中的
    for subdir in sorted(MATH_BASED_DIR.iterdir()):
        if subdir.is_dir() and subdir.name not in ("ga_framework", "__pycache__"):
            for pyfile in sorted(subdir.glob("*.py")):
                strategies.append(pyfile)

    # 頂層的
    for pyfile in sorted(MATH_BASED_DIR.glob("*.py")):
        if pyfile not in strategies:
            strategies.append(pyfile)

    return strategies


def read_strategy_source(filepath):
    """讀取策略原始碼"""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def parse_strategy_ast(source):
    """解析策略 AST"""
    try:
        return ast.parse(source)
    except SyntaxError as e:
        print(f"  ⚠️  AST 解析失敗: {e}")
        return None


# ---- 各項檢查 ----

def check_degree_le_2(source, ast_tree):
    """
    檢查 degree 參數是否 ≤ 2。
    尋找模式:
      - degree = IntParameter(..., default=2)  → 檢查 max
      - degree = DecimalParameter(..., default=2.0)
      - PolynomialFeatures(degree=...)
      - np.polyfit(..., deg=...)
    """
    violations = []
    notes = []

    if ast_tree is None:
        violations.append("無法解析 AST，跳過 degree 檢查")
        return violations, notes

    degree_maxes = []
    degree_uses = []

    for node in ast.walk(ast_tree):
        # 找 degree = IntParameter(low, high, ...) 或 DecimalParameter
        if isinstance(node, ast.Assign):
            for target in node.targets if isinstance(node.targets, list) else [node.targets]:
                if isinstance(target, ast.Name) and target.id == "degree":
                    if isinstance(node.value, ast.Call):
                        func = node.value
                        func_name = ""
                        if isinstance(func.func, ast.Name):
                            func_name = func.func.id
                        elif isinstance(func.func, ast.Attribute):
                            func_name = func.func.attr

                        if func_name in ("IntParameter", "DecimalParameter"):
                            # 第二個參數是 max
                            args = func.args
                            if len(args) >= 2:
                                try:
                                    degree_max = ast.literal_eval(args[1])
                                    degree_maxes.append(degree_max)
                                except (ValueError, TypeError):
                                    notes.append(f"degree 參數使用動態值，無法靜態分析")
                                    pass

        # 找 PolynomialFeatures(degree=N)
        if isinstance(node, ast.Call):
            kw = {}
            for kwarg in node.keywords:
                if kwarg.arg == "degree":
                    try:
                        degree_uses.append(ast.literal_eval(kwarg.value))
                    except (ValueError, TypeError):
                        pass

            # 檢查是否是 PolynomialFeatures(...)
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name == "PolynomialFeatures":
                for kwarg in node.keywords:
                    if kwarg.arg == "degree":
                        try:
                            val = ast.literal_eval(kwarg.value)
                            degree_uses.append(val)
                        except (ValueError, TypeError):
                            pass

    # 評估
    all_degrees = degree_maxes + degree_uses
    if not all_degrees:
        notes.append("未找到 degree 參數定義 — 可能不是多項式策略")
    else:
        for d in all_degrees:
            if d > 2:
                violations.append(
                    f"degree={d} 超過上限 2。在 SNR≈0.02 下高次多項式必然 overfit。"
                )
            elif d == 2:
                notes.append(f"degree={d}，符合約束 (≤2)")
            else:
                notes.append(f"degree={d}，符合約束 (≤2)")

    return violations, notes


def check_use_ridge(source, ast_tree):
    """檢查是否使用 Ridge 正則化"""
    violations = []
    notes = []

    # 文字搜尋
    uses_ridge = bool(re.search(r'Ridge\b', source))
    uses_lasso = bool(re.search(r'Lasso\b', source))
    uses_sklearn_linear = bool(re.search(r'from sklearn\.linear_model import', source))

    if uses_ridge:
        notes.append("✅ 使用 Ridge 正則化 (sklearn.linear_model.Ridge)")
    elif uses_lasso:
        violations.append("❌ 使用 Lasso (L1) 正則化。在極低 SNR 下 Lasso 會錯誤地將係數歸零。應改用 Ridge (L2)。")
    elif uses_sklearn_linear:
        notes.append("⚠️  匯入了 sklearn.linear_model 但未明確使用 Ridge")
    else:
        # 可能是非多項式策略，不需 Ridge
        notes.append("ℹ️  未使用 sklearn.linear_model (可能非多項式策略，跳過)")

    # 檢查是否同時有自訂正則化參數 alpha
    has_alpha = bool(re.search(r'alpha\s*=\s*(?:DecimalParameter|RealParameter|IntParameter)', source))
    if has_alpha and uses_ridge:
        notes.append("✅ Ridge alpha 參數可供 GA 優化")

    return violations, notes


def check_predict_returns(source, ast_tree):
    """檢查預測目標是收益率 (連續值) 還是方向 (二元值)"""
    violations = []
    notes = []

    # 文字特徵搜尋
    returns_patterns = [
        r'log_return', r'pct_change', r'\.pct_change\(\)',
        r'future_returns', r'next_return', r'return\s*[=:]',
        r'predict.*return', r'regression', r'predict\(.*\)', r'Ridge\(',
    ]
    direction_patterns = [
        r'direction', r'classification', r'label', r'up_down',
        r'np\.sign\(', r'classify', r'LogisticRegression',
        r'predict_proba', r'accuracy_score',
    ]

    returns_hits = sum(1 for p in returns_patterns if re.search(p, source, re.IGNORECASE))
    direction_hits = sum(1 for p in direction_patterns if re.search(p, source, re.IGNORECASE))

    if returns_hits > 0 and direction_hits == 0:
        notes.append("✅ 預測目標為連續收益率")
    elif direction_hits > 0 and returns_hits == 0:
        # 如果使用 Ridge 但同時有 direction 關鍵字 → 可能是混合策略
        if re.search(r'Ridge\b', source):
            notes.append("⚠️  檢測到 Ridge + direction 關鍵字 — 可能是混合預測")
        else:
            violations.append(
                "預測目標似乎是方向分類 (二元值)。"
                "在 SNR≈0.02 下，方向分類損失微弱信號的資訊量。建議預測連續收益率。"
            )
    elif returns_hits > 0 and direction_hits > 0:
        notes.append("⚠️  檢測到收益率和方向特徵 — 策略可能混合兩種模式")
    else:
        notes.append("ℹ️  無法判斷預測目標類型 (未檢測到明確的收益率或方向計算)")

    return violations, notes


def check_use_rolling_window(source, ast_tree):
    """檢查是否使用滾動窗口訓練"""
    violations = []
    notes = []

    rolling_patterns = [
        r'rolling\(window', r'\.rolling\(', r'rolling_window',
        r'walk_forward', r'expanding_window', r'sliding_window',
        r'time_series_split', r'TimeSeriesSplit',
    ]
    expand_patterns = [
        r'\.fit\(.*\)\s*$',  # 單次 fit (無窗口)
        r'cross_val_score',
    ]

    rolling_hits = sum(1 for p in rolling_patterns if re.search(p, source, re.IGNORECASE))

    # 檢查是否有 index-based 滾動窗口（train_start / train_end / retrain_interval）
    has_train_start = bool(re.search(r'train_start\b', source))
    has_train_end = bool(re.search(r'train_end\b', source))
    has_retrain_interval = bool(re.search(r'retrain_interval\b', source))
    has_window_variable = bool(re.search(
        r'(?:window|train_window)\s*[:=]\s*(?:IntParameter|DecimalParameter|RealParameter|\d+)',
        source,
    ))

    index_based_hits = sum([has_train_start, has_train_end, has_retrain_interval, has_window_variable])

    # 也檢查 populate_indicators 中是否有 rolling 相關
    has_populate = 'populate_indicators' in source

    if rolling_hits >= 2:
        notes.append("✅ 使用滾動窗口 (檢測到 rolling/walk_forward 相關程式碼)")
    elif index_based_hits >= 2:
        notes.append("✅ 使用 index-based 滾動窗口 (train_start/train_end/retrain_interval)")
    elif rolling_hits == 1:
        notes.append("⚠️  檢測到少量滾動窗口相關程式碼，可能不完整")
    elif index_based_hits == 1:
        notes.append("⚠️  檢測到 index-based 窗口片段，可能不完整")
    elif has_populate:
        notes.append("ℹ️  未檢測到明確的滾動窗口訓練。建議使用 walk-forward 而非全局擬合。")
    else:
        notes.append("ℹ️  無法判斷是否使用滾動窗口")

    # 檢查是否有明確的 train/test split
    if re.search(r'(train|test)_(start|end|split)', source):
        notes.append("✅ 檢測到 train/test 分割")

    return violations, notes


def check_multi_tf(source, ast_tree):
    """檢查多 TF 支援"""
    violations = []
    notes = []

    # 尋找 informative_pairs 或 merge_informative_pair
    has_informative = bool(re.search(r'informative_', source))
    has_multiple_tf = bool(re.search(r'(?:timeframe|tf)\s*=\s*[\"\'](?:5m|15m|1h|4h)', source))

    # 尋找多 TF 相關的參數
    tf_patterns = re.findall(r'[\"\'](5m|15m|30m|1h|4h|1d)[\"\']', source)
    unique_tfs = set(tf_patterns)

    if has_informative:
        notes.append("✅ 使用 informative_pairs (多 TF 支援)")
        if len(unique_tfs) >= 2:
            notes.append(f"✅ 檢測到 {len(unique_tfs)} 個時間框架: {', '.join(sorted(unique_tfs))}")
    elif len(unique_tfs) >= 2:
        notes.append(f"✅ 檢測到多時間框架: {', '.join(sorted(unique_tfs))}")
    else:
        notes.append("ℹ️  未檢測到多 TF 支援。建議使用 Wavelet MRA 多 TF 編碼。")

    return violations, notes


def check_snr_aware_bounds(source, ast_tree):
    """檢查 SNR-aware 預期邊界"""
    violations = []
    notes = []

    # 尋找 stoploss, roi, trailing 等設定
    # 基於 SNR≈0.02，預期 Sharpe ≤ 0.4，年化收益 ≤ 20%

    # 檢查是否有過度樂觀的 stoploss (< -0.5% → 太寬)
    stoploss_match = re.search(r'stoploss\s*=\s*(-?[\d.]+)', source)
    if stoploss_match:
        sl_val = float(stoploss_match.group(1))
        if sl_val < -0.10:
            violations.append(
                f"stoploss={sl_val} 過寬。在 SNR≈0.02 下單筆虧損 >10% 不合理。"
            )
        elif sl_val > -0.01:
            notes.append(f"⚠️  stoploss={sl_val} 可能過緊，會導致頻繁止損")
        else:
            notes.append(f"✅ stoploss={sl_val}，在合理範圍")

    # 檢查 ROI 是否過於樂觀
    roi_match = re.search(r'minimal_roi\s*=\s*\{([^}]+)\}', source)
    if roi_match:
        roi_content = roi_match.group(1)
        roi_values = re.findall(r'[\"\']?\d+[\"\']?\s*:\s*(-?[\d.]+)', roi_content)
        if roi_values:
            max_roi = max(abs(float(v)) for v in roi_values)
            if max_roi > 0.20:
                violations.append(
                    f"ROI 最高目標 {max_roi:.1%} 過於樂觀。"
                    f"在 SNR≈0.02 下預期收益應 ≤ 20%。"
                )
            else:
                notes.append(f"✅ ROI 設定合理 (最大 {max_roi:.1%})")

    # 檢查 Sharpe 相關的限制或懲罰
    has_sharpe_penalty = bool(re.search(r'sharpe.*(?:penal|cap|limit|max|bound)', source, re.IGNORECASE))
    if has_sharpe_penalty:
        notes.append("✅ 策略包含 Sharpe 上限/懲罰機制")
    else:
        notes.append("ℹ️  未檢測到 Sharpe 上限機制。建議加入 SNR-aware 懲罰 (Sharpe > 0.4 → 懲罰)。")

    return violations, notes


# ---- 檢查調度 ----

CHECK_MAP = {
    "check_degree_le_2": check_degree_le_2,
    "check_use_ridge": check_use_ridge,
    "check_predict_returns": check_predict_returns,
    "check_use_rolling_window": check_use_rolling_window,
    "check_multi_tf": check_multi_tf,
    "check_snr_aware_bounds": check_snr_aware_bounds,
}


def validate_strategy(strategy_name, source, ast_tree, verbose=False):
    """執行所有約束檢查"""
    results = []

    for key, constraint in CONSTRAINTS.items():
        check_func = CHECK_MAP.get(constraint["check"])
        if check_func is None:
            continue

        violations, notes = check_func(source, ast_tree)
        passed = len(violations) == 0

        results.append({
            "constraint_id": constraint["id"],
            "name": constraint["name"],
            "severity": constraint["severity"],
            "passed": passed,
            "violations": violations,
            "notes": notes,
        })

    return results


def print_validation_report(strategy_name, filepath, results, verbose=False):
    """列印驗證報告"""
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = sum(1 for r in results if not r["passed"])
    hard_failed = sum(1 for r in results if not r["passed"] and r["severity"] == "HARD")
    soft_failed = sum(1 for r in results if not r["passed"] and r["severity"] == "SOFT")

    print()
    print("=" * 70)
    print(f"  數學約束驗證報告: {strategy_name}")
    print("=" * 70)
    print(f"  策略檔案: {filepath}")
    print(f"  總約束數: {len(results)}")
    print(f"  ✅ 通過: {passed_count}")
    print(f"  ❌ 失敗: {failed_count} (HARD: {hard_failed}, SOFT: {soft_failed})")
    print("-" * 70)

    for r in results:
        icon = "✅" if r["passed"] else "❌"
        sev = f"[{r['severity']}]"
        print(f"  {icon} {sev} {r['constraint_id']}: {r['name']}")

        if verbose or not r["passed"]:
            for v in r["violations"]:
                print(f"       ❌ {v}")
            for n in r["notes"]:
                prefix = "       ℹ️ " if r["passed"] else "       ⚠️ "
                print(f"{prefix}{n}")
        elif r["notes"] and verbose:
            for n in r["notes"]:
                print(f"       ℹ️ {n}")

    print("-" * 70)

    # 總結
    if failed_count == 0:
        print("  🎉 所有數學約束通過！策略符合理論設計。")
    elif hard_failed > 0:
        print(f"  ⛔ {hard_failed} 個硬約束失敗 — 策略違反數學鐵律，建議修正後再運行 GA。")
    else:
        print(f"  ⚠️  {soft_failed} 個軟約束未通過 — 策略可用但建議改進。")

    print("=" * 70)
    print()

    return hard_failed == 0


def main():
    parser = argparse.ArgumentParser(
        description="數學約束驗證器 — 檢查策略是否遵守數學鐵律",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
數學鐵律:
  LAW-01 [HARD]  degree ≤ 2
  LAW-02 [HARD]  使用 Ridge (非 Lasso)
  LAW-03 [SOFT]  預測收益率 (非方向)
  LAW-04 [SOFT]  使用滾動窗口
  LAW-05 [SOFT]  多 TF 支援
  LAW-06 [SOFT]  SNR-aware 邊界

範例:
  python3 constraint_validator.py --strategy=PolyReg_Adaptive_v2
  python3 constraint_validator.py --strategy=Adaptive_Scalp_v2 --verbose
  python3 constraint_validator.py --list
        """,
    )

    parser.add_argument(
        "--strategy", "-s",
        type=str,
        help="策略名稱 (如 PolyReg_Adaptive_v2)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有策略並驗證",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細輸出 (顯示通過項目的 notes)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式輸出結果",
    )

    args = parser.parse_args()

    if args.list:
        strategies = list_all_strategies()
        if not strategies:
            print("❌ 找不到任何策略")
            sys.exit(1)

        print(f"找到 {len(strategies)} 個策略，開始驗證...\n")

        all_passed = True
        for strat_file in strategies:
            strat_name = strat_file.stem
            source = read_strategy_source(strat_file)
            ast_tree = parse_strategy_ast(source)
            results = validate_strategy(strat_name, source, ast_tree, verbose=args.verbose)
            passed = print_validation_report(strat_name, strat_file, results, verbose=args.verbose)
            if not passed:
                all_passed = False

        if all_passed:
            print("✅ 所有策略通過數學約束驗證！")
        else:
            print("⚠️  部分策略未通過驗證，請檢視上方報告。")

    elif args.strategy:
        filepath = find_strategy_file(args.strategy)
        if filepath is None:
            print(f"❌ 找不到策略: {args.strategy}")
            print(f"   搜尋路徑: {MATH_BASED_DIR}")
            sys.exit(1)

        source = read_strategy_source(filepath)
        ast_tree = parse_strategy_ast(source)
        results = validate_strategy(args.strategy, source, ast_tree, verbose=args.verbose)

        if args.json:
            import json
            output = {
                "strategy": args.strategy,
                "file": str(filepath),
                "results": [
                    {
                        "id": r["constraint_id"],
                        "name": r["name"],
                        "severity": r["severity"],
                        "passed": r["passed"],
                        "violations": r["violations"],
                        "notes": r["notes"] if args.verbose else [],
                    }
                    for r in results
                ],
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            passed = print_validation_report(args.strategy, filepath, results, verbose=args.verbose)
            sys.exit(0 if passed else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
