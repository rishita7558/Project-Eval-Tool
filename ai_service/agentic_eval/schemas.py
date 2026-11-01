"""
Typed data schemas for the Agentic Evaluation Engine.
Covers plans, tool calls, audit traces, specialist agent contracts, and run state.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


class WorkflowType(str, enum.Enum):
    INDIVIDUAL_ASSIGNMENT = "individual_assignment"
    BATCH_ASSIGNMENT = "batch_assignment"
    INDIVIDUAL_SUMMARY = "individual_summary"
    BATCH_SUMMARY = "batch_summary"


class StepStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class ActorType(str, enum.Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HUMAN = "human"


@dataclass
class ToolCallRecord:
    """Auditable record of a single allowlisted tool invocation."""
    tool_call_id: str
    tool_name: str
    sanitized_arguments: Dict[str, Any]
    output: Any
    duration_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "toolCallId": self.tool_call_id,
            "toolName": self.tool_name,
            "arguments": self.sanitized_arguments,
            "output": self.output if self.success else None,
            "durationMs": round(self.duration_ms, 2),
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class AuditEvent:
    """
    Immutable audit event capturing what occurred, why it was chosen,
    what evidence backed it, and the resulting transition.
    """
    event_id: str
    run_id: str
    action: str
    rationale: str
    actor_type: ActorType
    evidence_references: List[str] = field(default_factory=list)
    outcome: str = "SUCCESS"
    next_step: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eventId": self.event_id,
            "runId": self.run_id,
            "action": self.action,
            "rationale": self.rationale,
            "actorType": self.actor_type.value,
            "evidenceReferences": self.evidence_references,
            "outcome": self.outcome,
            "nextStep": self.next_step,
            "timestamp": self.timestamp,
        }


@dataclass
class PlanStep:
    """A discrete, verifiable unit of execution inside a plan."""
    step_id: str
    tool: str
    purpose: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stepId": self.step_id,
            "tool": self.tool,
            "purpose": self.purpose,
            "status": self.status.value,
            "hasResult": self.result is not None,
            "error": self.error,
        }


@dataclass
class ExecutionPlan:
    """Structured plan emitted by the Planner and validated by code policy."""
    plan_id: str
    workflow: WorkflowType
    mode: int
    steps: List[PlanStep] = field(default_factory=list)
    replan_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "planId": self.plan_id,
            "workflow": self.workflow.value,
            "mode": self.mode,
            "steps": [s.to_dict() for s in self.steps],
            "replanCount": self.replan_count,
            "createdAt": self.created_at,
        }


@dataclass
class AgentOutput:
    """Standardized output from specialist agents (Evaluator, Auditor, Critic)."""
    role: str
    decision: str  # "CONTINUE", "RETRY", "NEEDS_REVIEW", "FAIL"
    score_proposal: Optional[float] = None
    rationale: str = ""
    evidence_spans: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "decision": self.decision,
            "scoreProposal": self.score_proposal,
            "rationale": self.rationale,
            "evidenceSpans": self.evidence_spans,
            "findings": self.findings,
            "flags": self.flags,
            "model": self.model,
        }

