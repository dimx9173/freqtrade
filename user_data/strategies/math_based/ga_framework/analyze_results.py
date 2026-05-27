#!/usr/bin/env python3
"""
數學策略 GA 迭代結果分析器
分析 hyperopt 結果並產生報告
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime


def find_latest_hyperopt(strategy_name):
    """尋找最新的 hyperopt 結果檔案"""
    hyperopt_dir = Path("hyperopt_results")
    if not hyperopt_dir.exists():
        return None

    # 尋找符合策略名稱的 .fthypt 檔案
    files = list(hyperopt_dir.glob(f"strategy_{strategy_name}_*.fthypt"))
    if not files:
        return None

    # 按修改時間排序
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files[0]


def analyze_hyperopt_result(filepath):
    """分析 hyperopt 結果"""
    # 這裡需要根據實際的 .fthypt 格式來解析
    # 目前先提供基本資訊
    return {
        "file": str(filepath),
        "size": filepath.stat().st_size,
        "modified": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
    }


def generate_report(strategy_name, output_dir):
    """產生分析報告"""
    latest = find_latest_hyperopt(strategy_name)

    report = f"""# GA 迭代分析報告

## 策略資訊
- **策略**: {strategy_name}
- **分析時間**: {datetime.now().isoformat()}

## Hyperopt 結果
"""

    if latest:
        info = analyze_hyperopt_result(latest)
        report += f"""
- **最新結果**: {info["file"]}
- **檔案大小**: {info["size"]} bytes
- **修改時間**: {info["modified"]}
"""
    else:
        report += "\n未找到 hyperopt 結果檔案\n"

    # 儲存報告
    os.makedirs(output_dir, exist_ok=True)
    report_file = os.path.join(
        output_dir, f"analysis_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    )

    with open(report_file, "w") as f:
        f.write(report)

    print(f"報告已儲存: {report_file}")
    return report


def main():
    if len(sys.argv) < 2:
        print("用法: python3 analyze_results.py <策略名稱> [輸出目錄]")
        print("範例: python3 analyze_results.py nsgaii_bb_rpb_tsl_bi")
        sys.exit(1)

    strategy_name = sys.argv[1]
    output_dir = (
        sys.argv[2]
        if len(sys.argv) > 2
        else f"strategies/math_based/ga_framework/reports/{strategy_name}"
    )

    report = generate_report(strategy_name, output_dir)
    print("\n" + "=" * 50)
    print(report)


if __name__ == "__main__":
    main()
