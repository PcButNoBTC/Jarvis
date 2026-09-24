from blueprint_optimizer import propose
def test_optimizer_proposes_experiment_on_decline():
    result=propose("qualified_leads",100,80,service="AI Website")
    assert result["action"]=="generate_experiment"
    assert result["delta"]==-20.0
def test_optimizer_preserves_success():
    result=propose("qualified_leads",100,130,target=120,service="AI Website")
    assert result["action"]=="preserve_pattern_and_test_reuse"
