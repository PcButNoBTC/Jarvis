from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import httpx

USER_AGENT = "Luma/0.1 (+business-research)"

def analyze_website(url: str) -> dict:
    original = url.strip()
    if not original:
        raise ValueError("URL is required")
    if not re.match(r"^https?://", original, re.I):
        original = "https://" + original

    parsed = urlparse(original)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid website URL")

    started = time.perf_counter()
    result = {
        "url": original,
        "http_status": None,
        "https": parsed.scheme == "https",
        "response_time_ms": None,
        "title": None,
        "description": None,
        "has_mobile_viewport": False,
        "has_contact_form": False,
        "has_phone_link": False,
        "cms": None,
        "error": None,
    }

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(8.0, connect=4.0),
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(original)
            result["http_status"] = response.status_code
            result["https"] = response.url.scheme == "https"
            result["response_time_ms"] = round((time.perf_counter() - started) * 1000)
            html = response.text[:2_000_000]
            lower = html.lower()

            title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            desc = re.search(
                r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
                html, re.I | re.S
            )
            result["title"] = re.sub(r"\s+", " ", title.group(1)).strip() if title else None
            result["description"] = re.sub(r"\s+", " ", desc.group(1)).strip() if desc else None
            result["has_mobile_viewport"] = "name="viewport"" in lower or "name='viewport'" in lower
            result["has_contact_form"] = "<form" in lower and any(
                token in lower for token in ("contact", "quote", "appointment", "inquiry")
            )
            result["has_phone_link"] = "tel:" in lower

            cms_markers = {
                "WordPress": ("wp-content", "wp-includes"),
                "Wix": ("wixstatic.com",),
                "Squarespace": ("static1.squarespace.com",),
                "Shopify": ("cdn.shopify.com", "shopify.com/s/"),
                "Webflow": ("webflow.css", "webflow.com"),
            }
            for name, markers in cms_markers.items():
                if any(marker in lower for marker in markers):
                    result["cms"] = name
                    break
    except Exception as exc:
        result["response_time_ms"] = round((time.perf_counter() - started) * 1000)
        result["error"] = type(exc).__name__

    return result
