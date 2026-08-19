"""Shared API hardening helpers (JWT sessions, API key fallback, CORS)."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from services.accounts import (
    ROLE_ADMIN,
    Principal,
    decode_token,
)

_bearer = HTTPBearer(auto_error=False)


def parse_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:3000"]


def _api_key_ok(x_api_key: str | None) -> bool:
    expected = os.getenv("API_KEY", "").strip()
    return bool(expected) and bool(x_api_key) and x_api_key == expected


def get_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer),
    ],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Principal:
    """Require a farmer/admin JWT, or the legacy service API key (admin)."""
    if credentials and credentials.credentials:
        try:
            return decode_token(credentials.credentials)
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Sign in again.",
            ) from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session. Sign in again.",
            ) from exc
    if _api_key_ok(x_api_key):
        return Principal(username="api-key", role=ROLE_ADMIN)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in required.",
    )


def require_user(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    return principal


def require_admin(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
    if principal.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return principal
