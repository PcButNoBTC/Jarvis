"""Small deterministic workflow primitives used by Luma automation.

This is deliberately not a general-purpose workflow engine. It provides the
state model needed for follow-ups, delivery gates, and scheduled jobs while
keeping consequential actions explicit.
"""
from __future__ import annotations

WORKFLOWS = {
    "proposal_follow_up": {
        "steps": ["wait", "draft_follow_up", "human_approval", "send"],
        "external_action": "send",
    },
    "project_delivery": {
        "steps": ["requirements", "generate", "validate", "client_review", "launch", "handoff"],
        "external_action": "launch",
    },
    "research": {
        "steps": ["research", "qualify", "create_opportunities"],
        "external_action": None,
    },
}


def workflow_definition(name: str) -> dict:
    if name not in WORKFLOWS:
        raise ValueError(f"Unknown workflow: {name}")
    return {"name": name, **WORKFLOWS[name]}


def next_step(name: str, current: str | None) -> str | None:
    steps = workflow_definition(name)["steps"]
    if current is None:
        return steps[0]
    try:
        index = steps.index(current)
    except ValueError:
        raise ValueError(f"Unknown workflow step: {current}")
    return steps[index + 1] if index + 1 < len(steps) else None
