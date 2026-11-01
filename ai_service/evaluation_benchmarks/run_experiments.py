"""
CLI runner for the experimental evaluation and ablation benchmark harness.
Usage:
    cd ai_service
    .\\venv\\Scripts\\python.exe -m evaluation_benchmarks.run_experiments
"""

import asyncio
import os
import sys

# Ensure ai_service is on sys.path
AI_SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AI_SERVICE_ROOT not in sys.path:
    sys.path.insert(0, AI_SERVICE_ROOT)

from evaluation_benchmarks.experiment_runner import ExperimentRunner, save_experiment_results


async def main():
    print("=" * 72)
    print("Agentic Virtual Classroom — Experimental Evaluation Benchmark Runner")
    print("=" * 72)

    runner = ExperimentRunner()
    print("Running 5-group ablation study across benchmark cases...")
    results = await runner.run_ablation()

    print(f"\nCompleted evaluation of {results['caseCount']} cases across 5 groups.")
    print("-" * 72)
    print(f"{'Group':<8} {'Configuration':<25} {'MAE':<8} {'RMSE':<8} {'Within 1.5':<12} {'Review Rate':<12}")
    print("-" * 72)
    for g in results["groups"]:
        m = g["metrics"]
        print(f"{g['groupId']:<8} {g['groupName'][:24]:<25} {m['MAE']:<8.3f} {m['RMSE']:<8.3f} {m['withinTolerance1_5']*100:<11.1f}% {m['humanReviewRate']*100:<11.1f}%")

    report_path = save_experiment_results(results)
    print("-" * 72)
    print(f"Report saved to: {report_path}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())

