"""Runtime governance for Luma actions.

Every consequential action is evaluated before execution. Policies are fail-closed
for unknown tools and hard budget limits are enforced before provider calls.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Decision:
    action: str
    decision: str
    reason: str
    risk: str
    estimated_cost: float = 0.0

RISK_BY_ACTION={
    "read":"low","research":"low","draft":"low","create_artifact":"medium",
    "write_crm":"medium","send_message":"high","create_event":"high",
    "deploy":"critical","charge_payment":"critical","delete":"critical",
}

def evaluate_action(action, *, tools, approval_required=True, approved=False,
                    spent=0.0, budget=0.0, estimated_cost=0.0):
    risk=RISK_BY_ACTION.get(action,"high")
    if action not in set(tools or []):
        return Decision(action,"deny","tool_not_allowed",risk,estimated_cost)
    if budget >= 0 and spent + estimated_cost > budget:
        return Decision(action,"deny","budget_exceeded",risk,estimated_cost)
    if approval_required and risk in {"high","critical"} and not approved:
        return Decision(action,"approval_required","human_approval_required",risk,estimated_cost)
    return Decision(action,"allow","policy_passed",risk,estimated_cost)

def normalize_policy(agent, row=None):
    row=row or {}
    return {
        "agent_name":agent,
        "budget_usd":float(row.get("budget_usd") or 0),
        "tools":row.get("tools") or [],
        "enabled":bool(row.get("enabled",True)),
        "approval_required":bool(row.get("approval_required",True)),
    }
