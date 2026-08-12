"""Admin API — review intro leads and curate verified commission agents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Any, Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db as get_db_context
from models import Mandi
from rate_limit import limiter
from security import require_api_key
from services.agent_intro_store import (
    VALID_STATUSES,
    list_agent_intro_requests,
    update_agent_intro_status,
)

router = APIRouter(
    tags=["admin"],
    dependencies=[Depends(require_api_key)],
)

_PHONE_DIGITS = re.compile(r"\D+")


def get_db() -> Generator[Session, None, None]:
    with get_db_context() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]


class LeadStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=32)
    admin_note: str = Field(default="", max_length=500)

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return normalized


class CuratedAgent(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    phone: str = Field(..., min_length=10, max_length=20)
    license_id: str = Field(..., min_length=2, max_length=64)
    notes: str = Field(default="", max_length=200)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = _PHONE_DIGITS.sub("", value or "")
        if len(digits) < 10:
            raise ValueError("phone must contain at least 10 digits.")
        return digits[-10:]


class MandiAgentsUpdate(BaseModel):
    agents: list[CuratedAgent] = Field(default_factory=list, max_length=12)


def _is_curated_agent(agent: dict[str, Any]) -> bool:
    """Seed fiction has no verified_at; admin-curated agents always do."""
    return bool(str(agent.get("verified_at") or "").strip())


def _serialize_mandi(mandi: Mandi) -> dict[str, Any]:
    agents = list(mandi.verified_agents or [])
    curated = [a for a in agents if isinstance(a, dict) and _is_curated_agent(a)]
    official = mandi.official_contacts or {}
    return {
        "id": mandi.id,
        "name": mandi.name,
        "state": mandi.state,
        "district": mandi.district,
        "curated_agents": curated,
        "official_contact_count": len(
            (official.get("contacts") if isinstance(official, dict) else []) or []
        ),
    }


@router.get("/leads")
@limiter.limit("30/minute")
def get_leads(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
) -> dict[str, Any]:
    """List farmer agent-intro requests (newest first)."""
    if status_filter and status_filter not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )
    leads = list_agent_intro_requests(status=status_filter)
    return {"count": len(leads), "leads": leads}


@router.patch("/leads/{request_id}")
@limiter.limit("30/minute")
def patch_lead(
    request: Request,
    request_id: str,
    payload: LeadStatusUpdate,
) -> dict[str, Any]:
    """Update lead triage status: pending | contacted | closed."""
    try:
        row = update_agent_intro_status(
            request_id,
            status=payload.status,
            admin_note=payload.admin_note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{request_id}' not found.",
        )
    return {"status": "updated", "lead": row}


@router.get("/mandis")
@limiter.limit("30/minute")
def get_mandis(request: Request, db: DbSession) -> dict[str, Any]:
    """List mandis with curated agent counts for the admin editor."""
    mandis = list(db.scalars(select(Mandi).order_by(Mandi.state, Mandi.name)).all())
    return {
        "count": len(mandis),
        "mandis": [_serialize_mandi(m) for m in mandis],
    }


@router.put("/mandis/{mandi_id}/agents")
@limiter.limit("20/minute")
def put_mandi_agents(
    request: Request,
    mandi_id: int,
    payload: MandiAgentsUpdate,
    db: DbSession,
) -> dict[str, Any]:
    """
    Replace curated commission agents for one mandi.

    Agents are stamped with verified_at so live routes can distinguish them
    from seed demo placeholders.
    """
    mandi = db.get(Mandi, mandi_id)
    if mandi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandi id {mandi_id} not found.",
        )

    stamp = datetime.now(timezone.utc).isoformat()
    curated = [
        {
            "name": agent.name.strip(),
            "phone": agent.phone,
            "license_id": agent.license_id.strip(),
            "notes": agent.notes.strip(),
            "verified_at": stamp,
            "source": "admin_curated",
        }
        for agent in payload.agents
    ]
    mandi.verified_agents = curated
    db.commit()
    db.refresh(mandi)

    return {
        "status": "updated",
        "mandi": _serialize_mandi(mandi),
    }
