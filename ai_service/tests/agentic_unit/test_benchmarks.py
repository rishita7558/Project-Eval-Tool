"""
Unit tests for Milestone 6: Benchmark Dataset Loader and Experiment Runner.
"""

import asyncio
import os
import sys
import tempfile
import pytest

AI_SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if AI_SERVICE_ROOT not in sys.path:
    sys.path.insert(0, AI_SERVICE_ROOT)

from evaluation_benchmarks.dataset_loader import (
    get_demonstration_cases,
    load_benchmark_dataset,
)
from evaluation_benchmarks.experiment_runner import (
    ExperimentRunner,
    save_experiment_results,
)


class TestBenchmarkSuite:
    def test_demonstration_cases_cover_all_profiles(self):
        cases = get_demonstration_cases()
        assert len(cases) == 6
        case_types = {c.case_type for c in cases}
        expected_types = {"strong", "average", "weak", "incomplete", "borderline", "adversarial"}
        assert expected_types == case_types

    def test_dataset_provenance_labels(self):
        dataset = load_benchmark_dataset()
        assert dataset["isHumanReference"] is False
        assert dataset["isSyntheticDemonstration"] is True
        assert "demonstration" in dataset["datasetName"].lower()

    def test_ablation_experiment_run(self):
        runner = ExperimentRunner()
        results = asyncio.run(runner.run_ablation())
        assert results["caseCount"] == 6
        assert len(results["groups"]) == 5

        # Check groups A through E
        group_ids = [g["groupId"] for g in results["groups"]]
        assert group_ids == ["A", "B", "C", "D", "E"]

        # Verify metrics exist for each group
        for g in results["groups"]:
            m = g["metrics"]
            assert "MAE" in m
            assert "RMSE" in m
            assert "withinTolerance1_5" in m
            assert "humanReviewRate" in m
            assert "evidenceVerificationRate" in m

    def test_save_results_and_generate_report(self):
        runner = ExperimentRunner()
        results = asyncio.run(runner.run_ablation())
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = save_experiment_results(results, output_dir=tmpdir)
            assert os.path.isfile(report_file)
            with open(report_file, "r", encoding="utf-8") as f:
                content = f.read()
                assert "Comparative Ablation Summary" in content
                assert "Group A" in content
                assert "Group E" in content

