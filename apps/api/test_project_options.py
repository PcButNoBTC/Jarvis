from project_options import option_definitions, validate_options


def test_ai_website_has_service_specific_options():
    keys = {item["key"] for item in option_definitions("AI Website")}
    assert {"hosting", "contact_capture", "communication", "analytics", "handoff"}.issubset(keys)


def test_appointment_options_do_not_require_website_hosting():
    keys = {item["key"] for item in option_definitions("Appointment Automation")}
    assert "calendar_provider" in keys
    assert "hosting" not in keys


def test_required_option_validation():
    assert "hosting" in validate_options("AI Website", {})
    assert validate_options("AI Website", {"hosting": "vercel", "contact_capture": "native_form", "communication": "email", "handoff": "digital_package"}) == []
