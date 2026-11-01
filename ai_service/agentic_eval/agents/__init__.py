"""
Specialist multi-agent collaboration modules:
Evidence Auditor and Critic / Consistency Reviewer.
"""

from agentic_eval.agents.evidence_auditor import EvidenceAuditorAgent
from agentic_eval.agents.critic_agent import CriticAgent

__all__ = [
    "EvidenceAuditorAgent",
    "CriticAgent",
]

