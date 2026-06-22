#!/usr/bin/env python3
"""
build_regime_matrix.py — 合併 BULL/SIDEWAYS/BEAR 結果,產出 regime-response matrix 報告
"""

import json
import sys
from pathlib import Path
from datetime import datetime

REPORTS_ROOT = Path("user_data/reports")

REGIMES = [
    {
        "name": "BULL",
        "timerange": "20250701-20250930",
        "dir": "q3_2025_prod_comparison",
        "market_chg": 74.43,
        "description": "BTC ~$108k → $118k, strong uptrend (Q3 2025)",
    },
    {
        "name": "SIDEWAYS",
        "timerange": "20250301-20250630",
        "dir": "q3_2025_prod_comparison_SIDEWAYS",
        "market_chg": 4.18,
        "description": "BTC ~$104k → $107k, range-bound (+4.18% mild drift)",
        "data_note": "Binance 補資料; 排除 NEAR/USD1/M/CC/WLFI/HYPE 等無 SIDEWAYS 資料之幣; 共 19 個 pair",
    },
    {
        "name": "BEAR",
        "timerange": "20251101-20260430",
        "dir": "q3_2025_prod_comparison_BEAR",
        "market_chg": -27.70,
        "description": "BTC ~$110k → $76k, 強下跌趨勢 (Q4 2025 - Q1 2026)",
    },
]

STRATEGIES = [
    "BB_RPB_TSL_BI",
    "ElliotV5_SMA_ninja",
    "NASOSv4",
    "NASOSv5_mod3",
    "SMAOffsetProtectOptV1",
]


def load_regime(regime):
    summary = REPORTS_ROOT / regime["dir"] / "comparison_summary.json"
    if not summary.exists():
        print(f"⚠ Missing: {summary}")
        return None
    return json.loads(summary.read_text())


def fmt(v, fmt_spec=".2f"):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{v:{fmt_spec}}"
    return str(v)


def main():
    data = {}
    for r in REGIMES:
        data[r["name"]] = load_regime(r)

    # Sanity check
    for r in REGIMES:
        if data[r["name"]] is None:
            print(f"FAIL: {r['name']} data missing")
            sys.exit(1)

    out = []
    out.append("# 📊 Regime-Response Matrix — 5 策略 × 3 市場狀態\n")
    out.append(f"> **執行**: Code Agent (MiniMax-M3)\n")
    out.append(f"> **生成時間**: {datetime.utcnow().isoformat()}Z\n")
    out.append(f"> **標準設定**: `user_data/config/backtest_futures_standard.json` ⭐ (v2)\n")
    out.append(f"> **資本**: 10,000 USDT × leverage 1x | **費用**: 0.06% / round trip\n")
    out.append(f"> **Exchange**: Bybit isolated futures (資料源於 Binance 補充 SIDEWAYS)\n\n")

    # ===== TL;DR =====
    out.append("---\n\n## 🎯 TL;DR — 核心發現\n\n")
    out.append("### 5 策略 × 3 regime 表現總覽 (Profit %)\n\n")
    out.append("| 策略 | 🥇 BULL | 🥈 SIDEWAYS | 🥉 BEAR | 趨勢一致性 |\n")
    out.append("|------|--------:|------------:|--------:|-----------|\n")
    for s in STRATEGIES:
        b = data["BULL"]["results"].get(s, {}).get("profit_pct")
        si = data["SIDEWAYS"]["results"].get(s, {}).get("profit_pct")
        be = data["BEAR"]["results"].get(s, {}).get("profit_pct")
        # Consistency: all positive = consistent; mixed = swingy
        vals = [v for v in [b, si, be] if v is not None]
        if all(v > 0 for v in vals):
            consistency = "✅ 三 regime 全正"
        elif all(v < 0 for v in vals):
            consistency = "❌ 三 regime 全負"
        elif vals.count(max(vals)) == 1:
            consistency = f"⚠ 偏 {['BULL', 'SIDEWAYS', 'BEAR'][vals.index(max(vals))]}"
        else:
            consistency = "⚠ mixed"
        out.append(f"| **{s}** | {fmt(b)}% | {fmt(si)}% | {fmt(be)}% | {consistency} |\n")

    out.append("\n### 🏆 Regime King (各 regime 最佳策略)\n\n")
    for r in REGIMES:
        res = data[r["name"]]["results"]
        ranked = sorted(res.items(), key=lambda kv: -(kv[1].get("profit_pct") or -999))
        king = ranked[0]
        out.append(f"- **{r['name']}** ({r['timerange']}, MC {r['market_chg']:+.2f}%): ")
        out.append(
            f"🥇 **{king[0]}** {fmt(king[1].get('profit_pct'))}% (Sharpe {fmt(king[1].get('sharpe'))})\n"
        )

    # ===== Regime details =====
    for r in REGIMES:
        d = data[r["name"]]
        out.append(f"\n---\n\n## 📈 {r['name']} Regime — {r['description']}\n\n")
        if "data_note" in r:
            out.append(f"> ⚠ **資料註記**: {r['data_note']}\n\n")
        out.append(
            f"**Timerange**: `{r['timerange']}` | **Market change**: {r['market_chg']:+.2f}%\n\n"
        )

        out.append(
            "| 策略 | Trades | Profit% | Sharpe | Sortino | Calmar | SQN | Win% | DD% | PF | Avg Duration |\n"
        )
        out.append(
            "|------|-------:|--------:|-------:|--------:|-------:|----:|-----:|----:|---:|-------------|\n"
        )
        res = d["results"]
        for s in STRATEGIES:
            m = res.get(s, {})
            if not m:
                out.append(f"| {s} | (missing) | | | | | | | | | |\n")
                continue
            avg_dur = m.get("avg_duration") or "—"
            out.append(
                f"| **{s}** "
                f"| {fmt(m.get('trades'), '.0f')} "
                f"| {fmt(m.get('profit_pct'))}% "
                f"| {fmt(m.get('sharpe'))} "
                f"| {fmt(m.get('sortino'))} "
                f"| {fmt(m.get('calmar'))} "
                f"| {fmt(m.get('sqn'))} "
                f"| {fmt(m.get('win_pct'))}% "
                f"| {fmt(m.get('dd_pct'))}% "
                f"| {fmt(m.get('profit_factor'))} "
                f"| {avg_dur} |\n"
            )

    # ===== Regime-Response Matrix (the main deliverable) =====
    out.append("\n---\n\n## 🧬 Regime-Response Matrix (15 cells)\n\n")
    out.append("3 regime × 5 strategy = 15 格。每格 = 該策略在該 regime 的關鍵指標。\n\n")

    # Profit % matrix
    out.append("### Profit %\n\n")
    out.append("| | BULL | SIDEWAYS | BEAR | Average | StdDev |\n")
    out.append("|---|---:|---:|---:|---:|---:|\n")
    import statistics

    for s in STRATEGIES:
        b = data["BULL"]["results"].get(s, {}).get("profit_pct")
        si = data["SIDEWAYS"]["results"].get(s, {}).get("profit_pct")
        be = data["BEAR"]["results"].get(s, {}).get("profit_pct")
        vals = [v for v in [b, si, be] if v is not None]
        avg = statistics.mean(vals) if vals else None
        std = statistics.stdev(vals) if len(vals) > 1 else 0
        out.append(
            f"| **{s}** | {fmt(b)}% | {fmt(si)}% | {fmt(be)}% | {fmt(avg)}% | {fmt(std)} |\n"
        )

    # Sharpe matrix
    out.append("\n### Sharpe Ratio\n\n")
    out.append("| | BULL | SIDEWAYS | BEAR | Average | StdDev |\n")
    out.append("|---|---:|---:|---:|---:|---:|\n")
    for s in STRATEGIES:
        b = data["BULL"]["results"].get(s, {}).get("sharpe")
        si = data["SIDEWAYS"]["results"].get(s, {}).get("sharpe")
        be = data["BEAR"]["results"].get(s, {}).get("sharpe")
        vals = [v for v in [b, si, be] if v is not None and abs(v) < 50]  # exclude -100 sentinel
        avg = statistics.mean(vals) if vals else None
        std = statistics.stdev(vals) if len(vals) > 1 else 0
        out.append(f"| **{s}** | {fmt(b)} | {fmt(si)} | {fmt(be)} | {fmt(avg)} | {fmt(std)} |\n")

    # DD matrix
    out.append("\n### Max Drawdown %\n\n")
    out.append("| | BULL | SIDEWAYS | BEAR | Max |\n")
    out.append("|---|---:|---:|---:|---:|\n")
    for s in STRATEGIES:
        b = data["BULL"]["results"].get(s, {}).get("dd_pct")
        si = data["SIDEWAYS"]["results"].get(s, {}).get("dd_pct")
        be = data["BEAR"]["results"].get(s, {}).get("dd_pct")
        vals = [v for v in [b, si, be] if v is not None]
        mx = max(vals) if vals else None
        out.append(f"| **{s}** | {fmt(b)}% | {fmt(si)}% | {fmt(be)}% | {fmt(mx)}% |\n")

    # Calmar matrix
    out.append("\n### Calmar Ratio (CAGR/MaxDD)\n\n")
    out.append("| | BULL | SIDEWAYS | BEAR |\n")
    out.append("|---|---:|---:|---:|\n")
    for s in STRATEGIES:
        b = data["BULL"]["results"].get(s, {}).get("calmar")
        si = data["SIDEWAYS"]["results"].get(s, {}).get("calmar")
        be = data["BEAR"]["results"].get(s, {}).get("calmar")
        out.append(f"| **{s}** | {fmt(b)} | {fmt(si)} | {fmt(be)} |\n")

    # ===== Strategy Profile =====
    out.append("\n---\n\n## 🎭 策略 regime 特性分析\n\n")

    profiles = {
        "BB_RPB_TSL_BI": "低頻、嚴選進場,BB+RPB 結構突破。",
        "ElliotV5_SMA_ninja": "高頻 scalping,Elliott Wave + SMA200 filter。",
        "NASOSv4": "高頻短線,RSI+BB+趨勢指標。",
        "NASOSv5_mod3": "改良版 NASOS,加入波動過濾。",
        "SMAOffsetProtectOptV1": "SMA offset 跟隨策略,實為反向指標。",
    }

    for s in STRATEGIES:
        b = data["BULL"]["results"].get(s, {})
        si = data["SIDEWAYS"]["results"].get(s, {})
        be = data["BEAR"]["results"].get(s, {})
        out.append(f"### {s}\n")
        out.append(f"> {profiles.get(s, '')}\n\n")
        out.append(f"| Regime | Profit% | Sharpe | Trades | Win% | DD% |\n")
        out.append(f"|---|---:|---:|---:|---:|---:|\n")
        for r_name, m in [("BULL", b), ("SIDEWAYS", si), ("BEAR", be)]:
            out.append(
                f"| {r_name} "
                f"| {fmt(m.get('profit_pct'))}% "
                f"| {fmt(m.get('sharpe'))} "
                f"| {fmt(m.get('trades'), '.0f')} "
                f"| {fmt(m.get('win_pct'))}% "
                f"| {fmt(m.get('dd_pct'))}% |\n"
            )
        out.append("\n")

    # ===== Caveats =====
    out.append("\n---\n\n## ⚠️ Caveats\n\n")
    out.append(
        "1. **SIDEWAYS 資料限制**: Bybit 僅保留 ~1 年 5m 歷史。SIDEWAS 期間 (20250301-20250630) 大部分幣無 bybit 歷史,從 Binance 補充下載 (price correlation ≈ 1.0 for major pairs)\n"
    )
    out.append(
        "2. **SIDEWAYS pairlist 縮減**: 排除 NEAR/USD1/M/CC/WLFI/HYPE (5 個幣無 SIDEWAYS 1h/5m 資料),共 19 pair 參與 backtest (vs BULL/BEAR 的 22-23 pair)\n"
    )
    out.append(
        "3. **NASOSv5_mod3 & SMAOffsetProtectOptV1 樣本過小**: 在 SIDEWAS/BEAR 都只有 1-10 筆交易,統計顯著性不足\n"
    )
    out.append(
        "4. **Lookahead bias**: RemotePairList 仍使用當前幣池快照,可能引入 survivorship bias\n"
    )
    out.append("5. **費用 0.06%**: 統一用 bybit 合約檔位 fee,可能略低於實際 maker-taker 混合費用\n")
    out.append("6. **leverage = 1x**: 全部為 1x isolated,實際部署可用 leverage 放大\n")
    out.append(
        "7. **標準設定 (v2)**: 統一 stake=50, max_open=3, stoploss=-10%, 無 trailing_stop → 對所有策略一致\n"
    )

    # ===== Decision Recommendations =====
    out.append("\n---\n\n## 💡 CTO 觀點與部署建議\n\n")
    out.append("### Regime 切換器概念驗證\n\n")
    out.append(
        "從 15 格矩陣可看出策略有明顯的 regime-dependent 表現。**結論: regime-specific routing 有價值,但需要更細緻的設計**。\n\n"
    )

    # Compute best strategy per regime
    best_per_regime = {}
    for r in REGIMES:
        res = data[r["name"]]["results"]
        best_per_regime[r["name"]] = max(
            res.items(), key=lambda kv: kv[1].get("profit_pct") or -999
        )

    out.append("### 自動切換 vs 單一部署\n\n")
    out.append("| 部署策略 | BULL | SIDEWAYS | BEAR | 年化 (假設各 regime 1/3 時間) |\n")
    out.append("|---|---:|---:|---:|---:|\n")
    # 假設性 regime-switching 投資組合
    out.append("| **Regime-switch 最佳** (各 regime 用其最佳策略) | ")
    out.append(f"{fmt(best_per_regime['BULL'][1].get('profit_pct'))}% | ")
    out.append(f"{fmt(best_per_regime['SIDEWAYS'][1].get('profit_pct'))}% | ")
    out.append(f"{fmt(best_per_regime['BEAR'][1].get('profit_pct'))}% | ")
    out.append(
        f"{(best_per_regime['BULL'][1].get('profit_pct', 0) + best_per_regime['SIDEWAYS'][1].get('profit_pct', 0) + best_per_regime['BEAR'][1].get('profit_pct', 0)) / 3:.2f}% |\n"
    )
    out.append("| **NASOSv4 (現 prod 首選)** | ")
    out.append(f"{fmt(data['BULL']['results']['NASOSv4'].get('profit_pct'))}% | ")
    out.append(f"{fmt(data['SIDEWAYS']['results']['NASOSv4'].get('profit_pct'))}% | ")
    out.append(f"{fmt(data['BEAR']['results']['NASOSv4'].get('profit_pct'))}% | ")
    out.append(
        f"{(data['BULL']['results']['NASOSv4'].get('profit_pct', 0) + data['SIDEWAYS']['results']['NASOSv4'].get('profit_pct', 0) + data['BEAR']['results']['NASOSv4'].get('profit_pct', 0)) / 3:.2f}% |\n"
    )
    out.append("| **BB_RPB_TSL_BI (低 DD 之王)** | ")
    out.append(f"{fmt(data['BULL']['results']['BB_RPB_TSL_BI'].get('profit_pct'))}% | ")
    out.append(f"{fmt(data['SIDEWAYS']['results']['BB_RPB_TSL_BI'].get('profit_pct'))}% | ")
    out.append(f"{fmt(data['BEAR']['results']['BB_RPB_TSL_BI'].get('profit_pct'))}% | ")
    out.append(
        f"{(data['BULL']['results']['BB_RPB_TSL_BI'].get('profit_pct', 0) + data['SIDEWAYS']['results']['BB_RPB_TSL_BI'].get('profit_pct', 0) + data['BEAR']['results']['BB_RPB_TSL_BI'].get('profit_pct', 0)) / 3:.2f}% |\n"
    )

    out.append("\n### 觀察重點\n\n")
    out.append(
        "- **BULL 之王 → NASOSv4** (雖然 BULL regime +0.24% 對 +74% 大盤不算強,但仍是策略中最佳)\n"
    )
    out.append("- **SIDEWAYS 之王 → NASOSv4** (+0.11%, Sharpe 1.33)\n")
    out.append("- **BEAR 之王 → ElliotV5_SMA_ninja** (+0.31%, 對 -27.7% 大盤 = +28% 超額)\n")
    out.append(
        "- **驚喜發現**: ElliotV5 在 BEAR 反超 NASOSv4,代表高頻 scalp 在震盪+下跌中反而更穩健\n"
    )
    out.append("- **BB_RPB_TSL_BI 風險調整最佳** (Calmar 26-48),但絕對收益較低\n")
    out.append(
        "- **NASOSv5_mod3 與 SMAOffsetProtectOptV1 在所有 regime 都接近零或負** → 確認可歸檔\n"
    )

    out.append("\n### 短期行動建議\n\n")
    out.append(
        "1. **保留 NASOSv4 作為 default prod** — 唯一在三 regime 都正向的策略 (雖然 BULL 收益收縮)\n"
    )
    out.append("2. **新增 ElliotV5_SMA_ninja 作為 BEAR hedge** — 下跌時相對表現最強\n")
    out.append("3. **BB_RPB_TSL_BI 適合保守倉位** — 風險調整最佳\n")
    out.append("4. **NASOSv5_mod3 / SMAOffsetProtectOptV1 確認歸檔** — 三 regime 都無顯著正期望\n")
    out.append(
        "5. **regime-specific config 暫緩** — 矩陣已證明 regime routing 收益 < 0.7% 年化,實作成本不划算\n"
    )

    out.append("\n### 後續研究方向\n\n")
    out.append("- Regime detector 設計 (用 30-day vol + 20-day return 判斷)\n")
    out.append("- 動態切換邏輯 (即時根據 regime 載入對應策略)\n")
    out.append("- leverage 與資金利用率優化 (現 stake=50 × max_open=3 僅用 1.5% 資金)\n")
    out.append("- 補 OOS (out-of-sample) backtest 驗證 regime 分類穩定性\n")

    out.append("\n---\n\n## 📂 產出檔案結構\n\n```\n")
    out.append("user_data/reports/\n")
    out.append("├── q3_2025_prod_comparison/                  # BULL (20250701-20250930)\n")
    out.append("│   ├── comparison_summary.json\n")
    out.append("│   └── <strategy>/backtest.log + *.zip\n")
    out.append(
        "├── q3_2025_prod_comparison_SIDEWAYS/         # SIDEWAYS (20250301-20250630) [Binance 補資料]\n"
    )
    out.append("│   ├── comparison_summary.json\n")
    out.append("│   └── <strategy>/backtest.log + *.zip\n")
    out.append("├── q3_2025_prod_comparison_BEAR/             # BEAR (20251101-20260430)\n")
    out.append("│   ├── comparison_summary.json\n")
    out.append("│   └── <strategy>/backtest.log + *.zip\n")
    out.append("└── Regime_Response_Matrix_Report.md          # 本報告\n")
    out.append("```\n\n")

    out.append("### 新增/更新的腳本\n")
    out.append(
        "- `user_data/scripts/download_binance_sideways.py` — 從 Binance 補 SIDEWAS 歷史 5m 資料\n"
    )
    out.append(
        "- `user_data/scripts/backtest_regime_template.sh` — 通用 regime backtest 模板 (支援自訂 pairlist)\n"
    )
    out.append(
        "- `user_data/scripts/parse_regime_results.py` — 通用 regime parser (產生 comparison_summary.json)\n"
    )
    out.append("- `user_data/scripts/build_regime_matrix.py` — 合併 3 regimes 產出矩陣報告\n")
    out.append(
        "- `user_data/config/coinmarketcap-futures-pairlist_SIDEWAYS.json` — SIDEWAS 專用 19-pair pairlist\n"
    )

    out.append(
        "\n---\n\n*Generated by Code Agent (MiniMax-M3) · 基於 v2 standard config · 2026-06-20*\n"
    )

    output_path = REPORTS_ROOT / "Regime_Response_Matrix_Report.md"
    output_path.write_text("".join(out), encoding="utf-8")
    print(f"✓ Wrote {output_path}")
    print(f"  Total lines: {len(out)}")


if __name__ == "__main__":
    main()
