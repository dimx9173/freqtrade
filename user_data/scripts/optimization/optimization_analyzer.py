#!/usr/bin/env python3
"""
FreqAI Optimization Performance Analyzer
=========================================

Advanced performance analysis tool for FreqAI optimization results.
Provides detailed analysis, trend identification, and visualization.

Features:
- Performance trend analysis
- Parameter correlation analysis
- Optimization effectiveness scoring
- Comparative analysis across iterations
- Export reports and recommendations

Author: AI Quantitative Strategy Engineer
Version: 1.0.0
"""

import os
import json
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
import seaborn as sns
import warnings

warnings.filterwarnings("ignore")


class OptimizationAnalyzer:
    """Comprehensive analyzer for FreqAI optimization results"""

    def __init__(self, report_dir: str = "user_data/report"):
        """Initialize the analyzer"""
        self.base_dir = Path("/Users/carlos/pCloud Drive/CryptoWork/freqtrade")
        self.report_dir = self.base_dir / report_dir

        if not self.report_dir.exists():
            raise FileNotFoundError(f"Report directory not found: {self.report_dir}")

        self.optimization_data = []
        self.performance_targets = {
            "annual_return": 100.0,
            "annual_loss": 10.0,
            "max_drawdown": 8.0,
            "win_rate": 60.0,
            "profit_loss_ratio": 2.5,
        }

        print(f"📊 Optimizer Analyzer initialized")
        print(f"📁 Report directory: {self.report_dir}")

    def load_optimization_reports(self) -> bool:
        """Load all optimization reports from directory"""
        print("🔍 Loading optimization reports...")

        try:
            # Find all optimization reports
            report_files = list(self.report_dir.glob("optimization_report_iter*.json"))

            if not report_files:
                print("❌ No optimization reports found")
                return False

            print(f"📋 Found {len(report_files)} optimization reports")

            # Load and process each report
            for report_file in sorted(report_files):
                try:
                    with open(report_file, "r") as f:
                        report_data = json.load(f)

                    # Extract key information
                    iteration = report_data.get("iteration", 0)
                    timestamp = report_data.get("timestamp", "")
                    performance = report_data.get("performance_metrics", {})
                    suggestions = report_data.get("optimization_suggestions", {})
                    hyperopt = report_data.get("hyperopt_result", {})

                    # Compile data record
                    data_record = {
                        "iteration": iteration,
                        "timestamp": timestamp,
                        "report_file": str(report_file),
                        # Performance metrics
                        "performance_score": performance.get("performance_score", 0.0),
                        "total_profit": performance.get("total_profit", 0.0),
                        "win_rate": performance.get("win_rate", 0.0),
                        "max_drawdown": performance.get("max_drawdown", 0.0),
                        "total_trades": performance.get("total_trades", 0),
                        "sharpe": performance.get("sharpe", 0.0),
                        # Hyperopt results
                        "hyperopt_success": hyperopt.get("success", False),
                        "hyperopt_duration": hyperopt.get("duration", 0.0),
                        # Optimization adjustments
                        "adjustments_made": len(suggestions.get("parameter_adjustments", {})),
                        "suggestions_count": len(suggestions.get("strategy_modifications", [])),
                    }

                    self.optimization_data.append(data_record)

                except Exception as e:
                    print(f"⚠️  Error loading {report_file}: {str(e)}")
                    continue

            if self.optimization_data:
                self.optimization_data.sort(key=lambda x: x["iteration"])
                print(f"✅ Loaded {len(self.optimization_data)} optimization records")
                return True
            else:
                print("❌ No valid optimization data found")
                return False

        except Exception as e:
            print(f"💥 Error loading optimization reports: {str(e)}")
            return False

    def analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze performance trends across iterations"""
        print("📈 Analyzing performance trends...")

        if not self.optimization_data:
            return {"error": "No optimization data available"}

        try:
            df = pd.DataFrame(self.optimization_data)

            analysis = {
                "iterations_analyzed": len(df),
                "date_range": {
                    "start": df["timestamp"].min() if not df.empty else "N/A",
                    "end": df["timestamp"].max() if not df.empty else "N/A",
                },
            }

            # Performance score trends
            if "performance_score" in df.columns:
                scores = df["performance_score"].dropna()
                if not scores.empty:
                    analysis["performance_score"] = {
                        "initial": float(scores.iloc[0]),
                        "final": float(scores.iloc[-1]),
                        "best": float(scores.max()),
                        "worst": float(scores.min()),
                        "average": float(scores.mean()),
                        "improvement": float(scores.iloc[-1] - scores.iloc[0])
                        if len(scores) > 1
                        else 0.0,
                        "trend": "improving"
                        if len(scores) > 1 and scores.iloc[-1] > scores.iloc[0]
                        else "declining",
                        "volatility": float(scores.std()) if len(scores) > 1 else 0.0,
                    }

            # Profit trends
            if "total_profit" in df.columns:
                profits = df["total_profit"].dropna()
                if not profits.empty:
                    analysis["profit_trends"] = {
                        "initial": float(profits.iloc[0]),
                        "final": float(profits.iloc[-1]),
                        "best": float(profits.max()),
                        "worst": float(profits.min()),
                        "average": float(profits.mean()),
                        "improvement": float(profits.iloc[-1] - profits.iloc[0])
                        if len(profits) > 1
                        else 0.0,
                        "target_achieved": float(profits.max())
                        >= self.performance_targets["annual_return"],
                    }

            # Win rate trends
            if "win_rate" in df.columns:
                win_rates = df["win_rate"].dropna()
                if not win_rates.empty:
                    analysis["win_rate_trends"] = {
                        "initial": float(win_rates.iloc[0]),
                        "final": float(win_rates.iloc[-1]),
                        "best": float(win_rates.max()),
                        "average": float(win_rates.mean()),
                        "improvement": float(win_rates.iloc[-1] - win_rates.iloc[0])
                        if len(win_rates) > 1
                        else 0.0,
                        "target_achieved": float(win_rates.max())
                        >= self.performance_targets["win_rate"],
                    }

            # Drawdown trends
            if "max_drawdown" in df.columns:
                drawdowns = df["max_drawdown"].dropna()
                if not drawdowns.empty:
                    analysis["drawdown_trends"] = {
                        "initial": float(drawdowns.iloc[0]),
                        "final": float(drawdowns.iloc[-1]),
                        "best": float(drawdowns.min()),  # Lower is better for drawdown
                        "worst": float(drawdowns.max()),
                        "average": float(drawdowns.mean()),
                        "improvement": float(drawdowns.iloc[0] - drawdowns.iloc[-1])
                        if len(drawdowns) > 1
                        else 0.0,  # Reduction is improvement
                        "target_achieved": float(drawdowns.min())
                        <= self.performance_targets["max_drawdown"],
                    }

            # Trade frequency analysis
            if "total_trades" in df.columns:
                trades = df["total_trades"].dropna()
                if not trades.empty:
                    analysis["trade_frequency"] = {
                        "initial": int(trades.iloc[0]),
                        "final": int(trades.iloc[-1]),
                        "maximum": int(trades.max()),
                        "minimum": int(trades.min()),
                        "average": float(trades.mean()),
                        "trend": "increasing"
                        if len(trades) > 1 and trades.iloc[-1] > trades.iloc[0]
                        else "decreasing",
                    }

            return analysis

        except Exception as e:
            print(f"💥 Error analyzing performance trends: {str(e)}")
            return {"error": str(e)}

    def analyze_optimization_effectiveness(self) -> Dict[str, Any]:
        """Analyze the effectiveness of optimization process"""
        print("🎯 Analyzing optimization effectiveness...")

        if not self.optimization_data:
            return {"error": "No optimization data available"}

        try:
            df = pd.DataFrame(self.optimization_data)

            effectiveness = {
                "overall_assessment": "unknown",
                "target_achievement": {},
                "optimization_efficiency": {},
                "recommendations": [],
            }

            # Target achievement analysis
            if not df.empty:
                best_performance = (
                    df.loc[df["performance_score"].idxmax()]
                    if "performance_score" in df.columns
                    else None
                )

                if best_performance is not None:
                    targets_met = 0
                    total_targets = 0

                    # Check each target
                    if "total_profit" in best_performance:
                        total_targets += 1
                        if (
                            best_performance["total_profit"]
                            >= self.performance_targets["annual_return"]
                        ):
                            targets_met += 1

                    if "win_rate" in best_performance:
                        total_targets += 1
                        if best_performance["win_rate"] >= self.performance_targets["win_rate"]:
                            targets_met += 1

                    if "max_drawdown" in best_performance:
                        total_targets += 1
                        if (
                            best_performance["max_drawdown"]
                            <= self.performance_targets["max_drawdown"]
                        ):
                            targets_met += 1

                    effectiveness["target_achievement"] = {
                        "targets_met": targets_met,
                        "total_targets": total_targets,
                        "achievement_rate": (targets_met / total_targets * 100)
                        if total_targets > 0
                        else 0,
                        "best_performance": {
                            "iteration": int(best_performance["iteration"]),
                            "performance_score": float(best_performance["performance_score"]),
                            "total_profit": float(best_performance.get("total_profit", 0)),
                            "win_rate": float(best_performance.get("win_rate", 0)),
                            "max_drawdown": float(best_performance.get("max_drawdown", 0)),
                        },
                    }

            # Optimization efficiency
            if len(df) > 1:
                # Calculate improvement rate per iteration
                score_improvement = 0
                if "performance_score" in df.columns:
                    initial_score = df["performance_score"].iloc[0]
                    final_score = df["performance_score"].iloc[-1]
                    score_improvement = (
                        (final_score - initial_score) / len(df) if len(df) > 0 else 0
                    )

                # Calculate consistency
                score_volatility = (
                    df["performance_score"].std() if "performance_score" in df.columns else 0
                )

                effectiveness["optimization_efficiency"] = {
                    "improvement_per_iteration": float(score_improvement),
                    "score_volatility": float(score_volatility),
                    "consistency_rating": "high"
                    if score_volatility < 5
                    else "medium"
                    if score_volatility < 15
                    else "low",
                    "convergence_trend": self.analyze_convergence_trend(df),
                }

            # Generate recommendations
            effectiveness["recommendations"] = self.generate_optimization_recommendations(df)

            # Overall assessment
            achievement_rate = effectiveness.get("target_achievement", {}).get(
                "achievement_rate", 0
            )
            if achievement_rate >= 80:
                effectiveness["overall_assessment"] = "excellent"
            elif achievement_rate >= 60:
                effectiveness["overall_assessment"] = "good"
            elif achievement_rate >= 40:
                effectiveness["overall_assessment"] = "fair"
            else:
                effectiveness["overall_assessment"] = "needs_improvement"

            return effectiveness

        except Exception as e:
            print(f"💥 Error analyzing optimization effectiveness: {str(e)}")
            return {"error": str(e)}

    def analyze_convergence_trend(self, df: pd.DataFrame) -> str:
        """Analyze if optimization is converging"""
        if len(df) < 3 or "performance_score" in df.columns:
            return "insufficient_data"

        scores = df["performance_score"].dropna()
        if len(scores) < 3:
            return "insufficient_data"

        # Calculate recent vs early improvement rates
        mid_point = len(scores) // 2
        early_trend = np.polyfit(range(mid_point), scores[:mid_point], 1)[0] if mid_point > 1 else 0
        recent_trend = (
            np.polyfit(range(len(scores) - mid_point), scores[mid_point:], 1)[0]
            if len(scores) - mid_point > 1
            else 0
        )

        if abs(recent_trend) < 0.1:
            return "converged"
        elif recent_trend > early_trend:
            return "accelerating"
        elif recent_trend > 0:
            return "improving"
        else:
            return "deteriorating"

    def generate_optimization_recommendations(self, df: pd.DataFrame) -> List[str]:
        """Generate specific recommendations for optimization improvement"""
        recommendations = []

        if df.empty:
            return recommendations

        try:
            # Analyze performance trends
            if "performance_score" in df.columns:
                scores = df["performance_score"].dropna()
                if not scores.empty:
                    final_score = scores.iloc[-1]
                    score_trend = scores.iloc[-1] - scores.iloc[0] if len(scores) > 1 else 0

                    if final_score < 50:
                        recommendations.append(
                            "Performance score is low - consider revising optimization targets or strategy parameters"
                        )

                    if score_trend < 0:
                        recommendations.append(
                            "Performance is declining - review recent parameter changes and consider reverting"
                        )

                    if len(scores) > 3 and scores.std() > 15:
                        recommendations.append(
                            "High performance volatility detected - consider more conservative optimization steps"
                        )

            # Analyze profit trends
            if "total_profit" in df.columns:
                profits = df["total_profit"].dropna()
                if not profits.empty and profits.iloc[-1] < 50:
                    recommendations.append(
                        "Low profitability - increase position sizing parameters or lower entry thresholds"
                    )

            # Analyze win rate
            if "win_rate" in df.columns:
                win_rates = df["win_rate"].dropna()
                if not win_rates.empty and win_rates.iloc[-1] < 50:
                    recommendations.append(
                        "Low win rate - tighten signal quality filters or improve entry conditions"
                    )

            # Analyze drawdown
            if "max_drawdown" in df.columns:
                drawdowns = df["max_drawdown"].dropna()
                if not drawdowns.empty and drawdowns.iloc[-1] > 15:
                    recommendations.append(
                        "High drawdown - implement stricter risk management and position sizing controls"
                    )

            # Analyze trade frequency
            if "total_trades" in df.columns:
                trades = df["total_trades"].dropna()
                if not trades.empty:
                    avg_trades = trades.mean()
                    if avg_trades < 20:
                        recommendations.append(
                            "Low trade frequency - consider lowering confidence thresholds or expanding time windows"
                        )
                    elif avg_trades > 200:
                        recommendations.append(
                            "Very high trade frequency - consider tightening filters to improve trade quality"
                        )

            # General optimization recommendations
            if len(df) >= 3:
                recommendations.append(
                    "Consider running additional iterations with fine-tuned parameters"
                )

            if len(df) < 3:
                recommendations.append(
                    "Insufficient data for comprehensive analysis - run more optimization iterations"
                )

        except Exception as e:
            recommendations.append(f"Error generating recommendations: {str(e)}")

        return recommendations

    def create_performance_visualization(self, output_dir: str = "user_data/report") -> bool:
        """Create comprehensive performance visualization"""
        print("📊 Creating performance visualization...")

        if not self.optimization_data:
            print("❌ No data available for visualization")
            return False

        try:
            df = pd.DataFrame(self.optimization_data)

            # Setup the plot
            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle("FreqAI Optimization Performance Analysis", fontsize=16, fontweight="bold")

            # Performance Score Trend
            if "performance_score" in df.columns:
                axes[0, 0].plot(
                    df["iteration"], df["performance_score"], marker="o", linewidth=2, markersize=6
                )
                axes[0, 0].set_title("Performance Score Trend")
                axes[0, 0].set_xlabel("Iteration")
                axes[0, 0].set_ylabel("Performance Score")
                axes[0, 0].grid(True, alpha=0.3)
                axes[0, 0].axhline(y=75, color="g", linestyle="--", alpha=0.7, label="Target (75)")
                axes[0, 0].legend()

            # Profit Trend
            if "total_profit" in df.columns:
                axes[0, 1].plot(
                    df["iteration"],
                    df["total_profit"],
                    marker="s",
                    linewidth=2,
                    markersize=6,
                    color="green",
                )
                axes[0, 1].set_title("Total Profit Trend")
                axes[0, 1].set_xlabel("Iteration")
                axes[0, 1].set_ylabel("Profit (%)")
                axes[0, 1].grid(True, alpha=0.3)
                axes[0, 1].axhline(
                    y=100, color="r", linestyle="--", alpha=0.7, label="Target (100%)"
                )
                axes[0, 1].legend()

            # Win Rate Trend
            if "win_rate" in df.columns:
                axes[0, 2].plot(
                    df["iteration"],
                    df["win_rate"],
                    marker="^",
                    linewidth=2,
                    markersize=6,
                    color="blue",
                )
                axes[0, 2].set_title("Win Rate Trend")
                axes[0, 2].set_xlabel("Iteration")
                axes[0, 2].set_ylabel("Win Rate (%)")
                axes[0, 2].grid(True, alpha=0.3)
                axes[0, 2].axhline(y=60, color="r", linestyle="--", alpha=0.7, label="Target (60%)")
                axes[0, 2].legend()

            # Max Drawdown Trend
            if "max_drawdown" in df.columns:
                axes[1, 0].plot(
                    df["iteration"],
                    df["max_drawdown"],
                    marker="v",
                    linewidth=2,
                    markersize=6,
                    color="red",
                )
                axes[1, 0].set_title("Max Drawdown Trend")
                axes[1, 0].set_xlabel("Iteration")
                axes[1, 0].set_ylabel("Max Drawdown (%)")
                axes[1, 0].grid(True, alpha=0.3)
                axes[1, 0].axhline(y=8, color="g", linestyle="--", alpha=0.7, label="Target (8%)")
                axes[1, 0].legend()

            # Trade Frequency
            if "total_trades" in df.columns:
                axes[1, 1].bar(df["iteration"], df["total_trades"], alpha=0.7, color="orange")
                axes[1, 1].set_title("Trade Frequency by Iteration")
                axes[1, 1].set_xlabel("Iteration")
                axes[1, 1].set_ylabel("Total Trades")
                axes[1, 1].grid(True, alpha=0.3)

            # Performance Score Distribution
            if "performance_score" in df.columns:
                axes[1, 2].hist(
                    df["performance_score"],
                    bins=min(len(df), 10),
                    alpha=0.7,
                    color="purple",
                    edgecolor="black",
                )
                axes[1, 2].set_title("Performance Score Distribution")
                axes[1, 2].set_xlabel("Performance Score")
                axes[1, 2].set_ylabel("Frequency")
                axes[1, 2].grid(True, alpha=0.3)

            plt.tight_layout()

            # Save the plot
            output_path = (
                Path(output_dir)
                / f"optimization_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.show()

            print(f"✅ Visualization saved to: {output_path}")
            return True

        except Exception as e:
            print(f"💥 Error creating visualization: {str(e)}")
            return False

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report"""
        print("📋 Generating comprehensive analysis report...")

        report = {
            "analysis_timestamp": datetime.now().isoformat(),
            "data_summary": {
                "total_iterations": len(self.optimization_data),
                "date_range": "N/A",
                "performance_targets": self.performance_targets,
            },
        }

        if not self.optimization_data:
            report["error"] = "No optimization data available"
            return report

        # Get date range
        if self.optimization_data:
            timestamps = [d["timestamp"] for d in self.optimization_data if d.get("timestamp")]
            if timestamps:
                report["data_summary"]["date_range"] = {
                    "start": min(timestamps),
                    "end": max(timestamps),
                }

        # Add detailed analysis
        report["performance_trends"] = self.analyze_performance_trends()
        report["optimization_effectiveness"] = self.analyze_optimization_effectiveness()

        # Add raw data
        report["iteration_data"] = self.optimization_data

        return report

    def save_report(self, report: Dict[str, Any], output_dir: str = "user_data/report") -> str:
        """Save comprehensive report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path(output_dir) / f"optimization_analysis_{timestamp}.json"

        try:
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2, default=str)

            print(f"✅ Analysis report saved to: {report_file}")
            return str(report_file)

        except Exception as e:
            print(f"💥 Error saving report: {str(e)}")
            return ""

    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print comprehensive summary of analysis"""
        print("\n" + "=" * 80)
        print("📊 FREQAI OPTIMIZATION ANALYSIS SUMMARY")
        print("=" * 80)

        # Data summary
        data_summary = report.get("data_summary", {})
        print(f"📋 Analysis Overview:")
        print(f"   Total Iterations: {data_summary.get('total_iterations', 0)}")
        print(f"   Analysis Date: {data_summary.get('analysis_timestamp', 'N/A')[:19]}")

        # Performance trends
        perf_trends = report.get("performance_trends", {})
        if "performance_score" in perf_trends:
            score_data = perf_trends["performance_score"]
            print(f"\n🎯 Performance Score Analysis:")
            print(f"   Initial Score: {score_data.get('initial', 0):.1f}")
            print(f"   Final Score: {score_data.get('final', 0):.1f}")
            print(f"   Best Score: {score_data.get('best', 0):.1f}")
            print(f"   Improvement: {score_data.get('improvement', 0):+.1f}")
            print(f"   Trend: {score_data.get('trend', 'unknown').upper()}")

        # Profit analysis
        if "profit_trends" in perf_trends:
            profit_data = perf_trends["profit_trends"]
            print(f"\n💰 Profit Analysis:")
            print(f"   Best Profit: {profit_data.get('best', 0):.2f}%")
            print(f"   Final Profit: {profit_data.get('final', 0):.2f}%")
            print(
                f"   Target Achieved: {'✅ YES' if profit_data.get('target_achieved', False) else '❌ NO'}"
            )

        # Effectiveness analysis
        effectiveness = report.get("optimization_effectiveness", {})
        if "target_achievement" in effectiveness:
            target_data = effectiveness["target_achievement"]
            print(f"\n🎯 Target Achievement:")
            print(
                f"   Targets Met: {target_data.get('targets_met', 0)}/{target_data.get('total_targets', 0)}"
            )
            print(f"   Achievement Rate: {target_data.get('achievement_rate', 0):.1f}%")
            print(
                f"   Overall Assessment: {effectiveness.get('overall_assessment', 'unknown').upper()}"
            )

        # Recommendations
        recommendations = effectiveness.get("recommendations", [])
        if recommendations:
            print(f"\n💡 Key Recommendations:")
            for i, rec in enumerate(recommendations[:5], 1):  # Show top 5
                print(f"   {i}. {rec}")

        print("\n" + "=" * 80)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="FreqAI Optimization Performance Analyzer")
    parser.add_argument(
        "--report-dir", default="user_data/report", help="Directory containing optimization reports"
    )
    parser.add_argument(
        "--output-dir", default="user_data/report", help="Output directory for analysis results"
    )
    parser.add_argument("--visualize", action="store_true", help="Create performance visualization")
    parser.add_argument(
        "--save-report", action="store_true", help="Save comprehensive analysis report"
    )

    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════╗
║            FreqAI Optimization Performance Analyzer          ║
║                     Analysis & Insights                      ║
╚══════════════════════════════════════════════════════════════╝
""")

    try:
        # Initialize analyzer
        analyzer = OptimizationAnalyzer(args.report_dir)

        # Load optimization reports
        if not analyzer.load_optimization_reports():
            print("💥 Failed to load optimization reports")
            return 1

        # Generate comprehensive report
        report = analyzer.generate_comprehensive_report()

        # Print summary
        analyzer.print_summary(report)

        # Create visualization if requested
        if args.visualize:
            analyzer.create_performance_visualization(args.output_dir)

        # Save report if requested
        if args.save_report:
            analyzer.save_report(report, args.output_dir)

        print("\n✅ Analysis completed successfully!")
        return 0

    except Exception as e:
        print(f"\n💥 Critical error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())
