"""Arbitrage API routes — maps HTTP traffic to the optimization service."""

from __future__ import annotations

from typing import Annotated, Any, Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db as get_db_context
from models import CropPrice
from rate_limit import limiter
from security import require_api_key
from services.arbitrage_engine import calculate_crop_arbitrage
from services.gemini_agent import generate_live_briefing

router = APIRouter(
    tags=["arbitrage"],
    dependencies=[Depends(require_api_key)],
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that reuses our database context manager."""
    with get_db_context() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]


class BriefingAgentCard(BaseModel):
    name: str = Field(default="", max_length=128)
    phone: str = Field(default="", max_length=32)
    license_id: str = Field(default="", max_length=64)


class RouteBriefingRequest(BaseModel):
    """Single selected corridor sent from the dashboard for live LLM analysis."""

    crop_name: str = Field(..., min_length=1, max_length=64)
    source_mandi: str = Field(..., min_length=1, max_length=128)
    destination_mandi: str = Field(..., min_length=1, max_length=128)
    source_state: str = Field(..., min_length=1, max_length=64)
    destination_state: str = Field(..., min_length=1, max_length=64)
    source_price_per_quintal: float = Field(..., ge=0, le=1_000_000)
    destination_price_per_quintal: float = Field(..., ge=0, le=1_000_000)
    gross_spread: float | None = Field(default=None, ge=-1_000_000, le=1_000_000)
    distance_km: float = Field(..., ge=0, le=20_000)
    transit_cost: float = Field(..., ge=0, le=1_000_000)
    net_profit: float = Field(..., ge=-1_000_000, le=1_000_000)
    destination_verified_agents: list[BriefingAgentCard] = Field(
        default_factory=list,
        max_length=8,
    )
    agent_name: str | None = Field(default=None, max_length=128)
    price_date: str | None = Field(default=None, max_length=32)


@router.get("/")
@limiter.limit("30/minute")
def get_crop_arbitrage(
    request: Request,
    db: DbSession,
    crop_name: str = Query(..., min_length=1, max_length=64, description="Crop to evaluate, e.g. Onion"),
) -> dict[str, Any]:
    """
    Return profitable mandi-to-mandi arbitrage routes for a crop.

    Each route includes ``destination_verified_agents`` so the UI can show
    actionable commission-agent contact cards at the selling market.

    Example: ``GET /api/arbitrage?crop_name=Onion``
    """
    normalized = crop_name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="crop_name must not be empty.",
        )

    try:
        price_exists = db.scalar(
            select(CropPrice.id).where(CropPrice.crop_name == normalized).limit(1)
        )
        if price_exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No price data found for crop '{normalized}'.",
            )

        result = calculate_crop_arbitrage(db, normalized)
        return {
            "crop_name": normalized,
            "route_count": len(result["routes"]),
            "data_source_used": result["data_source_used"],
            "status": result.get("status", "ok"),
            "message": result.get("message", ""),
            "agents_status": result["agents_status"],
            "max_staleness_days": result.get("max_staleness_days"),
            "routes": result["routes"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate arbitrage for '{normalized}': {exc}",
        ) from exc


@router.post("/briefing")
@limiter.limit("5/minute")
async def get_route_briefing(
    request: Request,
    payload: RouteBriefingRequest,
) -> dict[str, Any]:
    """
    Live Gemini analysis for one selected route.

    Always returns caption + Devanagari speech text. If Gemini fails, the
    original regional simulation templates are used so the UI never crashes.
    """
    try:
        briefing = await generate_live_briefing(payload.model_dump())
        return {
            "crop_name": payload.crop_name,
            "source_mandi": payload.source_mandi,
            "destination_mandi": payload.destination_mandi,
            **briefing,
        }
    except Exception:
        # Last-resort shield — generate_live_briefing already falls back internally.
        from services.gemini_agent import fallback_briefing

        result = fallback_briefing(payload.model_dump())
        result["cached"] = False
        return {
            "crop_name": payload.crop_name,
            "source_mandi": payload.source_mandi,
            "destination_mandi": payload.destination_mandi,
            **result,
        }
