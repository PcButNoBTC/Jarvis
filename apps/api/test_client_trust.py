from client_trust import assess_opportunity, outreach_disposition, should_expand

def test_unproven_problem_requires_review():
    result = assess_opportunity(90, 90, 80, 90, 10, problem_proven=False)
    assert result["disposition"] == "review"

def test_high_intrusiveness_suppresses():
    result = assess_opportunity(90, 90, 90, 90, 80, problem_proven=True)
    assert result["disposition"] == "suppress"

def test_expansion_requires_value_and_new_evidence():
    assert should_expand("successful", True, True)
    assert not should_expand("successful", False, True)
    assert not should_expand("successful", True, False)

def test_decline_stops_outreach():
    assert outreach_disposition("not_interested", 1) == "suppress"
