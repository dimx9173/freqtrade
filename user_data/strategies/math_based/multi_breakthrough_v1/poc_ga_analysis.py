#!/usr/bin/env python3
"""
Hybrid_v3 GA fthypt 分析工具
============================
解析 fthypt (NDJSON) 格式, 提取所有 trial 統計與 top 10 結果。
用於評估是否需要重跑 hyperopt。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np


def analyze_fthypt(fthypt_path: str, top_n: int = 10) -> None:
    """Analyze a Freqtrade hyperopt fthypt file (NDJSON format)."""
    trials = []
    with open(fthypt_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trials.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not trials:
        print(f"❌ No trials in {fthypt_path}")
        return

    print("=" * 70)
    print(f"📊 {fthypt_path}")
    print(f"   {len(trials)} trials loaded")
    print("=" * 70)

    # Top N by loss
    top = sorted(trials, key=lambda t: t.get('loss', 999))[:top_n]
    print(f"\n=== Top {top_n} by loss ===")
    for i, t in enumerate(top):
        p = t.get('params_dict', {})
        print(f"  #{i+1}: loss={t['loss']:.3f}")
        roi_str = " → ".join([
            f"{p.get(f'roi_p{k}', 0):.1%}@{p.get(f'roi_t{k}', 0)}min"
            for k in [1, 2, 3]
        ])
        print(f"     ROI: {roi_str}")
        print(f"     SL: {p.get('stoploss', 0):.2%}, "
              f"Trail: {p.get('trailing_stop_positive', 0):.3f} @ "
              f"offset {p.get('trailing_stop_positive_offset_p1', 0):.3f}")

    # Param distribution
    print(f"\n=== Param distribution (n={len(trials)}) ===")
    keys = ['roi_t1', 'roi_t2', 'roi_t3',
            'roi_p1', 'roi_p2', 'roi_p3',
            'stoploss', 'trailing_stop_positive', 'trailing_stop_positive_offset_p1']
    for k in keys:
        vals = [t['params_dict'].get(k) for t in trials
                if t.get('params_dict', {}).get(k) is not None]
        if not vals:
            continue
        print(f"  {k}: mean={np.mean(vals):.3f}, "
              f"min={min(vals):.3f}, max={max(vals):.3f}, "
              f"std={np.std(vals):.3f}, median={np.median(vals):.3f}")

    # Loss by bucket for key params
    print(f"\n=== Loss by Stoploss bucket ===")
    buckets = defaultdict(list)
    for t in trials:
        sl = t['params_dict'].get('stoploss', 0)
        sl_bucket = round(sl, 2)
        buckets[sl_bucket].append(t['loss'])
    sorted_buckets = sorted(buckets.items())[:15]
    for sl, losses in sorted_buckets:
        print(f"  SL={sl:+.2%}: n={len(losses)}, "
              f"mean={np.mean(losses):.2f}, best={min(losses):.2f}")

    # Trailing offset distribution
    print(f"\n=== Loss by Trailing offset bucket ===")
    buckets = defaultdict(list)
    for t in trials:
        offset = t['params_dict'].get('trailing_stop_positive_offset_p1', 0)
        bucket = round(offset, 2)
        buckets[bucket].append(t['loss'])
    for offset, losses in sorted(buckets.items())[:10]:
        print(f"  offset={offset:.3f}: n={len(losses)}, "
              f"mean={np.mean(losses):.2f}, best={min(losses):.2f}")

    # ROI p3 distribution (the most variable ROI)
    print(f"\n=== Loss by roi_p3 bucket ===")
    buckets = defaultdict(list)
    for t in trials:
        p3 = t['params_dict'].get('roi_p3', 0)
        bucket = round(p3, 2)
        buckets[bucket].append(t['loss'])
    for p3, losses in sorted(buckets.items())[:10]:
        print(f"  roi_p3={p3:.1%}: n={len(losses)}, "
              f"mean={np.mean(losses):.2f}, best={min(losses):.2f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python poc_ga_analysis.py <fthypt_path> [top_n]")
        sys.exit(1)

    fthypt = sys.argv[1]
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    if not Path(fthypt).exists():
        print(f"❌ File not found: {fthypt}")
        sys.exit(1)

    analyze_fthypt(fthypt, top_n)
