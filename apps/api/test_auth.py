from auth import hash_password, verify_password, issue_token, verify_token

def test_password_and_token_roundtrip(monkeypatch):
    monkeypatch.setenv("LUMA_AUTH_SECRET", "test-secret")
    encoded=hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong", encoded)
    token=issue_token("00000000-0000-0000-0000-000000000001","owner","owner@example.com")
    claims=verify_token(token)
    assert claims["role"]=="owner"
