from service_adapters import build_plan, qa_checks

def test_website_adapter_exposes_provider_actions_and_qa():
    plan = build_plan("AI Website", {"configuration": {"hosting": "vercel", "contact_capture": "native_form"}})
    assert plan["kind"] == "static_site"
    assert "hosting:vercel" in plan["provider_actions"]
    assert any(check["key"] == "contact_path" for check in plan["qa_checks"])

def test_appointment_adapter_has_calendar_qa():
    checks = qa_checks("Appointment Automation", {"calendar_provider": "Google Calendar"})
    assert any(check["key"] == "calendar" for check in checks)
