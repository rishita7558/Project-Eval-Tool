"""
Structured audit events, decision explanations, and telemetry manager.
Enforces data redaction (no credentials or full student bodies in traces)
and structures inspectable reasoning for professors.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agentic_eval.schemas import AuditEvent, ToolCallRecord

logger = logging.getLogger("agentic_eval")


def sanitize_payload(obj: Any, max_string_len: int = 200, depth: int = 0) -> Any:
    """Recursively truncate long strings and redact sensitive credentials."""
    if depth > 4:
        return "<depth_limit_reached>"

    sensitive_keys = {"api_key", "groq_api_key", "openai_api_key", "password", "jwt_secret", "secret", "token"}

    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if str(k).lower() in sensitive_keys:
                sanitized[k] = "[REDACTED_CREDENTIAL]"
            else:
                sanitized[k] = sanitize_payload(v, max_string_len, depth + 1)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_payload(item, max_string_len, depth + 1) for item in obj[:15]]
    elif isinstance(obj, str):
        if len(obj) > max_string_len:
            return obj[:max_string_len] + f"... [+{len(obj) - max_string_len} chars redacted]"
        return obj
    return obj


class TraceManager:
    """Central store for in-memory audit traces and telemetry for active sessions."""

    def __init__(self):
        self._traces_by_run: Dict[str, List[Dict[str, Any]]] = {}

    def record_event(self, event: AuditEvent) -> None:
        if event.run_id not in self._traces_by_run:
            self._traces_by_run[event.run_id] = []
        payload = event.to_dict()
        self._traces_by_run[event.run_id].append(payload)
        logger.info(
            f"[AgenticTrace] run={event.run_id} action={event.action} outcome={event.outcome} actor={event.actor_type.value}"
        )

    def get_run_trace(self, run_id: str) -> List[Dict[str, Any]]:
        return self._traces_by_run.get(run_id, [])

    def clear(self) -> None:
        self._traces_by_run.clear()


# Global trace manager
trace_manager = TraceManager()

