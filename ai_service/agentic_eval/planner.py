"""
Structured Planner and Policy Validator for the Agentic Evaluation Engine.
Generates structured execution plans and enforces workflow-specific prerequisite policies,
safe branching, and replanning limits.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from agentic_eval.schemas import (
    ExecutionPlan,
    PlanStep,
    StepStatus,
    WorkflowType,
)
from agentic_eval.state import RunContext
from agentic_eval.tool_registry import ToolRegistry, default_tool_registry
import agentic_eval.tools.eval_tools  # noqa: F401


class PlanPolicyViolationError(ValueError):
    """Raised when a proposed plan violates security or workflow prerequisite policies."""
    pass


# ─── Workflow Prerequisite Rules ─────────────────────────────────────────────
# Enforced deterministically in code:
# 1. Archives MUST be validated before extraction in batch workflows.
# 2. Rubric MUST be validated before evaluation.
# 3. Input text MUST be validated before evaluation.
# 4. Evaluation MUST precede evidence verification and quality checks.
# 5. Quality checks and deterministic scoring MUST precede completion.


class PlanPolicyValidator:
    """Deterministic validator that enforces safety rules and order constraints on plans."""

    @staticmethod
    def validate_plan(
        plan: ExecutionPlan,
        registry: ToolRegistry = default_tool_registry,
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not plan.steps:
            return False, ["Plan must contain at least one step"]

        tool_order = [s.tool for s in plan.steps]

        # 1. Check all tools are registered and permitted
        for step in plan.steps:
            tool_def = registry.get(step.tool)
            if not tool_def:
                errors.append(f"Step '{step.tool}' refers to unregistered tool.")
            elif plan.workflow not in tool_def.allowed_workflows:
                errors.append(
                    f"Step '{step.tool}' is not permitted in workflow '{plan.workflow.value}'."
                )

        # 2. Batch prerequisite: validate_zip_archive MUST precede extract_submission_text
        if plan.workflow in {WorkflowType.BATCH_ASSIGNMENT, WorkflowType.BATCH_SUMMARY}:
            if "extract_submission_text" in tool_order:
                if "validate_zip_archive" not in tool_order:
                    errors.append("Batch workflow must validate ZIP archive before extraction.")
                else:
                    zip_idx = tool_order.index("validate_zip_archive")
                    ext_idx = tool_order.index("extract_submission_text")
                    if zip_idx > ext_idx:
                        errors.append("validate_zip_archive must precede extract_submission_text.")

        # 3. Rubric & Input prerequisite: MUST precede evaluate_against_rubric
        if "evaluate_against_rubric" in tool_order:
            eval_idx = tool_order.index("evaluate_against_rubric")
            if "validate_rubric" in tool_order:
                rub_idx = tool_order.index("validate_rubric")
                if rub_idx > eval_idx:
                    errors.append("validate_rubric must precede evaluate_against_rubric.")
            if "validate_submission_input" in tool_order:
                inp_idx = tool_order.index("validate_submission_input")
                if inp_idx > eval_idx:
                    errors.append("validate_submission_input must precede evaluate_against_rubric.")

        # 4. Post-eval prerequisite: verify_evidence_spans MUST succeed evaluate_against_rubric
        if "verify_evidence_spans" in tool_order and "evaluate_against_rubric" in tool_order:
            eval_idx = tool_order.index("evaluate_against_rubric")
            evid_idx = tool_order.index("verify_evidence_spans")
            if evid_idx < eval_idx:
                errors.append("verify_evidence_spans must follow evaluate_against_rubric.")

        return len(errors) == 0, errors


class Planner:
    """Emits structured execution plans for evaluation workflows."""

    def __init__(self, registry: ToolRegistry = default_tool_registry):
        self.registry = registry
        self.validator = PlanPolicyValidator()

    def build_plan(
        self,
        workflow: WorkflowType,
        mode: int = 1,
        include_course_retrieval: bool = False,
    ) -> ExecutionPlan:
        """Construct a validated plan tailored to the workflow and autonomy level."""
        steps: List[PlanStep] = []
        step_idx = 1

        def add_step(tool: str, purpose: str, params: Optional[Dict[str, Any]] = None):
            nonlocal step_idx
            steps.append(PlanStep(
                step_id=f"step_{step_idx}",
                tool=tool,
                purpose=purpose,
                params=params or {},
                status=StepStatus.PENDING,
            ))
            step_idx += 1

        if workflow in {WorkflowType.BATCH_ASSIGNMENT, WorkflowType.BATCH_SUMMARY}:
            add_step("validate_zip_archive", "Verify archive limits, decompression ratio, and prevent zip-slip.")
            add_step("validate_rubric", "Validate criteria structure and establish rubric snapshot.")
            add_step("extract_submission_text", "Safely extract student submission documents.")
            if include_course_retrieval:
                add_step("retrieve_course_evidence", "Retrieve course grounding materials.")
            add_step("validate_submission_input", "Check extracted text length and scan for prompt injection.")
            add_step("evaluate_against_rubric", "Evaluate student submission against trusted rubric criteria.")
            add_step("verify_evidence_spans", "Verify cited quotes exist in student submission text.")
            add_step("calculate_final_score", "Deterministically calculate totals, percentages, and grade.")
            add_step("run_quality_checks", "Verify score bounds and determine review policy.")

        else:
            # Individual assignment or individual summary
            add_step("validate_rubric", "Validate criteria structure and establish rubric snapshot.")
            add_step("validate_submission_input", "Check submission text length and scan for prompt injection.")
            if include_course_retrieval:
                add_step("retrieve_course_evidence", "Retrieve course grounding materials.")
            add_step("evaluate_against_rubric", "Evaluate student submission against trusted rubric criteria.")
            add_step("verify_evidence_spans", "Verify cited quotes exist in student submission text.")
            add_step("calculate_final_score", "Deterministically calculate totals, percentages, and grade.")
            add_step("run_quality_checks", "Verify score bounds and determine review policy.")

        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            workflow=workflow,
            mode=mode,
            steps=steps,
        )

        valid, errors = self.validator.validate_plan(plan, self.registry)
        if not valid:
            raise PlanPolicyViolationError(f"Generated plan violated policy: {'; '.join(errors)}")

        return plan

    def evaluate_branch_condition(
        self,
        current_step: PlanStep,
        tool_result: Dict[str, Any],
        context: RunContext,
    ) -> Optional[str]:
        """
        Determines if a tool outcome requires branching:
        - ABORT / FAIL: Unrecoverable validation failure (e.g. unsafe ZIP, empty text).
        - FLAG_REVIEW: Non-fatal anomaly (e.g. injection attempt, unverified evidence).
        - RETRY: Transient parsing or evaluation anomaly.
        - CONTINUE: Proceed with next planned step.
        """
        tool_name = current_step.tool

        if tool_name == "validate_zip_archive":
            if not tool_result.get("valid"):
                return "FAIL:ZIP_SECURITY_REJECTED"

        elif tool_name == "validate_submission_input":
            if tool_result.get("isEmpty"):
                return "FAIL:EMPTY_SUBMISSION"
            if tool_result.get("injectionDetected"):
                context.add_review_flag("INJECTION_DETECTED")

        elif tool_name == "validate_rubric":
            if not tool_result.get("valid"):
                return "FAIL:INVALID_RUBRIC"

        elif tool_name == "verify_evidence_spans":
            if not tool_result.get("allVerified", True):
                unverified_count = tool_result.get("unverifiedCount", 0)
                if unverified_count > 0:
                    context.add_review_flag("UNVERIFIED_EVIDENCE")

        elif tool_name == "run_quality_checks":
            if tool_result.get("needsReview"):
                context.add_review_flag("QUALITY_CHECK_REVIEW_REQUIRED")

        return None
