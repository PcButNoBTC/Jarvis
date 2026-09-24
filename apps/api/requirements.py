"""Compile project configuration into deterministic delivery requirements.

The compiler is intentionally provider-neutral. It turns the selections made in
Project Configuration into an explicit build contract that service adapters can
consume without guessing what the client chose.
"""
from __future__ import annotations

from typing import Any

from project_options import option_definitions, validate_options


def compile_requirements(service: str | None, selected: dict[str, Any] | None,
                         existing: dict[str, Any] | None = None) -> dict[str, Any]:
    selected = selected or {}
    existing = existing or {}
    service = service or "Custom Automation"
    missing = validate_options(service, selected)
    if missing:
        raise ValueError("Missing required project options: " + ", ".join(missing))

    requirements: dict[str, Any] = dict(existing)
    requirements["service"] = service
    requirements["configuration"] = dict(selected)
    requirements["configuration_complete"] = True
    requirements.setdefault("approved", False)

    if service == "AI Website":
        requirements.update({
            "hosting": selected.get("hosting"),
            "contact_capture": selected.get("contact_capture"),
            "communication": selected.get("communication"),
            "analytics": selected.get("analytics", "none"),
            "handoff": selected.get("handoff"),
            "domain": selected.get("domain"),
            "privacy_url": selected.get("privacy_url"),
            "terms_url": selected.get("terms_url"),
        })
        requirements.setdefault("acceptance_criteria", [
            "Responsive layout",
            "Primary contact path",
            "Approved business details",
            "Selected lead-capture path",
            "Selected analytics behavior",
            "Deployment and handoff documentation",
        ])
    elif service == "Lead Capture System":
        requirements.update({
            "capture_destination": selected.get("capture_destination"),
            "notification_channel": selected.get("notification_channel"),
            "qualification": selected.get("qualification"),
            "analytics": selected.get("analytics", "none"),
            "delivery_destination": selected.get("delivery_destination"),
        })
    elif service == "Appointment Automation":
        requirements.update({
            "calendar_provider": selected.get("calendar_provider"),
            "reminders": selected.get("reminders"),
            "follow_up": selected.get("follow_up"),
            "crm": selected.get("crm"),
            "handoff": selected.get("handoff"),
        })
    elif service == "AI Receptionist":
        requirements.update({
            "phone_provider": selected.get("phone_provider"),
            "call_routing": selected.get("call_routing"),
            "business_hours": selected.get("business_hours"),
            "escalation": selected.get("escalation"),
            "crm": selected.get("crm"),
            "analytics": selected.get("analytics", "none"),
        })
    elif service == "Review Automation":
        requirements.update({
            "review_platform": selected.get("review_platform"),
            "trigger": selected.get("trigger"),
            "message_channel": selected.get("message_channel"),
            "crm": selected.get("crm"),
            "analytics": selected.get("analytics", "none"),
        })
    elif service == "Video Walkthrough":
        requirements.update({
            "delivery_destination": selected.get("delivery_destination"),
            "branding": selected.get("branding"),
            "video_length": selected.get("video_length"),
        })
    else:
        requirements.update({
            "trigger": selected.get("trigger"),
            "source_system": selected.get("source_system"),
            "destination_system": selected.get("destination_system"),
            "notification_channel": selected.get("notification_channel"),
            "credentials_ready": selected.get("credentials_ready"),
            "test_approved": selected.get("test_approved"),
        })

    requirements["build_contract"] = {
        "service": service,
        "required_options": [item["key"] for item in option_definitions(service) if item.get("required")],
        "selected_options": dict(selected),
    }
    return requirements


def configuration_summary(service: str | None, selected: dict[str, Any] | None) -> dict[str, Any]:
    selected = selected or {}
    missing = validate_options(service, selected)
    return {
        "service": service,
        "complete": not missing,
        "missing": missing,
        "selected": selected,
    }
