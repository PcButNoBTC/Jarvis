from sales import build_call_prep, build_proposal_content


def test_call_prep_preserves_observed_evidence():
    result = build_call_prep({
        "service_name": "AI Website",
        "problem_evidence": [{"factor": "no_contact_form_observed", "points": 15}],
    })
    assert "no_contact_form_observed" in result["evidence"][0]
    assert result["discovery_questions"]


def test_proposal_contains_scope_and_pricing():
    result = build_proposal_content(
        "Acme",
        {
            "name": "AI Website — Acme",
            "description": "Focused website improvement.",
            "setup_price": 750,
            "recurring_price": None,
            "deliverables": ["Requirements", "Implementation"],
            "assumptions": ["Client provides access."],
            "exclusions": ["Third-party fees."],
        },
        {
            "title": "Website improvement",
            "description": "Observed website signals.",
            "delivery_days": 7,
        },
    )
    assert "Acme" in result
    assert "$750.00" in result
    assert "Implementation" in result
    assert "Third-party fees." in result
