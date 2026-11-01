"""
Configuration and feature flags for the Agentic Evaluation Engine.
Provides centralized, validated configuration with strict safety defaults.
All agentic capabilities default to FALSE/OFF to preserve known-good baseline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


def _bool_from_env(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").strip().lower()
    if not val:
        return default
    return val in {"1", "true", "yes", "on", "enabled"}


def _int_from_env(key: str, default: int) -> int:
    val = os.environ.get(key, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _float_from_env(key: str, default: float) -> float:
    val = os.environ.get(key, "").strip()
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class ExecutionBudgets:
    """Configurable bounds to prevent infinite loops, runaway tool calls, and budget exhaustion."""
    max_plan_steps: int = 10
    max_tool_calls: int = 15
    max_retries: int = 3
    max_execution_time_seconds: float = 60.0
    max_token_budget: int = 8000


@dataclass(frozen=True)
class AgenticConfig:
    """Centralized configuration for agentic evaluation capabilities."""
    # Master switch
    eval_enabled: bool = False

    # Granular capability switches
    planner_enabled: bool = False
    tools_enabled: bool = False
    critic_enabled: bool = False
    multi_agent_enabled: bool = False
    shadow_mode: bool = False

    # Operating mode:
    # 0 = Baseline (Standard non-agentic evaluator)
    # 1 = Assisted (Planner generates structured plan; execution follows fixed sequence)
    # 2 = Bounded Autonomous (Agent chooses allowed tools & safe branches within strict budgets)
    # 3 = Multi-Agent Review (Specialist agents: Evaluator, Evidence Auditor, Critic)
    mode: int = 0

    # Budgets
    budgets: ExecutionBudgets = field(default_factory=ExecutionBudgets)


# Global config cache
_GLOBAL_CONFIG: Optional[AgenticConfig] = None


def load_config() -> AgenticConfig:
    """Load configuration from environment variables with safe defaults."""
    eval_enabled = _bool_from_env("AGENTIC_EVAL_ENABLED", False)
    mode = _int_from_env("AGENTIC_MODE", 0)

    # Budgets
    budgets = ExecutionBudgets(
        max_plan_steps=_int_from_env("AGENTIC_MAX_PLAN_STEPS", 10),
        max_tool_calls=_int_from_env("AGENTIC_MAX_TOOL_CALLS", 15),
        max_retries=_int_from_env("AGENTIC_MAX_RETRIES", 3),
        max_execution_time_seconds=_float_from_env("AGENTIC_MAX_TIME_SECONDS", 60.0),
        max_token_budget=_int_from_env("AGENTIC_MAX_TOKEN_BUDGET", 8000),
    )

    # If master switch is disabled, all sub-capabilities are treated as disabled
    if not eval_enabled:
        return AgenticConfig(
            eval_enabled=False,
            planner_enabled=False,
            tools_enabled=False,
            critic_enabled=False,
            multi_agent_enabled=False,
            shadow_mode=_bool_from_env("AGENTIC_SHADOW_MODE", False),
            mode=0,
            budgets=budgets,
        )

    return AgenticConfig(
        eval_enabled=True,
        planner_enabled=_bool_from_env("AGENTIC_PLANNER_ENABLED", mode >= 1),
        tools_enabled=_bool_from_env("AGENTIC_TOOLS_ENABLED", mode >= 1),
        critic_enabled=_bool_from_env("AGENTIC_CRITIC_ENABLED", mode >= 2),
        multi_agent_enabled=_bool_from_env("AGENTIC_MULTI_AGENT_ENABLED", mode >= 3),
        shadow_mode=_bool_from_env("AGENTIC_SHADOW_MODE", False),
        mode=mode,
        budgets=budgets,
    )


def get_config() -> AgenticConfig:
    """Get the active configuration (cached or newly loaded)."""
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None:
        _GLOBAL_CONFIG = load_config()
    return _GLOBAL_CONFIG


def set_config(config: Optional[AgenticConfig]) -> None:
    """Explicitly set or reset the active configuration (useful for testing)."""
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = config


class ConfigOverride:
    """Context manager for scoped configuration overrides during testing or runs."""
    def __init__(self, **kwargs):
        self.overrides = kwargs
        self._prev = None

    def __enter__(self) -> AgenticConfig:
        self._prev = get_config()
        base = load_config()
        budgets = self.overrides.get("budgets", base.budgets)
        new_config = AgenticConfig(
            eval_enabled=self.overrides.get("eval_enabled", base.eval_enabled),
            planner_enabled=self.overrides.get("planner_enabled", base.planner_enabled),
            tools_enabled=self.overrides.get("tools_enabled", base.tools_enabled),
            critic_enabled=self.overrides.get("critic_enabled", base.critic_enabled),
            multi_agent_enabled=self.overrides.get("multi_agent_enabled", base.multi_agent_enabled),
            shadow_mode=self.overrides.get("shadow_mode", base.shadow_mode),
            mode=self.overrides.get("mode", base.mode),
            budgets=budgets,
        )
        set_config(new_config)
        return new_config

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_config(self._prev)

