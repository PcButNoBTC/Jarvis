from provider_adapters import GoogleCalendarAdapter, MicrosoftOutlookAdapter, HubSpotAdapter, CalendlyAdapter

class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}
        self.content = b"{}"
        self.text = "{}"
    @property
    def is_success(self): return 200 <= self.status_code < 300
    def json(self): return self._data

def test_google_calendar_create_event(monkeypatch):
    seen = {}
    def fake_request(method, url, **kwargs):
        seen.update(method=method, url=url, kwargs=kwargs)
        return FakeResponse(200, {"id": "event-1"})
    monkeypatch.setattr("provider_adapters.httpx.request", fake_request)
    result = GoogleCalendarAdapter({"access_token": "x"}).execute(
        "create_event", {"calendar_id": "primary", "event": {"summary": "Test"}}
    )
    assert result.status == "ok"
    assert seen["url"].endswith("/calendars/primary/events")
    assert seen["kwargs"]["json"]["summary"] == "Test"

def test_outlook_create_event(monkeypatch):
    monkeypatch.setattr("provider_adapters.httpx.request", lambda *a, **k: FakeResponse(201, {"id": "event-1"}))
    result = MicrosoftOutlookAdapter({"access_token": "x"}).execute(
        "create_event", {"event": {"subject": "Test"}}
    )
    assert result.status == "ok"

def test_hubspot_contact(monkeypatch):
    seen = {}
    def fake_request(method, url, **kwargs):
        seen.update(method=method, url=url, kwargs=kwargs)
        return FakeResponse(201, {"id": "contact-1"})
    monkeypatch.setattr("provider_adapters.httpx.request", fake_request)
    result = HubSpotAdapter({"access_token": "x"}).execute(
        "create_contact", {"email": "owner@example.com"}
    )
    assert result.status == "ok"
    assert seen["kwargs"]["json"]["properties"]["email"] == "owner@example.com"

def test_calendly_event_types(monkeypatch):
    monkeypatch.setattr("provider_adapters.httpx.request", lambda *a, **k: FakeResponse(200, {"collection": []}))
    result = CalendlyAdapter({"access_token": "x"}).execute("list_event_types")
    assert result.status == "ok"
