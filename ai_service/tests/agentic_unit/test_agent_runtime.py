"""
Unit tests for Milestone 1: Agent Runtime Foundation, State Machine,
Feature Flags, Execution Budgets, and Trace Observability.
"""

import os
import sys
import time
import pytest

AI_SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if AI_SERVICE_ROOT not in sys.path:
    sys.path.insert(0, AI_SERVICE_ROOT)

from agentic_eval.config import (
    AgenticConfig,
    ExecutionBudgets,
    ConfigOverride,
    get_config,
    load_config,
)
from agentic_eval.schemas import (
    ActorType,
    AuditEvent,
    ToolCallRecord,
    WorkflowType,
)
from agentic_eval.state import (
    BudgetExceededError,
    InvalidStateTransitionError,
    RunContext,
)
from agentic_eval.traces import (
    TraceManager,
    sanitize_payload,
)
from eval_validation.review_policy import EvalStatus


class TestAgenticConfig:
    def test_default_config_is_safe_baseline(self):
        config = load_config()
        assert config.eval_enabled is False
        assert config.planner_enabled is False
        assert config.tools_enabled is False
        assert config.critic_enabled is False
        assert config.multi_agent_enabled is False
        assert config.mode == 0

    def test_config_override_scoped_context(self):
        assert get_config().eval_enabled is False
        with ConfigOverride(eval_enabled=True, mode=2, planner_enabled=True, tools_enabled=True):
            active = get_config()
            assert active.eval_enabled is True
            assert active.mode == 2
            assert active.planner_enabled is True
            assert active.tools_enabled is True
        assert get_config().eval_enabled is False

    def test_budget_defaults_enforced(self):
        budgets = ExecutionBudgets()
        assert budgets.max_plan_steps == 10
        assert budgets.max_tool_calls == 15
        assert budgets.max_retries == 3
        assert budgets.max_execution_time_seconds == 60.0
        assert budgets.max_token_budget == 8000


class TestRunContextStateMachine:
    def test_initial_state_is_received(self):
        ctx = RunContext(workflow_type=WorkflowType.INDIVIDUAL_ASSIGNMENT, submission_id="sub_001")
        assert ctx.current_state == EvalStatus.RECEIVED
        assert ctx.submission_id == "sub_001"
        assert len(ctx.audit_events) == 0

    def test_legal_state_progression(self):
        ctx = RunContext(workflow_type=WorkflowType.INDIVIDUAL_ASSIGNMENT, submission_id="sub_001")
        ctx.transition_to(EvalStatus.VALIDATING, "Validating submission input")
        assert ctx.current_state == EvalStatus.VALIDATING

        ctx.transition_to(EvalStatus.EVALUATING, "Running evaluator")
        assert ctx.current_state == EvalStatus.EVALUATING

        ctx.transition_to(EvalStatus.VALIDATING_RESULT, "Checking output criteria")
        assert ctx.current_state == EvalStatus.VALIDATING_RESULT

        ctx.transition_to(EvalStatus.COMPLETED, "Grading completed")
        assert ctx.current_state == EvalStatus.COMPLETED
        assert ctx.end_time is not None
        assert len(ctx.audit_events) == 4

    def test_illegal_state_transition_raises(self):
        ctx = RunContext(workflow_type=WorkflowType.INDIVIDUAL_ASSIGNMENT, submission_id="sub_001")
        # Direct jump from RECEIVED to COMPLETED is forbidden by legal state machine
        with pytest.raises(InvalidStateTransitionError, match="Cannot transition"):
            ctx.transition_to(EvalStatus.COMPLETED)
        assert ctx.current_state == EvalStatus.RECEIVED

    def test_terminal_state_prevents_transitions(self):
        ctx = RunContext(workflow_type=WorkflowType.INDIVIDUAL_ASSIGNMENT)
        ctx.transition_to(EvalStatus.FAILED, "Immediate failure")
        with pytest.raises(InvalidStateTransitionError):
            ctx.transition_to(EvalStatus.COMPLETED)


class TestExecutionBudgets:
    def test_tool_call_budget_enforcement(self):
        ctx = RunContext()
        small_budget = ExecutionBudgets(max_tool_calls=2)
        # Add 2 dummy tool records
        ctx.record_tool_call(ToolCallRecord("1", "tool_a", {}, {}, 10.0, True))
        ctx.record_tool_call(ToolCallRecord("2", "tool_b", {}, {}, 12.0, True))

        with pytest.raises(BudgetExceededError, match="Maximum tool call budget reached"):
            ctx.check_budget_limits(small_budget)
        assert ctx.failure_code == "BUDGET_TOOL_CALLS_EXCEEDED"

    def test_plan_steps_budget_enforcement(self):
        ctx = RunContext()
        small_budget = ExecutionBudgets(max_plan_steps=2)
        ctx.completed_steps = ["step_1", "step_2"]

        with pytest.raises(BudgetExceededError, match="Maximum plan step budget reached"):
            ctx.check_budget_limits(small_budget)
        assert ctx.failure_code == "BUDGET_PLAN_STEPS_EXCEEDED"

    def test_token_budget_enforcement(self):
        ctx = RunContext()
        small_budget = ExecutionBudgets(max_token_budget=100)
        ctx.total_tokens_used = 150

        with pytest.raises(BudgetExceededError, match="Token budget exceeded"):
            ctx.check_budget_limits(small_budget)
        assert ctx.failure_code == "BUDGET_TOKENS_EXCEEDED"

    def test_time_budget_enforcement(self):
        ctx = RunContext()
        ctx.start_time = time.monotonic() - 100.0  # 100s ago
        budget = ExecutionBudgets(max_execution_time_seconds=30.0)

        with pytest.raises(BudgetExceededError, match="Execution time limit exceeded"):
            ctx.check_budget_limits(budget)
        assert ctx.failure_code == "BUDGET_TIME_EXCEEDED"


class TestObservabilityAndSanitization:
    def test_credential_sanitization(self):
        payload = {
            "api_key": "gsk_secret1234567890",
            "groq_api_key": "gsk_groqsecret",
            "normal_field": "hello world",
            "nested": {
                "jwt_secret": "myjwtsecret",
                "other": "safe",
            }
        }
        sanitized = sanitize_payload(payload)
        assert sanitized["api_key"] == "[REDACTED_CREDENTIAL]"
        assert sanitized["groq_api_key"] == "[REDACTED_CREDENTIAL]"
        assert sanitized["nested"]["jwt_secret"] == "[REDACTED_CREDENTIAL]"
        assert sanitized["normal_field"] == "hello world"
        assert sanitized["nested"]["other"] == "safe"

    def test_long_string_truncation(self):
        long_str = "A" * 500
        sanitized = sanitize_payload(long_str, max_string_len=50)
        assert len(sanitized) < 150
        assert "redacted" in sanitized

    def test_trace_manager_records_by_run_id(self):
        tm = TraceManager()
        evt1 = AuditEvent(event_id="e1", run_id="run_100", action="TEST_ACTION", rationale="Testing", actor_type=ActorType.DETERMINISTIC)
        evt2 = AuditEvent(event_id="e2", run_id="run_200", action="ANOTHER_ACTION", rationale="Testing 2", actor_type=ActorType.LLM)
        tm.record_event(evt1)
        tm.record_event(evt2)

        trace_100 = tm.get_run_trace("run_100")
        assert len(trace_100) == 1
        assert trace_100[0]["eventId"] == "e1"

        trace_200 = tm.get_run_trace("run_200")
        assert len(trace_200) == 1
        assert trace_200[0]["eventId"] == "e2"

