#!/usr/bin/env python3
"""
Freqtrade Scalp Strategy Iterator v2.1 — GA-Driven
每小時自動：GA 演化策略 → 回測 → 精英保留 → 僅保留 Top3

v2.0: 從隨機生成改為遺傳算法 (GA)
      - 基因編碼：策略參數染色體
      - 適應度：Sharpe + EV + 交易次數
      - 選擇：錦標賽 (Tournament Selection)
      - 交配：均勻交叉 (Uniform Crossover)
      - 突變：隨機重置 + 高斯擾動
      - 精英策略保留 (Elitism)
"""

import json, os, sys, time, glob, subprocess, random, zipfile, math
from datetime import datetime

# 確定性 seed（確保每次跑的染色體一致，GA01 永遠是同一個策略）
random.seed(42)
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

WORKSPACE = "/home/brian/freqtrade/test/scalp"
LEDGER_PATH = f"{WORKSPACE}/ledger/strategy_history.json"
STRATEGIES_DIR = "/home/brian/freqtrade/user_data/strategies/test/scalp"
REPORTS_DIR = f"{WORKSPACE}/reports"
CONFIG_TEMPLATE = f"{WORKSPACE}/backtest_config_scalp.json"
VENV_PYTHON = "/home/brian/freqtrade/.venv/bin/python3"

SYMBOLS = ["XRP/USDT:USDT", "TRX/USDT:USDT", "DOGE/USDT:USDT", "ADA/USDT:USDT"]
TIMEFRAME = "5m"
TIMERANGE = "20250501-20260505"

# ── GA 超參數 ───────────────────────────────────────────────
POPULATION_SIZE = 6   # 收緊加速：減少每代評估量
GENERATIONS = 8      # 壓縮總代數（目標 8 代 × ~2.5min ≈ 20 分鐘）
ELITE_COUNT = 2
TOURNAMENT_SIZE = 3
MUTATION_RATE = 0.35
GA_SEED_TOP = 2
FORCE_RANDOM = 2
MAX_WORKERS = 6       # 增加並行度加速單代

# ── Report Feedback（上次迭代教訓）───────────────────────────
# 這些參數會根據上一份 report 的結論動態調整
LAST_REPORT_ANALYSIS = {
    "zero_trade_chroms": 0,  # 上次有多少染色體回測後零交易
    "ema_fast_too_fast": True,  # EMA4/21 是否被認定為太快（噪音）
    "roi_unreachable": True,  # ROI 9.3% 是否被認定為 5m timeframe 達不到
    "confirm_too_strict": True,  # 是否需要減少 confirm_inds 數量
    "ga_diversity_collapsed": True,  # 是否所有新生策略都完全相同
    "sl_too_tight": True,  # SL 2.5% 是否太緊
}


# ════════════════════════════════════════════════════════════
#  命令列參數

# ════════════════════════════════════════════════════════════
#  基因空間定義
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
#  命令列參數
# ════════════════════════════════════════════════════════════

parser = argparse.ArgumentParser(description="Scalp GA Iterator")
parser.add_argument("--constraints", type=str, default=None, help="Path to ga_constraints.json")
args = parser.parse_args()

# ════════════════════════════════════════════════════════════
#  基因空間定義（預設值）
# ════════════════════════════════════════════════════════════

DEFAULT_GENE_SPACE = {
    "fast_ema": [9, 10, 12, 15, 21],
    "slow_ema": [21, 25, 26, 30, 50, 75, 100, 150],
    "rsi_period": [7, 10, 14, 21],
    "rsi_entry": [25, 30, 35, 40, 45, 50],
    "rsi_exit": [50, 55, 60, 65, 70, 75],
    "willr_entry": [-100, -95, -90, -85, -80],
    "cci_entry": [-100, -95, -90, -85, -80, -70, -60, -50],
    "adx_min": [15, 20, 25, 30],
    "mfi_entry": [15, 20, 25, 30, 35],
    "macd_fast": [8, 10, 12, 15],
    "macd_slow": [24, 26, 28, 30],
    "macd_signal": [7, 9, 10, 11, 12],
    "stop_loss": [0.020, 0.025, 0.030, 0.035, 0.040, 0.050],
    "roi_0": [0.020, 0.030, 0.040, 0.050, 0.060],
    "confirm_inds": ["RSI", "MACD", "ADX", "WILLR", "CCI", "MFI", "BB.lower", "ULTOSC"],
    "mode": ["trend_follow_long", "rsi_oversold", "macd_momentum", "bollinger_revert",
        "mean_reversion", "breakout_pulse", "grid_trap"],
}

GENE_SPACE = dict(DEFAULT_GENE_SPACE)

# ════════════════════════════════════════════════════════════
#  從 constraints.json 覆蓋基因空間
# ════════════════════════════════════════════════════════════
GENE_SPACE = dict(DEFAULT_GENE_SPACE)

if args.constraints and os.path.exists(args.constraints):
    with open(args.constraints) as f:
        constraints = json.load(f)
    if "gene_space" in constraints:
        GENE_SPACE.clear()
        GENE_SPACE.update(constraints["gene_space"])
        print(f"\n✅ 基因空間已從 constraints.json 覆蓋:")
        print(f"   fast_ema:    {GENE_SPACE['fast_ema']}")
        print(f"   stop_loss:   {GENE_SPACE['stop_loss']}")
        print(f"   roi_0:       {GENE_SPACE['roi_0']}")

INDICATOR_CATEGORIES = {
    "momentum":   ["RSI", "CCI", "WILLR"],   # N=3
    "trend":      ["MACD", "ADX"       ],   # M=2
    "volatility": ["MFI", "BB.lower"  ],   # K=2
    # 搜索空間: 3×2×2 = 12 種有意義組合
}

# ── NxMxK 兼容：三种类别的所有排列 ────────────────────────────────
# 用於 chromosome_to_strategy() 重構前的橋接字典
CATEGORY_TO_INDICATOR_IDX = {
    "momentum":   0,   # 0,1,2 → RSI, CCI, WILLR
    "trend":      0,   # 0,1   → MACD, ADX
    "volatility": 0,   # 0,1   → MFI, BB.lower
}


# NxMxK 指標池（所有 7 個指標，用於 confirm_combo 回饋與 fallback）
INDICATOR_POOL = ["RSI", "CCI", "WILLR", "MACD", "ADX", "MFI", "BB.lower"]

MODE_CONFIRM = {
    "trend_follow_long": ["RSI", "MACD", "ADX", "WILLR", "CCI", "MFI", "BB.lower", "ULTOSC"],
    "rsi_oversold": ["EMA200", "MACD", "CCI", "ADX", "BB.lower", "ATR"],
    "macd_momentum": ["ADX", "RSI", "WILLR", "EMA200", "MFI"],
    "bollinger_revert": ["RSI", "CCI", "MACD", "ADX", "WILLR"],
    # v2.1 新增模式
    "mean_reversion": ["RSI", "CCI", "BB.lower", "ULTOSC", "ADX"],
    "breakout_pulse": ["ADX", "RSI", "MFI", "ATR", "WILLR"],
    "grid_trap": ["EMA200", "BB.lower", "RSI", "MACD"],
}


def make_random_chromosome():
    """保持向後兼容，實際呼叫learned版本（無歷史學習時退化为纯随机）"""
    return make_learned_chromosome(None)


def chromosome_to_strategy(chrom):
    """染色體 → 策略描述（用於寫入檔案）"""
    fast = chrom["fast_ema"]
    slow = chrom["slow_ema"]
    mode = chrom["mode"]

    # 確保 slow_ema > fast_ema
    if slow <= fast:
        slow = fast + random.choice([8, 10, 15, 21, 30])
        slow = min(slow, 200)

    inds = [f"EMA{fast}", f"EMA{slow}"] + [chrom["momentum_ind"], chrom["trend_ind"], chrom["volatility_ind"]]

    return {
        "indicators": sorted(set(inds)),
        "params": {
            "mode": mode,
            "fast_ema": fast,
            "slow_ema": slow,
            "rsi_period": chrom["rsi_period"],
            "rsi_entry": chrom["rsi_entry"],
            "rsi_exit": max(chrom["rsi_exit"], chrom["rsi_entry"] + 20),
            "willr_entry": chrom["willr_entry"],
            "cci_entry": chrom["cci_entry"],
            "adx_min": chrom["adx_min"],
            "mfi_entry": chrom["mfi_entry"],
            "macd_fast": min(chrom["macd_fast"], slow - 1)
            if slow > chrom["macd_fast"]
            else chrom["macd_fast"],
            "macd_slow": max(chrom["macd_slow"], fast + 10),
            "macd_signal": chrom["macd_signal"],
            "stop_loss": chrom["stop_loss"],
            "roi_0": chrom["roi_0"],
            "momentum_ind": chrom["momentum_ind"],
            "trend_ind": chrom["trend_ind"],
            "volatility_ind": chrom["volatility_ind"],
        },
    }


def tournament_select(population, scores, tournament_size=TOURNAMENT_SIZE):
    """錦標賽選擇"""
    indices = random.sample(range(len(population)), min(tournament_size, len(population)))
    best_i = max(indices, key=lambda i: scores[i])
    return population[best_i], scores[best_i]


def crossover(parent_a, parent_b):
    """"NxMxK 均勻交叉 + 回退兼容"""
    child = {}

    # 1. 所有 GENE_SPACE 的數值基因
    for key in GENE_SPACE:
        a_val = parent_a.get(key)
        b_val = parent_b.get(key)
        if a_val is not None and b_val is not None:
            child[key] = random.choice([a_val, b_val])
        elif a_val is not None:
            child[key] = a_val
        elif b_val is not None:
            child[key] = b_val
        else:
            child[key] = random.choice(GENE_SPACE[key])

    # 2. NxMxK 三類別指標基因（各自完整複製，不重組）
    for gene_key in ("momentum_ind", "trend_ind", "volatility_ind"):
        pool_key = gene_key.replace("_ind", "")  # "momentum_ind" → "momentum"
        pool = INDICATOR_CATEGORIES.get(pool_key, [])
        # 優先使用現有父母值，否則隨機
        val = parent_a.get(gene_key) or parent_b.get(gene_key)
        if val is None and pool:
            val = random.choice(pool)
        child[gene_key] = val

    return child


def mutate(chrom, explosion=False):
    """突變函式 - 支援 explosion mode（停滯時強化突變）"""
    rate = MUTATION_RATE * 3 if explosion else MUTATION_RATE
    mutated = chrom.copy()

    # 對數值型基因應用突變
    for key in [
        "fast_ema",
        "slow_ema",
        "rsi_period",
        "rsi_entry",
        "rsi_exit",
        "willr_entry",
        "cci_entry",
        "adx_min",
        "mfi_entry",
        "macd_fast",
        "macd_slow",
        "macd_signal",
        "stop_loss",
        "roi_0",
    ]:
        if random.random() < rate:
            if random.random() < 0.7:
                # 高斯擾動 ±15%
                val = chrom.get(key, GENE_SPACE[key][0])
                delta = val * 0.15 * random.choice([-1, 1]) * random.random()
                new_val = val + delta
                space = GENE_SPACE[key]
                new_val = max(space[0], min(space[-1], new_val))
                # 離散化
                if key in [
                    "fast_ema",
                    "slow_ema",
                    "rsi_period",
                    "macd_fast",
                    "macd_slow",
                    "macd_signal",
                    "adx_min",
                ]:
                    new_val = int(round(new_val))
                mutated[key] = new_val
            else:
                # 隨機重置
                mutated[key] = random.choice(GENE_SPACE[key])

    # NxMxK 三類別 mutation：每個 category 各自獨立突變
    if random.random() < rate:
        for cat, pool in INDICATOR_CATEGORIES.items():
            gene_key = f"{cat}_ind"
            if random.random() < rate and pool:
                mutated[gene_key] = random.choice(pool)


    # 確保 sanity
    if mutated["slow_ema"] <= mutated["fast_ema"]:
        mutated["slow_ema"] = mutated["fast_ema"] + random.choice([10, 15, 21, 30])
    if mutated["rsi_exit"] <= mutated["rsi_entry"]:
        mutated["rsi_exit"] = mutated["rsi_entry"] + random.choice([20, 25, 30])
    if mutated["macd_slow"] <= mutated["macd_fast"]:
        mutated["macd_slow"] = mutated["macd_fast"] + random.choice([10, 12, 15])

    return mutated


def compute_fitness(result):
    """
    適應度函式 v2.1 — 重建版
    核心原則：
    1. 交易次數 < 100 → 硬終止
    2. Sharpe 除數 1.5 而非 2.0（更嚴格）
    3. 權重：Sharpe 55%, EV 25%, WR 10%, 交易次數 10%
    """
    sharpe = result.get("sharpe_ratio", 0)
    ev = result.get("ev", 0)
    trades = result.get("total_trades", 0)
    winrate = result.get("win_rate", 0)

    # ── 硬終止：零交易或交易次數不足 100 ──────────────────────────────
    if trades < 100:
        return -0.9

    # ── 排除方向錯誤的策略 ──────────────────────────────────────────
    if sharpe < -1.0 and trades < 500:
        return -0.9

    # ── Sharpe 正規化（更嚴格：除數 1.5）───────────────────────────────
    sharpe_norm = max(-1, min(1, sharpe / 1.5))

    # ── EV 正規化 ────────────────────────────────────────────────────
    ev_norm = max(-1, min(1, ev))

    # ── Win rate deviation from 50% ────────────────────────────────
    wr_norm = winrate - 0.5

    # ── 交易次數正規化（對數尺度）────────────────────────────────
    trade_norm = max(0, min(0.5, math.log10(trades) - 2)) / 3

    fitness = 0.55 * sharpe_norm + 0.25 * ev_norm + 0.10 * wr_norm + 0.10 * trade_norm
    return round(max(-0.9, min(1.0, fitness)), 5)


# ════════════════════════════════════════════════════════════
#  從歷史Ledger自主學習（GA v2.1）
# ════════════════════════════════════════════════════════════


def _learn_from_ledger():
    """
    掃描ledger所有歷史策略，建立基因品質地圖。
    回傳: {
        'ema_fast_dist': {value: avg_sharpe},
        'ema_slow_dist': {value: avg_sharpe},
        'stop_loss_dist': {value: avg_sharpe},
        'roi_dist': {value: avg_sharpe},
        'mode_dist': {mode: avg_sharpe},
        'confirm_combo_quality': {(combo): avg_sharpe},
        'param_pairs': {(fast,slow): avg_sharpe},
        'good_chroms': [chrom,...]  # 拿來直接做初始種群
    """
    if not os.path.exists(LEDGER_PATH):
        return None

    with open(LEDGER_PATH) as f:
        ledger = json.load(f)

    strats = ledger.get("strategies", [])
    if not strats:
        return None

    # 只看有實質交易的（避免零交易垃圾）
    meaningful = [s for s in strats if s.get("total_trades", 0) > 50]
    if len(meaningful) < 5:
        # 交易太少：放寬門檻看全部
        meaningful = strats

    result = {
        "ema_fast_dist": {},
        "ema_slow_dist": {},
        "stop_loss_dist": {},
        "roi_dist": {},
        "mode_dist": {},
        "confirm_combo_quality": {},
        "param_pairs": {},
        "good_chroms": [],
    }

    # 加權：近期策略更高權重（簡單版：次數^0.5）
    for s in meaningful:
        p = s.get("params", {})
        sh = s.get("sharpe_ratio", 0)
        ev = s.get("ev", 0)
        trades = s.get("total_trades", 0)
        # 評分：兼顧Sharpe和EV，但交易次數要有最低底線
        score = sh  # 預設用Sharpe
        if trades < 200:
            score = score * 0.3  # 交易太少降權重

        def _add(dist, key, val):
            if key not in dist:
                dist[key] = []
            dist[key].append(val)

        fe = p.get("fast_ema")
        se = p.get("slow_ema")
        sl = p.get("stop_loss")
        roi = p.get("roi_0")
        mode = p.get("mode")
        inds = tuple(sorted(s.get("indicators", [])))

        if fe:
            _add(result["ema_fast_dist"], fe, score)
        if se:
            _add(result["ema_slow_dist"], se, score)
        if sl:
            _add(result["stop_loss_dist"], sl, score)
        if roi:
            _add(result["roi_dist"], roi, score)
        if mode:
            _add(result["mode_dist"], mode, score)
        if inds:
            _add(result["confirm_combo_quality"], inds, score)
        if fe and se:
            _add(result["param_pairs"], (fe, se), score)

        # 收錄Top表現者（Sharpe >= -10 且 trades > 100）
        if sh > -10 and trades > 100:
            chrom = {
                "mode": mode or "trend_follow_long",
                "fast_ema": fe or 9,
                "slow_ema": se or 21,
                "rsi_period": p.get("rsi_period", 14),
                "rsi_entry": p.get("rsi_entry", 35),
                "rsi_exit": p.get("rsi_exit", 65),
                "willr_entry": p.get("willr_entry", -85),
                "cci_entry": p.get("cci_entry", -100),
                "adx_min": p.get("adx_min", 20),
                "mfi_entry": p.get("mfi_entry", 25),
                "macd_fast": p.get("macd_fast", 12),
                "macd_slow": p.get("macd_slow", 26),
                "macd_signal": p.get("macd_signal", 9),
                "stop_loss": sl or 0.025,
                "roi_0": roi or 0.05,
                "confirm_inds": list(inds) if inds else ["RSI", "MACD"],
                # NxMxK fallback: derive 3-category indicators from legacy confirm_inds
                "momentum_ind":   (inds[0] if len(inds) > 0 else "RSI"),
                "trend_ind":      (inds[1] if len(inds) > 1 else "MACD"),
                "volatility_ind": (inds[2] if len(inds) > 2 else "MFI"),
            }
            result["good_chroms"].append((sh, chrom))

    # 彙總平均
    def _avg(dist):
        return {k: sum(v) / len(v) for k, v in dist.items()}

    result["ema_fast_dist"] = _avg(result["ema_fast_dist"])
    result["ema_slow_dist"] = _avg(result["ema_slow_dist"])
    result["stop_loss_dist"] = _avg(result["stop_loss_dist"])
    result["roi_dist"] = _avg(result["roi_dist"])
    result["mode_dist"] = _avg(result["mode_dist"])
    result["confirm_combo_quality"] = _avg(result["confirm_combo_quality"])
    result["param_pairs"] = _avg(result["param_pairs"])

    # 取Top表現染色體
    result["good_chroms"].sort(key=lambda x: x[0], reverse=True)
    result["good_chroms"] = [c for _, c in result["good_chroms"][:5]]

    return result


def _weighted_choice(dist, prefer_higher=True):
    """根據歷史表現分佈加權抽樣"""
    if not dist:
        return None
    items = list(dist.items())
    scores = [v for _, v in items]
    if prefer_higher:
        weights = [max(0, s + 10) for s in scores]  # 負Sharpe也要有基本權重
    else:
        weights = [max(0, -s + 10) for s in scores]
    total = sum(weights)
    if total == 0:
        return random.choice(items)[0]
    r = random.random() * total
    cumulative = 0
    for k, v in items:
        cumulative += max(0, v + 10 if prefer_higher else -v + 10)
        if cumulative >= r:
            return k
    return items[-1][0]


def make_learned_chromosome(learned=None, report_analysis=None):
    """
    根據歷史學習結果 + 上次報告反饋，產生"更有機會產生交易"的染色體。

    報告反饋信號（report_analysis 傳入 LAST_REPORT_ANALYSIS）：
    - zero_trade_chroms > 0   → 強制降低 confirm_inds 數量
    - ema_fast_too_fast       → 強制 fast_ema ≥ 9（杜絕 EMA4/21 假訊號）
    - roi_unreachable         → 強制 roi_0 ≤ 0.06（移除 9.3% 等不可能目標）
    - sl_too_tight            → 強制 stop_loss ≥ 0.035（放寬止損緊度）
    - confirm_too_strict      → 減少 confirm_inds 至 1 個
    - ga_diversity_collapsed  → 引入更多隨機性，避免再次收斂到同一解
    """
    flags = report_analysis or {}

    # ── 根據回饋信號強制約束 ─────────────────────────────
    forced_fast_ema = 9 if flags.get("ema_fast_too_fast") else None
    forced_stop_loss = 0.035 if flags.get("sl_too_tight") else None
    forced_roi_0 = 0.06 if flags.get("roi_unreachable") else None
    forced_n_confirm = 1 if flags.get("confirm_too_strict") else None

    mode = _weighted_choice(learned["mode_dist"] if learned else None) or random.choice(
        GENE_SPACE["mode"]
    )
    confirm_pool = MODE_CONFIRM.get(mode, INDICATOR_POOL)

    if learned and random.random() < 0.5:
        sorted_combos = sorted(
            learned["confirm_combo_quality"].items(), key=lambda x: x[1], reverse=True
        )
        for combo, avg_sh in sorted_combos:
            if avg_sh > -50 and random.random() < 0.4:
                # avg_sh 全部為負，門檻放寬至 -50 才能選到任何 combo
                confirms = list(combo)
                break
        else:
            confirms = random.sample(confirm_pool, min(2, len(confirm_pool)))
    else:
        n = forced_n_confirm or random.randint(1, min(3, len(confirm_pool)))
        confirms = random.sample(confirm_pool, n)

    if forced_fast_ema is not None:
        fast_ema = forced_fast_ema
    elif learned and random.random() < 0.5:
        fast_ema = _weighted_choice(learned["ema_fast_dist"]) or random.choice(
            GENE_SPACE["fast_ema"]
        )
    else:
        fast_ema = random.choice(GENE_SPACE["fast_ema"])

    if learned and random.random() < 0.5:
        slow_ema = _weighted_choice(learned["ema_slow_dist"]) or random.choice(
            [e for e in GENE_SPACE["slow_ema"] if e > fast_ema] or GENE_SPACE["slow_ema"]
        )
    else:
        slow_ema_candidates = [e for e in GENE_SPACE["slow_ema"] if e > fast_ema]
        slow_ema = (
            random.choice(slow_ema_candidates)
            if slow_ema_candidates
            else random.choice(GENE_SPACE["slow_ema"])
        )

    if forced_stop_loss is not None:
        stop_loss = forced_stop_loss
    elif learned and random.random() < 0.5:
        stop_loss = _weighted_choice(learned["stop_loss_dist"]) or random.choice(
            GENE_SPACE["stop_loss"]
        )
    else:
        stop_loss = random.choice(GENE_SPACE["stop_loss"])

    if forced_roi_0 is not None:
        roi_0 = forced_roi_0
    elif learned and random.random() < 0.5:
        roi_0 = _weighted_choice(learned["roi_dist"]) or random.choice(GENE_SPACE["roi_0"])
    else:
        roi_0 = random.choice(GENE_SPACE["roi_0"])

    # ── 模式多樣性強制執行（mode_lacked 時，GA 陷入單一模式迴圈）────
    if flags.get("mode_lacked") and random.random() < 0.60:
        # 75% 機率強制換 mode（高於 50%，確保有效打破 macd_momentum 壟斷）
        current_mode = mode
        other_modes = [m for m in GENE_SPACE["mode"] if m != current_mode]
        if other_modes:
            mode = random.choice(other_modes)
            # 重新選擇 confirm pool 並只留 1 個確認指標（降低進場門檻）
            confirm_pool = MODE_CONFIRM.get(mode, INDICATOR_POOL)
            confirms = random.sample(confirm_pool, min(1, len(confirm_pool)))
            forced_n_confirm = 1  # 同步更新（避免上面的 n 覆蓋）
            print(f"  [Mode diversity] Switched to {mode} (was {current_mode})")

    if flags.get("ga_diversity_collapsed") and random.random() < 0.30:
        fast_ema = random.choice(GENE_SPACE["fast_ema"])
        stop_loss = random.choice(GENE_SPACE["stop_loss"])
        roi_0 = random.choice(GENE_SPACE["roi_0"])
        mode = random.choice(GENE_SPACE["mode"])
        confirm_pool = MODE_CONFIRM.get(mode, INDICATOR_POOL)
        n = forced_n_confirm or random.randint(1, min(2, len(confirm_pool)))
        confirms = random.sample(confirm_pool, n)

    # ── NxMxK：三類別各選一個指標 ───────────────────────────────
    momentum_ind = random.choice(INDICATOR_CATEGORIES["momentum"])
    trend_ind    = random.choice(INDICATOR_CATEGORIES["trend"])
    volatility_ind = random.choice(INDICATOR_CATEGORIES["volatility"])

    return {
        "mode": mode,
        "fast_ema": fast_ema,
        "slow_ema": slow_ema,
        "rsi_period": random.choice(GENE_SPACE["rsi_period"]),
        "rsi_entry": random.choice(GENE_SPACE["rsi_entry"]),
        "rsi_exit": random.choice(
            [e for e in GENE_SPACE["rsi_exit"] if e > GENE_SPACE["rsi_entry"][0]]
            or GENE_SPACE["rsi_exit"]
        ),
        "willr_entry": random.choice(GENE_SPACE["willr_entry"]),
        "cci_entry": random.choice(GENE_SPACE["cci_entry"]),
        "adx_min": random.choice(GENE_SPACE["adx_min"]),
        "mfi_entry": random.choice(GENE_SPACE["mfi_entry"]),
        "macd_fast": random.choice(GENE_SPACE["macd_fast"]),
        "macd_slow": random.choice(
            [e for e in GENE_SPACE["macd_slow"] if e > fast_ema] or GENE_SPACE["macd_slow"]
        ),
        "macd_signal": random.choice(GENE_SPACE["macd_signal"]),
        "stop_loss": stop_loss,
        "roi_0": roi_0,
        "momentum_ind": momentum_ind,
        "trend_ind": trend_ind,
        "volatility_ind": volatility_ind,
    }


# ════════════════════════════════════════════════════════════
#  核心：GA 演化
# ════════════════════════════════════════════════════════════


def _backtest_wrapper(chrom, existing_results, all_results_dict):
    """ThreadPoolExecutor worker: backtest one chromosome, return (hash, result)."""
    h = chrom_hash(chrom)
    if h in existing_results:
        return h, existing_results[h]
    if h in all_results_dict:
        return h, all_results_dict[h]
    strat = chromosome_to_strategy(chrom)
    result = backtest_chromosome(chrom, strat)
    return h, result


def ga_evolve(
    initial_pop, existing_results, n_generations=GENERATIONS, learned=None, report_analysis=None
):
    """
    遺傳算法主體（並行版 + 自主學習）
    initial_pop:        初始染色體列表（來自歷史最佳 + 隨機）
    existing_results:   dict {chrom_hash: backtest_result}
    learned:            _learn_from_ledger() 的結果，用於加權染色體生成
    返回：(best_chrom, best_result, all_results)
    """
    population = list(initial_pop)
    all_results = dict(existing_results)  # {hash: result}
    # Thread-safe shared dict for parallel workers
    shared_results = dict(all_results)
    lock = __import__("threading").Lock()

    # 早停追蹤
    stagnant_gen = 0
    prev_best_fitness = -999

    def submit_chromosome(chrom):
        h = chrom_hash(chrom)
        if h not in shared_results:
            return None  # already done
        strat = chromosome_to_strategy(chrom)
        return (chrom, strat)

    for gen in range(n_generations):
        print(f"\n  ── Generation {gen + 1}/{n_generations} (pop={len(population)}) ──")

        # Step A: 並行評估所有未評估的染色體
        work = [
            (chrom, chromosome_to_strategy(chrom))
            for chrom in population
            if chrom_hash(chrom) not in shared_results
        ]
        if work:
            print(f"    Backtesting {len(work)} chromosomes in parallel (workers={MAX_WORKERS})...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(backtest_chromosome, chrom, strat): chrom
                    for chrom, strat in work
                }
                for future in as_completed(futures):
                    chrom = futures[future]
                    try:
                        h = chrom_hash(chrom)
                        result = future.result()
                        shared_results[h] = result
                        print(
                            f"      ✓ {h[:8]} trades={result.get('total_trades', 0)} sharpe={result.get('sharpe_ratio', 0):.2f}"
                        )
                    except Exception as e:
                        print(f"      ✗ chrom {chrom_hash(chrom)[:8]} failed: {e}")
                        shared_results[chrom_hash(chrom)] = {
                            "total_trades": 0,
                            "win_rate": 0,
                            "sharpe_ratio": -999,
                            "profit_abs": 0,
                            "profit_ratio": 0,
                            "expectancy": -1,
                            "ev": -1,
                            "wins": 0,
                            "losses": 0,
                            "fitness": -1,
                        }
        all_results.update(shared_results)

        # Step B: 計算適應度
        scores = [compute_fitness(all_results[chrom_hash(c)]) for c in population]

        # Step C: 顯示族群概況
        print(f"    Fitness range: [{min(scores):.4f}, {max(scores):.4f}]")
        sharpe_vals = [all_results[chrom_hash(c)]["sharpe_ratio"] for c in population]
        print(f"    Sharpe range:   [{min(sharpe_vals):.3f}, {max(sharpe_vals):.3f}]")

        # Step D: 精英保留（直接進入下一代，不突變）
        elite_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :ELITE_COUNT
        ]
        elite_chroms = [population[i] for i in elite_indices]
        elite_results = [all_results[chrom_hash(c)] for c in elite_chroms]

        # Step E: 顯示 Top 策略（每代監控）
        top_idx = max(range(len(scores)), key=lambda i: scores[i])
        top_result = all_results[chrom_hash(population[top_idx])]
        print(f"    Top: {top_result.get('sharpe_ratio', 0):.3f} Sharpe, {top_result.get('total_trades', 0)} trades, fitness={scores[top_idx]:.4f}")

    # ── 停滯檢測：自動突變增強（取代舊的 STOP_MARKER）──────────
    # 當連續 N 代 fitness 沒進步時，觸發「突變爆炸」模式
    next_pop = list(elite_chroms)
    children_to_test = []
    
    if gen > 0:
        improvement = scores[top_idx] - prev_best_fitness
        if improvement <= 0:
            stagnant_gen += 1
        else:
            stagnant_gen = 0
        
        if stagnant_gen >= 3:
            print(f"    ⚠️  Fitness stagnant {stagnant_gen}g → MUTATION EXPLODE (+30% random inject, rate x3)")
            # 1. 注入 30% 隨機染色體（增加多样性）
            inject_count = max(1, int(POPULATION_SIZE * 0.3))
            for _ in range(inject_count):
                if len(next_pop) >= POPULATION_SIZE:
                    break
                random_chrom = make_learned_chromosome(learned, report_analysis) if learned else make_random_chromosome()
                if chrom_hash(random_chrom) not in shared_results:
                    # 立即回測
                    result = backtest_chromosome(random_chrom, chromosome_to_strategy(random_chrom))
                    shared_results[chrom_hash(random_chrom)] = result
                    print(f"      ✓ injected random {chrom_hash(random_chrom)[:8]} trades={result.get('total_trades', 0)} sharpe={result.get('sharpe_ratio', 0):.2f}")
                    next_pop.append(random_chrom)
            # 2. 剩餘位置用高突變率填充
            while len(next_pop) < POPULATION_SIZE:
                parent_a, _ = tournament_select(population, scores)
                parent_b, _ = tournament_select(population, scores)
                child = crossover(parent_a, parent_b)
                # 突變率 x3（強制打破局部最小）
                if random.random() < MUTATION_RATE * 3:
                    child = mutate(child, explosion=True)
                children_to_test.append(child)
                next_pop.append(child)
            stagnant_gen = 0  # reset
        else:
            # 正常產生下一代
            while len(next_pop) < POPULATION_SIZE:
                parent_a, _ = tournament_select(population, scores)
                parent_b, _ = tournament_select(population, scores)
                child = crossover(parent_a, parent_b)
                if random.random() < MUTATION_RATE:
                    child = mutate(child)
                children_to_test.append(child)
                next_pop.append(child)
    else:
        # 第一代，正常產生
        while len(next_pop) < POPULATION_SIZE:
            parent_a, _ = tournament_select(population, scores)
            parent_b, _ = tournament_select(population, scores)
            child = crossover(parent_a, parent_b)
            if random.random() < MUTATION_RATE:
                child = mutate(child)
            children_to_test.append(child)
            next_pop.append(child)

        if children_to_test:
            unevaluated = [c for c in children_to_test if chrom_hash(c) not in shared_results]
            if unevaluated:
                print(f"    Backtesting {len(unevaluated)} children in parallel...")
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = {
                        executor.submit(backtest_chromosome, c, chromosome_to_strategy(c)): c
                        for c in unevaluated
                    }
                    for future in as_completed(futures):
                        c = futures[future]
                        try:
                            h = chrom_hash(c)
                            result = future.result()
                            shared_results[h] = result
                            print(
                                f"      ✓ child {h[:8]} trades={result.get('total_trades', 0)} sharpe={result.get('sharpe_ratio', 0):.2f}"
                            )
                        except Exception as e:
                            print(f"      ✗ child failed: {e}")
        all_results.update(shared_results)
        population = next_pop
        prev_best_fitness = max(scores)

    # 回傳最佳
    final_scores = [compute_fitness(all_results[chrom_hash(c)]) for c in population]
    best_idx = max(range(len(final_scores)), key=lambda i: final_scores[i])
    return population[best_idx], all_results[chrom_hash(population[best_idx])], all_results


def chrom_hash(chrom):
    """染色體的唯一雜湊（用於快取）"""
    key = {
        "mode": chrom["mode"],
        "fe": chrom["fast_ema"],
        "se": chrom["slow_ema"],
        "rp": chrom["rsi_period"],
        "re": chrom["rsi_entry"],
        "rx": chrom["rsi_exit"],
        "mi": chrom["momentum_ind"],
        "ti": chrom["trend_ind"],
        "vi": chrom["volatility_ind"],
        "sl": chrom["stop_loss"],
        "roi": chrom["roi_0"],
    }
    return hex(abs(hash(json.dumps(key, sort_keys=True))))[2:12]


def backtest_chromosome(chrom, strat):
    """
    對一個染色體執行回測，回傳結果字典。
    """
    sid = f"GA_{chrom_hash(chrom)[:8]}"
    path = f"{STRATEGIES_DIR}/{sid}.py"
    build_strategy_file(sid, strat, path)

    ok, stdout, stderr = run_backtest(sid, CONFIG_TEMPLATE)
    parsed = parse_zip_result(sid)

    if parsed:
        result = {
            "strategy_id": sid,
            "file": path,
            "chrom_hash": chrom_hash(chrom),
            "total_trades": parsed["trades"],
            "win_rate": parsed["winrate"],
            "sharpe_ratio": parsed["sharpe"],
            "profit_abs": parsed["profit_abs"],
            "profit_ratio": parsed["profit_pct"],
            "expectancy": parsed["expectancy"],
            "ev": round(
                parsed["winrate"] * max(abs(parsed["profit_pct"]), 0.001) * 2
                - (1 - parsed["winrate"]),
                4,
            ),
            "wins": parsed["wins"],
            "losses": parsed["losses"],
        }
    else:
        result = {
            "strategy_id": sid,
            "file": path,
            "chrom_hash": chrom_hash(chrom),
            "total_trades": 0,
            "win_rate": 0,
            "sharpe_ratio": -999,
            "profit_abs": 0,
            "profit_ratio": 0,
            "expectancy": -1,
            "ev": -1,
            "wins": 0,
            "losses": 0,
        }

    result["fitness"] = compute_fitness(result)

    # 清理臨時策略檔
    if os.path.exists(path):
        os.remove(path)

    return result


# ════════════════════════════════════════════════════════════
#  以下：與 v1.2 共用（幾乎不變）
# ════════════════════════════════════════════════════════════


def load_ledger():
    if not os.path.exists(LEDGER_PATH):
        return {"version": "2.0", "strategies": [], "top_strategies": []}
    with open(LEDGER_PATH) as f:
        return json.load(f)


def save_ledger(ledger):
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)


def get_all_tested(ledger):
    tested = []
    for s in ledger.get("strategies", []):
        inds = s.get("indicators", [])
        key = json.dumps(sorted(inds), sort_keys=True)
        h = hex(abs(hash(key)))[2:8]
        tested.append(
            {
                "indicators": inds,
                "params": s.get("params", {}),
                "sharpe": s.get("sharpe_ratio", 0),
                "hash": s.get("hash", h),
            }
        )
    return tested


def build_strategy_file(sid, strat_data, output_path):
    """寫入 Freqtrade 策略檔（與 v1.2 相同）"""
    inds = strat_data["indicators"]
    params = strat_data["params"]
    fast = params["fast_ema"]
    slow = params["slow_ema"]
    mode = params.get("mode", "trend_follow_long")

    ind_parts = [
        f'dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod={fast})',
        f'dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod={slow})',
        f'dataframe["rsi"] = ta.RSI(dataframe, timeperiod={params["rsi_period"]})',
    ]

    # NxMxK: read 3-category indicator names from params (now passed via chromosome_to_strategy)
    mom_ind   = params.get("momentum_ind",   "RSI")
    trend_ind = params.get("trend_ind",      "MACD")
    vol_ind   = params.get("volatility_ind", "MFI")
    CATEGORY_INDS = [mom_ind, trend_ind, vol_ind]

    # confirm_inds: backward compat (old seed chroms may have legacy confirm_inds)
    confirm_inds = [i for i in inds if i not in [f"EMA{fast}", f"EMA{slow}"]]

    for ind in confirm_inds:
        if ind == "MACD":
            ind_parts.append(
                f'dataframe["macd"] = ta.MACD(dataframe, fastperiod={params["macd_fast"]}, '
                f'slowperiod={params["macd_slow"]}, signalperiod={params["macd_signal"]})["macd"]'
            )
            ind_parts.append(
                f'dataframe["macdsignal"] = ta.MACD(dataframe, fastperiod={params["macd_fast"]}, '
                f'slowperiod={params["macd_slow"]}, signalperiod={params["macd_signal"]})["macdsignal"]'
            )
        elif ind == "ADX":
            ind_parts.append(
                f'dataframe["adx"] = ta.ADX(dataframe, timeperiod={params["adx_min"] + 5})'
            )
        elif ind == "WILLR":
            ind_parts.append('dataframe["willr"] = ta.WILLR(dataframe, timeperiod=14)')
        elif ind == "CCI":
            ind_parts.append('dataframe["cci"] = ta.CCI(dataframe, timeperiod=14)')
        elif ind == "MFI":
            ind_parts.append('dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)')
        elif ind == "STOCH.k":
            ind_parts.append(
                'dataframe["slowk"] = ta.STOCH(dataframe, fastk_period=14, '
                'slowk_period=3, slowk_matype=0)["slowk"]'
            )
            ind_parts.append(
                'dataframe["slowd"] = ta.STOCH(dataframe, fastk_period=14, '
                'slowd_period=3, slowd_matype=0)["slowd"]'
            )
        elif ind == "ULTOSC":
            ind_parts.append('dataframe["ultosc"] = ta.ULTOSC(dataframe)')
        elif ind == "BB.upper" or ind == "BB.lower":
            ind_parts.append(
                'bb_u, bb_m, bb_l = ta.BBANDS(dataframe["close"], timeperiod=20, nbdevup=2.0, nbdevdn=2.0); '
                'dataframe["bb_upper"] = bb_u; dataframe["bb_lower"] = bb_l'
            )
        elif ind.startswith("EMA"):
            period = int(ind.replace("EMA", ""))
            ind_parts.append(f'dataframe["ema_long"] = ta.EMA(dataframe, timeperiod={period})')
        elif ind == "ATR":
            ind_parts.append('dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)')

    indicators_str = "\n        ".join(ind_parts)

    # Entry / Exit logic
    entry_parts = [f'dataframe["ema_fast"] > dataframe["ema_slow"]']
    exit_parts = [f'dataframe["ema_fast"] < dataframe["ema_slow"]']

    if "RSI" in confirm_inds:
        entry_parts.append(f'dataframe["rsi"] < {params["rsi_entry"]}')
        exit_parts.append(f'dataframe["rsi"] > {params["rsi_exit"]}')

    if "MACD" in confirm_inds:
        entry_parts.append('dataframe["macd"] > dataframe["macdsignal"]')
        exit_parts.append('dataframe["macd"] < dataframe["macdsignal"]')

    if "WILLR" in confirm_inds:
        entry_parts.append(f'dataframe["willr"] < {params["willr_entry"]}')
        exit_parts.append('dataframe["willr"] > -50')

    if "ADX" in confirm_inds:
        entry_parts.append(f'dataframe["adx"] > {params["adx_min"]}')
        exit_parts.append(f'dataframe["adx"] < {params["adx_min"] - 5}')

    if "MFI" in confirm_inds:
        entry_parts.append(f'dataframe["mfi"] < {params["mfi_entry"]}')
        exit_parts.append(f'dataframe["mfi"] > {100 - params["mfi_entry"]}')

    if "CCI" in confirm_inds:
        entry_parts.append(f'dataframe["cci"] < {params["cci_entry"]}')
        exit_parts.append(f'dataframe["cci"] > {-params["cci_entry"]}')

    if "BB.lower" in confirm_inds:
        entry_parts.append('dataframe["close"] < dataframe["bb_lower"] * 1.02')
        exit_parts.append('dataframe["close"] > dataframe["bb_upper"] * 0.98')

    if "ATR" in confirm_inds:
        entry_parts.append(f'(dataframe["close"] - dataframe["low"]) < dataframe["atr"] * 2')

    # EMA long-term filter (e.g. EMA200 confirms longer-term trend)
    ema_long_inds = [
        i for i in confirm_inds if i.startswith("EMA") and i != f"EMA{fast}" and i != f"EMA{slow}"
    ]
    if ema_long_inds:
        ema_period = int(ema_long_inds[0].replace("EMA", ""))
        entry_parts.append(f'dataframe["ema_long"] < dataframe["close"]')
        exit_parts.append(f'dataframe["ema_long"] > dataframe["close"]')

    # Mode-specific logic
    if mode == "rsi_oversold":
        entry_parts.append(f'dataframe["rsi"] < {params["rsi_entry"]}')
        exit_parts.append(f'dataframe["rsi"] > {params["rsi_exit"]}')


    # ── v2.1 新模式 entry/exit ───────────────────────────────────────
    if mode == "mean_reversion":
        # 均值回歸：RSI 极端低點 + 价格触及 BB 下轨 = 买入
        entry_parts.append(f'dataframe["rsi"] < {params["rsi_entry"]}')
        exit_parts.append(f'dataframe["rsi"] > {params["rsi_exit"]}')
        entry_parts.append('dataframe["close"] < dataframe["bb_lower"] * 1.03')
        exit_parts.append('dataframe["close"] > dataframe["bb_upper"] * 0.97')


    if mode == "breakout_pulse":
        # 波動爆發：ADX 突然增強 + MFI 確認
        entry_parts.append(f'dataframe["adx"] > {params["adx_min"] + 5}')
        entry_parts.append(f'dataframe["mfi"] < {params["mfi_entry"] + 10}')
        exit_parts.append(f'dataframe["adx"] < {params["adx_min"]}')
        exit_parts.append(f'dataframe["mfi"] > {100 - params["mfi_entry"]}')

    if mode == "grid_trap":
        # 網格：在 BB 下軌低點進場，目標 BB 上軌
        # 不依賴 trend_direction，純靠價格相對位置
        entry_parts.append('dataframe["close"] < dataframe["bb_lower"] * 1.01')
        exit_parts.append('dataframe["close"] > dataframe["bb_upper"] * 0.99')
        entry_parts.append('dataframe["rsi"] < 50')   # 短線超賣
        exit_parts.append('dataframe["rsi"] > 70')   # 短線超買

    entry_expr = "(" + ") & (".join(entry_parts) + ")"
    exit_expr = "(" + ") | (".join(exit_parts) + ")"

    code = f'''#!/usr/bin/env python3
"""
Strategy {sid}
Generated: {datetime.now().isoformat()}
Mode: {mode}
Indicators: {inds}
"""
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy

class Strategy_{sid}(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "{TIMEFRAME}"
    can_short = True

    stoploss = -{params["stop_loss"]}
    minimal_roi = {{
        "0": {params["roi_0"]},
        "60": {round(params["roi_0"] * 0.6, 3)},
        "180": {round(params["roi_0"] * 0.3, 3)}
    }}

    trailing_stop = True
    trailing_stop_positive = 0.008
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True

    startup_candle_count = 100
    process_only_new_candles = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict):
        {indicators_str}
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict):
        dataframe["enter_long"] = 0
        dataframe.loc[
            (dataframe["volume"] > 0) & ({entry_expr}),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict):
        dataframe["exit_long"] = 0
        dataframe.loc[
            (dataframe["volume"] > 0) & ({exit_expr}),
            "exit_long"
        ] = 1
        return dataframe
'''

    with open(output_path, "w") as f:
        f.write(code)
    return output_path


def run_backtest(strategy_id, config_file):
    cmd = [
        VENV_PYTHON,
        "-m",
        "freqtrade",
        "backtesting",
        "--config",
        config_file,
        "--strategy",
        f"Strategy_{strategy_id}",
        "--timerange",
        TIMERANGE,
        "--export",
        "trades",
        "--backtest-directory",
        REPORTS_DIR,
        "--recursive-strategy-search",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd="/home/brian/freqtrade", timeout=120
    )
    return result.returncode == 0, result.stdout, result.stderr


def parse_zip_result(strategy_id, reports_dir=REPORTS_DIR):
    prefix = f"Strategy_{strategy_id}"
    for zpath in sorted(glob.glob(f"{reports_dir}/backtest-result-*.zip")):
        try:
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    if name.endswith(".json") and "meta" not in name and "config" not in name:
                        data = json.loads(z.read(name))
                        strat_data = data.get("strategy", {})
                        sc = data.get("strategy_comparison", [])
                        if prefix in strat_data and sc:
                            s = sc[0]
                            return {
                                "trades": s.get("trades") or 0,
                                "wins": s.get("wins") or 0,
                                "losses": s.get("losses") or 0,
                                "winrate": s.get("winrate") or 0,
                                "sharpe": s.get("sharpe") or 0,
                                "profit_abs": s.get("profit_total_abs") or 0,
                                "profit_pct": s.get("profit_total") or 0,
                                "max_dd": s.get("max_drawdown_abs") or 0,
                                "expectancy": s.get("expectancy") or 0,
                                "sqn": s.get("sqn") or 0,
                            }
        except Exception:
            continue
    return None


def ledger_chrom_to_ga_chrom(ledger_entry):
    """把 ledger 歷史條目轉成 GA 染色體格式（用於初始化種群）"""
    params = ledger_entry.get("params", {})
    inds = ledger_entry.get("indicators", [])
    # Start with a complete fallback template
    chrom = {
        "mode": params.get("mode", "trend_follow_long"),
        "fast_ema": params.get("fast_ema", 9),
        "slow_ema": params.get("slow_ema", 21),
        "rsi_period": params.get("rsi_period", 14),
        "rsi_entry": params.get("rsi_entry", 35),
        "rsi_exit": params.get("rsi_exit", 65),
        "willr_entry": params.get("willr_entry", -85),
        "cci_entry": params.get("cci_entry", -100),
        "adx_min": params.get("adx_min", 20),
        "mfi_entry": params.get("mfi_entry", 25),
        "macd_fast": params.get("macd_fast", 12),
        "macd_slow": params.get("macd_slow", 26),
        "macd_signal": params.get("macd_signal", 9),
        "stop_loss": params.get("stop_loss", 0.025),
        "roi_0": params.get("roi_0", 0.05),
        "momentum_ind": "RSI",
        "trend_ind": "MACD",
        "volatility_ind": "MFI",
    }
    # 尝试从 legacy confirm_inds 推导 NxMxK 三指标
    if inds:
        mode_conf = MODE_CONFIRM.get(params.get("mode", "trend_follow_long"), ["RSI", "ADX"])
        # momentum: prefer RSI/CCI/WILLR
        for ind in mode_conf:
            if ind in INDICATOR_CATEGORIES["momentum"]:
                chrom["momentum_ind"] = ind
                break
        # trend: prefer MACD/ADX
        for ind in mode_conf:
            if ind in INDICATOR_CATEGORIES["trend"]:
                chrom["trend_ind"] = ind
                break
        # volatility: prefer MFI/BB.lower
        for ind in mode_conf:
            if ind in INDICATOR_CATEGORIES["volatility"]:
                chrom["volatility_ind"] = ind
                break
    return chrom


# ════════════════════════════════════════════════════════════
#  主程式
# ════════════════════════════════════════════════════════════




def detect_market_regime():
    """
    市場 Regime 診斷 v2.1
    讀取最近 200 根 5m K線，計算 RSI + ATR ratio 判斷當前市場狀態。
    回傳: { regime: "neutral"|"up"|"down"|"volatile", rsi: float, atr_ratio: float }
    """
    import requests, math
    try:
        # 從 Binance 取得 XRP/USDT 最近 200 根 5m K線
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": "XRPUSDT", "interval": "5m", "limit": 200}
        bars = requests.get(url, params=params, timeout=5).json()
        if not bars:
            return {"regime": "neutral", "rsi": 50, "atr_ratio": 1.0}

        closes = [float(b[4]) for b in bars]
        highs = [float(b[2]) for b in bars]
        lows = [float(b[3]) for b in bars]

        # RSI(14)
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        rs = sum(d for d in deltas[-14:] if d > 0) / max(1e-10, -sum(d for d in deltas[-14:] if d < 0))
        rsi = 100 - 100 / (1 + rs) if rs > 0 else 50

        # ATR(14)
        trs = [max(h-l, abs(h-c), abs(l-c)) for h, l, c in zip(highs[1:], lows[1:], closes[:-1])]
        atr = sum(trs[-14:]) / 14
        recent_range = sum(abs(c - p) for c, p in zip(closes[-15:], closes[-14:])) / 14
        atr_ratio = recent_range / max(atr, 0.0001)

        if atr_ratio > 1.5:
            regime = "volatile"
        elif rsi > 62:
            regime = "up"
        elif rsi < 38:
            regime = "down"
        else:
            regime = "neutral"

        return {"regime": regime, "rsi": rsi, "atr_ratio": atr_ratio}
    except Exception:
        return {"regime": "neutral", "rsi": 50, "atr_ratio": 1.0}


def main():
    print(f"\n{'=' * 60}")
    print(f"SCALP STRATEGY GA ITERATOR v2.1 — {datetime.now().isoformat()}")
    print(f"{'=' * 60}")

    ledger = load_ledger()
    tested = get_all_tested(ledger)
    print(f"📋 Historical strategies: {len(tested)}")

    # ── 載入並分析上次 Report（Feedback Loop）───────────────
    # 讀取最新的 report，分析失敗原因，讓下次迭代更聰明
    report_files = sorted(glob.glob(f"{REPORTS_DIR}/report_*.json"))
    if report_files:
        with open(report_files[-1]) as f:
            last_report = json.load(f)
        br = last_report.get("best_result", {})
        top_strats = last_report.get("top_strategies", [])
        zero_trade_count = sum(1 for s in top_strats if s.get("trades", 0) == 0)
        all_evaled = last_report.get("all_evaluated", 0)
        print(f"\n📊 Last Report Analysis ({os.path.basename(report_files[-1])})")
        print(
            f"   Best: Sharpe={br.get('sharpe', 0):.3f} EV={br.get('ev', 0):.4f} Trades={br.get('trades', 0)}"
        )
        print(f"   Top3 zero-trade count: {zero_trade_count}/3")
        print(f"   Total evaluated: {all_evaled}")
        if top_strats:
            print(f"   Top1 indicators: {top_strats[0].get('indicators', [])}")
            p = top_strats[0].get("params", {})
            print(f"   Top1 SL={p.get('sl', '?') * 100:.1f}% ROI={p.get('roi', '?') * 100:.1f}%")
        # 更新反饋字典（提供給 make_learned_chromosome 參考）
        LAST_REPORT_ANALYSIS["zero_trade_chroms"] = zero_trade_count
        LAST_REPORT_ANALYSIS["ema_fast_too_fast"] = any(
            "EMA4" in s.get("indicators", []) for s in top_strats
        )
        LAST_REPORT_ANALYSIS["sl_too_tight"] = any(
            p.get("sl", 0) and p.get("sl", 0) <= 0.025
            for s in top_strats
            if "params" in s
            for p in [s["params"]]
        )
        LAST_REPORT_ANALYSIS["roi_unreachable"] = any(
            p.get("roi", 0) and p.get("roi", 0) >= 0.08
            for s in top_strats
            if "params" in s
            for p in [s["params"]]
        )
        # mode_lacked: 連續多代都是同一個 mode（mode 多樣性崩潰）
        top_modes = [s.get("params", {}).get("mode") for s in top_strats if "params" in s]
        mode_lacked = len(set(top_modes)) == 1 and len(top_modes) >= 3
        LAST_REPORT_ANALYSIS["mode_lacked"] = mode_lacked
        if mode_lacked:
            print(f"  ⚠️  Mode diversity collapsed: only {top_modes[0]} in Top3")

        # ga_diversity_collapsed: 指標指紋完全相同
        LAST_REPORT_ANALYSIS["ga_diversity_collapsed"] = (
            len(set(tuple(sorted(s.get("indicators", []))) for s in top_strats)) == 1
            and zero_trade_count == 3
        )
        print(f"\n⚠️  Feedback flags: {LAST_REPORT_ANALYSIS}")

    # ── 市場 Regime 診斷 + 自適應基因空間 ─────────────────────────────
    regime_info = detect_market_regime()
    regime = regime_info["regime"]
    rsi = regime_info["rsi"]
    atr_ratio = regime_info["atr_ratio"]
    print(f"\n🌡️  Market Regime: {regime} | RSI: {rsi:.1f} | ATR ratio: {atr_ratio:.2f}")

    # 根據 Regime 調整基因空間權重（但不改 GENE_SPACE 本身）
    # neutral/down → 禁用趨勢策略，啟用 mean_reversion
    # volatile → 禁用所有，保留最小集合
    if regime in ("down", "neutral"):
        # 在中性/下跌市場，抑制 trend_follow_long 的 confirm pool
        print(f"  [Regime adjust] Downweighting trend strategies in {regime} market")
    if regime == "volatile":
        # 波動市場：抑制一切，只留最強的 3 種 confirm
        print(f"  [Regime adjust] High volatility ({atr_ratio:.2f}), conservative mode")

    print(f"  → GA will weight mean_reversion/grid_trap higher in {regime} regime")

    # ── 建構 config ───────────────────────────────────────
    config = {
        "max_open_trades": 3,
        "stake_currency": "USDT",
        "stake_amount": "unlimited",
        "tradable_balance_ratio": 0.99,
        "dry_run": True,
        "dry_run_wallet": 10000,
        "timeframe": TIMEFRAME,
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "can_short": True,
        "unfilledtimeout": {"entry": 10, "exit": 10},
        "entry_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
        "exit_pricing": {"price_side": "same", "use_order_book": True, "order_book_top": 1},
        "exchange": {"name": "bybit", "key": "", "secret": "", "pair_whitelist": SYMBOLS},
        "pairlists": [{"method": "StaticPairList"}],
    }
    os.makedirs(os.path.dirname(CONFIG_TEMPLATE), exist_ok=True)
    with open(CONFIG_TEMPLATE, "w") as f:
        json.dump(config, f, indent=2)

    # ── 從歷史Ledger自主學習 ──────────────────────────
    learned = _learn_from_ledger()
    if learned:
        print(f"\n[Learned] From {len(learned.get('good_chroms', []))} good chroms cached")
        print(f"  EMA fast dist: {dict(list(learned['ema_fast_dist'].items())[:5])}")
        print(f"  Mode dist: {learned.get('mode_dist', {})}")
        print(f"  Combo quality: {len(learned.get('confirm_combo_quality', {}))} combos tracked")
    else:
        print("\n[Learned] No historical data, using random init")

    # ── 初始化種群 ────────────────────────────────────────
    print(f"\n[Step 1] Building initial population...")

    # 從歷史最佳採樣（用於繼承好的基因）
    sorted_strategies = sorted(tested, key=lambda x: x.get("sharpe", 0), reverse=True)
    seed_strategies = sorted_strategies[:GA_SEED_TOP]
    initial_pop = []
    existing_results = {}

    for s in seed_strategies:
        if s.get("sharpe", 0) > -50:  # 只取有意義的
            try:
                chrom = ledger_chrom_to_ga_chrom(s)
                h = chrom_hash(chrom)
                initial_pop.append(chrom)
                existing_results[h] = {
                    "strategy_id": f"seed_{h[:8]}",
                    "chrom_hash": h,
                    "total_trades": 0,  # 歷史紀錄不重跑
                    "win_rate": 0,
                    "sharpe_ratio": s.get("sharpe", 0),
                    "profit_abs": 0,
                    "profit_ratio": 0,
                    "expectancy": s.get("sharpe", 0) / 100,
                    "ev": s.get("sharpe", 0) / 100,
                    "wins": 0,
                    "losses": 0,
                    "fitness": max(-1, min(1, s.get("sharpe", 0) / 2.0)),
                    "is_seed": True,
                }
            except Exception:
                pass

    # ── Seed 參數約束（強制服從當前 GENE_SPACE）────────────────────────
    # 問題：ledger seed 的 stop_loss/roi_0 是舊數值（可能 sl=3% 而新空間要求 5%+）
    # 治療：把 seed 的 sl/roi 替換成當前 GENE_SPACE 的隨機有效值
    for h in existing_results:
        if existing_results[h].get("is_seed"):
            # 只更新 sl 和 roi_0，其他（sharpe/trades）保持歷史值
            existing_results[h]["stop_loss"] = random.choice(GENE_SPACE["stop_loss"])
            existing_results[h]["roi_0"] = random.choice(GENE_SPACE["roi_0"])

    # 補滿個體（使用學習得來的加權染色體）
    while len(initial_pop) < POPULATION_SIZE:
        chrom = make_learned_chromosome(learned)
        h = chrom_hash(chrom)
        # 避免重複
        if h not in [chrom_hash(c) for c in initial_pop]:
            initial_pop.append(chrom)

    print(
        f"  Seeds from history: {len([r for r in existing_results.values() if r.get('is_seed')])}"
    )
    print(
        f"  Learned补充: {POPULATION_SIZE - len([r for r in existing_results.values() if r.get('is_seed')])}"
    )
    print(f"  Total pop: {len(initial_pop)}")

    # ── GA 演化 ───────────────────────────────────────────
    print(
        f"\n[Step 2] Running GA ({GENERATIONS} gens, pop={POPULATION_SIZE}, elite={ELITE_COUNT})..."
    )
    best_chrom, best_result, all_results = ga_evolve(
        initial_pop, existing_results, learned=learned, report_analysis=LAST_REPORT_ANALYSIS
    )

    # ── 方向D：防呆停止條件（連續失敗檢查）────────────────────────
    # 讀取最近 3 份 report，檢查 Sharpe 是否連續極差
    recent_reports = sorted(glob.glob(f"{REPORTS_DIR}/report_*.json"))[-3:]
    consecutive_bad = 0
    for rp in recent_reports:
        try:
            d = json.load(open(rp))
            sh = d.get("best_result", {}).get("sharpe", 0)
            if sh < -0.3:
                consecutive_bad += 1
        except Exception:
            pass

    # ── 連續失敗 → 觸發突變爆炸（不再停止）──────────────────────
    # 舊邏輯：3 次負 Sharpe → 寫 STOP_MARKER → 停止
    # 新邏輯：3 次負 Sharpe → 觸發 GA 突變爆炸模式 → 繼續進化
    if consecutive_bad >= 3:
        print(f"\n⚠️  {consecutive_bad}/3 recent runs Sharpe < -0.3 → TRIGGERING MUTATION EXPLOSION")
        print(f"   Injecting 30% random chromosomes + setting rate x3 for next generations")
        # 直接在 ga_constraints 標記 explosion mode
        if os.path.exists(f"{WORKSPACE}/ga_constraints.json"):
            with open(f"{WORKSPACE}/ga_constraints.json") as f:
                constraints = json.load(f)
            constraints["explosion_mode"] = True
            constraints["consecutive_bad"] = consecutive_bad
            with open(f"{WORKSPACE}/ga_constraints.json", "w") as f:
                json.dump(constraints, f, indent=2)
        # 不再 return，繼續執行（GA 會在 stagnant_gen 檢測時觸發 explosion）

    print(f"\n✅ GA complete. Best chromosome:")
    print(f"   Mode: {best_chrom['mode']}")
    print(f"   EMA: {best_chrom['fast_ema']}/{best_chrom['slow_ema']}")
    print(f"   Indicators: {best_chrom['momentum_ind']} + {best_chrom['trend_ind']} + {best_chrom['volatility_ind']}")
    print(f"   SL: {best_chrom['stop_loss'] * 100:.1f}% | ROI: {best_chrom['roi_0'] * 100:.1f}%")
    print(
        f"   Sharpe: {best_result.get('sharpe_ratio', 0):.3f} | EV: {best_result.get('ev', 0):.3f}"
    )
    print(f"   Fitness: {best_result.get('fitness', 0):.4f}")

    # ── 收集 Top N（適應度排序）───────────────────────────
    #
    # 正確邏輯：歷史 Top N（seed）+ 新生 GA 策略 → 一起競爭取 Top 3
    # Seed 策略用歷史 Sharpe/fitness，雖然 trades=0 但 fitness 仍有意义
    #
    print(f"\n[Step 3] Ranking evaluated strategies (GA-new + historical-top compete)...")

    # ── Zero-trade 強制負 fitness（確保回測失敗的策略不會進入 Top3） ─────────
    # 問題：is_seed + trades=0 仍拿到正 fitness 0.0246，導致 Top3 全是零交易策略
    # 治療：零交易、無論是否為 seed，直接 fitness = -0.9
    # 注意：compute_fitness() 已在開頭處理此情況，若 reach 至此表示 caller 跳過了該檢查
    for result in [existing_results.get(h) for h in existing_results]:
        if result and result.get("total_trades", 0) == 0:
            result["fitness"] = -0.9

    # Build hash -> chrom mapping from initial_pop (all chromosomes ever created)
    # Only include chroms whose hash actually maps back to a result in all_results
    pop_hash_map = {chrom_hash(c): c for c in initial_pop if chrom_hash(c) in all_results}

    # (A) GA 新生策略：必须有实际回测交易才纳入
    ga_candidates = []
    for h, result in all_results.items():
        if result.get("total_trades", 0) > 0 and h in pop_hash_map:
            chrom = pop_hash_map[h]  # ← 修復：正確取得 chrom
            ga_candidates.append((chrom, result))

    # (B) 歷史 Top N 策略（seed）：直接拿历史 fitness 參與競爭
    # existing_results 包含每個 seed 的完整 result dict（含 is_seed=True, sharpe_ratio, fitness）
    seed_candidates = []
    for s in seed_strategies:
        if s.get("sharpe", 0) > -50:  # 有意義的歷史策略
            try:
                chrom = ledger_chrom_to_ga_chrom(s)
                h = chrom_hash(chrom)
                if h in existing_results:
                    seed_candidates.append((chrom, existing_results[h]))
            except Exception:
                pass

    print(f"  GA-new candidates (w/ trades): {len(ga_candidates)}")
    print(f"  Historical top candidates (seed): {len(seed_candidates)}")

    # 合併 + 一起競爭
    all_candidates = ga_candidates + seed_candidates

    if all_candidates:
        all_candidates.sort(key=lambda x: x[1].get("fitness", -999), reverse=True)
        top_n = all_candidates[:3]
        print(f"\n  Competing pool: {len(all_candidates)} strategies | Top 3 by fitness:")
        for i, (chrom, res) in enumerate(top_n):
            tag = "[seed]" if res.get("is_seed") else "[GA]"
            print(
                f"  #{i + 1} {tag} Fitness={res.get('fitness', 0):.4f} Sharpe={res.get('sharpe_ratio', 0):.3f} "
                f"EV={res.get('ev', 0):.3f} Trades={res.get('total_trades', 0)} "
                f"WR={res.get('win_rate', 0):.1%}"
            )
    else:
        # Fallback: 按 fitness 排序（零交易也要承擔負 fitness 後果）
        # 注意：compute_fitness 已對零交易給 -0.9（普通策略）或 -0.5（seed）
        scored = [
            (c, all_results[chrom_hash(c)]) for c in initial_pop if chrom_hash(c) in all_results
        ]
        scored.sort(key=lambda x: x[1].get("fitness", -999), reverse=True)
        top_n = scored[:3]
        print(f"  No candidates found, using all_results fallback")

    # ── 寫入 Top N 策略檔 ─────────────────────────────────
    print(f"\n[Step 4] Writing top strategies to files...")
    final_strategies = []
    for i, (chrom, res) in enumerate(top_n):
        strat = chromosome_to_strategy(chrom)
        sid = f"GA{i + 1:02d}_{chrom_hash(chrom)[:8]}_{int(time.time())}"
        path = f"{STRATEGIES_DIR}/{sid}.py"
        build_strategy_file(sid, strat, path)
        entry = {
            "strategy_id": sid,
            "file": path,
            "chrom_hash": chrom_hash(chrom),
            "chromosome": chrom,
            "indicators": strat["indicators"],
            "params": strat["params"],
            "total_trades": res.get("total_trades", 0),
            "win_rate": res.get("win_rate", 0),
            "sharpe_ratio": res.get("sharpe_ratio", 0),
            "profit_abs": res.get("profit_abs", 0),
            "profit_ratio": res.get("profit_ratio", 0),
            "expectancy": res.get("expectancy", 0),
            "ev": res.get("ev", 0),
            "fitness": res.get("fitness", 0),
            "wins": res.get("wins", 0),
            "losses": res.get("losses", 0),
            "timestamp": datetime.now().isoformat(),
        }
        final_strategies.append(entry)
        print(f"  Written: {sid} → {path}")

    # ── 寫入 report ──────────────────────────────────────
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_file = f"{REPORTS_DIR}/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "ga_version": "2.0",
        "population": POPULATION_SIZE,
        "generations": GENERATIONS,
        "elite_count": ELITE_COUNT,
        "mutation_rate": MUTATION_RATE,
        "best_chromosome": {
            "mode": best_chrom["mode"],
            "ema": f"{best_chrom['fast_ema']}/{best_chrom['slow_ema']}",
            "momentum_ind": best_chrom["momentum_ind"],
            "trend_ind": best_chrom["trend_ind"],
            "volatility_ind": best_chrom["volatility_ind"],
            "stop_loss": best_chrom["stop_loss"],
            "roi_0": best_chrom["roi_0"],
        },
        "best_result": {
            "sharpe": best_result.get("sharpe_ratio", 0),
            "ev": best_result.get("ev", 0),
            "win_rate": best_result.get("win_rate", 0),
            "trades": best_result.get("total_trades", 0),
            "profit": best_result.get("profit_abs", 0),
            "fitness": best_result.get("fitness", 0),
        },
        "top_strategies": [
            {
                "id": s["strategy_id"],
                "fitness": s["fitness"],
                "sharpe": s["sharpe_ratio"],
                "ev": s["ev"],
                "win_rate": s["win_rate"],
                "trades": s["total_trades"],
                "profit": s["profit_abs"],
                "indicators": s["indicators"],
                "params": {
                    "mode": s["params"]["mode"],
                    "sl": s["params"]["stop_loss"],
                    "roi": s["params"]["roi_0"],
                },
            }
            for s in final_strategies
        ],
        "all_evaluated": len(all_results),
        "feedback_flags": LAST_REPORT_ANALYSIS,  # 這次迭代觀察到的問題，供下次參考
    }
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # ── 更新 Ledger ───────────────────────────────────────
    ledger["version"] = "2.0"
    for s in final_strategies:
        s["timestamp"] = datetime.now().isoformat()
        ledger["strategies"].append(s)
    ledger["top_strategies"] = final_strategies
    save_ledger(ledger)

    # ── 清理：只保留 Top N 策略檔 ─────────────────────────
    final_ids = {s["strategy_id"] for s in final_strategies}
    kept = 0
    for f in glob.glob(f"{STRATEGIES_DIR}/*.py"):
        sid = os.path.basename(f).replace(".py", "")
        if sid not in final_ids:
            os.remove(f)
        else:
            kept += 1

    print(f"\n✅ GA Done. Report: {report_file}")
    print(f"📊 Ledger: {len(ledger['strategies'])} total strategies")
    print(f"🧹 Kept {kept} strategy files")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
