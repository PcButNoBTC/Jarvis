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



def parse_csv_prospects(csv_text: str) -> list[Prospect]:
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames or "name" not in {h.strip().lower() for h in reader.fieldnames if h}:
        raise ValueError("CSV must include a name column")

    result = []
    for row in reader:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if not normalized.get("name"):
            continue
        result.append(Prospect(
            name=normalized["name"],
            website_url=normalized.get("website_url") or normalized.get("website"),
            industry=normalized.get("industry"),
            phone=normalized.get("phone"),
            email=normalized.get("email"),
            source="csv",
            source_external_id=normalized.get("source_external_id") or normalized.get("id"),
            notes=normalized.get("notes"),
        ))
    return result
