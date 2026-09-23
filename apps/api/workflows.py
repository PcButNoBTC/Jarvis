"""Durable deterministic workflow primitives.

Workflows carry explicit approval boundaries, budgets and checkpointable state.
They remain intentionally small; provider-specific work belongs to adapters.
"""
from __future__ import annotations
from checkpoints import retry_delay

WORKFLOWS = {
    "proposal_follow_up": {"steps":["wait","draft_follow_up","human_approval","send"],"external_action":"send","approval_steps":["human_approval"]},
    "project_delivery": {"steps":["requirements","generate","validate","client_review","launch","handoff"],"external_action":"launch","approval_steps":["client_review","launch"]},
    "research": {"steps":["research","qualify","create_opportunities"],"external_action":None,"approval_steps":[]},
}

def workflow_definition(name: str) -> dict:
    if name not in WORKFLOWS: raise ValueError(f"Unknown workflow: {name}")
    return {"name":name,**WORKFLOWS[name]}

def next_step(name: str, current: str|None) -> str|None:
    steps=workflow_definition(name)["steps"]
    if current is None: return steps[0]
    if current not in steps: raise ValueError(f"Unknown workflow step: {current}")
    i=steps.index(current)
    return steps[i+1] if i+1<len(steps) else None

def is_approval_step(name: str, step: str|None) -> bool:
    return bool(step and step in workflow_definition(name).get("approval_steps",[]))

def retry_policy(attempt: int, max_attempts: int=3):
    return {"attempt":attempt,"max_attempts":max_attempts,"retryable":attempt < max_attempts,
            "delay_seconds":retry_delay(attempt)}
