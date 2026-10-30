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

from .models import User

TOKEN_TTL_SECONDS = 8 * 3600
# A per-process secret unless one is configured; restarting the API logs everyone out.
_SECRET = os.environ.get("AF07_SECRET_KEY", "").encode() or secrets.token_bytes(32)
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
    body = {"sub": user.username, "role": user.role, "emp": user.employee_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def decode_token(token: str) -> Dict:
    try:
        payload, sig = token.split(".")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")
    expected = _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token signature")
    claims = json.loads(_unb64(payload))
    if claims["exp"] < time.time():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again")
    return claims


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> Dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return decode_token(creds.credentials)


def require_admin(user: Dict = Depends(current_user)) -> Dict:
    if user["role"] != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Enterprise Admin / Project Manager role required")
    return user


def assert_self_or_admin(user: Dict, employee_id: str) -> None:
    if user["role"] != "ADMIN" and user.get("emp") != employee_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff can only access their own records")
