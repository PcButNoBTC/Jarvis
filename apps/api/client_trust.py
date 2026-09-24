"""Client-friendly, non-predatory defaults for Luma.

Designed for untapped local markets: be the best option, not the loudest.
Profit comes from trust, clear scope, and proof — then regional expansion.
"""
from __future__ import annotations

from typing import Any


CLIENT_PROMISE = [
    "We only recommend what we can observe on public information — not invented problems.",
    "You approve every external message and every scope before work starts.",
    "You keep ownership of your logins, phone numbers, domains, and customer data.",
    "If it is not a fit after a short conversation, we say so and stop — no pressure.",
    "You can track progress and approve stages in a simple client portal.",
]

LOCAL_PILOT_FRAMING = (
    "We are building this carefully with local businesses first. "
    "The goal is a clear, useful outcome — not a high-volume outreach machine."
)

TONE_RULES = [
    "Lead with observed evidence, not fear or urgency.",
    "One problem, one recommended path, one clear next step.",
    "Invite a short conversation; never imply the business is failing.",
    "Make ‘no’ easy and respectable.",
    "Do not claim results you have not delivered for this client.",
    "Do not auto-send; human approval is required.",
]


def client_promise_block(business_name: str | None = None) -> str:
    who = business_name or "you"
    lines = ["## Our promise to you", ""]
    for item in CLIENT_PROMISE:
        lines.append(f"- {item}")
    lines += ["", LOCAL_PILOT_FRAMING.replace("local businesses", f"businesses like {who}" if business_name else "local businesses")]
    return "\n".join(lines)


def client_promise_plain() -> str:
    return "\n".join(f"- {p}" for p in CLIENT_PROMISE) + "\n\n" + LOCAL_PILOT_FRAMING


def fit_checklist(opportunity: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pre-outreach fit / no-fit checks — reduces predatory spray."""
    opportunity = opportunity or {}
    evidence = opportunity.get("problem_evidence") or opportunity.get("factors") or []
    score = opportunity.get("score")
    try:
        score_n = float(score) if score is not None else None
    except (TypeError, ValueError):
        score_n = None
    email = opportunity.get("business_email") or opportunity.get("email")
    service = opportunity.get("service_name") or opportunity.get("service")
    rationale = opportunity.get("rationale") or opportunity.get("description")

    checks = [
        {"id": "has_evidence", "label": "At least one observed signal supports the recommendation", "ok": bool(evidence) or bool(rationale)},
        {"id": "has_service", "label": "A specific service is mapped (not a vague ‘AI’ pitch)", "ok": bool(service)},
        {"id": "score_floor", "label": "Opportunity score is strong enough to justify contact (or human override)", "ok": score_n is None or score_n >= 25},
        {"id": "has_contact", "label": "A real contact path exists (email or phone) — no guessing", "ok": bool(email) or bool(opportunity.get("phone"))},
        {"id": "human_review", "label": "A human will review the draft before any send", "ok": True},
        {"id": "no_fake_urgency", "label": "Message does not use fake scarcity or shame language", "ok": True},
    ]
    passed = all(c["ok"] for c in checks)
    return {
        "fit": passed,
        "checks": checks,
        "recommendation": (
            "OK to prepare a brief and draft outreach for human review."
            if passed
            else "Do not contact yet — fix failed checks or mark as not a fit."
        ),
        "no_fit_action": "Record reason and stop. Revisit only if new evidence appears.",
        "tone_rules": TONE_RULES,
        "promise": CLIENT_PROMISE,
    }


def soft_cta() -> str:
    return (
        "If this is useful, a 10–15 minute call is enough to see whether it is a real fit. "
        "If not, no follow-up pressure."
    )


def brief_footer(business_name: str | None = None) -> str:
    return (
        client_promise_block(business_name)
        + "\n\n### Suggested next step\n"
        + soft_cta()
    )
