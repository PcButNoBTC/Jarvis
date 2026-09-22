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
        {"provider": "google_calendar", "capabilities": ["create_event", "read_availability", "health_check"]},
        {"provider": "microsoft_outlook", "capabilities": ["create_event", "read_availability", "health_check"]},
        {"provider": "calendly", "capabilities": ["booking_link", "read_availability", "health_check"]},
        {"provider": "client_managed", "capabilities": ["handoff_only"]},
    ],
    "hosting": [
        {"provider": "self_hosted", "capabilities": ["deploy_static", "health_check"]},
        {"provider": "cloudflare_pages", "capabilities": ["deploy_static"]},
        {"provider": "vercel", "capabilities": ["deploy_static"]},
        {"provider": "netlify", "capabilities": ["deploy_static"]},
    ],
    "crm": [
        {"provider": "hubspot", "capabilities": ["create_contact", "create_deal", "health_check"]},
        {"provider": "salesforce", "capabilities": ["create_contact", "create_lead", "health_check"]},
        {"provider": "pipedrive", "capabilities": ["create_contact", "create_deal", "health_check"]},
        {"provider": "custom_crm", "capabilities": ["webhook", "health_check"]},
    ],
    "forms": [
        {"provider": "netlify_forms", "capabilities": ["capture_form", "health_check"]},
        {"provider": "webhook", "capabilities": ["receive_submission", "health_check"]},
        {"provider": "custom_form", "capabilities": ["receive_submission"]},
    ],
    "phone": [
        {"provider": "twilio", "capabilities": ["voice", "sms", "call_forwarding", "health_check"]},
        {"provider": "telnyx", "capabilities": ["voice", "sms", "call_forwarding", "health_check"]},
        {"provider": "existing_phone_system", "capabilities": ["call_forwarding"]},
    ],
    "dns": [
        {"provider": "cloudflare_dns", "capabilities": ["dns_records", "health_check"]},
        {"provider": "client_dns", "capabilities": ["dns_records"]},
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


SERVICE_INTEGRATION_SUGGESTIONS = {
    "AI Website": [
        {"category": "hosting", "reason": "Choose where the site will be deployed."},
        {"category": "forms", "reason": "Choose how website inquiries are captured."},
        {"category": "analytics", "reason": "Optional measurement of traffic and conversions."},
        {"category": "dns", "reason": "Needed when Luma manages domain routing."},
    ],
    "Lead Capture System": [
        {"category": "crm", "reason": "Optional destination for qualified leads."},
        {"category": "forms", "reason": "Capture submissions from the website or landing page."},
        {"category": "email", "reason": "Notify the owner when a lead arrives."},
    ],
    "Appointment Automation": [
        {"category": "calendar", "reason": "Connect the booking calendar."},
        {"category": "crm", "reason": "Optional contact/deal synchronization."},
        {"category": "email", "reason": "Optional confirmations and follow-up."},
    ],
    "AI Receptionist": [
        {"category": "phone", "reason": "Connect inbound calls, routing, and SMS where selected."},
        {"category": "calendar", "reason": "Optional appointment booking."},
        {"category": "crm", "reason": "Optional call/contact logging."},
    ],
    "Review Automation": [
        {"category": "email", "reason": "Send review requests."},
        {"category": "crm", "reason": "Optional trigger/source system."},
    ],
    "Video Walkthrough": [],
    "Custom Automation": [
        {"category": "email", "reason": "Optional notifications."},
        {"category": "crm", "reason": "Common workflow destination/source."},
    ],
}


def suggestions_for_service(service: str | None):
    return SERVICE_INTEGRATION_SUGGESTIONS.get(service or "Custom Automation", SERVICE_INTEGRATION_SUGGESTIONS["Custom Automation"])

PROVIDER_SETUP = {
    "google_calendar": {"auth": "oauth", "credentials": ["oauth_client"], "steps": ["Connect Google account", "Grant calendar permissions", "Select calendar", "Run availability test"], "human_approval": True},
    "microsoft_outlook": {"auth": "oauth", "credentials": ["oauth_client"], "steps": ["Connect Microsoft account", "Grant calendar permissions", "Select calendar", "Run availability test"], "human_approval": True},
    "calendly": {"auth": "api_key_or_oauth", "credentials": ["api_key_or_oauth"], "steps": ["Connect Calendly", "Select event type", "Run booking/availability test"], "human_approval": True},
    "twilio": {"auth": "api_credentials", "credentials": ["account_sid", "auth_token"], "steps": ["Connect Twilio", "Select or purchase number", "Configure webhook", "Run inbound/outbound test"], "human_approval": True},
    "telnyx": {"auth": "api_credentials", "credentials": ["api_key", "messaging_profile"], "steps": ["Connect Telnyx", "Select number", "Configure webhook", "Run inbound/outbound test"], "human_approval": True},
    "existing_phone_system": {"auth": "client_managed", "credentials": [], "steps": ["Provide forwarding/routing details", "Confirm escalation number", "Run call test"], "human_approval": True},
    "client_managed": {"auth": "client_managed", "credentials": [], "steps": ["Client completes provider setup", "Enter resulting booking URL or access details", "Run handoff test"], "human_approval": True},
}
def provider_setup(provider: str):
    return PROVIDER_SETUP.get(provider, {"auth": "provider_specific", "credentials": [], "steps": ["Connect provider", "Configure required settings", "Run health check"], "human_approval": True})
