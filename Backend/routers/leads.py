"""Lead capture — farmer requests for commission-agent introductions."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from rate_limit import limiter
from security import require_api_key
from services.agent_intro_store import save_agent_intro_request

router = APIRouter(
    tags=["leads"],
    dependencies=[Depends(require_api_key)],
)

_PHONE_DIGITS = re.compile(r"\D+")


class AgentIntroRequest(BaseModel):
    farmer_name: str = Field(..., min_length=2, max_length=128)
    farmer_phone: str = Field(..., min_length=10, max_length=20)
    crop_name: str = Field(..., min_length=1, max_length=64)
    source_mandi: str = Field(..., min_length=1, max_length=128)
    destination_mandi: str = Field(..., min_length=1, max_length=128)
    destination_state: str = Field(..., min_length=1, max_length=64)
    notes: str = Field(default="", max_length=500)

    @field_validator("farmer_phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = _PHONE_DIGITS.sub("", value or "")
        if len(digits) < 10:
            raise ValueError("farmer_phone must contain at least 10 digits.")
        # Keep last 10 digits for Indian mobiles with +91 prefix.
        return digits[-10:]


@router.post("/agent-intro")
@limiter.limit("5/minute")
def request_agent_intro(
    request: Request,
    payload: AgentIntroRequest,
) -> dict[str, str]:
    """
    Capture a farmer lead when no verified commission agent is available yet.

    Requests are stored locally in ``Backend/data/agent_intro_requests.jsonl``
    for manual follow-up / partner onboarding — not auto-dialed.
    """
    try:
        record = save_agent_intro_request(payload.model_dump())
        return {
            "status": "received",
            "request_id": record["id"],
            "message": (
                "Request saved. A MandiSync partner will follow up when a "
                "verified commission agent is available at this yard."
            ),
        }
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save agent intro request: {exc}",
        ) from exc
