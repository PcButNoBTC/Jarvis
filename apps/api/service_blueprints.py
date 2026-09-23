"""Reusable service blueprints.

A blueprint is the repeatable operating contract for a service. Client projects
instantiate a blueprint with configuration rather than inventing a workflow.
"""
from __future__ import annotations

from project_options import option_definitions

BLUEPRINTS={
    "AI Website":{"workflow":"project_delivery","qa":["requirements_complete","contact_path","hosting","production_domain"],"success_metrics":["qualified_leads","conversion_rate"]},
    "AI Receptionist":{"workflow":"project_delivery","qa":["requirements_complete","phone"],"success_metrics":["answered_calls","booked_appointments"]},
    "Lead Capture System":{"workflow":"project_delivery","qa":["requirements_complete","destination","notification"],"success_metrics":["leads_captured","lead_response_time"]},
    "Appointment Automation":{"workflow":"project_delivery","qa":["requirements_complete","calendar"],"success_metrics":["bookings","no_show_rate"]},
    "Review Automation":{"workflow":"project_delivery","qa":["requirements_complete","review_platform"],"success_metrics":["review_requests","reviews_received"]},
    "Video Walkthrough":{"workflow":"project_delivery","qa":["requirements_complete"],"success_metrics":["views","qualified_inquiries"]},
    "Custom Automation":{"workflow":"project_delivery","qa":["requirements_complete"],"success_metrics":["time_saved","error_rate"]},
}

def blueprint(service):
    base=BLUEPRINTS.get(service)
    if not base: raise ValueError("Unknown service blueprint")
    return {"service":service,**base,"required_options":[x["key"] for x in option_definitions(service) if x.get("required")]}

def instantiate(service, selected, requirements=None):
    b=blueprint(service)
    return {**b,"configuration":selected or {},"requirements":requirements or {},
            "instance_contract":{"service":service,"configuration":selected or {}}}
