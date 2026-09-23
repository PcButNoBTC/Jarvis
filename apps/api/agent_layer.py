"""Deterministic agent registry and governance policy.

Agents are orchestration roles, not unrestricted autonomous actors. Every role has
an explicit budget, tool scope, and approval boundary.
"""

AGENTS = {
    "research": {"job": "Find and structure evidence-backed opportunities", "tools": ["website_analysis", "lead_sources"], "approval_required": False, "default_budget": 0.10, "trust_rules": ["evidence_before_recommendation", "no_problem_no_pitch"]},
    "sales": {"job": "Prepare human-reviewable sales material", "tools": ["opportunity_read", "proposal_draft", "outreach_draft"], "approval_required": True, "default_budget": 0.25, "trust_rules": ["smallest_useful_solution", "respect_declines", "show_why_this_and_why_not"]},
    "project": {"job": "Coordinate requirements, tasks, milestones, and dependencies", "tools": ["project_read", "task_write", "milestone_write"], "approval_required": True, "default_budget": 0.20, "trust_rules": ["client_control", "clear_scope"]},
    "build": {"job": "Generate implementation artifacts from approved requirements", "tools": ["artifact_write", "qa_run"], "approval_required": True, "default_budget": 0.50, "trust_rules": ["approved_scope_only", "client_data_control"]},
    "qa": {"job": "Validate generated work against the build contract", "tools": ["artifact_read", "qa_run"], "approval_required": False, "default_budget": 0.20, "trust_rules": ["verify_before_launch", "report_failures"]},
    "launch": {"job": "Prepare and verify launch; production action stays gated", "tools": ["launch_read", "deployment_prepare"], "approval_required": True, "default_budget": 0.25, "trust_rules": ["explicit_approval", "no_fabricated_credentials"]},
}

def agent_definition(name):
    if name not in AGENTS:
        raise ValueError("Unknown agent")
    return {"name": name, **AGENTS[name]}

def agent_policy(name):
    definition = agent_definition(name)
    return {
        "agent": definition,
        "consequential_actions_require_approval": definition["approval_required"],
        "budget_usd": definition["default_budget"],
    }
