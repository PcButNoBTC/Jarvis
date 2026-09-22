"""HTTP provider adapters for providers that use straightforward API tokens.

OAuth providers still require an authorization flow; these adapters do not fake
OAuth. Credentials are read at runtime from environment variables and never
written to project configuration.
"""
import os
import httpx
from dataclasses import dataclass

@dataclass
class ProviderResponse:
    status:str; provider:str; capability:str; data:dict; error:str|None=None

class ProviderAdapter:
    provider="base"; capabilities=set()
    def __init__(self, credentials=None): self.credentials=credentials or {}
    def supports(self, capability): return capability in self.capabilities
    def health_check(self): return ProviderResponse("not_implemented",self.provider,"health_check",{}, "Adapter requires provider implementation")
    def execute(self, capability, payload=None):
        if not self.supports(capability): return ProviderResponse("unsupported",self.provider,capability,{},"Capability is not supported")
        return ProviderResponse("not_implemented",self.provider,capability,{},"Adapter requires provider implementation")

class TokenAdapter(ProviderAdapter):
    base_url=""
    token_env=""
    def token(self): return self.credentials.get("token") or os.getenv(self.token_env)
    def request(self, method, path, **kwargs):
        token=self.token()
        if not token: return None, "Missing provider token"
        headers=kwargs.pop("headers",{})
        headers["Authorization"]=f"Bearer {token}"
        try:
            response=httpx.request(method,self.base_url+path,headers=headers,timeout=20,**kwargs)
            data=response.json() if response.content else {}
            return (response,data)
        except Exception as exc: return None,str(exc)

class HubSpotAdapter(TokenAdapter):
    provider="hubspot"; capabilities={"health_check","create_contact","create_deal"}; base_url="https://api.hubapi.com"; token_env="HUBSPOT_ACCESS_TOKEN"
    def health_check(self):
        r,data=self.request("GET","/crm/v3/objects/contacts?limit=1")
        if r is None: return ProviderResponse("error",self.provider,"health_check",{},data)
        return ProviderResponse("ok" if r.is_success else "error",self.provider,"health_check",data,None if r.is_success else r.text)
    def execute(self,capability,payload=None):
        if capability=="create_contact":
            r,data=self.request("POST","/crm/v3/objects/contacts",json={"properties":payload or {}})
        elif capability=="create_deal":
            r,data=self.request("POST","/crm/v3/objects/deals",json={"properties":payload or {}})
        else: return super().execute(capability,payload)
        if r is None:return ProviderResponse("error",self.provider,capability,{},data)
        return ProviderResponse("ok" if r.is_success else "error",self.provider,capability,data,None if r.is_success else r.text)

class CalendlyAdapter(TokenAdapter):
    provider="calendly"; capabilities={"health_check","read_availability","booking_link"}; base_url="https://api.calendly.com"; token_env="CALENDLY_ACCESS_TOKEN"
    def health_check(self):
        r,data=self.request("GET","/users/me")
        if r is None:return ProviderResponse("error",self.provider,"health_check",{},data)
        return ProviderResponse("ok" if r.is_success else "error",self.provider,"health_check",data,None if r.is_success else r.text)
    def execute(self,capability,payload=None):
        if capability=="booking_link":
            return ProviderResponse("ok",self.provider,capability,{"url":(payload or {}).get("url")},"")
        return super().execute(capability,payload)

class TwilioAdapter(ProviderAdapter):
    provider="twilio"; capabilities={"health_check","call_forwarding","voice","sms"}
    def _auth(self):
        sid=os.getenv("TWILIO_ACCOUNT_SID"); token=os.getenv("TWILIO_AUTH_TOKEN")
        return sid,token
    def health_check(self):
        sid,token=self._auth()
        if not sid or not token:return ProviderResponse("error",self.provider,"health_check",{},"Missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN")
        try:
            r=httpx.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",auth=(sid,token),timeout=20)
            return ProviderResponse("ok" if r.is_success else "error",self.provider,"health_check",r.json() if r.content else {},None if r.is_success else r.text)
        except Exception as exc:return ProviderResponse("error",self.provider,"health_check",{},str(exc))

class StripeAdapter(TokenAdapter):
    provider="stripe"; capabilities={"health_check","create_invoice"}; base_url="https://api.stripe.com/v1"; token_env="STRIPE_SECRET_KEY"
    def health_check(self):
        r,data=self.request("GET","/balance")
        if r is None:return ProviderResponse("error",self.provider,"health_check",{},data)
        return ProviderResponse("ok" if r.is_success else "error",self.provider,"health_check",data,None if r.is_success else r.text)

class ClientManagedAdapter(ProviderAdapter):
    provider="client_managed"; capabilities={"handoff_only"}
    def execute(self,capability,payload=None): return ProviderResponse("handoff_required",self.provider,capability,payload or {},"Client must complete this provider action")

ADAPTERS={"hubspot":HubSpotAdapter,"calendly":CalendlyAdapter,"twilio":TwilioAdapter,"stripe":StripeAdapter,"client_managed":ClientManagedAdapter}

def get_adapter(provider,credentials=None):
    cls=ADAPTERS.get(provider,ProviderAdapter)
    adapter=cls(credentials)
    if cls is ProviderAdapter: adapter.provider=provider
    return adapter
