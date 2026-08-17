"""Shared API hardening helpers (auth + CORS origin parsing)."""

from __future__ import annotations

import os
import re

from fastapi import Header, HTTPException, status

_CLOUDFLARE_QUICK_TUNNEL = re.compile(
    r"^https://[a-z0-9-]+\.trycloudflare\.com$",
    re.IGNORECASE,
)


def parse_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:3000"]


def origin_is_allowed(origin: str) -> bool:
    """Exact ALLOWED_ORIGINS match, plus Cloudflare quick-tunnel hosts."""
    if not origin:
        return False
    if origin in parse_allowed_origins():
        return True
    extra = os.getenv("ALLOW_CLOUDFLARE_TUNNEL_ORIGINS", "true").strip().lower()
    if extra in {"1", "true", "yes", "on"} and _CLOUDFLARE_QUICK_TUNNEL.match(origin):
        return True
    return False


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Reject /api/arbitrage/* calls that omit or mismatch Backend/.env API_KEY."""
    expected = os.getenv("API_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API_KEY is not configured.",
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Send header X-API-Key.",
        )
