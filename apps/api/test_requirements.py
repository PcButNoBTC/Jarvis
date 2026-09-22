from requirements import compile_requirements


def test_website_configuration_becomes_build_contract():
    result = compile_requirements("AI Website", {
        "hosting": "vercel",
        "contact_capture": "crm",
        "communication": "email",
        "analytics": "plausible",
        "handoff": "digital_package",
        "domain": "example.com",
    })
    assert result["hosting"] == "vercel"
    assert result["contact_capture"] == "crm"
    assert result["configuration_complete"] is True
    assert result["build_contract"]["service"] == "AI Website"


def test_existing_requirements_are_preserved():
    result = compile_requirements(
        "Lead Capture System",
        {
            "capture_destination": "email",
            "notification_channel": "email",
            "qualification": "basic",
            "delivery_destination": "inbox",
        },
        {"custom_note": "approved"},
    )
    assert result["custom_note"] == "approved"
    assert result["delivery_destination"] == "inbox"
