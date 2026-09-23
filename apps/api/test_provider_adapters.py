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

def test_smtp_send_email(monkeypatch):
    class FakeSMTP:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def starttls(self): pass
        def login(self,*a): pass
        def send_message(self,msg): self.msg=msg
    monkeypatch.setattr("smtplib.SMTP",FakeSMTP)
    from provider_adapters import SMTPAdapter
    result=SMTPAdapter({"host":"smtp.example","port":587,"from":"ops@example.com"}).execute(
        "send_email",{"to":"client@example.com","subject":"Test","body":"Hello"})
    assert result.status=="ok"

def test_twilio_sms(monkeypatch):
    from provider_adapters import TwilioAdapter
    class Fake:
        is_success=True
        content=b'{"sid":"SM1"}'
        text=""
        def json(self): return {"sid":"SM1"}
    monkeypatch.setattr("provider_adapters.httpx.post",lambda *a,**k: Fake())
    result=TwilioAdapter({"account_sid":"AC1","auth_token":"x","from":"+15550000000"}).execute(
        "sms",{"to":"+15550000001","body":"Hello"})
    assert result.status=="ok"
