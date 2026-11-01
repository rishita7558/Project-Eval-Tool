"""
Specialist Evidence Auditor Agent.
Independently verifies cited student text passages, detects unsupported claims,
and flags hallucinations or ungrounded evaluations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agentic_eval.schemas import ActorType, AgentOutput
from agentic_eval.tools.eval_tools import tool_verify_evidence_spans


class EvidenceAuditorAgent:
    """Specialist auditor that independently verifies evaluator evidence citations."""

    def __init__(self, min_verification_rate: float = 0.70):
        self.min_verification_rate = min_verification_rate

    def audit_submission_evidence(
        self,
        student_text: str,
        evaluator_output: Dict[str, Any],
        rubric_criteria: List[Dict[str, Any]],
    ) -> AgentOutput:
        """
        Extracts cited evidence per criterion and verifies occurrence in student text.
        Returns a structured AgentOutput.
        """
        criteria_breakdown = evaluator_output.get("scoreBreakdown", {})
        all_cited: List[str] = []
        criterion_evidence_map: Dict[str, str] = {}

        for crit_name, data in criteria_breakdown.items():
            if isinstance(data, dict):
                ev = str(data.get("evidence", "")).strip()
                if ev:
                    all_cited.append(ev)
                    criterion_evidence_map[crit_name] = ev

        # If no explicit evidence spans cited, check qualitative feedback for quoted strings
        if not all_cited:
            feedback_str = str(evaluator_output.get("overallFeedback", ""))
            quotes = re.findall(r'"([^"]{10,120})"', feedback_str)
            all_cited.extend(quotes)

        # Run verification tool
        verification_res = tool_verify_evidence_spans(student_text, all_cited)

        findings: List[str] = []
        flags: List[str] = []
        unverified = verification_res.get("unverified", [])
        verified_count = verification_res.get("verifiedCount", 0)
        total_count = verified_count + len(unverified)
        rate = verification_res.get("verificationRate", 1.0)

        if unverified:
            findings.append(f"{len(unverified)} of {total_count} cited passages could not be verified in student text.")
            for u in unverified[:3]:
                findings.append(f"Unverified citation: \"{u[:80]}\"")
            flags.append("UNVERIFIED_EVIDENCE")

        if total_count > 0 and rate < self.min_verification_rate:
            flags.append("LOW_EVIDENCE_VERIFICATION_RATE")
            decision = "NEEDS_REVIEW"
            rationale = (
                f"Evidence auditor detected low grounding fidelity: only {rate*100:.1f}% "
                f"of cited evidence matches student submission."
            )
        elif unverified:
            decision = "NEEDS_REVIEW"
            rationale = "Some cited evidence passages could not be verified in the student submission text."
        else:
            decision = "CONTINUE"
            rationale = (
                f"All {verified_count} cited evidence passages independently verified against student text."
                if total_count > 0 else "No explicit quote spans required verification; submission passed textual presence check."
            )

        return AgentOutput(
            role="EvidenceAuditor",
            decision=decision,
            score_proposal=None,
            rationale=rationale,
            evidence_spans=verification_res.get("verified", []),
            findings=findings,
            flags=flags,
            model="deterministic-verifier",
        )

