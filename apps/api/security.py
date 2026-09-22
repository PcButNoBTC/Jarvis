"""Optional API-key protection for self-hosted Luma.

If LUMA_API_KEY is unset, local development remains open. In a real deployment,
set a strong key and place Luma behind TLS. This is intentionally simple until
full user/role authentication is introduced.
"""
import os
import secrets

API_KEY = os.getenv("LUMA_API_KEY")


def authorized(provided: str | None) -> bool:
    if not API_KEY:
        return True
    return bool(provided) and secrets.compare_digest(provided, API_KEY)
