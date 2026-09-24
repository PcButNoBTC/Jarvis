import json
from provider_runtime import load_credentials
def test_load_credentials_without_refresh(monkeypatch):
    monkeypatch.setattr("provider_runtime.backend",lambda: type("B",(),{"get":lambda s,r: json.dumps({"access_token":"a","expires_at":9999999999})})())
    value=load_credentials({"secret_ref":"x","provider":"google_calendar"})
    assert value["access_token"]=="a"
