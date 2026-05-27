#!/usr/bin/env python3
"""
決策室儀表板 (The War Room Dashboard)
階段三：人工審核與前向測試
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from tabulate import tabulate


class WarRoomDashboard:
    """決策室儀表板"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.optimized_dir = self.base_dir / "successful_strategies" / "optimized_candidates"
        self.graduated_dir = self.base_dir / "successful_strategies" / "graduated"

        # 確保目錄存在
        self.graduated_dir.mkdir(parents=True, exist_ok=True)

    def get_optimized_strategies(self):
        """獲取所有優化後的策略"""
        strategies = []

        for strategy_dir in self.optimized_dir.glob("optimized_*"):
            if strategy_dir.is_dir():
                report_file = strategy_dir / "optimization_report.json"

                if report_file.exists():
                    with open(report_file, "r") as f:
                        report = json.load(f)

                    strategies.append(
                        {"name": strategy_dir.name, "dir": strategy_dir, "report": report}
                    )

        return sorted(strategies, key=lambda x: x["name"], reverse=True)

    def display_strategy_list(self):
        """顯示優化策略列表"""
        strategies = self.get_optimized_strategies()

        if not strategies:
            print("\n⚠️  優化池中無策略待審核\n")
            return

        print("\n" + "=" * 80)
        print("  🎯 決策室 - 優化策略列表")
        print("=" * 80 + "\n")

        table_data = []
        for i, strategy in enumerate(strategies, 1):
            comp = strategy["report"].get("performance_comparison", {})

            table_data.append(
                [
                    i,
                    strategy["name"][:40],
                    f"{comp.get('sharpe_before', 0):.2f}",
                    f"{comp.get('sharpe_after', 0):.2f}",
                    f"{comp.get('sharpe_improvement', 0) * 100:.1f}%",
                    f"{comp.get('profit_after', 0):.2f}%",
                ]
            )

        headers = ["#", "策略名稱", "夏普(前)", "夏普(後)", "改進", "利潤"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print()

    def display_strategy_detail(self, strategy_name):
        """顯示策略詳細信息"""
        strategy_dir = self.optimized_dir / strategy_name
        report_file = strategy_dir / "optimization_report.json"

        if not report_file.exists():
            print(f"\n❌ 策略不存在: {strategy_name}\n")
            return

        with open(report_file, "r") as f:
            report = json.load(f)

        print("\n" + "=" * 80)
        print(f"  📋 策略詳情: {strategy_name}")
        print("=" * 80 + "\n")

        # 基本信息
        print("【基本信息】")
        print(f"  策略名稱: {strategy_name}")
        print(f"  優化時間: {report.get('timestamp', 'N/A')}")

        # 指標組合
        original_meta = report.get("original_metadata", {})
        indicators = original_meta.get("indicators", [])
        print(f"  技術指標: {', '.join(indicators)}")

        # 性能比較
        print("\n【性能比較】")
        comp = report.get("performance_comparison", {})

        comparison_data = [
            [
                "夏普比率",
                f"{comp.get('sharpe_before', 0):.3f}",
                f"{comp.get('sharpe_after', 0):.3f}",
                f"{comp.get('sharpe_improvement', 0) * 100:.1f}%",
            ],
            [
                "總利潤",
                f"{comp.get('profit_before', 0):.2f}%",
                f"{comp.get('profit_after', 0):.2f}%",
                f"{comp.get('profit_improvement', 0) * 100:.1f}%",
            ],
        ]

        print(
            tabulate(comparison_data, headers=["指標", "優化前", "優化後", "改進"], tablefmt="grid")
        )

        # 原始KPI（來自 Foundry）
        print("\n【Foundry 原始 KPI (3個月)】")
        foundry_kpis = original_meta.get("kpis", {}).get("3m", {})
        if foundry_kpis:
            kpi_data = [
                ["勝率", f"{foundry_kpis.get('win_rate', 0) * 100:.1f}%"],
                ["月均交易", f"{foundry_kpis.get('trades_per_month', 0):.0f}"],
                ["最大回撤", f"{foundry_kpis.get('max_drawdown', 0) * 100:.1f}%"],
                ["利潤因子", f"{foundry_kpis.get('profit_factor', 0):.2f}"],
            ]
            print(tabulate(kpi_data, headers=["指標", "值"], tablefmt="grid"))

        # 優化參數
        print("\n【優化參數】")
        optimized_params = report.get("optimized_params", {})
        if optimized_params:
            print(json.dumps(optimized_params, indent=2))
        else:
            print("  無優化參數記錄")

        # 策略文件路徑
        strategy_files = list(strategy_dir.glob("*.py"))
        if strategy_files:
            print(f"\n【策略文件】")
            print(f"  {strategy_files[0]}")

        print("\n" + "=" * 80 + "\n")

    def mark_as_graduated(self, strategy_name, notes=""):
        """標記策略為畢業（準備實盤）"""
        strategy_dir = self.optimized_dir / strategy_name

        if not strategy_dir.exists():
            print(f"\n❌ 策略不存在: {strategy_name}\n")
            return False

        # 移動到畢業目錄
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        graduated_path = self.graduated_dir / f"{strategy_name}_graduated_{timestamp}"

        import shutil

        shutil.move(str(strategy_dir), str(graduated_path))

        # 記錄畢業信息
        graduation_record = {
            "graduated_at": datetime.now().isoformat(),
            "notes": notes,
            "status": "ready_for_deployment",
        }

        with open(graduated_path / "graduation_record.json", "w") as f:
            json.dump(graduation_record, f, indent=2)

        print(f"\n✅ 策略已標記為畢業: {graduated_path.name}")
        print(f"   備註: {notes}\n")

        return True

    def show_menu(self):
        """顯示交互式菜單"""
        while True:
            print("\n" + "=" * 80)
            print("  🏛️  決策室 (The War Room)")
            print("=" * 80)
            print("\n請選擇操作:")
            print("  1. 查看優化策略列表")
            print("  2. 查看策略詳情")
            print("  3. 標記策略為畢業")
            print("  4. 查看畢業策略")
            print("  0. 退出")
            print()

            choice = input("請輸入選項 (0-4): ").strip()

            if choice == "1":
                self.display_strategy_list()
            elif choice == "2":
                strategy_name = input("請輸入策略名稱: ").strip()
                self.display_strategy_detail(strategy_name)
            elif choice == "3":
                strategy_name = input("請輸入策略名稱: ").strip()
                notes = input("請輸入審核備註: ").strip()
                self.mark_as_graduated(strategy_name, notes)
            elif choice == "4":
                self.show_graduated_strategies()
            elif choice == "0":
                print("\n👋 退出決策室\n")
                break
            else:
                print("\n❌ 無效選項，請重新選擇\n")

    def show_graduated_strategies(self):
        """顯示畢業策略"""
        graduated = list(self.graduated_dir.glob("*_graduated_*"))

        if not graduated:
            print("\n⚠️  暫無畢業策略\n")
            return

        print("\n" + "=" * 80)
        print("  🎓 畢業策略列表")
        print("=" * 80 + "\n")

        for i, grad_dir in enumerate(sorted(graduated, reverse=True), 1):
            print(f"{i}. {grad_dir.name}")

            record_file = grad_dir / "graduation_record.json"
            if record_file.exists():
                with open(record_file, "r") as f:
                    record = json.load(f)
                print(f"   畢業時間: {record.get('graduated_at', 'N/A')}")
                print(f"   備註: {record.get('notes', '無')}")
            print()


def main():
    """主函數"""
    dashboard = WarRoomDashboard()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "list":
            dashboard.display_strategy_list()
        elif command == "detail" and len(sys.argv) > 2:
            dashboard.display_strategy_detail(sys.argv[2])
        elif command == "graduated":
            dashboard.show_graduated_strategies()
        else:
            print("用法:")
            print("  python3 war_room_dashboard.py             # 交互式模式")
            print("  python3 war_room_dashboard.py list        # 列出所有策略")
            print("  python3 war_room_dashboard.py detail NAME # 查看詳情")
            print("  python3 war_room_dashboard.py graduated   # 畢業策略")
    else:
        # 交互式模式
        dashboard.show_menu()


if __name__ == "__main__":
    main()
