"""Client-trust and opportunity-fit rules.

Luma should earn business through evidence and useful recommendations, not pressure.
This module is deliberately deterministic so the policy can be tested and reused by
research, sales, and client-facing workflows.
"""

DISPOSITION_ALLOW = "allow"
DISPOSITION_REVIEW = "review"
DISPOSITION_SUPPRESS = "suppress"

def assess_opportunity(evidence_count=0, evidence_confidence=0, impact_confidence=0,
                       solution_fit=0, intrusiveness_risk=0, problem_proven=True):
    """Return a transparent, non-salesy fit assessment on a 0-100 scale."""
    evidence_count = max(0, min(100, float(evidence_count)))
    evidence_confidence = max(0, min(100, float(evidence_confidence)))
    impact_confidence = max(0, min(100, float(impact_confidence)))
    solution_fit = max(0, min(100, float(solution_fit)))
    intrusiveness_risk = max(0, min(100, float(intrusiveness_risk)))
    score = (
        evidence_count * 0.25
        + evidence_confidence * 0.25
        + impact_confidence * 0.20
        + solution_fit * 0.20
        + (100 - intrusiveness_risk) * 0.10
    )
    if not problem_proven:
        disposition = DISPOSITION_REVIEW
    elif intrusiveness_risk >= 70 or score < 45:
        disposition = DISPOSITION_SUPPRESS
    elif score < 65:
        disposition = DISPOSITION_REVIEW
    else:
        disposition = DISPOSITION_ALLOW
    return {
        "score": round(score, 2),
        "disposition": disposition,
        "factors": {
            "evidence": round(evidence_count, 2),
            "evidence_confidence": round(evidence_confidence, 2),
            "impact_confidence": round(impact_confidence, 2),
            "solution_fit": round(solution_fit, 2),
            "intrusiveness_risk": round(intrusiveness_risk, 2),
        },
        "reason": (
            "Recommend only when observable evidence and solution fit justify contact."
            if disposition == DISPOSITION_ALLOW else
            "Needs human review before outreach."
            if disposition == DISPOSITION_REVIEW else
            "Do not pursue this opportunity without new evidence or client re-engagement."
        ),
    }

def should_expand(existing_outcome, client_approved=False, new_problem_evidence=False):
    """Expansion requires demonstrated value and a separately evidenced need."""
    if not client_approved or not new_problem_evidence:
        return False
    return existing_outcome in {"improved", "successful", "operationally_valuable"}

def outreach_disposition(preference="normal", prior_contact_count=0):
    preference = (preference or "normal").lower()
    if preference in {"do_not_contact", "not_interested", "complaint"}:
        return DISPOSITION_SUPPRESS
    if prior_contact_count >= 3:
        return DISPOSITION_REVIEW
    return DISPOSITION_ALLOW

def client_facing_recommendation(problem, evidence, impact, recommended_solution,
                                 alternatives=None, why_not=None, confidence=None):
    return {
        "problem": problem,
        "evidence": evidence or [],
        "expected_impact": impact,
        "recommended_solution": recommended_solution,
        "alternatives": alternatives or [],
        "why_not": why_not or [],
        "confidence": confidence,
        "language": "observed",
    }
