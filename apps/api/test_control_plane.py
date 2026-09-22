from control_plane import validate_dependency_status, approval_type, revision_status

def test_dependency_blocker_detection():
    assert len(validate_dependency_status([{"name": "DNS", "required": True, "status": "pending"}])) == 1
    assert validate_dependency_status([{"name": "DNS", "required": True, "status": "complete"}]) == []

def test_approval_and_revision_validation():
    assert approval_type("launch") == "launch"
    assert revision_status("completed") == "completed"
