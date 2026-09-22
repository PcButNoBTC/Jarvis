from __future__ import annotations

def score_opportunity(analysis: dict, service_name: str | None = None) -> dict:
    score = 0
    factors = []

    if analysis.get("http_status") and analysis["http_status"] >= 400:
        score += 30
        factors.append({"factor": "site_error", "points": 30})
    if analysis.get("https") is False:
        score += 15
        factors.append({"factor": "no_https_observed", "points": 15})
    if analysis.get("has_mobile_viewport") is False:
        score += 20
        factors.append({"factor": "no_mobile_viewport_observed", "points": 20})
    if analysis.get("has_contact_form") is False:
        score += 15
        factors.append({"factor": "no_contact_form_observed", "points": 15})
    if analysis.get("has_phone_link") is False:
        score += 5
        factors.append({"factor": "no_phone_link_observed", "points": 5})
    if analysis.get("has_cta") is False:
        score += 10
        factors.append({"factor": "no_clear_cta_observed", "points": 10})
    if analysis.get("has_email_link") is False and analysis.get("has_contact_form") is False:
        score += 5
        factors.append({"factor": "no_email_or_contact_form_observed", "points": 5})
    if analysis.get("response_time_ms") and analysis["response_time_ms"] > 3000:
        score += 10
        factors.append({"factor": "slow_response_observed", "points": 10})

    score = min(score, 100)
    return {
        "score": score,
        "factors": factors,
        "service_hint": service_name,
        "confidence": "heuristic",
    }
