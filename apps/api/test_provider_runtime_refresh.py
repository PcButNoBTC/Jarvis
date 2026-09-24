import json
import provider_runtime

def test_refresh_persists_rotated_token(monkeypatch):
    store={}
    class Backend:
        def get(self,ref): return json.dumps({"access_token":"old","refresh_token":"r","expires_at":0})
        def put(self,ref,value): store[ref]=json.loads(value)
    monkeypatch.setattr(provider_runtime,"backend",lambda:Backend())
    monkeypatch.setattr(provider_runtime,"refresh_request",lambda provider,token:{"access_token":"new","refresh_token":"r2","expires_in":3600})
    value=provider_runtime.load_credentials({"secret_ref":"oauth/google_calendar/1","provider":"google_calendar"})
    assert value["access_token"]=="new"
    assert value["refresh_token"]=="r2"
    assert store["oauth/google_calendar/1"]["access_token"]=="new"
