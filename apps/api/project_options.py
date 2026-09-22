"""Service-specific project configuration definitions for Luma.

Definitions are intentionally declarative so the UI, API validation, and future
build/delivery adapters can share the same project configuration vocabulary.
"""

SERVICE_PROJECT_OPTIONS = {
    "AI Website": [
        {"key": "hosting", "label": "Hosting / deployment", "type": "select", "required": True,
         "options": [
             {"value": "client_hosting", "label": "Client's existing hosting"},
             {"value": "cloudflare_pages", "label": "Cloudflare Pages"},
             {"value": "vercel", "label": "Vercel"},
             {"value": "netlify", "label": "Netlify"},
             {"value": "self_hosted", "label": "Self-hosted"},
             {"value": "custom", "label": "Other / custom"},
             {"value": "help_me_choose", "label": "Help me choose"},
         ]},
        {"key": "contact_capture", "label": "Lead capture", "type": "select", "required": True,
         "options": [
             {"value": "native_form", "label": "Native website form"},
             {"value": "netlify_forms", "label": "Netlify Forms"},
             {"value": "external_form", "label": "External form provider"},
             {"value": "crm", "label": "Send directly to CRM"},
             {"value": "email_only", "label": "Email notification only"},
         ]},
        {"key": "communication", "label": "Primary contact channel", "type": "select", "required": True,
         "options": [
             {"value": "email", "label": "Email"},
             {"value": "phone", "label": "Phone"},
             {"value": "email_and_phone", "label": "Email + phone"},
             {"value": "client_managed", "label": "Client-managed"},
         ]},
        {"key": "analytics", "label": "Analytics / measurement", "type": "select", "required": False,
         "options": [
             {"value": "none", "label": "None"},
             {"value": "plausible", "label": "Plausible"},
             {"value": "google_analytics", "label": "Google Analytics"},
             {"value": "custom", "label": "Custom"},
         ]},
        {"key": "handoff", "label": "Handoff", "type": "select", "required": True,
         "options": [
             {"value": "digital_package", "label": "Digital package"},
             {"value": "client_walkthrough", "label": "Client walkthrough"},
             {"value": "live_activation", "label": "Live activation"},
         ]},
        {"key": "domain", "label": "Production domain", "type": "text", "required": False,
         "placeholder": "example.com"},
        {"key": "privacy_url", "label": "Privacy policy URL", "type": "text", "required": False},
        {"key": "terms_url", "label": "Terms URL", "type": "text", "required": False},
    ],
    "Lead Capture System": [
        {"key": "capture_destination", "label": "Lead destination", "type": "select", "required": True,
         "options": [
             {"value": "email", "label": "Email inbox"},
             {"value": "crm", "label": "CRM"},
             {"value": "spreadsheet", "label": "Spreadsheet"},
             {"value": "webhook", "label": "Webhook / API"},
         ]},
        {"key": "notification_channel", "label": "New lead notification", "type": "select", "required": True,
         "options": [
             {"value": "email", "label": "Email"},
             {"value": "sms", "label": "SMS"},
             {"value": "client_managed", "label": "Client-managed"},
         ]},
        {"key": "qualification", "label": "Lead qualification", "type": "select", "required": True,
         "options": [
             {"value": "basic", "label": "Basic rules"},
             {"value": "ai_assisted", "label": "AI-assisted"},
             {"value": "client_managed", "label": "Client-managed"},
         ]},
        {"key": "analytics", "label": "Measurement", "type": "select", "required": False,
         "options": [{"value": "none", "label": "None"}, {"value": "custom", "label": "Custom"}]},
        {"key": "delivery_destination", "label": "Delivery destination", "type": "text", "required": True,
         "placeholder": "Inbox, CRM, webhook URL, etc."},
    ],
    "Appointment Automation": [
        {"key": "calendar_provider", "label": "Calendar / booking provider", "type": "text", "required": True,
         "placeholder": "Google Calendar, Calendly, etc."},
        {"key": "reminders", "label": "Reminder channel", "type": "select", "required": True,
         "options": [{"value": "email", "label": "Email"}, {"value": "sms", "label": "SMS"}, {"value": "none", "label": "None"}]},
        {"key": "follow_up", "label": "No-show / follow-up", "type": "select", "required": True,
         "options": [{"value": "email", "label": "Email"}, {"value": "sms", "label": "SMS"}, {"value": "none", "label": "None"}]},
        {"key": "crm", "label": "CRM destination", "type": "text", "required": False},
        {"key": "handoff", "label": "Handoff", "type": "select", "required": True,
         "options": [{"value": "digital_package", "label": "Digital package"}, {"value": "client_walkthrough", "label": "Client walkthrough"}, {"value": "live_activation", "label": "Live activation"}]},
    ],
    "AI Receptionist": [
        {"key": "phone_provider", "label": "Phone / voice provider", "type": "text", "required": True,
         "placeholder": "Existing phone system or provider"},
        {"key": "call_routing", "label": "Call routing", "type": "select", "required": True,
         "options": [{"value": "ai_first", "label": "AI first"}, {"value": "human_first", "label": "Human first"}, {"value": "after_hours", "label": "AI after hours"}]},
        {"key": "business_hours", "label": "Business hours", "type": "text", "required": True,
         "placeholder": "Mon–Fri 9–5"},
        {"key": "escalation", "label": "Human escalation", "type": "text", "required": True,
         "placeholder": "Who receives escalations?"},
        {"key": "crm", "label": "CRM / logging destination", "type": "text", "required": False},
        {"key": "analytics", "label": "Call analytics", "type": "select", "required": False,
         "options": [{"value": "none", "label": "None"}, {"value": "provider", "label": "Provider analytics"}, {"value": "custom", "label": "Custom"}]},
    ],
    "Review Automation": [
        {"key": "review_platform", "label": "Review platform", "type": "text", "required": True,
         "placeholder": "Google, Yelp, industry platform, etc."},
        {"key": "trigger", "label": "Request trigger", "type": "select", "required": True,
         "options": [{"value": "completed_job", "label": "Completed job"}, {"value": "appointment", "label": "Appointment completed"}, {"value": "manual", "label": "Manual trigger"}]},
        {"key": "message_channel", "label": "Request channel", "type": "select", "required": True,
         "options": [{"value": "email", "label": "Email"}, {"value": "sms", "label": "SMS"}, {"value": "both", "label": "Email + SMS"}]},
        {"key": "crm", "label": "CRM / source", "type": "text", "required": False},
        {"key": "analytics", "label": "Measurement", "type": "select", "required": False,
         "options": [{"value": "none", "label": "None"}, {"value": "custom", "label": "Custom"}]},
    ],
    "Video Walkthrough": [
        {"key": "delivery_destination", "label": "Delivery destination", "type": "select", "required": True,
         "options": [{"value": "client_files", "label": "Client files"}, {"value": "youtube", "label": "YouTube"}, {"value": "vimeo", "label": "Vimeo"}, {"value": "website", "label": "Website"}]},
        {"key": "branding", "label": "Branding", "type": "select", "required": True,
         "options": [{"value": "client_brand", "label": "Client branding"}, {"value": "minimal", "label": "Minimal"}, {"value": "none", "label": "None"}]},
        {"key": "video_length", "label": "Target length", "type": "select", "required": True,
         "options": [{"value": "short", "label": "30–60 seconds"}, {"value": "standard", "label": "1–2 minutes"}, {"value": "extended", "label": "2–5 minutes"}]},
    ],
    "Custom Automation": [
        {"key": "trigger", "label": "Workflow trigger", "type": "text", "required": True,
         "placeholder": "What starts the workflow?"},
        {"key": "source_system", "label": "Source system", "type": "text", "required": True},
        {"key": "destination_system", "label": "Destination system", "type": "text", "required": True},
        {"key": "notification_channel", "label": "Notification", "type": "select", "required": False,
         "options": [{"value": "email", "label": "Email"}, {"value": "sms", "label": "SMS"}, {"value": "none", "label": "None"}]},
        {"key": "credentials_ready", "label": "Credentials / access ready", "type": "boolean", "required": True},
        {"key": "test_approved", "label": "Production test approved", "type": "boolean", "required": True},
    ],
}

def option_definitions(service_name):
    return SERVICE_PROJECT_OPTIONS.get(service_name, [
        {"key": "requirements_approved", "label": "Requirements approved", "type": "boolean", "required": True},
        {"key": "delivery_destination", "label": "Delivery destination", "type": "text", "required": True},
    ])

def validate_options(service_name, selected):
    selected = selected or {}
    errors = []
    for option in option_definitions(service_name):
        if not option.get("required"):
            continue
        value = selected.get(option["key"])
        missing = value is None or value == "" or value is False
        if missing:
            errors.append(option["key"])
    return errors

def option_summary(service_name, selected):
    definitions = option_definitions(service_name)
    return [
        {
            "key": item["key"],
            "label": item["label"],
            "value": selected.get(item["key"]),
            "configured": selected.get(item["key"]) not in (None, "", False),
        }
        for item in definitions
    ]
