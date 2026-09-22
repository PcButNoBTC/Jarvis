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
