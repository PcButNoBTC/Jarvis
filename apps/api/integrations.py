"""Provider-neutral integration registry.

Providers are declarations until credentials and a real adapter are connected.
This prevents the UI and automation layer from pretending an integration exists
when only a configuration choice has been saved.
"""
INTEGRATION_PROVIDERS = {
    "email": [
        {"provider": "smtp", "capabilities": ["send_email", "health_check"]},
        {"provider": "gmail", "capabilities": ["send_email", "health_check"]},
    ],
    "calendar": [
        {"provider": "google_calendar", "capabilities": ["create_event", "health_check"]},
    ],
    "hosting": [
        {"provider": "self_hosted", "capabilities": ["deploy_static", "health_check"]},
        {"provider": "cloudflare_pages", "capabilities": ["deploy_static"]},
        {"provider": "vercel", "capabilities": ["deploy_static"]},
        {"provider": "netlify", "capabilities": ["deploy_static"]},
    ],
    "analytics": [
        {"provider": "plausible", "capabilities": ["track", "health_check"]},
    ],
    "payments": [
        {"provider": "stripe", "capabilities": ["create_invoice", "record_payment", "health_check"]},
    ],
}


def providers(category: str | None = None):
    if category:
        return INTEGRATION_PROVIDERS.get(category, [])
    return INTEGRATION_PROVIDERS
