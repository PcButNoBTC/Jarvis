import base64
import hashlib
from oauth import state, verify_state, authorization_url

def test_oauth_state_roundtrip(monkeypatch):
    monkeypatch.setenv("LUMA_AUTH_SECRET", "test-secret")
    value = state("google_calendar", "00000000-0000-0000-0000-000000000001")
    claims = verify_state(value)
    assert claims["provider"] == "google_calendar"

def test_calendly_authorization_uses_pkce(monkeypatch):
    monkeypatch.setenv("LUMA_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("CALENDLY_CLIENT_ID", "client")
    url = authorization_url(
        "calendly",
        "00000000-0000-0000-0000-000000000001",
        "https://example.com/callback",
    )
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url

def test_state_secret_is_not_fixed_at_import(monkeypatch):
    monkeypatch.setenv("LUMA_AUTH_SECRET", "first")
    first = state("google_calendar", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("LUMA_AUTH_SECRET", "second")
    assert verify_state(first) is None
