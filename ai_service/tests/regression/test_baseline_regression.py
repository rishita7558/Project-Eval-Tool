"""
Baseline regression tests for all four evaluation workflows.
Verifies that the non-agentic baseline execution path functions identically
and remains fully operational without modifications or regressions.
"""

import io
import json
import os
import sys
import tempfile
import zipfile
from unittest.mock import MagicMock, patch
import pytest

AI_SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if AI_SERVICE_ROOT not in sys.path:
    sys.path.insert(0, AI_SERVICE_ROOT)

VALID_RUBRIC_TEXT = """
Clarity - 5 points
Technical Accuracy - 10 points
Coverage - 5 points
"""

VALID_CRITERIA = [
    {"name": "Clarity", "maxScore": 5.0, "description": ""},
    {"name": "Technical Accuracy", "maxScore": 10.0, "description": ""},
    {"name": "Coverage", "maxScore": 5.0, "description": ""},
]

VALID_STUDENT_TEXT = (
    "Dynamic programming solves optimization problems by caching solutions to overlapping sub-problems. "
    "Memoization stores intermediate results to ensure each sub-problem is computed once, optimizing runtime."
)

VALID_LLM_ASSIGNMENT_RESPONSE = {
    "overallScore": 17.0,
    "criteria": [
        {"name": "Clarity", "score": 4.0, "maxScore": 5.0, "feedback": "Clear explanation of dynamic programming."},
        {"name": "Technical Accuracy", "score": 9.0, "maxScore": 10.0, "feedback": "Accurate description of memoization."},
        {"name": "Coverage", "score": 4.0, "maxScore": 5.0, "feedback": "Good coverage of core concepts."},
    ],
    "requiredConcepts": ["dynamic programming", "memoization"],
    "strengths": ["Strong conceptual grasp"],
    "weakAreas": ["Could include time complexity trade-offs"],
    "mistakes": [],
    "missingConcepts": [],
    "missingKeyPoints": [],
    "conceptsCovered": ["dynamic programming", "memoization"],
    "scoreExplanation": "High quality answer.",
    "feedback": "Well written response.",
    "confidence": 0.90,
}

VALID_LLM_SUMMARY_RESPONSE = {
    "metrics": {
        "topicCoverage": {"score": 8.5, "reason": "Addresses key lecture topics."},
        "conceptUnderstanding": {"score": 8.0, "reason": "Accurate concepts."},
        "clarityReadability": {"score": 8.0, "reason": "Readable and organized."},
        "technicalAccuracy": {"score": 8.0, "reason": "Technically sound."},
        "completeness": {"score": 7.5, "reason": "Most core points covered."},
        "conciseness": {"score": 8.0, "reason": "Succinct summary."},
        "logicalFlow": {"score": 8.0, "reason": "Coherent paragraphs."},
        "keywordMatch": {"score": 8.0, "reason": "Uses required terminology."},
        "criticalThinkingDepth": {"score": 7.0, "reason": "Shows understanding."},
        "aiConfidence": {"score": 9.0, "reason": "Clear signal."},
    },
    "strengths": ["Clear synthesis of material"],
    "weakAreas": ["Minor omissions in edge cases"],
    "improvements": ["Add concrete examples"],
    "summaryInsights": "Comprehensive and clear summary.",
    "missingKeyPoints": [],
    "conceptsCovered": ["dynamic programming", "memoization"],
}


def _make_mock_response(payload_dict):
    mock = MagicMock()
    mock.content = json.dumps(payload_dict)
    return mock


class TestBaselineWorkflows:
    """Verifies baseline execution across all four workflows."""

    @patch("assignment_evaluation.pipelines.orchestrator.ChatGroq")
    def test_workflow_1_single_assignment_baseline(self, MockGroq):
        """Workflow 1: Individual assignment evaluation."""
        import asyncio
        from assignment_evaluation.pipelines.orchestrator import evaluate_single_submission_with_llm

        MockGroq.return_value.invoke.return_value = _make_mock_response(VALID_LLM_ASSIGNMENT_RESPONSE)
        rubric_pkg = {
            "criteria": VALID_CRITERIA,
            "rubricText": VALID_RUBRIC_TEXT,
            "assignmentQuestion": "Explain dynamic programming.",
            "modelAnswer": "DP divides problems into sub-problems.",
        }

        result = asyncio.run(evaluate_single_submission_with_llm(
            student_text=VALID_STUDENT_TEXT,
            rubric_package=rubric_pkg,
            assignment_type="text",
            student_name="Alice Smith",
            file_name="alice.txt",
        ))

        assert result["success"] is True
        assert result["score"] == pytest.approx(17.0, abs=0.01)
        assert result["maxScore"] == 20.0
        assert "scoreBreakdown" in result
        assert len(result["scoreBreakdown"]) == 3
        assert result["needsReview"] is False
        assert result["injectionDetected"] is False

    def test_workflow_2_batch_assignment_zip_extraction(self):
        """Workflow 2: Batch assignment safe archive validation & extraction."""
        from assignment_evaluation.pipelines.orchestrator import _safe_extract_zip
        from eval_validation.input_validator import validate_zip_security

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("alice.txt", VALID_STUDENT_TEXT)
            zf.writestr("bob.txt", VALID_STUDENT_TEXT)
        buf.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(buf.read())
            zpath = f.name

        try:
            zip_check = validate_zip_security(zpath)
            assert zip_check.valid is True
            assert zip_check.entry_count == 2

            with tempfile.TemporaryDirectory() as dest:
                extracted = _safe_extract_zip(zpath, dest)
                assert len(extracted) == 2
        finally:
            if os.path.exists(zpath):
                os.unlink(zpath)

    @patch("summary_evaluation.agents.ai_evaluator.ChatGroq")
    def test_workflow_3_single_summary_baseline(self, MockGroq):
        """Workflow 3: Individual summary evaluation baseline."""
        from summary_evaluation.agents.ai_evaluator import evaluate_summary_with_ai

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = MagicMock(content=json.dumps(VALID_LLM_SUMMARY_RESPONSE))
        MockGroq.return_value.__or__ = lambda self, other: mock_chain

        with patch("summary_evaluation.agents.ai_evaluator.PromptTemplate") as MockPrompt:
            MockPrompt.from_template.return_value.__or__ = lambda self, other: mock_chain
            reference_package = {
                "reference_summary": "Lecture on dynamic programming and memoization.",
                "core_concepts": ["dynamic programming", "memoization"],
                "learning_objectives": ["Apply DP memoization"],
                "important_keywords": ["dynamic programming", "memoization"],
            }
            metrics = {"similarity": 0.85, "coverage": 0.80, "completeness": 0.90}
            result = evaluate_summary_with_ai(
                student_summary=VALID_STUDENT_TEXT,
                reference_package=reference_package,
                core_concepts=reference_package["core_concepts"],
                deterministic_metrics=metrics,
            )

        assert "overallScore" in result
        assert result["overallScore"] > 0
        assert "metrics" in result
        assert "topicCoverage" in result["metrics"]
        assert "needsReview" in result

    def test_workflow_4_batch_summary_zip_baseline(self):
        """Workflow 4: Batch summary archive validation and extraction."""
        from summary_evaluation.utils.zip_handler import safe_extract_zip, get_submission_files

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("student1.txt", "Summary content 1")
            zf.writestr("student2.txt", "Summary content 2")
        buf.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(buf.read())
            zpath = f.name

        try:
            with tempfile.TemporaryDirectory() as dest:
                out_dir = safe_extract_zip(zpath, dest)
                files = get_submission_files(out_dir)
                assert len(files) == 2
        finally:
            if os.path.exists(zpath):
                os.unlink(zpath)
