"""Self-hosted authentication primitives.

Passwords are hashed with scrypt and sessions are stateless HMAC tokens. The
system is deliberately dependency-free; production deployments should put the
API behind TLS and can replace this module with an external identity provider.
"""
import base64, hashlib, hmac, json, os, secrets, time

AUTH_SECRET = os.getenv("LUMA_AUTH_SECRET", "")
TOKEN_TTL = int(os.getenv("LUMA_AUTH_TOKEN_TTL_SECONDS", "3600"))

def _secret():
    if not AUTH_SECRET:
        raise RuntimeError("LUMA_AUTH_SECRET is required for user authentication")
    return AUTH_SECRET.encode()

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()

def verify_password(password, encoded):
    try:
        _, salt, digest = encoded.split("$", 2)
        salt_b = base64.urlsafe_b64decode(salt.encode())
        expected = base64.urlsafe_b64decode(digest.encode())
        actual = hashlib.scrypt(password.encode(), salt=salt_b, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def issue_token(user_id, role, email):
    payload = {"sub": str(user_id), "role": role, "email": email, "exp": int(time.time()) + TOKEN_TTL}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + sig

def verify_token(token):
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        payload = json.loads(raw)
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
