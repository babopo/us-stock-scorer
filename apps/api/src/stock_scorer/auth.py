import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


DEFAULT_ADMIN_SESSION_TTL_SECONDS = 12 * 60 * 60
DEFAULT_STOCK_SCORER_READ_TOKEN = "local-read-token"

bearer_security = HTTPBearer(auto_error=False)
_admin_sessions: dict[str, datetime] = {}


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in_seconds: int
    expires_at: datetime


class AdminSessionResponse(BaseModel):
    authenticated: bool
    role: str
    expires_at: datetime | None


class AdminLogoutResponse(BaseModel):
    status: str


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    role: str
    expires_at: datetime | None = None


BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_security)]


def login_admin(payload: AdminLoginRequest) -> AdminLoginResponse:
    username = os.getenv("ADMIN_USERNAME", "")
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username or not password:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")

    if not secrets.compare_digest(payload.username, username) or not secrets.compare_digest(payload.password, password):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    ttl_seconds = get_admin_session_ttl_seconds()
    expires_at = now_utc() + timedelta(seconds=ttl_seconds)
    access_token = secrets.token_urlsafe(32)
    _admin_sessions[access_token] = expires_at

    return AdminLoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=ttl_seconds,
        expires_at=expires_at,
    )


def get_admin_session(credentials: BearerCredentials) -> AdminSessionResponse:
    principal = require_admin_access(credentials)
    return AdminSessionResponse(authenticated=True, role=principal.role, expires_at=principal.expires_at)


def logout_admin(credentials: BearerCredentials) -> AdminLogoutResponse:
    token = require_bearer_token(credentials)
    require_admin_access(credentials)
    _admin_sessions.pop(token, None)
    return AdminLogoutResponse(status="logged_out")


def require_read_access(credentials: BearerCredentials) -> AuthenticatedPrincipal:
    if not is_read_auth_configured():
        raise HTTPException(status_code=503, detail="API authentication is not configured")

    token = require_bearer_token(credentials)
    if token_matches(token, get_read_token()):
        return AuthenticatedPrincipal(role="read")

    admin_principal = get_admin_principal(token)
    if admin_principal:
        return admin_principal

    raise HTTPException(status_code=401, detail="Invalid bearer token")


def require_admin_access(credentials: BearerCredentials) -> AuthenticatedPrincipal:
    if not is_admin_auth_configured():
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")

    token = require_bearer_token(credentials)
    admin_principal = get_admin_principal(token)
    if admin_principal:
        return admin_principal

    if token_matches(token, get_read_token()):
        raise HTTPException(status_code=403, detail="Admin authorization is required")

    raise HTTPException(status_code=401, detail="Invalid bearer token")


def require_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authorization bearer token is required")
    return credentials.credentials


def get_admin_principal(token: str) -> AuthenticatedPrincipal | None:
    if token_matches(token, os.getenv("ADMIN_AUTH_TOKEN")):
        return AuthenticatedPrincipal(role="admin")

    if not are_admin_credentials_configured():
        return None

    expires_at = _admin_sessions.get(token)
    if not expires_at:
        return None

    if expires_at <= now_utc():
        _admin_sessions.pop(token, None)
        return None

    return AuthenticatedPrincipal(role="admin", expires_at=expires_at)


def is_read_auth_configured() -> bool:
    return bool(get_read_token() or is_admin_auth_configured())


def is_admin_auth_configured() -> bool:
    return bool(os.getenv("ADMIN_AUTH_TOKEN") or are_admin_credentials_configured())


def are_admin_credentials_configured() -> bool:
    return bool(os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD"))


def token_matches(token: str, expected: str | None) -> bool:
    return bool(expected) and secrets.compare_digest(token, expected)


def get_read_token() -> str:
    return os.getenv("STOCK_SCORER_READ_TOKEN") or DEFAULT_STOCK_SCORER_READ_TOKEN


def get_admin_session_ttl_seconds() -> int:
    raw_value = os.getenv("ADMIN_SESSION_TTL_SECONDS", str(DEFAULT_ADMIN_SESSION_TTL_SECONDS))
    try:
        ttl_seconds = int(raw_value)
    except ValueError:
        return DEFAULT_ADMIN_SESSION_TTL_SECONDS
    return ttl_seconds if ttl_seconds > 0 else DEFAULT_ADMIN_SESSION_TTL_SECONDS


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
