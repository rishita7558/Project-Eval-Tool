"""
Run context and explicit state machine for the Agentic Evaluation Engine.
Reuses the legal evaluation state transitions from eval_validation.review_policy.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agentic_eval.config import ExecutionBudgets, get_config
from agentic_eval.schemas import (
    ActorType,
    AuditEvent,
    ExecutionPlan,
    ToolCallRecord,
    WorkflowType,
)
from eval_validation.review_policy import (
    EvalStatus,
    assert_legal_transition,
    is_legal_transition,
)


class BudgetExceededError(RuntimeError):
    """Raised when an evaluation run exceeds configured time, step, or tool call limits."""
    pass


class InvalidStateTransitionError(ValueError):
    """Raised when attempting an unauthorized or unmapped state machine transition."""
    pass


@dataclass
class RunContext:
    """
    Explicit, auditable context for an individual evaluation run.
    Stores complete operational telemetry, legal state, and budget tracking.
    """
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_type: WorkflowType = WorkflowType.INDIVIDUAL_ASSIGNMENT
    submission_id: str = ""
    evaluation_session_id: Optional[str] = None
    rubric_snapshot_id: Optional[str] = None

    current_state: EvalStatus = EvalStatus.RECEIVED
    plan: Optional[ExecutionPlan] = None
    completed_steps: List[str] = field(default_factory=list)
    tool_invocations: List[ToolCallRecord] = field(default_factory=list)
    audit_events: List[AuditEvent] = field(default_factory=list)

    retry_counts: Dict[str, int] = field(default_factory=dict)
    review_flags: List[str] = field(default_factory=list)
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None

    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    total_tokens_used: int = 0
    estimated_cost: float = 0.0
    model_name: Optional[str] = None

    # Draft and verified results
    draft_result: Optional[Dict[str, Any]] = None
    final_result: Optional[Dict[str, Any]] = None

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    def transition_to(self, new_status: EvalStatus, reason: str = "", actor: ActorType = ActorType.DETERMINISTIC) -> None:
        """Enforce legal evaluation state transitions from review_policy."""
        if not is_legal_transition(self.current_state, new_status):
            msg = f"Cannot transition run {self.run_id} from {self.current_state} to {new_status}"
            self.record_audit_event(
                action="INVALID_TRANSITION_REJECTED",
                rationale=msg,
                actor_type=ActorType.DETERMINISTIC,
                outcome="REJECTED",
            )
            raise InvalidStateTransitionError(msg)

        prev_state = self.current_state
        self.current_state = new_status

        self.record_audit_event(
            action=f"STATE_TRANSITION:{prev_state.value}->{new_status.value}",
            rationale=reason or f"Transitioned to {new_status.value}",
            actor_type=actor,
            outcome="SUCCESS",
            next_step=new_status.value,
        )

        if new_status in {EvalStatus.COMPLETED, EvalStatus.FAILED}:
            self.end_time = time.monotonic()

    def check_budget_limits(self, budgets: Optional[ExecutionBudgets] = None) -> None:
        """Verify the run has not exceeded plan step, tool call, time, or token limits."""
        cfg_budgets = budgets or get_config().budgets

        # 1. Elapsed time check
        if self.elapsed_seconds() > cfg_budgets.max_execution_time_seconds:
            err = f"Execution time limit exceeded ({self.elapsed_seconds():.1f}s > {cfg_budgets.max_execution_time_seconds}s)"
            self.failure_code = "BUDGET_TIME_EXCEEDED"
            self.failure_message = err
            raise BudgetExceededError(err)

        # 2. Tool calls limit
        if len(self.tool_invocations) >= cfg_budgets.max_tool_calls:
            err = f"Maximum tool call budget reached ({len(self.tool_invocations)} >= {cfg_budgets.max_tool_calls})"
            self.failure_code = "BUDGET_TOOL_CALLS_EXCEEDED"
            self.failure_message = err
            raise BudgetExceededError(err)

        # 3. Plan steps limit
        if len(self.completed_steps) >= cfg_budgets.max_plan_steps:
            err = f"Maximum plan step budget reached ({len(self.completed_steps)} >= {cfg_budgets.max_plan_steps})"
            self.failure_code = "BUDGET_PLAN_STEPS_EXCEEDED"
            self.failure_message = err
            raise BudgetExceededError(err)

        # 4. Token budget
        if self.total_tokens_used > cfg_budgets.max_token_budget:
            err = f"Token budget exceeded ({self.total_tokens_used} > {cfg_budgets.max_token_budget})"
            self.failure_code = "BUDGET_TOKENS_EXCEEDED"
            self.failure_message = err
            raise BudgetExceededError(err)

    def record_tool_call(self, record: ToolCallRecord) -> None:
        self.tool_invocations.append(record)

    def record_audit_event(
        self,
        action: str,
        rationale: str,
        actor_type: ActorType = ActorType.DETERMINISTIC,
        evidence_references: Optional[List[str]] = None,
        outcome: str = "SUCCESS",
        next_step: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            run_id=self.run_id,
            action=action,
            rationale=rationale,
            actor_type=actor_type,
            evidence_references=evidence_references or [],
            outcome=outcome,
            next_step=next_step,
        )
        self.audit_events.append(event)
        return event

    def add_review_flag(self, flag: str) -> None:
        if flag and flag not in self.review_flags:
            self.review_flags.append(flag)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Sanitized summary suitable for logs and API responses (no secrets or huge raw text)."""
        return {
            "runId": self.run_id,
            "workflowType": self.workflow_type.value,
            "submissionId": self.submission_id,
            "sessionId": self.evaluation_session_id,
            "currentState": self.current_state.value,
            "completedStepCount": len(self.completed_steps),
            "toolCallCount": len(self.tool_invocations),
            "auditEventCount": len(self.audit_events),
            "elapsedSeconds": round(self.elapsed_seconds(), 2),
            "reviewFlags": self.review_flags,
            "needsReview": self.current_state == EvalStatus.NEEDS_REVIEW or bool(self.review_flags),
            "failureCode": self.failure_code,
            "failureMessage": self.failure_message,
            "totalTokensUsed": self.total_tokens_used,
            "model": self.model_name,
        }

