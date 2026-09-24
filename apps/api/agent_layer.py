"""Deterministic agent registry and runtime governance policy."""
AGENTS={
 "research":{"job":"Find and structure evidence-backed opportunities","tools":["research","read","draft"],"approval_required":False,"default_budget":0.10,"trust_rules":["evidence_before_recommendation","no_problem_no_pitch"]},
 "sales":{"job":"Prepare human-reviewable sales material","tools":["read","draft","send_message"],"approval_required":True,"default_budget":0.25,"trust_rules":["smallest_useful_solution","respect_declines","show_why_this_and_why_not"]},
 "project":{"job":"Coordinate requirements tasks milestones and dependencies","tools":["read","draft","create_artifact","write_crm"],"approval_required":True,"default_budget":0.20,"trust_rules":["client_control","clear_scope"]},
 "build":{"job":"Generate implementation artifacts from approved requirements","tools":["read","create_artifact"],"approval_required":True,"default_budget":0.50,"trust_rules":["approved_scope_only","client_data_control"]},
 "qa":{"job":"Validate generated work against the build contract","tools":["read","research"],"approval_required":False,"default_budget":0.20,"trust_rules":["verify_before_launch","report_failures"]},
 "launch":{"job":"Prepare and verify launch; production action stays gated","tools":["read","create_artifact","deploy"],"approval_required":True,"default_budget":0.25,"trust_rules":["explicit_approval","no_fabricated_credentials"]},
}
def agent_definition(name):
    if name not in AGENTS: raise ValueError("Unknown agent")
    return {"name":name,**AGENTS[name]}
def agent_policy(name):
    d=agent_definition(name)
    return {"agent":d,"consequential_actions_require_approval":d["approval_required"],"budget_usd":d["default_budget"]}
