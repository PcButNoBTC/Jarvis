"""Sales follow-up and pipeline stage transitions."""
from __future__ import annotations

from typing import Any

PIPELINE_STAGES = [
    "new", "researched", "briefed", "contacted", "qualified", "proposal", "won", "lost",
]

STAGE_NEXT_ACTION = {
    "new": "Run website research",
    "researched": "Generate client brief",
    "briefed": "Share brief and book discovery",
    "contacted": "Log call outcome; update qualification",
    "qualified": "Create offer or proposal",
    "proposal": "Follow up on proposal; confirm decision date",
    "won": "Create project and configure delivery options",
    "lost": "Record reason; no further outreach unless reopened",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"researched", "lost"},
    "researched": {"briefed", "lost"},
    "briefed": {"contacted", "qualified", "lost"},
    "contacted": {"qualified", "proposal", "lost"},
    "qualified": {"proposal", "lost"},
    "proposal": {"won", "lost"},
    "won": set(),
    "lost": {"new"},
}


def can_transition(current: str, target: str) -> bool:
    current = (current or "new").lower()
    target = target.lower()
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())


def transition(current: str, target: str) -> dict[str, Any]:
    current = (current or "new").lower()
    target = target.lower()
    if target not in PIPELINE_STAGES:
        return {"ok": False, "error": f"Unknown stage: {target}"}
    if not can_transition(current, target):
        return {
            "ok": False,
            "error": f"Cannot move from {current} to {target}",
            "allowed": sorted(ALLOWED_TRANSITIONS.get(current, set())),
        }
    return {
        "ok": True,
        "from": current,
        "to": target,
        "next_action": STAGE_NEXT_ACTION.get(target),
        "follow_up_days": follow_up_days(target),
    }


def follow_up_days(stage: str) -> int | None:
    return {"briefed": 2, "contacted": 3, "qualified": 5, "proposal": 4}.get(stage)


def follow_up_plan(stage: str) -> list[dict[str, Any]]:
    stage = (stage or "new").lower()
    plans = {
        "briefed": [
            {"day": 0, "action": "Send share_text brief"},
            {"day": 2, "action": "Polite check-in if no reply"},
        ],
        "contacted": [
            {"day": 0, "action": "Log call notes and objections"},
            {"day": 3, "action": "Send agreed next material (offer or answers)"},
        ],
        "proposal": [
            {"day": 0, "action": "Send proposal"},
            {"day": 3, "action": "Confirm questions"},
            {"day": 7, "action": "Decision follow-up or close-lost with reason"},
        ],
    }
    return plans.get(stage, [{"day": 0, "action": STAGE_NEXT_ACTION.get(stage, "Review opportunity")}])
