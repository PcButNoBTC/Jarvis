from agent_layer import agent_definition, agent_policy

def test_agent_registry_has_governed_roles():
    policy = agent_policy("launch")
    assert policy["agent"]["approval_required"] is True
    assert "deployment_prepare" in policy["agent"]["tools"]
    assert agent_definition("qa")["default_budget"] > 0
