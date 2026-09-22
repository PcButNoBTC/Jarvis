from service_adapters import build_plan


def test_website_adapter_exposes_provider_actions():
    plan = build_plan("AI Website", {"configuration": {"hosting": "vercel", "analytics": "plausible"}})
    assert plan["kind"] == "static_site"
    assert "hosting:vercel" in plan["provider_actions"]
