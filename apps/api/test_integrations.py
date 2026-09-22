from integrations import providers


def test_hosting_registry_exposes_supported_providers():
    names = {item["provider"] for item in providers("hosting")}
    assert {"self_hosted", "vercel", "netlify"}.issubset(names)
