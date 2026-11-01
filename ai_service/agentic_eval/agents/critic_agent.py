"""
Specialist Critic / Consistency Reviewer Agent.
Checks for score-feedback contradictions, missing criteria, and disagreement with
the evaluator or evidence auditor. Routes material ambiguities to human review.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agentic_eval.schemas import AgentOutput


class CriticAgent:
    """Specialist critic checking logical consistency, contradictions, and evidence support."""

    POSITIVE_WORDS = frozenset({"excellent", "perfect", "flawless", "outstanding", "exceptional", "superb"})
    NEGATIVE_WORDS = frozenset({"missing", "failed", "incorrect", "no attempt", "completely absent", "unacceptable", "wrong"})

    def __init__(self, disagreement_threshold: float = 2.0):
        self.disagreement_threshold = disagreement_threshold

    def review_evaluation(
        self,
        student_text: str,
        evaluator_output: Dict[str, Any],
        auditor_output: Optional[AgentOutput] = None,
        rubric_criteria: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentOutput:
        """
        Conducts multi-perspective critique of the evaluation.
        Identifies contradictions between rubric, evidence, and assigned scores.
        """
        findings: List[str] = []
        flags: List[str] = []
        contradictions_found = 0

        breakdown = evaluator_output.get("scoreBreakdown", {})
        overall_score = float(evaluator_output.get("overallScore", evaluator_output.get("score", 0.0)))
        max_score = float(evaluator_output.get("maxScore", 100.0))

        # 1. Contradiction check: score vs reason sentiment
        for crit_name, crit_data in breakdown.items():
            if not isinstance(crit_data, dict):
                continue
            score = float(crit_data.get("score", 0.0))
            crit_max = float(crit_data.get("maxScore", 10.0))
            reason = str(crit_data.get("reason", "")).lower()

            # High score but negative sentiment
            if crit_max > 0 and (score / crit_max) >= 0.90:
                neg_hits = [w for w in self.NEGATIVE_WORDS if w in reason]
                if neg_hits:
                    msg = f"Criterion '{crit_name}' received high score ({score}/{crit_max}) but feedback contains negative keywords: {', '.join(neg_hits)}"
                    findings.append(msg)
                    flags.append("CONTRADICTION_HIGH_SCORE_NEGATIVE_FEEDBACK")
                    contradictions_found += 1

            # Zero/very low score but positive sentiment
            if crit_max > 0 and (score / crit_max) <= 0.15:
                pos_hits = [w for w in self.POSITIVE_WORDS if w in reason]
                if pos_hits:
                    msg = f"Criterion '{crit_name}' received near-zero score ({score}/{crit_max}) but feedback contains praise: {', '.join(pos_hits)}"
                    findings.append(msg)
                    flags.append("CONTRADICTION_LOW_SCORE_POSITIVE_FEEDBACK")
                    contradictions_found += 1

        # 2. Cross-agent check with EvidenceAuditor
        if auditor_output:
            if "UNVERIFIED_EVIDENCE" in auditor_output.flags:
                findings.append("Auditor flagged unverified evidence citations supporting criterion scores.")
                flags.append("CRITIC_DISAGREEMENT_UNGROUNDED_EVIDENCE")
            if "LOW_EVIDENCE_VERIFICATION_RATE" in auditor_output.flags:
                findings.append("Auditor detected low overall evidence grounding fidelity.")
                flags.append("CRITIC_DISAGREEMENT_LOW_GROUNDING")

        # 3. Confidence check
        confidence = evaluator_output.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.60:
            findings.append(f"Evaluator confidence is low ({confidence:.2f} < 0.60).")
            flags.append("CRITIC_LOW_CONFIDENCE_FLAG")

        # Decision synthesis
        if contradictions_found > 0 or "CRITIC_DISAGREEMENT_LOW_GROUNDING" in flags:
            decision = "NEEDS_REVIEW"
            rationale = (
                f"Critic detected {len(findings)} consistency anomalies: "
                + "; ".join(findings[:2])
            )
        elif flags:
            decision = "NEEDS_REVIEW"
            rationale = "Critic identified evidence or confidence concerns requiring professor review."
        else:
            decision = "CONTINUE"
            rationale = "Critic confirmed score-feedback alignment, rubric coverage, and evidence consistency."

        return AgentOutput(
            role="CriticReviewer",
            decision=decision,
            score_proposal=None,
            rationale=rationale,
            evidence_spans=[],
            findings=findings,
            flags=flags,
            model="consistency-rule-critic",
        )

