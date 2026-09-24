"""Provider adapters for calendar, CRM, phone, and billing services.

Adapters accept runtime credentials. Credentials should normally come from the
secret backend and are never persisted in project configuration.
"""
import os
import httpx
from dataclasses import dataclass

@dataclass
class ProviderResponse:
    status: str
    provider: str
    capability: str
    data: dict
    error: str | None = None

class ProviderAdapter:
    provider = "base"
    capabilities = set()
    def __init__(self, credentials=None): self.credentials = credentials or {}
    def supports(self, capability): return capability in self.capabilities
    def health_check(self): return ProviderResponse("not_implemented", self.provider, "health_check", {}, "Adapter requires implementation")
    def execute(self, capability, payload=None):
        if not self.supports(capability): return ProviderResponse("unsupported", self.provider, capability, {}, "Capability is not supported")
        return ProviderResponse("not_implemented", self.provider, capability, {}, "Adapter requires implementation")

class TokenAdapter(ProviderAdapter):
    base_url = ""
    token_env = ""
    def token(self): return self.credentials.get("access_token") or self.credentials.get("token") or os.getenv(self.token_env)
    def request(self, method, path, **kwargs):
        token = self.token()
        if not token: return None, "Missing provider token"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Accept", "application/json")
        try:
            response = httpx.request(method, self.base_url + path, headers=headers, timeout=20, **kwargs)
            data = response.json() if response.content else {}
            return response, data
        except Exception as exc:
            return None, str(exc)

class SMTPAdapter(ProviderAdapter):
    provider = "smtp"
    capabilities = {"health_check", "send_email"}
    def health_check(self):
        host=self.credentials.get("host") or os.getenv("SMTP_HOST")
        port=int(self.credentials.get("port") or os.getenv("SMTP_PORT","587"))
        return ProviderResponse("ok" if host and port else "error",self.provider,"health_check",{"host_configured":bool(host),"port":port},
                                None if host else "Missing SMTP host")
    def execute(self, capability, payload=None):
        if capability!="send_email": return super().execute(capability,payload)
        import smtplib
        from email.message import EmailMessage
        payload=payload or {}
        host=self.credentials.get("host") or os.getenv("SMTP_HOST")
        port=int(self.credentials.get("port") or os.getenv("SMTP_PORT","587"))
        username=self.credentials.get("username") or os.getenv("SMTP_USERNAME")
        password=self.credentials.get("password") or os.getenv("SMTP_PASSWORD")
        sender=payload.get("from") or self.credentials.get("from") or username
        if not host or not sender or not payload.get("to"):
            return ProviderResponse("error",self.provider,capability,{},"Missing SMTP host/sender/recipient")
        message=EmailMessage()
        message["From"]=sender; message["To"]=payload["to"]; message["Subject"]=payload.get("subject","")
        message.set_content(payload.get("body",""))
        try:
            with smtplib.SMTP(host,port,timeout=20) as smtp:
                smtp.starttls()
                if username and password: smtp.login(username,password)
                smtp.send_message(message)
            return ProviderResponse("ok",self.provider,capability,{"sent":True,"to":payload["to"]})
        except Exception as exc:
            return ProviderResponse("error",self.provider,capability,{},type(exc).__name__)

class GoogleCalendarAdapter(TokenAdapter):
    provider = "google_calendar"
    capabilities = {"health_check", "list_calendars", "read_availability", "create_event"}
    base_url = "https://www.googleapis.com/calendar/v3"
    token_env = "GOOGLE_ACCESS_TOKEN"
    def health_check(self):
        r, data = self.request("GET", "/users/me/calendarList?maxResults=1")
        return ProviderResponse("ok" if r is not None and r.is_success else "error", self.provider, "health_check", data if isinstance(data, dict) else {}, None if r is not None and r.is_success else str(data))
    def execute(self, capability, payload=None):
        payload = payload or {}
        if capability == "list_calendars":
            r, data = self.request("GET", "/users/me/calendarList")
        elif capability == "read_availability":
            r, data = self.request("POST", "/freeBusy", json={
                "timeMin": payload["time_min"], "timeMax": payload["time_max"],
                "items": [{"id": payload.get("calendar_id", "primary")}],
            })
        elif capability == "create_event":
            calendar_id = payload.get("calendar_id", "primary")
            r, data = self.request("POST", f"/calendars/{calendar_id}/events", json=payload["event"])
        else:
            return super().execute(capability, payload)
        if r is None: return ProviderResponse("error", self.provider, capability, {}, data)
        return ProviderResponse("ok" if r.is_success else "error", self.provider, capability, data, None if r.is_success else r.text)

class MicrosoftOutlookAdapter(TokenAdapter):
    provider = "microsoft_outlook"
    capabilities = {"health_check", "list_calendars", "read_availability", "create_event"}
    base_url = "https://graph.microsoft.com/v1.0"
    token_env = "MICROSOFT_ACCESS_TOKEN"
    def health_check(self):
        r, data = self.request("GET", "/me/calendars?$top=1")
        return ProviderResponse("ok" if r is not None and r.is_success else "error", self.provider, "health_check", data if isinstance(data, dict) else {}, None if r is not None and r.is_success else str(data))
    def execute(self, capability, payload=None):
        payload = payload or {}
        if capability == "list_calendars":
            r, data = self.request("GET", "/me/calendars")
        elif capability == "read_availability":
            r, data = self.request("POST", "/me/calendar/getSchedule", json={
                "schedules": payload["schedules"],
                "startTime": {"dateTime": payload["start_time"], "timeZone": payload.get("time_zone", "UTC")},
                "endTime": {"dateTime": payload["end_time"], "timeZone": payload.get("time_zone", "UTC")},
                "availabilityViewInterval": payload.get("interval_minutes", 30),
            })
        elif capability == "create_event":
            r, data = self.request("POST", "/me/events", json=payload["event"])
        else:
            return super().execute(capability, payload)
        if r is None: return ProviderResponse("error", self.provider, capability, {}, data)
        return ProviderResponse("ok" if r.is_success else "error", self.provider, capability, data, None if r.is_success else r.text)

class HubSpotAdapter(TokenAdapter):
    provider = "hubspot"; capabilities = {"health_check", "create_contact", "create_deal", "list_contacts"}; base_url = "https://api.hubapi.com"; token_env = "HUBSPOT_ACCESS_TOKEN"
    def health_check(self):
        r, data = self.request("GET", "/crm/v3/objects/contacts?limit=1")
        return ProviderResponse("ok" if r is not None and r.is_success else "error", self.provider, "health_check", data if isinstance(data, dict) else {}, None if r is not None and r.is_success else str(data))
    def execute(self, capability, payload=None):
        payload = payload or {}
        if capability == "create_contact":
            r, data = self.request("POST", "/crm/v3/objects/contacts", json={"properties": payload})
        elif capability == "create_deal":
            r, data = self.request("POST", "/crm/v3/objects/deals", json={"properties": payload})
        elif capability == "list_contacts":
            r, data = self.request("GET", "/crm/v3/objects/contacts?limit=100")
        else:
            return super().execute(capability, payload)
        if r is None: return ProviderResponse("error", self.provider, capability, {}, data)
        return ProviderResponse("ok" if r.is_success else "error", self.provider, capability, data, None if r.is_success else r.text)

class CalendlyAdapter(TokenAdapter):
    provider = "calendly"; capabilities = {"health_check", "booking_link", "list_event_types"}; base_url = "https://api.calendly.com"; token_env = "CALENDLY_ACCESS_TOKEN"
    def health_check(self):
        r, data = self.request("GET", "/users/me")
        return ProviderResponse("ok" if r is not None and r.is_success else "error", self.provider, "health_check", data if isinstance(data, dict) else {}, None if r is not None and r.is_success else str(data))
    def execute(self, capability, payload=None):
        if capability == "booking_link":
            return ProviderResponse("ok", self.provider, capability, {"url": (payload or {}).get("url")})
        if capability == "list_event_types":
            r, data = self.request("GET", "/event_types?active=true&count=100")
            if r is None: return ProviderResponse("error", self.provider, capability, {}, data)
            return ProviderResponse("ok" if r.is_success else "error", self.provider, capability, data, None if r.is_success else r.text)
        return super().execute(capability, payload)

class TwilioAdapter(ProviderAdapter):
    provider = "twilio"; capabilities = {"health_check", "call_forwarding", "voice", "sms", "place_call"}
    def health_check(self):
        sid=self.credentials.get("account_sid") or os.getenv("TWILIO_ACCOUNT_SID")
        token=self.credentials.get("auth_token") or os.getenv("TWILIO_AUTH_TOKEN")
        if not sid or not token: return ProviderResponse("error",self.provider,"health_check",{},"Missing Twilio credentials")
        try:
            r=httpx.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",auth=(sid,token),timeout=20)
            return ProviderResponse("ok" if r.is_success else "error",self.provider,"health_check",r.json() if r.content else {},None if r.is_success else r.text)
        except Exception as exc: return ProviderResponse("error",self.provider,"health_check",{},type(exc).__name__)
    def execute(self, capability, payload=None):
        payload=payload or {}
        sid=self.credentials.get("account_sid") or os.getenv("TWILIO_ACCOUNT_SID")
        token=self.credentials.get("auth_token") or os.getenv("TWILIO_AUTH_TOKEN")
        if capability=="place_call":
            import re
            to=payload.get("to")
            sender=payload.get("from") or self.credentials.get("from") or os.getenv("TWILIO_FROM_NUMBER")
            twiml_url=payload.get("url") or os.getenv("LUMA_VOICE_TWIML_URL")
            if not sid or not token or not sender or not to or not twiml_url:
                return ProviderResponse("error",self.provider,capability,{},"Missing Twilio SID/token/from/url")
            if not re.fullmatch(r"\+[1-9]\d{7,14}",to) or not re.fullmatch(r"\+[1-9]\d{7,14}",sender):
                return ProviderResponse("error",self.provider,capability,{},"Phone numbers must use E.164 format")
            try:
                r=httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
                             auth=(sid,token),data={"From":sender,"To":to,"Url":twiml_url,**({"StatusCallback":payload.get("status_callback") or os.getenv("LUMA_VOICE_STATUS_CALLBACK_URL"),"StatusCallbackEvent":["initiated","ringing","answered","completed"]} if (payload.get("status_callback") or os.getenv("LUMA_VOICE_STATUS_CALLBACK_URL")) else {})},timeout=20)
                data=r.json() if r.content else {}
                return ProviderResponse("ok" if r.is_success else "error",self.provider,capability,data,None if r.is_success else r.text)
            except Exception as exc:
                return ProviderResponse("error",self.provider,capability,{},type(exc).__name__)
        if capability!="sms": return super().execute(capability,payload)
        sender=payload.get("from") or self.credentials.get("from") or os.getenv("TWILIO_FROM_NUMBER")
        if not sid or not token or not sender or not payload.get("to") or not payload.get("body"):
            return ProviderResponse("error",self.provider,capability,{},"Missing Twilio SMS fields")
        try:
            r=httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                         auth=(sid,token),data={"From":sender,"To":payload["to"],"Body":payload["body"]},timeout=20)
            data=r.json() if r.content else {}
            return ProviderResponse("ok" if r.is_success else "error",self.provider,capability,data,None if r.is_success else r.text)
        except Exception as exc: return ProviderResponse("error",self.provider,capability,{},type(exc).__name__)

class StripeAdapter(TokenAdapter):
    provider = "stripe"; capabilities = {"health_check", "create_invoice"}; base_url = "https://api.stripe.com/v1"; token_env = "STRIPE_SECRET_KEY"
    def health_check(self):
        r, data = self.request("GET", "/balance")
        return ProviderResponse("ok" if r is not None and r.is_success else "error", self.provider, "health_check", data if isinstance(data, dict) else {}, None if r is not None and r.is_success else str(data))

class ClientManagedAdapter(ProviderAdapter):
    provider = "client_managed"; capabilities = {"handoff_only"}
    def execute(self, capability, payload=None): return ProviderResponse("handoff_required", self.provider, capability, payload or {}, "Client must complete this provider action")

ADAPTERS = {
    "smtp": SMTPAdapter,
    "google_calendar": GoogleCalendarAdapter,
    "microsoft_outlook": MicrosoftOutlookAdapter,
    "hubspot": HubSpotAdapter,
    "calendly": CalendlyAdapter,
    "twilio": TwilioAdapter,
    "stripe": StripeAdapter,
    "client_managed": ClientManagedAdapter,
}
def get_adapter(provider, credentials=None):
    cls = ADAPTERS.get(provider, ProviderAdapter)
    adapter = cls(credentials)
    if cls is ProviderAdapter: adapter.provider = provider
    return adapter
