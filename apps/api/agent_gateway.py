"""Scoped agent-facing tool gateway.

Agents receive a small catalog of control-plane operations instead of direct SQL
or provider credentials. Consequential operations must pass governance first.
"""
TOOLS={
 "business.read":{"scope":"read","risk":"low"},
 "opportunity.read":{"scope":"read","risk":"low"},
 "evidence.read":{"scope":"read","risk":"low"},
 "proposal.draft":{"scope":"draft","risk":"low"},
 "project.read":{"scope":"read","risk":"low"},
 "project.configure":{"scope":"create_artifact","risk":"medium"},
 "workflow.checkpoint":{"scope":"read","risk":"low"},
 "message.send":{"scope":"send_message","risk":"high"},
 "calendar.create_event":{"scope":"create_event","risk":"high"},
 "project.deploy":{"scope":"deploy","risk":"critical"},
}
def catalog(): return [{"name":k,**v} for k,v in TOOLS.items()]
def resolve(name):
    if name not in TOOLS: raise KeyError(name)
    return TOOLS[name]
