"""Service adapter plans and capability-aware requirements."""
from __future__ import annotations
from typing import Any

SERVICE_ADAPTERS = {
    "AI Website": {"kind":"static_site","outputs":["responsive_site","contact_path","deployment_docs"]},
    "Lead Capture System": {"kind":"lead_capture","outputs":["capture_form","routing_spec","test_plan"]},
    "Appointment Automation": {"kind":"workflow","outputs":["booking_spec","reminder_spec","follow_up_spec","activation_checklist"]},
    "AI Receptionist": {"kind":"workflow","outputs":["call_flow","escalation_rules","activation_checklist"]},
    "Review Automation": {"kind":"workflow","outputs":["review_trigger","message_sequence","reporting_spec"]},
    "Video Walkthrough": {"kind":"content","outputs":["production_brief","scene_plan","asset_checklist"]},
    "Custom Automation": {"kind":"workflow","outputs":["process_map","workflow_spec","test_plan"]},
}

def build_plan(service: str | None, requirements: dict[str, Any]) -> dict[str, Any]:
    adapter = SERVICE_ADAPTERS.get(service or "", SERVICE_ADAPTERS["Custom Automation"])
    config = requirements.get("configuration") or {}
    return {
        "service": service or "Custom Automation",
        "kind": adapter["kind"],
        "outputs": adapter["outputs"],
        "configuration": config,
        "requirements": requirements,
        "provider_actions": _provider_actions(service, config),
        "qa_checks": qa_checks(service, config),
    }

def _provider_actions(service: str | None, config: dict[str, Any]) -> list[str]:
    mapping = {
        "AI Website": [("hosting","hosting"),("contact_capture","lead_capture"),("analytics","analytics")],
        "Appointment Automation": [("calendar_provider","calendar")],
        "AI Receptionist": [("phone_provider","phone")],
        "Review Automation": [("review_platform","review_platform")],
        "Lead Capture System": [("capture_destination","lead_destination")],
    }
    return [f"{label}:{config.get(key, 'pending')}" for key, label in mapping.get(service or "", [])]

def qa_checks(service: str | None, config: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [{"key":"requirements_complete","label":"Required project configuration is complete"}]
    if service == "AI Website":
        checks += [
            {"key":"contact_path","label":"Contact/lead capture path is configured"},
            {"key":"hosting","label":"Hosting target is configured"},
            {"key":"production_domain","label":"Production domain is known or intentionally deferred"},
        ]
    elif service == "Lead Capture System":
        checks += [
            {"key":"destination","label":"Lead destination is configured"},
            {"key":"notification","label":"Lead notification path is configured"},
        ]
    elif service == "Appointment Automation":
        checks += [{"key":"calendar","label":"Booking/calendar provider is configured"}]
    elif service == "AI Receptionist":
        checks += [{"key":"phone","label":"Phone/voice provider and escalation path are configured"}]
    elif service == "Review Automation":
        checks += [{"key":"review_platform","label":"Review platform is configured"}]
    return checks
