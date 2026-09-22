"""Strong-MVP project control plane helpers.

All consequential project changes are explicit records. Dependencies block work,
approvals prove who authorized a transition, and revisions preserve the client
review loop without overwriting history.
"""

ALLOWED_APPROVALS = {"requirements", "build", "qa", "launch", "handoff"}
REVISION_STATUSES = {"requested", "accepted", "rejected", "completed"}

def validate_dependency_status(dependencies):
    blockers = []
    for item in dependencies or []:
        if item.get("required", True) and item.get("status", "pending") not in {"complete", "approved"}:
            blockers.append(item)
    return blockers

def approval_type(value):
    if value not in ALLOWED_APPROVALS:
        raise ValueError("Unknown approval type")
    return value

def revision_status(value):
    if value not in REVISION_STATUSES:
        raise ValueError("Unknown revision status")
    return value
