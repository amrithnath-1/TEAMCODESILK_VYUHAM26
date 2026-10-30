"""Authentication (PBKDF2 password hashes + HMAC-signed bearer tokens) and RBAC guards."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .models import User

TOKEN_TTL_SECONDS = 8 * 3600
_token_secret = None


def check_config() -> None:
    """Outside development the signing key must not live in the database it protects."""
    if db.environment() != "development" and len(os.environ.get("AF07_SECRET_KEY", "")) < 32:
        raise RuntimeError("AF07_SECRET_KEY must be set to at least 32 characters outside development")


def check_demo_passwords(users) -> None:
    """The demo passwords are published in a public repository, so anyone could sign in with them."""
    from .seed import ADMIN_ACCOUNT, STAFF_PASSWORD     # here because seed imports this module
    if db.environment() == "development" or os.environ.get("VYUHAM_ALLOW_DEMO_PASSWORDS", "").lower() == "true":
        return
    known = [u.username for u in users if any(verify_password(p, u) for p in (ADMIN_ACCOUNT["password"], STAFF_PASSWORD))]
    if known:
        raise RuntimeError(f"{len(known)} account(s) still use the published demo passwords. Run scripts.rotate_demo_passwords, or set VYUHAM_ALLOW_DEMO_PASSWORDS=true to accept this.")


def _secret() -> bytes:
    """AF07_SECRET_KEY if set, otherwise (development only) a random key kept in the database."""
    global _token_secret
    if _token_secret is None:
        env = os.environ.get("AF07_SECRET_KEY", "")
        if env:
            _token_secret = env.encode()
        else:
            stored = db.get_meta("token_secret")
            if not stored:
                stored = secrets.token_hex(32)
                db.set_meta("token_secret", stored)
            _token_secret = stored.encode()
    return _token_secret


_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()
    return {"password_hash": digest, "salt": salt}


def verify_password(password: str, user: User) -> bool:
    candidate = hash_password(password, user.salt)["password_hash"]
    return hmac.compare_digest(candidate, user.password_hash)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_token(user: User) -> str:
    body = {"sub": user.username, "role": user.role, "emp": user.employee_id, "org": db.org(), "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def decode_token(token: str) -> Dict:
    try:
        payload, sig = token.split(".")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token signature")
    claims = json.loads(_unb64(payload))
    if claims["exp"] < time.time():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again")
    return claims


def coarse_role(role: str) -> str:
    return "ADMIN" if role in ("OWNER", "ADMIN") else "STAFF"


def organization_from(authorization: Optional[str]) -> str:
    """The organization in a valid token, or NO_ORG. Scopes the whole request before any route runs."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return db.NO_ORG
    try:
        return decode_token(authorization.split(" ", 1)[1].strip()).get("org", db.DEFAULT_ORG)
    except HTTPException:
        return db.NO_ORG


REAUTH_TTL_SECONDS = 300


def issue_reauth(username: str, purpose: str) -> str:
    """Short-lived proof that the signed-in user just re-entered their password, for one kind of action."""
    payload = _b64(json.dumps({"sub": username, "purpose": purpose, "exp": int(time.time()) + REAUTH_TTL_SECONDS}, separators=(",", ":")).encode())
    return f"{payload}.{_b64(hmac.new(_secret(), b'reauth:' + payload.encode(), hashlib.sha256).digest())}"


def check_reauth(token: str, username: str, purpose: str) -> None:
    denied = HTTPException(403, "Please confirm your password again to make this change")
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(_secret(), b"reauth:" + payload.encode(), hashlib.sha256).digest())
        claims = json.loads(_unb64(payload)) if hmac.compare_digest(sig.encode(), expected.encode()) else None
    except (ValueError, TypeError):
        raise denied
    if not claims or claims["sub"] != username or claims["purpose"] != purpose or claims["exp"] < time.time():
        raise denied


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> Dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    claims = decode_token(creds.credentials)
    from .state import STORE    # imported here because state -> seed -> auth
    account = STORE.user(claims["sub"])
    if account is None:         # deactivated or removed since the token was issued
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is no longer active")
    # "role" is the coarse admin-or-not check used across the app; "org_role" is the exact role.
    return {**claims, "role": coarse_role(account.role), "org_role": account.role, "emp": account.employee_id}


def require_admin(user: Dict = Depends(current_user)) -> Dict:
    if user["role"] != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Enterprise Admin / Project Manager role required")
    return user


def assert_self_or_admin(user: Dict, employee_id: str) -> None:
    if user["role"] != "ADMIN" and user.get("emp") != employee_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff can only access their own records")
