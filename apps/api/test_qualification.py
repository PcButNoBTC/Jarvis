from qualification import score_opportunity, map_to_service_opportunities


def test_score_flags_missing_mobile_and_form():
    result = score_opportunity({"https": True, "has_mobile_viewport": False, "has_contact_form": False})
    assert result["score"] == 35
    assert {f["factor"] for f in result["factors"]} == {
        "no_mobile_viewport_observed",
        "no_contact_form_observed",
    }


def test_score_caps_at_100():
    result = score_opportunity(
        {
            "http_status": 500,
            "https": False,
            "has_mobile_viewport": False,
            "has_contact_form": False,
            "has_phone_link": False,
            "response_time_ms": 5000,
        }
    )
    # base aggregate can still reach high; service-agnostic call returns base
    assert result["score"] >= 90
    assert result["score"] <= 100


def test_score_flags_missing_conversion_signals():
    result = score_opportunity(
        {
            "https": True,
            "has_mobile_viewport": True,
            "has_contact_form": False,
            "has_phone_link": True,
            "has_cta": False,
            "has_email_link": False,
        }
    )
    factors = {f["factor"] for f in result["factors"]}
    assert "no_clear_cta_observed" in factors
    assert "no_email_or_contact_form_observed" in factors


def test_service_specific_score_for_ai_website():
    analysis = {
        "http_status": 500,
        "https": False,
        "has_mobile_viewport": False,
        "has_contact_form": True,
        "has_phone_link": True,
        "has_cta": True,
        "has_email_link": True,
    }
    result = score_opportunity(analysis, "AI Website")
    assert result["service_hint"] == "AI Website"
    assert result["score"] >= 50  # site_error + no_https + no_mobile weighted heavily
    assert "base_score" in result


def test_map_to_service_opportunities_creates_multiple():
    analysis = {
        "https": True,
        "has_mobile_viewport": True,
        "has_contact_form": False,
        "has_phone_link": False,
        "has_cta": False,
        "has_email_link": False,
        "http_status": 200,
    }
    opps = map_to_service_opportunities(analysis)
    assert len(opps) >= 2
    services = {o["service"] for o in opps}
    # Lead capture and receptionist / appointment should surface
    assert "Lead Capture System" in services or "AI Receptionist" in services
    for o in opps:
        assert o["score"] >= 25
        assert "factors" in o
        assert "title" in o
        assert "description" in o
        assert o["confidence"] == "heuristic"


def test_map_empty_when_no_negative_signals():
    analysis = {
        "https": True,
        "has_mobile_viewport": True,
        "has_contact_form": True,
        "has_phone_link": True,
        "has_cta": True,
        "has_email_link": True,
        "http_status": 200,
        "response_time_ms": 400,
    }
    opps = map_to_service_opportunities(analysis)
    assert opps == []


def test_map_fallback_custom_automation():
    # Only a weak signal that no single service weights highly enough alone
    # (Review Automation has very low weights; we force a minimal factor set)
    analysis = {
        "https": True,
        "has_mobile_viewport": True,
        "has_contact_form": True,
        "has_phone_link": True,
        "has_cta": True,
        "has_email_link": True,
        "http_status": 200,
        "response_time_ms": 3500,  # slow only
    }
    opps = map_to_service_opportunities(analysis)
    # slow_response is weighted for AI Website and Custom; should still produce at least one
    assert len(opps) >= 1
    assert all(o["score"] > 0 for o in opps)


def test_opportunities_sorted_by_score_desc():
    analysis = {
        "http_status": 500,
        "https": False,
        "has_mobile_viewport": False,
        "has_contact_form": False,
        "has_phone_link": False,
        "has_cta": False,
        "has_email_link": False,
        "response_time_ms": 5000,
    }
    opps = map_to_service_opportunities(analysis)
    scores = [o["score"] for o in opps]
    assert scores == sorted(scores, reverse=True)
