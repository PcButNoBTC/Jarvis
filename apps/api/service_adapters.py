"""Service adapter contracts for Luma delivery.

Adapters turn compiled requirements into an explicit build plan. The existing
artifact generator can consume these plans now, while provider-specific
implementations can be added without changing the project lifecycle.
"""
from __future__ import annotations

from typing import Any

SERVICE_ADAPTERS = {
    "AI Website": {
        "kind": "static_site",
        "outputs": ["responsive_site", "contact_path", "deployment_docs"],
    },
    "Lead Capture System": {
        "kind": "lead_capture",
        "outputs": ["capture_form", "routing_spec", "test_plan"],
    },
    "Appointment Automation": {
        "kind": "workflow",
        "outputs": ["booking_spec", "reminder_spec", "follow_up_spec", "activation_checklist"],
    },
    "AI Receptionist": {
        "kind": "workflow",
        "outputs": ["call_flow", "escalation_rules", "activation_checklist"],
    },
    "Review Automation": {
        "kind": "workflow",
        "outputs": ["review_trigger", "message_sequence", "reporting_spec"],
    },
    "Video Walkthrough": {
        "kind": "content",
        "outputs": ["production_brief", "scene_plan", "asset_checklist"],
    },
    "Custom Automation": {
        "kind": "workflow",
        "outputs": ["process_map", "workflow_spec", "test_plan"],
    },
}


def build_plan(service: str | None, requirements: dict[str, Any]) -> dict[str, Any]:
    adapter = SERVICE_ADAPTERS.get(service or "", SERVICE_ADAPTERS["Custom Automation"])
    return {
        "service": service or "Custom Automation",
        "kind": adapter["kind"],
        "outputs": adapter["outputs"],
        "configuration": requirements.get("configuration") or {},
        "requirements": requirements,
        "provider_actions": _provider_actions(service, requirements),
    }


def _provider_actions(service: str | None, requirements: dict[str, Any]) -> list[str]:
    config = requirements.get("configuration") or {}
    actions: list[str] = []
    if service == "AI Website":
        actions.append(f"hosting:{config.get('hosting', 'pending')}")
        actions.append(f"lead_capture:{config.get('contact_capture', 'pending')}")
        actions.append(f"analytics:{config.get('analytics', 'none')}")
    elif service == "Appointment Automation":
        actions.append(f"calendar:{config.get('calendar_provider', 'pending')}")
    elif service == "AI Receptionist":
        actions.append(f"phone:{config.get('phone_provider', 'pending')}")
    elif service == "Review Automation":
        actions.append(f"review_platform:{config.get('review_platform', 'pending')}")
    return actions
