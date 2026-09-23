"""OAuth helpers for Luma's customer-facing provider connections.

Authorization codes are short-lived and are never stored. Provider access and
refresh tokens belong in the configured secret backend, not PostgreSQL.
"""
import base64, hashlib, hmac, json, os, secrets, time
from urllib.parse import urlencode

def _state_secret():
    return os.getenv("LUMA_AUTH_SECRET", "")

PROVIDERS = {
    "google_calendar": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scopes": "https://www.googleapis.com/auth/calendar",
        "client_id_env": "GOOGLE_CLIENT_ID",
        "client_secret_env": "GOOGLE_CLIENT_SECRET",
    },
    "microsoft_outlook": {
        "authorize": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": "offline_access Calendars.ReadWrite",
        "client_id_env": "MICROSOFT_CLIENT_ID",
        "client_secret_env": "MICROSOFT_CLIENT_SECRET",
    },
    "hubspot": {
        "authorize": "https://app.hubspot.com/oauth/authorize",
        "token": "https://api.hubapi.com/oauth/v1/token",
        "scopes": "crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.deals.write",
        "client_id_env": "HUBSPOT_CLIENT_ID",
        "client_secret_env": "HUBSPOT_CLIENT_SECRET",
    },
    "calendly": {
        "authorize": "https://auth.calendly.com/oauth/authorize",
        "token": "https://auth.calendly.com/oauth/token",
        "scopes": "default",
        "client_id_env": "CALENDLY_CLIENT_ID",
        "client_secret_env": "CALENDLY_CLIENT_SECRET",
    },
}


def config(provider):
    if provider not in PROVIDERS:
        raise KeyError(provider)
    return PROVIDERS[provider]


def state(provider, project_id, code_verifier=None):
    secret = _state_secret()
    if not secret:
        raise RuntimeError("LUMA_AUTH_SECRET is required")
    payload = {
        "provider": provider,
        "project_id": str(project_id),
        "nonce": secrets.token_urlsafe(16),
        "exp": int(time.time()) + 600,
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    raw = json.dumps(payload, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + sig


def verify_state(value):
    try:
        body, sig = value.split(".", 1)
        expected = hmac.new(_state_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return payload if int(payload["exp"]) >= int(time.time()) else None
    except Exception:
        return None


def _pkce_verifier():
    return secrets.token_urlsafe(48)


def _pkce_challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


def authorization_url(provider, project_id, redirect_uri):
    c = config(provider)
    client_id = os.getenv(c["client_id_env"])
    if not client_id:
        raise RuntimeError(f"Missing OAuth client id for {provider}")

    verifier = _pkce_verifier() if provider == "calendly" else None
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": c["scopes"],
        "state": state(provider, project_id, verifier),
    }
    if provider == "google_calendar":
        params.update(access_type="offline", prompt="consent")
    if provider == "calendly":
        params.update(code_challenge=_pkce_challenge(verifier), code_challenge_method="S256")
    return c["authorize"] + "?" + urlencode(params)


def token_request(provider, code, redirect_uri, code_verifier=None):
    c = config(provider)
    client_id = os.getenv(c["client_id_env"])
    client_secret = os.getenv(c["client_secret_env"])
    if not client_id:
        raise RuntimeError(f"Missing OAuth client id for {provider}")
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if client_secret:
        data["client_secret"] = client_secret
    if provider == "calendly":
        data["code_verifier"] = code_verifier or ""
    response = __import__("httpx").post(c["token"], data=data, timeout=20)
    if not response.is_success:
        raise RuntimeError(f"{provider} token exchange failed: {response.text[:500]}")
    return response.json()


def refresh_request(provider, refresh_token):
    c = config(provider)
    client_id = os.getenv(c["client_id_env"])
    client_secret = os.getenv(c["client_secret_env"])
    data = {"grant_type": "refresh_token", "client_id": client_id, "refresh_token": refresh_token}
    if client_secret:
        data["client_secret"] = client_secret
    response = __import__("httpx").post(c["token"], data=data, timeout=20)
    if not response.is_success:
        raise RuntimeError(f"{provider} token refresh failed: {response.text[:500]}")
    return response.json()
