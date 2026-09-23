"""Credential-aware provider runtime.

Loads integration credentials from the configured secret backend, refreshes OAuth
tokens before expiry, persists rotated credentials, and records provider health.
Provider adapters never receive database access or secret references.
"""
from __future__ import annotations
import json, time
from oauth import refresh_request
from secret_backend import backend
from provider_adapters import get_adapter

REFRESH_SKEW_SECONDS=120

def _decode(value):
    if not value: return {}
    if isinstance(value,dict): return value
    return json.loads(value)

def load_credentials(integration):
    secret_ref=integration.get("secret_ref")
    if not secret_ref:
        raise RuntimeError("Integration has no secret reference")
    credentials=_decode(backend().get(secret_ref))
    if not credentials.get("access_token") and credentials.get("token"):
        credentials["access_token"]=credentials["token"]
    expires_at=credentials.get("expires_at")
    if expires_at is None and integration.get("expires_at"):
        expires_at=integration["expires_at"].timestamp() if hasattr(integration["expires_at"],"timestamp") else None
    if credentials.get("refresh_token") and expires_at and float(expires_at) <= time.time()+REFRESH_SKEW_SECONDS:
        refreshed=refresh_request(integration["provider"],credentials["refresh_token"])
        credentials={**credentials,**refreshed}
        if refreshed.get("refresh_token"):
            credentials["refresh_token"]=refreshed["refresh_token"]
        backend().put(secret_ref,json.dumps(credentials))
    return credentials

def execute_integration(integration, capability, payload=None):
    credentials=load_credentials(integration)
    adapter=get_adapter(integration["provider"],credentials)
    if capability=="health_check":
        return adapter.health_check()
    return adapter.execute(capability,payload or {})

def provider_status(integration):
    try:
        result=execute_integration(integration,"health_check")
        return {"status":result.status,"provider":result.provider,"error":result.error}
    except Exception as exc:
        return {"status":"error","provider":integration.get("provider"),"error":type(exc).__name__}
