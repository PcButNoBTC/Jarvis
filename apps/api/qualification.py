from __future__ import annotations

# Factor → points (same as the original aggregate scorer)
FACTOR_POINTS = {
    "site_error": 30,
    "no_https_observed": 15,
    "no_mobile_viewport_observed": 20,
    "no_contact_form_observed": 15,
    "no_phone_link_observed": 5,
    "no_clear_cta_observed": 10,
    "no_email_or_contact_form_observed": 5,
    "slow_response_observed": 10,
}

# Which factors strengthen which services (weights are additive on top of base)
# Higher weight = stronger signal for that service.
SERVICE_FACTOR_WEIGHTS: dict[str, dict[str, float]] = {
    "AI Website": {
        "site_error": 1.0,
        "no_https_observed": 1.0,
        "no_mobile_viewport_observed": 1.0,
        "slow_response_observed": 0.8,
        "no_clear_cta_observed": 0.4,
        "no_contact_form_observed": 0.3,
    },
    "Lead Capture System": {
        "no_contact_form_observed": 1.0,
        "no_clear_cta_observed": 0.9,
        "no_email_or_contact_form_observed": 1.0,
        "no_phone_link_observed": 0.4,
    },
    "AI Receptionist": {
        "no_phone_link_observed": 1.5,
        "no_contact_form_observed": 0.6,
        "no_clear_cta_observed": 0.4,
        "no_email_or_contact_form_observed": 0.5,
    },
    "Appointment Automation": {
        "no_clear_cta_observed": 1.0,
        "no_contact_form_observed": 0.8,
        "no_phone_link_observed": 0.8,
        "no_email_or_contact_form_observed": 0.4,
    },
    "Review Automation": {
        # Weaker default signals; can be strengthened later with industry heuristics
        "no_clear_cta_observed": 0.2,
        "no_contact_form_observed": 0.2,
    },
    "Custom Automation": {
        # Catches multi-signal or residual cases
        "site_error": 0.5,
        "no_https_observed": 0.3,
        "no_mobile_viewport_observed": 0.3,
        "no_contact_form_observed": 0.4,
        "no_phone_link_observed": 0.3,
        "no_clear_cta_observed": 0.4,
        "no_email_or_contact_form_observed": 0.3,
        "slow_response_observed": 0.4,
    },
}

# Minimum service score to emit as a real opportunity (0-100 scale)
MIN_SERVICE_SCORE = 25


def _collect_factors(analysis: dict) -> list[dict]:
    """Extract observed negative factors with points (evidence-first)."""
    factors: list[dict] = []

    if analysis.get("http_status") and analysis["http_status"] >= 400:
        factors.append({"factor": "site_error", "points": FACTOR_POINTS["site_error"]})
    if analysis.get("https") is False:
        factors.append({"factor": "no_https_observed", "points": FACTOR_POINTS["no_https_observed"]})
    if analysis.get("has_mobile_viewport") is False:
        factors.append(
            {"factor": "no_mobile_viewport_observed", "points": FACTOR_POINTS["no_mobile_viewport_observed"]}
        )
    if analysis.get("has_contact_form") is False:
        factors.append(
            {"factor": "no_contact_form_observed", "points": FACTOR_POINTS["no_contact_form_observed"]}
        )
    if analysis.get("has_phone_link") is False:
        factors.append(
            {"factor": "no_phone_link_observed", "points": FACTOR_POINTS["no_phone_link_observed"]}
        )
    if analysis.get("has_cta") is False:
        factors.append(
            {"factor": "no_clear_cta_observed", "points": FACTOR_POINTS["no_clear_cta_observed"]}
        )
    if analysis.get("has_email_link") is False and analysis.get("has_contact_form") is False:
        factors.append(
            {
                "factor": "no_email_or_contact_form_observed",
                "points": FACTOR_POINTS["no_email_or_contact_form_observed"],
            }
        )
    if analysis.get("response_time_ms") and analysis["response_time_ms"] > 3000:
        factors.append(
            {"factor": "slow_response_observed", "points": FACTOR_POINTS["slow_response_observed"]}
        )

    return factors


def score_opportunity(analysis: dict, service_name: str | None = None) -> dict:
    """
    Backward-compatible aggregate score.
    When service_name is given, also return a service-weighted score for that service.
    """
    factors = _collect_factors(analysis)
    base_score = min(sum(f["points"] for f in factors), 100)

    if service_name and service_name in SERVICE_FACTOR_WEIGHTS:
        weights = SERVICE_FACTOR_WEIGHTS[service_name]
        weighted = 0.0
        for f in factors:
            w = weights.get(f["factor"], 0.0)
            weighted += f["points"] * w
        service_score = min(int(round(weighted)), 100)
    else:
        service_score = base_score

    return {
        "score": service_score if service_name else base_score,
        "base_score": base_score,
        "factors": factors,
        "service_hint": service_name,
        "confidence": "heuristic",
    }


def map_to_service_opportunities(analysis: dict) -> list[dict]:
    """
    Turn raw website signals into service-specific opportunities.

    Returns a list of dicts sorted by score descending:
      {
        "service": str,
        "score": int (0-100),
        "factors": [ {factor, points}, ... ],  # only factors that contributed to this service
        "confidence": "heuristic",
        "title": str,
        "description": str,
      }
    Only services that reach MIN_SERVICE_SCORE are included.
    If nothing reaches the threshold but there are factors, a single Custom Automation
    opportunity is emitted so the pipeline still surfaces something for human review.
    """
    factors = _collect_factors(analysis)
    if not factors:
        return []

    results: list[dict] = []

    for service, weights in SERVICE_FACTOR_WEIGHTS.items():
        weighted = 0.0
        contributing: list[dict] = []
        for f in factors:
            w = weights.get(f["factor"], 0.0)
            if w > 0:
                weighted += f["points"] * w
                contributing.append(f)

        score = min(int(round(weighted)), 100)
        if score < MIN_SERVICE_SCORE:
            continue

        title, description = _service_copy(service, contributing)
        results.append(
            {
                "service": service,
                "score": score,
                "factors": contributing,
                "confidence": "heuristic",
                "title": title,
                "description": description,
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)

    # Fallback: if every service scored below threshold, still surface Custom Automation
    if not results and factors:
        title, description = _service_copy("Custom Automation", factors)
        results.append(
            {
                "service": "Custom Automation",
                "score": min(sum(f["points"] for f in factors), 100),
                "factors": factors,
                "confidence": "heuristic",
                "title": title,
                "description": description,
            }
        )

    return results


def _service_copy(service: str, factors: list[dict]) -> tuple[str, str]:
    """Human-readable title + description tied to the observed evidence."""
    factor_names = [f["factor"].replace("_", " ") for f in factors[:4]]
    evidence_bit = ", ".join(factor_names) if factor_names else "observed technical signals"

    titles = {
        "AI Website": "Website improvement opportunity",
        "Lead Capture System": "Lead capture gap",
        "AI Receptionist": "Inbound call / receptionist opportunity",
        "Appointment Automation": "Appointment & booking automation opportunity",
        "Review Automation": "Review request automation opportunity",
        "Custom Automation": "Custom workflow automation opportunity",
        "Video Walkthrough": "Video walkthrough opportunity",
    }
    descriptions = {
        "AI Website": (
            f"Observed website signals ({evidence_bit}) that may justify a conversion-focused "
            "website improvement conversation."
        ),
        "Lead Capture System": (
            f"Observed missing or weak lead intake signals ({evidence_bit}). "
            "A structured lead capture and routing workflow may improve conversion."
        ),
        "AI Receptionist": (
            f"Observed weak phone / inbound contact signals ({evidence_bit}). "
            "An AI-assisted receptionist or call-handling flow may recover missed opportunities."
        ),
        "Appointment Automation": (
            f"Observed weak booking / CTA signals ({evidence_bit}). "
            "Appointment booking, reminders and follow-up automation may reduce friction."
        ),
        "Review Automation": (
            f"Observed signals ({evidence_bit}) that could support a review-request and follow-up workflow."
        ),
        "Custom Automation": (
            f"Multiple or residual signals ({evidence_bit}) suggest a scoped custom automation "
            "tied to a measurable business problem."
        ),
        "Video Walkthrough": (
            "A short business / property / service walkthrough video may strengthen trust and conversion."
        ),
    }

    return (
        titles.get(service, f"{service} opportunity"),
        descriptions.get(
            service,
            f"Observed signals ({evidence_bit}) that may justify a {service} conversation.",
        ),
    )
