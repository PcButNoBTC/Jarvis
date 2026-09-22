from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Prospect:
    name: str
    website_url: str | None = None
    industry: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str = "manual"
    source_url: str | None = None
    source_external_id: str | None = None
    notes: str | None = None


def normalize_domain(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip()
    if not value:
        return None
    if "://" not in value:
        value = "https://" + value
    host = (urlparse(value).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def dedupe_key(prospect: Prospect) -> tuple[str, str]:
    if prospect.source_external_id:
        return ("source_id", f"{prospect.source}:{prospect.source_external_id}")
    if prospect.email:
        return ("email", prospect.email.strip().lower())
    domain = normalize_domain(prospect.website_url)
    if domain:
        return ("domain", domain)
    return ("name", prospect.name.strip().lower())
