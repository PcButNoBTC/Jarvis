"""Layered self-hosted API authentication.

LUMA_API_KEY remains a deployment-level emergency key. User sessions use signed
Bearer tokens and roles. Portal token routes remain separately scoped.
"""
import os, secrets
from auth import verify_token

API_KEY=os.getenv("LUMA_API_KEY")
PUBLIC_PATHS={"/","/health","/auth/login","/docs","/openapi.json","/redoc","/voice/twilio/incoming","/voice/twilio/gather","/voice/stream"}

def authorized(provided):
    if not API_KEY:
        return False
    return bool(provided) and secrets.compare_digest(provided, API_KEY)

def authenticate(api_key=None, bearer=None):
    if API_KEY and authorized(api_key):
        return {"sub":"api-key","role":"owner","email":"api-key"}
    if bearer:
        return verify_token(bearer)
    if not API_KEY and not bearer:
        return {"sub":"local","role":"owner","email":"local"}
    return None

def can(role, *allowed):
    return role in set(allowed)
