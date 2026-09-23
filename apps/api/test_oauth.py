from oauth import state, verify_state
def test_oauth_state_roundtrip(monkeypatch):
    monkeypatch.setenv("LUMA_AUTH_SECRET","test-secret")
    value=state("google_calendar","00000000-0000-0000-0000-000000000001")
    claims=verify_state(value)
    assert claims["provider"]=="google_calendar"
