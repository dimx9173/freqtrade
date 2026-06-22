#!/usr/bin/env python3
"""
parse_3model_comparison.py — 從 raw backtest log 重建三模型比較報告
"""

import json
import re
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("user_data/reports/q3_2025_3model_comparison")

MODELS = [
    ("MiniMax-M2.5", "M25_bull_strategy", "M25_bull_strategy.log"),
    ("MiniMax-M2.7", "M27_bull_strategy", "M27_bull_strategy.log"),
    ("MiniMax-M3", "M3_bull_trend", "M3_bull_trend.log"),
]

METRIC_PATTERNS = {
    "trades": r"Total/Daily Avg Trades\s*│\s*(\d+)\s*/\s*([\d.]+)",
    "starting": r"Starting balance\s*│\s*([\d.]+) USDT",
    "final": r"Final balance\s*│\s*([\d.]+) USDT",
    "profit_usdt": r"Absolute profit\s*│\s*(-?[\d.]+) USDT",
    "profit_pct": r"Total profit %\s*│\s*(-?[\d.]+)%",
    "cagr": r"CAGR %\s*│\s*(-?[\d.]+)%",
    "sortino": r"Sortino\s*│\s*(-?[\d.]+)",
    "sharpe": r"Sharpe\s*│\s*(-?[\d.]+)",
    "calmar": r"Calmar\s*│\s*(-?[\d.]+)",
    "sqn": r"SQN\s*│\s*(-?[\d.]+)",
    "profit_factor": r"Profit factor\s*│\s*(-?[\d.]+)",
    "expectancy": r"Expectancy \(Ratio\)\s*│\s*(-?[\d.]+)\s*\((-?[\d.]+)\)",
    "max_open": r"Max open trades\s*│\s*(\d+)",
    "win_pct": r"Win\s+Draw\s+Loss\s+Win%\s*│\s*(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)",
    "dd_abs": r"Absolute drawdown\s*│\s*(-?[\d.]+) USDT\s*\((-?[\d.]+)%\)",
    "market_chg": r"Market change\s*│\s*(-?[\d.]+)%",
    "best_day": r"Best day\s*│\s*(-?[\d.]+) USDT",
    "worst_day": r"Worst day\s*│\s*(-?[\d.]+) USDT",
    "max_consec_w": r"Max Consecutive Wins\s*/\s*Loss\s*│\s*(\d+)\s*/\s*(\d+)",
}


def parse_log(path):
    text = Path(path).read_text(errors="replace")
    m = {}
    sm_start = text.find("SUMMARY METRICS")
    sm_end = text.find("Backtested", sm_start)
    if sm_start == -1 or sm_end == -1:
        return m
    block = text[sm_start:sm_end]
    for key, pat in METRIC_PATTERNS.items():
        match = re.search(pat, block)
        if match:
            if key == "trades":
                m["trades"] = int(match.group(1))
                m["trades_per_day"] = float(match.group(2))
            elif key == "expectancy":
                m["expectancy_pct"] = float(match.group(1))
                m["expectancy_ratio"] = float(match.group(2))
            elif key == "dd_abs":
                m["dd_usdt"] = float(match.group(1))
                m["dd_pct"] = float(match.group(2))
            elif key == "win_pct":
                m["wins"] = int(match.group(1))
                m["draws"] = int(match.group(2))
                m["losses"] = int(match.group(3))
                m["win_pct"] = float(match.group(4))
            elif key == "max_consec_w":
                m["max_consec_wins"] = int(match.group(1))
                m["max_consec_losses"] = int(match.group(2))
            else:
                val = match.group(1).replace(",", "")
                try:
                    m[key] = float(val) if "." in val or "-" in val else int(val)
                except ValueError:
                    m[key] = val.strip()
    return m


def fmt(v, fs=".2f"):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{v:{fs}}"
    return str(v)


def main():
    data = {}
    for label, strat_name, log_file in MODELS:
        path = LOG_DIR / log_file
        if not path.exists():
            print(f"WARN: missing {path}")
            continue
        m = parse_log(path)
        data[label] = {"strategy_file": strat_name + ".py", "metrics": m}
        print(
            f"  ok {label}: {m.get('trades')} trades, {m.get('profit_pct')}% profit, Sharpe {m.get('sharpe')}"
        )

    out = []
    out.append("# Q3 2025 (BULL Regime) — 三模型策略獨立生成比較報告 (v2 修正版)\n\n")
    out.append(f"> **執行**: Code Agent (MiniMax-M3) — 修正原始報告 M2.7 數據錯誤\n")
    out.append(f"> **生成時間**: {datetime.utcnow().isoformat()}Z\n")
    out.append(f"> **範圍**: 2025-07-01 ~ 2025-09-30 (92 天, BULL Regime)\n")
    out.append(f"> **設定**: `user_data/config/backtest_futures_standard.json` (v2 standard)\n")
    out.append(f"> **資本**: 10,000 USDT × leverage 1x | **費用**: 0.06% / round trip\n")
    out.append(
        f"> **Pairlist**: 25 個 USDT 合約幣 (CoinMarketCap 標準,RemotePairList via HTTP)\n\n"
    )

    out.append("---\n\n## ⚠️ v1 報告修正說明\n\n")
    out.append("**v1 報告 (`Q3_2025_3Model_Comparison_Report.md`) 的 M2.7 數據錯誤**:\n\n")
    out.append("| 指標 | v1 報告 (錯誤) | v2 修正 (log 真實值) |\n")
    out.append("|---|---:|---:|\n")
    out.append(f"| Trades | 3105 | **{data['MiniMax-M2.7']['metrics'].get('trades')}** |\n")
    out.append(
        f"| Profit % | -1.47% | **+{data['MiniMax-M2.7']['metrics'].get('profit_pct')}%** |\n"
    )
    out.append(
        f"| Profit USDT | -146.62 | **+{data['MiniMax-M2.7']['metrics'].get('profit_usdt')}** |\n"
    )
    out.append(f"| Sharpe | -55.38 | **{data['MiniMax-M2.7']['metrics'].get('sharpe')}** |\n")
    out.append(f"| Win % | 30.2% | **{data['MiniMax-M2.7']['metrics'].get('win_pct')}%** |\n")
    out.append(
        f"| Market change | 74.43% | **{data['MiniMax-M2.7']['metrics'].get('market_chg')}%** |\n\n"
    )
    out.append(
        "**修正原因**: v1 報告是基於 placeholder 數據撰寫,backtest 實際完成後 log 在 `q3_2025_3model_comparison/M27_bull_strategy.log` 顯示真實結果。\n"
    )
    out.append("**v1 結論被推翻**: M2.7 不是「過度交易災難」,**反而是三模型中表現最佳**。\n\n")
    out.append("---\n\n")

    # ===== TL;DR =====
    out.append("## 🎯 執行摘要 (TL;DR) — 真實結果\n\n")
    out.append(
        "| 排名 | 模型 | 策略檔 | 總回報 | Sharpe | Sortino | Calmar | 勝率 | 交易次數 | 結論 |\n"
    )
    out.append(
        "|------|------|--------|--------|--------|---------|--------|------|----------|------|\n"
    )
    ranked = sorted(data.items(), key=lambda kv: -(kv[1]["metrics"].get("profit_pct") or -999))
    for i, (label, d) in enumerate(ranked, 1):
        m = d["metrics"]
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else "🥉")
        out.append(
            f"| {medal} **#{i}** | **{label}** "
            f"| `{d['strategy_file']}` "
            f"| **{'+' if m.get('profit_pct', 0) > 0 else ''}{fmt(m.get('profit_pct'))}%** "
            f"| **{fmt(m.get('sharpe'))}** "
            f"| {fmt(m.get('sortino'))} "
            f"| {fmt(m.get('calmar'))} "
            f"| **{fmt(m.get('win_pct'))}%** "
            f"| {fmt(m.get('trades'), '.0f')} "
            f"| {'冠軍' if i == 1 else ('亞軍' if i == 2 else '季軍')} |\n"
        )

    out.append("\n### 🚨 關鍵發現 (修正版)\n\n")
    out.append(
        "1. **M2.7 是真正的 BULL 之王**: +0.33% profit, Sharpe **5.70**, Calmar **38.14** — 風險調整最佳\n"
    )
    out.append("2. **M2.5 是穩健第二**: +0.17%, Sharpe 3.14, 311 trades, 84.2% 勝率\n")
    out.append("3. **M3 (我) 表現最差**: +0.03%, Sharpe 0.91 — 過度嚴格,期望低\n")
    out.append("4. **3 個模型都跑輸大盤 +74%** — 統一標準設定 (stake=50, max_open=3) 結構性限制\n")
    out.append(
        "5. **M2.7 market change = 71.02%** (vs M2.5/M3 的 74.43%) — 用了不同 pairlist 過濾,可能排除部分幣\n"
    )

    out.append("\n### 對大盤超額 (Strategy % - Buy & Hold)\n\n")
    for label, d in data.items():
        m = d["metrics"]
        mchg = m.get("market_chg", 74.43)
        excess = m.get("profit_pct", 0) - mchg
        out.append(
            f"- {label}: {fmt(m.get('profit_pct'))}% - {fmt(mchg)}% = **{excess:+.2f}%** 超額\n"
        )

    # ===== Full metrics =====
    out.append("\n---\n\n## 📊 完整指標對照表\n\n")
    out.append("| 指標 | 🥇 M2.7 | 🥈 M2.5 | 🥉 M3 |\n")
    out.append("|------|--------:|--------:|------:|\n")
    metric_labels = [
        ("profit_pct", "總獲利 %", True),
        ("profit_usdt", "總獲利 USDT", True),
        ("trades", "交易筆數", False),
        ("trades_per_day", "日均交易", True),
        ("sharpe", "Sharpe", True),
        ("sortino", "Sortino", True),
        ("calmar", "Calmar", True),
        ("sqn", "SQN", True),
        ("profit_factor", "Profit Factor", True),
        ("win_pct", "勝率", True),
        ("dd_pct", "Max DD %", True),
        ("dd_usdt", "Max DD USDT", True),
        ("market_chg", "Market Change", True),
    ]
    # Sort by ranked order
    order = [ranked[i][0] for i in range(len(ranked))]
    for key, label, is_pct in metric_labels:
        row = f"| **{label}** |"
        for mdl in order:
            v = data[mdl]["metrics"].get(key)
            if v is None:
                row += " — |"
            elif is_pct:
                row += f" {fmt(v)}{'%' if 'pct' in key else ''} |"
            else:
                row += f" {fmt(v, '.0f')} |"
        out.append(row + "\n")

    # ===== Strategy file analysis =====
    out.append("\n---\n\n## 🧠 各模型策略設計摘要 (從原始碼)\n\n")

    # Quick peek at strategy files
    strategies_info = {
        "MiniMax-M2.5": {
            "file": "M25_bull_strategy.py",
            "highlights": [
                "嚴格趨勢過濾 (ADX > 30 等嚴格設定)",
                "簡化進場邏輯",
                "ROI 為主出場",
                "結果: 84.2% 勝率, 311 筆中等頻率",
            ],
            "score": "🥈 穩健,但略輸 M2.7 的風險調整",
        },
        "MiniMax-M2.7": {
            "file": "M27_bull_strategy.py",
            "highlights": [
                "Sharpe 5.70, Calmar 38.14 (最高)",
                "Market change 71.02% (獨特 pairlist 過濾)",
                "254 trades / 2.79 per day (中等頻率)",
                "結果: **最佳風險調整後報酬**,但絕對獲利與 M2.5 接近",
            ],
            "score": "🥇 **BULL 之王**,風險調整無人能敵",
        },
        "MiniMax-M3": {
            "file": "M3_bull_trend.py",
            "highlights": [
                "多重確認 (EMA + ADX + 量能 + 突破)",
                "ADX > 20 (中等寬鬆)",
                "進場時機太晚,353 trades 但勝率僅 43.3%",
                "結果: 期望值平庸,需 hyperopt",
            ],
            "score": "🥉 表現最差,需重新設計或優化",
        },
    }

    for label in order:
        info = strategies_info.get(label, {})
        out.append(f"### {label}\n\n")
        out.append(f"**策略檔**: `{info.get('file', '?')}`\n\n")
        out.append("**特性**:\n")
        for h in info.get("highlights", []):
            out.append(f"- {h}\n")
        out.append(f"\n**評分**: {info.get('score', '—')}\n\n")

    # ===== Deployment decision =====
    out.append("---\n\n## ✅ 部署決策 (修正版)\n\n")
    out.append("### 推薦部署優先級\n\n")
    out.append("| 優先 | 模型 | 理由 |\n")
    out.append("|---|---|---|\n")
    out.append("| 🥇 **#1** | **M2.7** | Sharpe 5.70, Calmar 38.14 風險調整最佳 |\n")
    out.append("| 🥈 #2 | M2.5 | 穩健,84.2% 勝率,易於理解 |\n")
    out.append("| 🥉 #3 | M3 | 表現最差,需 hyperopt |\n\n")

    out.append("### ⚠️ Caveats (修正版)\n\n")
    out.append(
        "1. **統一標準設定** (stake=50, max_open=3) 對所有模型都是結構性限制。套用 NASOSv4 sweep 的 stake=200 設定後,預期報酬可放大 4x\n"
    )
    out.append("2. **單一 regime** 結論僅適用 Q3 2025 BULL — 需補 SIDEWAS + BEAR backtest 才完整\n")
    out.append("3. **M2.7 用 71.02% market change** — 需確認 pairlist 是否排除部分幣\n")
    out.append("4. **Lookahead bias** — RemotePairList 使用當前幣池\n")
    out.append("5. **無 hyperopt** — 參數都是手設,非最佳化\n")

    out.append("\n---\n\n## 📂 產出\n\n")
    out.append("```\n")
    out.append("user_data/reports/q3_2025_3model_comparison/\n")
    out.append("├── Q3_2025_3Model_Comparison_Report.md      (v1 舊版,含錯誤數據)\n")
    out.append("├── Q3_2025_3Model_Comparison_Report_v2.md   (本報告,修正版)\n")
    out.append("├── M25_bull_strategy.log                    (raw backtest log)\n")
    out.append("├── M27_bull_strategy.log                    (raw backtest log)\n")
    out.append("└── M3_bull_trend.log                        (raw backtest log)\n")
    out.append("```\n\n")

    out.append("### 策略檔\n")
    out.append("- `user_data/strategies/model_comparison/M25_bull_strategy.py`\n")
    out.append("- `user_data/strategies/model_comparison/M27_bull_strategy.py`\n")
    out.append("- `user_data/strategies/model_comparison/M3_bull_trend.py`\n")

    out.append(
        "\n---\n\n*Generated by Code Agent (MiniMax-M3) — 修正 v1 M2.7 數據錯誤 · 2026-06-20*\n"
    )

    output_path = LOG_DIR / "Q3_2025_3Model_Comparison_Report_v2.md"
    output_path.write_text("".join(out), encoding="utf-8")
    print(f"\n✓ Wrote {output_path}")

    # Also archive old version
    import shutil

    old = LOG_DIR / "Q3_2025_3Model_Comparison_Report.md"
    if old.exists():
        archive = LOG_DIR / "Q3_2025_3Model_Comparison_Report.v1_deprecated.md"
        shutil.move(old, archive)
        print(f"⚠ Archived old version to {archive.name}")


if __name__ == "__main__":
    main()
