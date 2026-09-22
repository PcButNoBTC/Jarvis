from sales import (
    build_call_prep,
    build_proposal_content,
    build_outreach_sequence,
    default_offer_scope,
)


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


def test_outreach_sequence_uses_plain_evidence():
    seq = build_outreach_sequence(
        {
            "business_name": "Acme Plumbing",
            "service_name": "Lead Capture System",
            "industry": "plumbing",
            "problem_evidence": [
                {"factor": "no_contact_form_observed", "points": 15},
                {"factor": "no_clear_cta_observed", "points": 10},
            ],
        }
    )
    assert len(seq["touches"]) == 3
    assert seq["touches"][0]["day"] == 1
    assert "contact or quote form" in seq["touches"][0]["body"]
    assert "Acme Plumbing" in seq["touches"][0]["subject"] or "Acme Plumbing" in seq["touches"][0]["body"]
    assert "service and estimate calls" in seq["touches"][0]["body"]


def test_default_offer_scope_is_service_specific():
    scope = default_offer_scope("AI Receptionist", "City Dental")
    assert "City Dental" in scope["name"]
    assert any("call" in d.lower() or "Call" in d for d in scope["deliverables"])
    assert scope["exclusions"]
