from workflows import workflow_definition, next_step


def test_delivery_workflow_has_approval_boundary():
    definition = workflow_definition("project_delivery")
    assert "client_review" in definition["steps"]
    assert definition["external_action"] == "launch"


def test_next_step_advances_deterministically():
    assert next_step("research", None) == "research"
    assert next_step("research", "research") == "qualify"
    assert next_step("research", "create_opportunities") is None
