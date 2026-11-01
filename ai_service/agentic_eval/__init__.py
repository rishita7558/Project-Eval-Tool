"""
Agentic Evaluation Layer.
Provides bounded autonomy, structured planning, safe tool registry,
auditable decision tracing, and specialist multi-agent collaboration
for the Agentic Virtual Classroom evaluation pipelines.
"""

from agentic_eval.config import AgenticConfig, get_config, load_config, set_config, ConfigOverride
from agentic_eval.schemas import (
    WorkflowType,
    StepStatus,
    ActorType,
    ToolCallRecord,
    AuditEvent,
    PlanStep,
    ExecutionPlan,
    AgentOutput,
)
from agentic_eval.state import (
    RunContext,
    BudgetExceededError,
    InvalidStateTransitionError,
)
from agentic_eval.traces import trace_manager, sanitize_payload

__all__ = [
    "AgenticConfig",
    "get_config",
    "load_config",
    "set_config",
    "ConfigOverride",
    "WorkflowType",
    "StepStatus",
    "ActorType",
    "ToolCallRecord",
    "AuditEvent",
    "PlanStep",
    "ExecutionPlan",
    "AgentOutput",
    "RunContext",
    "BudgetExceededError",
    "InvalidStateTransitionError",
    "trace_manager",
    "sanitize_payload",
]

