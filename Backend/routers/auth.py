"""Login and session endpoints."""

from __future__ import annotations

from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db as get_db_context
from rate_limit import limiter
from security import require_user
from services.accounts import Principal, authenticate, issue_token, register_user

router = APIRouter(tags=["auth"])


def get_db() -> Generator[Session, None, None]:
    with get_db_context() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)


@router.post("/register")
@limiter.limit("6/minute")
def register(request: Request, db: DbSession, body: RegisterRequest) -> dict[str, str]:
    try:
        principal = register_user(db, body.username, body.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    token, expires = issue_token(principal)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": principal.username,
        "role": principal.role,
        "expires_at": expires.isoformat(),
    }


@router.post("/login")
@limiter.limit("8/minute")
def login(request: Request, db: DbSession, body: LoginRequest) -> dict[str, str]:
    principal = authenticate(db, body.username, body.password)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    token, expires = issue_token(principal)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": principal.username,
        "role": principal.role,
        "expires_at": expires.isoformat(),
    }


@router.get("/me")
def me(principal: Annotated[Principal, Depends(require_user)]) -> dict[str, str]:
    return {"username": principal.username, "role": principal.role}
