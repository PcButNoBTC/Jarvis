"""OAuth configuration and signed state helpers for calendar/CRM connections."""
import base64, hashlib, hmac, json, os, secrets, time
from urllib.parse import urlencode
STATE_SECRET=os.getenv("LUMA_AUTH_SECRET","")
PROVIDERS={
 "google_calendar":{"authorize":"https://accounts.google.com/o/oauth2/v2/auth","token":"https://oauth2.googleapis.com/token","scopes":"https://www.googleapis.com/auth/calendar"},
 "microsoft_outlook":{"authorize":"https://login.microsoftonline.com/common/oauth2/v2.0/authorize","token":"https://login.microsoftonline.com/common/oauth2/v2.0/token","scopes":"offline_access Calendars.ReadWrite"},
 "hubspot":{"authorize":"https://app.hubspot.com/oauth/authorize","token":"https://api.hubapi.com/oauth/v1/token","scopes":"crm.objects.contacts.read crm.objects.contacts.write crm.objects.deals.read crm.objects.deals.write"},
}
def config(provider): return PROVIDERS[provider]
def state(provider, project_id):
    if not STATE_SECRET: raise RuntimeError("LUMA_AUTH_SECRET is required")
    payload=json.dumps({"provider":provider,"project_id":str(project_id),"nonce":secrets.token_urlsafe(16),"exp":int(time.time())+600},separators=(",",":"))
    body=base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig=hmac.new(STATE_SECRET.encode(),body.encode(),hashlib.sha256).hexdigest()
    return body+"."+sig
def verify_state(value):
    try:
        body,sig=value.split(".",1); expected=hmac.new(STATE_SECRET.encode(),body.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): return None
        payload=json.loads(base64.urlsafe_b64decode(body+"="*(-len(body)%4)))
        return payload if int(payload["exp"])>=int(time.time()) else None
    except Exception: return None
def authorization_url(provider, project_id, redirect_uri):
    ids={"google_calendar":"GOOGLE_CLIENT_ID","microsoft_outlook":"MICROSOFT_CLIENT_ID","hubspot":"HUBSPOT_CLIENT_ID"}
    c=config(provider); client_id=os.getenv(ids[provider])
    if not client_id: raise RuntimeError(f"Missing OAuth client id for {provider}")
    params={"client_id":client_id,"redirect_uri":redirect_uri,"response_type":"code","scope":c["scopes"],"state":state(provider,project_id)}
    if provider=="google_calendar": params.update(access_type="offline",prompt="consent")
    return c["authorize"]+"?"+urlencode(params)
