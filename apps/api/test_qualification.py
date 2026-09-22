from qualification import score_opportunity


def test_score_flags_missing_mobile_and_form():
    result = score_opportunity({"https": True, "has_mobile_viewport": False, "has_contact_form": False})
    assert result["score"] == 35
    assert {f["factor"] for f in result["factors"]} == {
        "no_mobile_viewport_observed",
        "no_contact_form_observed",
    }


def test_score_caps_at_100():
    result = score_opportunity({
        "http_status": 500,
        "https": False,
        "has_mobile_viewport": False,
        "has_contact_form": False,
        "has_phone_link": False,
        "response_time_ms": 5000,
    })
    assert result["score"] == 95


def test_score_flags_missing_conversion_signals():
    result = score_opportunity({
        "https": True,
        "has_mobile_viewport": True,
        "has_contact_form": False,
        "has_phone_link": True,
        "has_cta": False,
        "has_email_link": False,
    })
    factors = {f["factor"] for f in result["factors"]}
    assert "no_clear_cta_observed" in factors
    assert "no_email_or_contact_form_observed" in factors
