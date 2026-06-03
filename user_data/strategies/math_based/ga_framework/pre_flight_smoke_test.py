#!/usr/bin/env python3
"""
Pre-Flight Smoke Test for Math-Based GA Framework.

Runs BEFORE a full backtest/hyperopt to catch:
  - Entry conditions too strict (too few signals)
  - Over-trading (excessive signals)
  - Known pitfalls (Negative KB) via AST scanning

Exit Codes:
  0 = All clear
  1 = Generic error / --strict mode hit a WARN
  2 = Too few entry signals (< 15/month)
  3 = Over-trading (> 100/month)
  4 = DANGEROUS negative KB pattern found

Usage:
  python3 pre_flight_smoke_test.py --strategy NAME --config PATH --timerange 202501-202503
  python3 pre_flight_smoke_test.py --strategy NAME --config PATH --timerange 202501-202503 --json
  python3 pre_flight_smoke_test.py --strategy NAME --config PATH --timerange 202501-202503 --strict
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Any

# ==============================================================================
# Path Resolution
# ==============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent  # ga_framework/
MATH_BASED_DIR = SCRIPT_DIR.parent  # math_based/
USER_DATA_DIR = MATH_BASED_DIR.parent.parent  # user_data/
FREQTRADE_ROOT = USER_DATA_DIR.parent  # ~/freqtrade/

_venv_bin = FREQTRADE_ROOT / ".venv" / "bin" / "freqtrade"
FREQTRADE_BIN = str(_venv_bin) if _venv_bin.exists() else "freqtrade"

# ==============================================================================
# ANSI Colors (matching run_ga.sh convention)
# ==============================================================================
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
PURPLE = "\033[0;35m"
NC = "\033[0m"

# ==============================================================================
# Exit Codes
# ==============================================================================
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_TOO_FEW = 2
EXIT_OVER_TRADING = 3
EXIT_DANGER_KB = 4

# ==============================================================================
# Negative KB Definitions
# ==============================================================================


class Severity:
    DANGER = "DANGER"
    WARN = "WARN"


class NegativeKBHit:
    __slots__ = ("kb_id", "severity", "title", "line_no", "code_snippet", "detail")

    def __init__(
        self,
        kb_id: str,
        severity: str,
        title: str,
        line_no: int = 0,
        code_snippet: str = "",
        detail: str = "",
    ):
        self.kb_id = kb_id
        self.severity = severity
        self.title = title
        self.line_no = line_no
        self.code_snippet = code_snippet
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {
            "kb_id": self.kb_id,
            "severity": self.severity,
            "title": self.title,
            "line_no": self.line_no,
            "code_snippet": self.code_snippet,
            "detail": self.detail,
        }


# ---- AST-based checks ----


def _find_assign_value(tree: ast.AST, var_name: str) -> Any:
    """Walk AST to find module-level assignment value for var_name.
    Returns the ast.literal_eval value or None if not found."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        return None
    return None


def _has_function(tree: ast.AST, func_name: str) -> bool:
    """Check if a function/method with this name is defined anywhere in the tree.

    Note: uses ast.walk (recursive) so it finds methods inside ClassDef, not just
    top-level functions. This is essential for strategy checks (populate_* and
    leverage() are class methods, not module-level).
    Phase 1 review: previously used ast.iter_child_nodes which silently missed
    all in-class methods.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return True
    return False


def _count_functions_in_body(body: list[ast.stmt], func_name: str) -> int:
    """Count occurrences of function definition in a list of statements."""
    count = 0
    for node in body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            count += 1
    return count


def check_trailing_stop_conflict(source: str, tree: ast.AST) -> list[NegativeKBHit]:
    """
    NKB-003: trailing_stop=True + use_custom_stoploss=True conflict.
    use_custom_stoploss=True completely overrides trailing_stop settings.
    """
    trailing_stop = _find_assign_value(tree, "trailing_stop")
    use_custom = _find_assign_value(tree, "use_custom_stoploss")

    if trailing_stop is True and use_custom is True:
        # Find the line numbers
        line_ts = _find_line_no(source, r"^\s*trailing_stop\s*=\s*True")
        line_cs = _find_line_no(source, r"^\s*use_custom_stoploss\s*=\s*True")
        detail = (
            "use_custom_stoploss=True renders trailing_stop settings ineffective. "
            "Set trailing_stop=False or remove use_custom_stoploss."
        )
        return [
            NegativeKBHit(
                kb_id="NKB-003",
                severity=Severity.WARN,
                title="trailing_stop=True + use_custom_stoploss=True (redundant)",
                line_no=line_ts,
                code_snippet=_get_line(source, line_ts),
                detail=detail,
            )
        ]
    return []


def check_exit_trend_without_shift(tree: ast.AST, source: str) -> list[NegativeKBHit]:
    """
    NKB-001: populate_exit_trend sets exit_long / exit_short WITHOUT .shift(1)
    crossover logic. This causes LEVEL-triggered oscillation (trades/year > 5000).
    """
    hits: list[NegativeKBHit] = []

    # Walk into class bodies (populate_exit_trend is a method, not a top-level
    # function). Phase 1 review fix: previously used ast.iter_child_nodes which
    # silently missed in-class methods.
    def _iter_functions(node: ast.AST):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield child
            elif isinstance(child, ast.ClassDef):
                yield from _iter_functions(child)

    for node in _iter_functions(tree):
        if node.name not in ("populate_exit_trend",):
            continue

        # Walk the function body looking for assignments to exit_long / exit_short
        func_source_lines = source.splitlines()
        func_start = node.lineno
        func_end = node.end_lineno if node.end_lineno else len(func_source_lines)

        # Check if the function body has any .shift() calls
        func_text = "\n".join(func_source_lines[func_start:func_end])
        has_shift = ".shift(" in func_text

        # Check if it sets exit_long or exit_short
        sets_exit = bool(re.search(r"exit_(?:long|short)", func_text))

        # Only flag if it sets exit signals without shift
        if sets_exit and not has_shift:
            # Also check if it explicitly sets to 0 (which is fine — controlled by custom_exit)
            sets_zero = bool(re.search(r"""exit_(?:long|short)["']?\s*\]\s*=\s*0""", func_text))
            if sets_zero:
                # Setting to 0 is intentional — no LEVEL bug
                continue

            hits.append(
                NegativeKBHit(
                    kb_id="NKB-001",
                    severity=Severity.DANGER,
                    title="populate_exit_trend without .shift(1) crossover (LEVEL oscillation risk)",
                    line_no=node.lineno,
                    code_snippet=_get_line(source, node.lineno),
                    detail=(
                        "exit_long/exit_short set without .shift(1) crossover detection. "
                        "This causes every candle that meets the condition to trigger, "
                        "resulting in 5000+ trades/year and catastrophic losses. "
                        "Use (condition) & (~condition.shift(1)) pattern."
                    ),
                )
            )
        break

    return hits


def check_rsi_destructive_filter(source: str, tree: ast.AST) -> list[NegativeKBHit]:
    """
    NKB-002: rsi < 44 or rsi < 45 used as entry gate → destructive filter.
    Returns early from populate_entry_trend when RSI is below threshold,
    preventing ALL downstream entry conditions from executing.
    """
    hits: list[NegativeKBHit] = []
    pattern = re.compile(r"rsi.*?<\s*(4[0-9])", re.IGNORECASE)

    for i, line in enumerate(source.splitlines(), start=1):
        match = pattern.search(line)
        if match:
            threshold = int(match.group(1))
            if 40 <= threshold <= 49:
                hits.append(
                    NegativeKBHit(
                        kb_id="NKB-002",
                        severity=Severity.WARN,
                        title=f"rsi < {threshold} used in entry (destructive filter)",
                        line_no=i,
                        code_snippet=line.strip(),
                        detail=(
                            f"RSI < {threshold} acts as a hard gate — if RSI is below {threshold}, "
                            "ALL entry conditions are skipped. This is a known cause of 0 trades. "
                            "Consider removing or using rsi < 30 (extreme oversold) instead."
                        ),
                    )
                )
    return hits


def check_leverage_missing_in_futures(
    source: str, tree: ast.AST, trading_mode: str
) -> list[NegativeKBHit]:
    """
    NKB-006: In futures mode, leverage() method should be explicitly defined.
    Missing leverage() with futures can lead to default 1x silently.
    """
    if trading_mode != "futures":
        return []

    has_leverage = _has_function(tree, "leverage")
    if not has_leverage:
        return [
            NegativeKBHit(
                kb_id="NKB-006",
                severity=Severity.WARN,
                title="leverage() method missing in futures mode",
                line_no=0,
                code_snippet="",
                detail=(
                    "Running in futures mode without an explicit leverage() method. "
                    "Default is 1.0x — ensure this is intentional."
                ),
            )
        ]
    return []


def check_interface_version_mismatch(source: str, tree: ast.AST) -> list[NegativeKBHit]:
    """
    NKB-005: INTERFACE_VERSION mismatch with the API style used in the strategy.
    - INTERFACE_VERSION = 2  → uses populate_buy_trend / populate_sell_trend (v2 API)
    - INTERFACE_VERSION = 3  → uses populate_entry_trend / populate_exit_trend (v3 API)

    A mismatch silently produces 0 trades because freqtrade reads the wrong columns.
    Detected by checking INTERFACE_VERSION assignment vs presence of v2/v3 methods.
    """
    hits: list[NegativeKBHit] = []

    # Find INTERFACE_VERSION = N assignment
    interface_version = None
    iv_line = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "INTERFACE_VERSION":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                        interface_version = node.value.value
                        iv_line = node.lineno

    if interface_version is None:
        # No explicit version — freqtrade defaults to the v2/v3 of installed version.
        return []

    has_v2_buy = _has_function(tree, "populate_buy_trend")
    has_v2_sell = _has_function(tree, "populate_sell_trend")
    has_v3_entry = _has_function(tree, "populate_entry_trend")
    has_v3_exit = _has_function(tree, "populate_exit_trend")

    mismatch = False
    detail = ""
    if interface_version == 3 and (has_v2_buy or has_v2_sell) and not has_v3_entry:
        mismatch = True
        detail = (
            "INTERFACE_VERSION = 3 (v3 API expected) but strategy uses populate_buy_trend / "
            "populate_sell_trend (v2 API). freqtrade will SILENTLY skip entries → 0 trades."
        )
    elif interface_version == 2 and has_v3_entry and not has_v2_buy:
        mismatch = True
        detail = (
            "INTERFACE_VERSION = 2 (v2 API expected) but strategy uses populate_entry_trend "
            "(v3 API). freqtrade will SILENTLY skip entries → 0 trades."
        )

    if mismatch:
        hits.append(
            NegativeKBHit(
                kb_id="NKB-005",
                severity=Severity.DANGER,
                title=f"INTERFACE_VERSION={interface_version} mismatches API style used",
                line_no=iv_line,
                code_snippet=_get_line(source, iv_line),
                detail=detail,
            )
        )
    return hits


def _find_line_no(source: str, pattern: str) -> int:
    """Find first line number matching regex pattern."""
    for i, line in enumerate(source.splitlines(), start=1):
        if re.search(pattern, line):
            return i
    return 0


def _get_line(source: str, line_no: int) -> str:
    """Get a specific line from source by 1-based line number."""
    if line_no <= 0:
        return ""
    lines = source.splitlines()
    if line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


# ==============================================================================
# Strategy Discovery
# ==============================================================================


def find_strategy_file(strategy_name: str) -> Path | None:
    """Find the .py file for a strategy name, searching math_based/ recursively."""
    # 1. Search subdirectories (e.g., nsgaii_bb_rpb_tsl_bi/)
    for item in MATH_BASED_DIR.iterdir():
        if not item.is_dir():
            continue
        if item.name in ("ga_framework", "__pycache__"):
            continue
        candidate = item / f"{strategy_name}.py"
        if candidate.exists():
            return candidate

    # 2. Top-level
    candidate = MATH_BASED_DIR / f"{strategy_name}.py"
    if candidate.exists():
        return candidate

    # 3. Recursive deep search
    for py_file in MATH_BASED_DIR.rglob(f"{strategy_name}.py"):
        if "ga_framework" not in str(py_file) and "__pycache__" not in str(py_file):
            return py_file

    return None


# ==============================================================================
# Negative KB Scanner
# ==============================================================================


def scan_negative_kb(strategy_path: Path, trading_mode: str = "spot") -> list[NegativeKBHit]:
    """Run all negative KB checks on a strategy source file. Returns list of hits."""
    source = strategy_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [
            NegativeKBHit(
                kb_id="NKB-000",
                severity=Severity.DANGER,
                title=f"Strategy file has syntax error: {e}",
                line_no=e.lineno or 0,
                code_snippet="",
                detail=str(e),
            )
        ]

    hits: list[NegativeKBHit] = []
    hits.extend(check_trailing_stop_conflict(source, tree))
    hits.extend(check_exit_trend_without_shift(tree, source))
    hits.extend(check_rsi_destructive_filter(source, tree))
    hits.extend(check_leverage_missing_in_futures(source, tree, trading_mode))
    hits.extend(check_interface_version_mismatch(source, tree))
    return hits


# ==============================================================================
# Signal Counting
# ==============================================================================


def count_entry_signals(
    strategy_name: str, config_path: str, timerange_str: str
) -> tuple[int, str, dict[str, Any]]:
    """
    Load strategy + OHLCV data, compute entry signals, return (signal_count, pair, context).

    Returns:
        (count, pair_symbol, context_dict) where context contains metadata for reporting.
        count=0 means no entry signals found (could be 0 trades or error).
    """
    context: dict[str, Any] = {
        "pair": "",
        "timeframe": "",
        "total_candles": 0,
        "error": None,
    }

    try:
        # ---- Load config ----
        if not Path(config_path).exists():
            return 0, "", {**context, "error": f"Config file not found: {config_path}"}

        with open(config_path) as f:
            config = json.load(f)

        timeframe = config.get("timeframe", "5m")
        datadir = Path(config.get("datadir", str(USER_DATA_DIR / "data" / "binance")))
        context["timeframe"] = timeframe

        # Determine pairs to check
        exchange_config = config.get("exchange", {})
        pairs: list[str] = []
        if "pair_whitelist" in exchange_config:
            pairs = exchange_config["pair_whitelist"]
        elif "pair_blacklist" not in exchange_config:
            # Default: BTC/USDT — most strategies target BTC
            pairs = [
                "BTC/USDT:USDT" if "futures" in str(config.get("trading_mode", "")) else "BTC/USDT"
            ]

        if not pairs:
            context["error"] = "No pairs found in config"
            return 0, "", context

        pair = pairs[0]
        context["pair"] = pair

        # ---- Parse timerange ----
        # Accept formats: 202501-202503 (YYYYMM-YYYYMM) or 20250101-20250301 (YYYYMMDD-YYYYMMDD)
        timerange_match = re.match(r"(\d{6})-(\d{6,8})", timerange_str)
        if not timerange_match:
            context["error"] = f"Invalid timerange format: {timerange_str}"
            return 0, "", context

        start_raw, end_raw = timerange_match.groups()
        if len(start_raw) == 6:
            start = f"{start_raw}01"  # YYYYMM → YYYYMM01
        else:
            start = start_raw

        if len(end_raw) == 6:
            # End of month for YYYYMM → last day of month
            yr, mo = int(end_raw[:4]), int(end_raw[4:6])
            import calendar

            last_day = calendar.monthrange(yr, mo)[1]
            end = f"{end_raw}{last_day:02d}"
        else:
            end = end_raw

        context["timerange_parsed"] = f"{start}-{end}"

        # ---- Load OHLCV data ----
        # Wrap sys.path manipulation in try/finally to avoid leaking
        # FREQTRADE_ROOT into global import state (Phase 1 review BLOCKER #1).
        _orig_sys_path = sys.path.copy()
        try:
            sys.path.insert(0, str(FREQTRADE_ROOT))
            from freqtrade.configuration import TimeRange
            from freqtrade.data.history import load_pair_history
            from freqtrade.enums import CandleType
        finally:
            sys.path = _orig_sys_path

        trading_mode = config.get("trading_mode", "spot")
        candle_type = CandleType.FUTURES if trading_mode == "futures" else CandleType.SPOT

        timerange = TimeRange.parse_timerange(f"{start}-{end}")

        df = load_pair_history(
            pair=pair,
            timeframe=timeframe,
            datadir=datadir,
            timerange=timerange,
            fill_up_missing=False,
            drop_incomplete=False,
            candle_type=candle_type,
        )

        if df.empty:
            context["error"] = f"No OHLCV data found for {pair} in {timerange_str}"
            return 0, "", context

        context["total_candles"] = len(df)

        # ---- Load strategy ----
        strategy_file = find_strategy_file(strategy_name)
        if not strategy_file:
            context["error"] = f"Strategy file not found: {strategy_name}"
            return 0, "", context

        # Import strategy module dynamically
        spec = importlib.util.spec_from_file_location(strategy_name, strategy_file)
        if spec is None or spec.loader is None:
            context["error"] = f"Failed to load strategy module: {strategy_name}"
            return 0, "", context

        mod = importlib.util.module_from_spec(spec)
        sys.modules[strategy_name] = mod
        spec.loader.exec_module(mod)

        # Find IStrategy subclass
        strategy_cls = None
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                isinstance(attr, type)
                and hasattr(attr, "populate_entry_trend")
                and attr_name not in ("IStrategy", "HyperStrategyMixin")
            ):
                # Check it's a proper strategy subclass
                mro_names = [c.__name__ for c in attr.__mro__]
                if "IStrategy" in mro_names:
                    strategy_cls = attr
                    break

        if strategy_cls is None:
            context["error"] = f"No IStrategy subclass found in {strategy_name}.py"
            return 0, "", context

        # Build minimal config for strategy instantiation
        strategy_config = {
            "strategy": strategy_name,
            "timeframe": timeframe,
            "stake_currency": config.get("stake_currency", "USDT"),
            "dry_run": True,
            "exchange": {
                "name": exchange_config.get("name", "binance"),
                "key": "",
                "secret": "",
            },
            "trading_mode": trading_mode,
            "candle_type_def": candle_type,
            "runmode": "dry_run",
            "max_open_trades": config.get("max_open_trades", float("inf")),
            "stake_amount": config.get("stake_amount", "unlimited"),
            "minimal_roi": config.get("minimal_roi", {"0": 10.0}),
            "stoploss": config.get("stoploss", -0.10),
            "unfilledtimeout": config.get("unfilledtimeout", {}),
        }

        strategy = strategy_cls(strategy_config)

        # ---- Compute entry signals ----
        metadata = {"pair": pair}
        df_with_indicators = strategy.populate_indicators(df, metadata)
        df_with_signals = strategy.populate_entry_trend(df_with_indicators, metadata)

        # Count signals
        long_signals = int((df_with_signals.get("enter_long", 0) == 1).sum())
        short_signals = int((df_with_signals.get("enter_short", 0) == 1).sum())
        total_signals = long_signals + short_signals

        context["long_signals"] = long_signals
        context["short_signals"] = short_signals
        context["total_signals"] = total_signals

        return total_signals, pair, context

    except Exception as e:
        context["error"] = f"{type(e).__name__}: {e}"
        return 0, "", context


# ==============================================================================
# Timerange Parsing Helpers
# ==============================================================================


def parse_months_from_timerange(timerange_str: str) -> float | None:
    """Estimate months covered by a timerange string like 202501-202503."""
    # Group(4) capped at 2 digits to avoid the YYYYMMDD bug where "202501-20250315"
    # would have parsed group(4)="0315" → int("0315")=315 months (Phase 1 review
    # NEEDS-FIX #2). For day-granularity coverage, use count_entry_signals'
    # independent parser (which handles YYYYMMDD via calendar.monthrange).
    m = re.match(r"(\d{4})(\d{2})-(\d{4})(\d{2})$", timerange_str)
    if not m:
        return None
    y1, mo1 = int(m.group(1)), int(m.group(2))
    y2, mo2 = int(m.group(3)), int(m.group(4))
    return (y2 - y1) * 12 + (mo2 - mo1) + 1


# ==============================================================================
# Main
# ==============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-Flight Smoke Test — validates strategy before full GA run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exit Codes:
  0 = All clear
  1 = Error or --strict WARN
  2 = Too few entry signals
  3 = Over-trading (> 100/month)
  4 = DANGEROUS negative KB pattern

Examples:
  %(prog)s --strategy MyStrategy --config cfg.json --timerange 202501-202503
  %(prog)s --strategy MyStrategy --config cfg.json --timerange 202501-202503 --json
  %(prog)s --strategy MyStrategy --config cfg.json --timerange 202501-202503 --strict
        """,
    )
    parser.add_argument(
        "--strategy",
        "-s",
        type=str,
        required=True,
        help="Strategy class name (file must exist in math_based/)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        required=True,
        help="Freqtrade config JSON path",
    )
    parser.add_argument(
        "--timerange",
        "-t",
        type=str,
        required=True,
        help="Time range: YYYYMM-YYYYMM or YYYYMMDD-YYYYMMDD",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (machine-readable)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on ANY WARN (not just DANGEROUS)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--min-trades-per-month",
        type=float,
        default=15.0,
        help="Minimum trades per month threshold (default: 15)",
    )
    parser.add_argument(
        "--max-trades-per-month",
        type=float,
        default=100.0,
        help="Maximum trades per month threshold (default: 100)",
    )

    args = parser.parse_args()

    # ---- Find strategy file ----
    strategy_path = find_strategy_file(args.strategy)
    if strategy_path is None:
        msg = f"Strategy '{args.strategy}' not found in {MATH_BASED_DIR}"
        if args.json:
            print(json.dumps({"status": "ERROR", "error": msg}))
        else:
            print(f"{RED}❌ {msg}{NC}")
        return EXIT_ERROR

    if args.verbose:
        print(f"{GREEN}✅ Strategy file: {strategy_path}{NC}")

    # ---- Determine trading mode from config ----
    trading_mode = "spot"
    config_path = Path(args.config)
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            trading_mode = cfg.get("trading_mode", "spot")
        except (json.JSONDecodeError, OSError):
            pass

    # ---- Phase 1: Negative KB Scan ----
    if not args.json:
        print(f"{BLUE}🔍 Phase 1: Negative KB Scan{NC}")
        print("-" * 50)

    kb_hits = scan_negative_kb(strategy_path, trading_mode)

    if kb_hits and not args.json:
        for hit in kb_hits:
            prefix = (
                f"{RED}[{hit.severity}]{NC}"
                if hit.severity == Severity.DANGER
                else f"{YELLOW}[WARN]{NC}"
            )
            print(f"  {prefix} {hit.title}")
            if hit.line_no:
                print(f"    Line {hit.line_no}: {hit.code_snippet}")
            if args.verbose and hit.detail:
                print(f"    {hit.detail}")
        print()

    # ---- Phase 2: Signal Counting ----
    if not args.json:
        print(f"{BLUE}🔍 Phase 2: Entry Signal Counting{NC}")
        print("-" * 50)

    months = parse_months_from_timerange(args.timerange)
    if months is None:
        msg = f"Invalid timerange format: {args.timerange}"
        if args.json:
            print(json.dumps({"status": "ERROR", "error": msg}))
        else:
            print(f"{RED}❌ {msg}{NC}")
        return EXIT_ERROR

    signal_count, pair, ctx = count_entry_signals(args.strategy, args.config, args.timerange)

    if ctx.get("error"):
        if args.json:
            print(json.dumps({"status": "ERROR", "error": ctx["error"]}))
        else:
            print(f"{RED}❌ Signal counting failed: {ctx['error']}{NC}")
        return EXIT_ERROR

    signals_per_month = signal_count / months if months > 0 else 0
    min_threshold = args.min_trades_per_month * months
    max_threshold = args.max_trades_per_month * months

    if not args.json:
        print(f"  Pair:           {pair}")
        print(f"  Timeframe:      {ctx['timeframe']}")
        print(f"  Timerange:      {args.timerange} ({months:.1f} months)")
        print(f"  Candles loaded: {ctx['total_candles']}")
        print(f"  Long signals:   {ctx.get('long_signals', 0)}")
        print(f"  Short signals:  {ctx.get('short_signals', 0)}")
        print(f"  Total signals:  {signal_count} ({signals_per_month:.1f}/month)")
        print(
            f"  Thresholds:     {min_threshold:.0f}-{max_threshold:.0f} "
            f"(min {args.min_trades_per_month}/mo, max {args.max_trades_per_month}/mo)"
        )
        print()

    # ---- Phase 3: Determine Exit Code ----
    exit_code = EXIT_OK
    issues: list[str] = []
    danger_count = 0
    warn_count = 0

    for hit in kb_hits:
        if hit.severity == Severity.DANGER:
            exit_code = EXIT_DANGER_KB
            danger_count += 1
            issues.append(f"[DANGER] {hit.title}")
        elif hit.severity == Severity.WARN:
            warn_count += 1
            issues.append(f"[WARN] {hit.title}")

    if args.strict and warn_count > 0:
        exit_code = EXIT_ERROR
    if args.strict and danger_count > 0:
        exit_code = EXIT_ERROR

    trade_issue = None
    if signal_count < min_threshold:
        exit_code = EXIT_TOO_FEW
        trade_issue = f"TOO FEW: {signal_count} signals over {months:.1f} months "
        trade_issue += f"(need ≥ {min_threshold:.0f}) → strategy entry conditions too strict"
    elif signal_count > max_threshold:
        exit_code = EXIT_OVER_TRADING
        trade_issue = f"OVER-TRADING: {signal_count} signals over {months:.1f} months "
        trade_issue += f"(limit ≤ {max_threshold:.0f}) → strategy is too permissive"

    if trade_issue:
        issues.append(trade_issue)

    # ---- Output ----
    if args.json:
        result = {
            "status": "OK" if exit_code == EXIT_OK else "FAIL",
            "exit_code": exit_code,
            "strategy": args.strategy,
            "strategy_file": str(strategy_path),
            "timerange": args.timerange,
            "months": round(months, 1),
            "pair": pair,
            "timeframe": ctx.get("timeframe", ""),
            "total_candles": ctx.get("total_candles", 0),
            "signal_count": signal_count,
            "signals_per_month": round(signals_per_month, 1),
            "min_threshold": min_threshold,
            "max_threshold": max_threshold,
            "negative_kb_hits": [h.to_dict() for h in kb_hits],
            "issues": issues,
        }
        print(json.dumps(result, indent=2))
    else:
        if exit_code == EXIT_OK:
            print(
                f"{GREEN}✅ Pre-flight PASSED — {signal_count} signals ({signals_per_month:.1f}/month) "
                f"in acceptable range, {danger_count} danger / {warn_count} warn{NC}"
            )
        else:
            status_colors = {
                EXIT_ERROR: RED,
                EXIT_TOO_FEW: RED,
                EXIT_OVER_TRADING: RED,
                EXIT_DANGER_KB: RED,
            }
            color = status_colors.get(exit_code, RED)
            print(f"{color}❌ Pre-flight FAILED (exit code {exit_code}){NC}")
            for issue in issues:
                print(f"  {YELLOW}•{NC} {issue}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
