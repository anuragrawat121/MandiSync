"""Shared API hardening helpers (auth + CORS origin parsing)."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def parse_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://localhost:3000"]


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
