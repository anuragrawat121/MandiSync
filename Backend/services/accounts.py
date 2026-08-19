"""Password hashing, JWT sessions, and bootstrap accounts."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import AppUser

PBKDF2_ROUNDS = 200_000
TOKEN_HOURS = 12
ROLE_USER = "user"
ROLE_ADMIN = "admin"
USERNAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,31}$")
RESERVED_USERNAMES = {"admin", "api-key", "root", "system"}


@dataclass(frozen=True)
class Principal:
    username: str
    role: str


def _jwt_secret() -> str:
    secret = (os.getenv("JWT_SECRET") or os.getenv("API_KEY") or "").strip()
    if not secret:
        secret = "mandisync-dev-jwt-secret"
    return secret


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ROUNDS,
    )
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, rounds_s, salt_hex, digest_hex = stored.split("$", 3)
        rounds = int(rounds_s)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            rounds,
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def issue_token(principal: Principal) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    token = jwt.encode(
        {
            "sub": principal.username,
            "role": principal.role,
            "exp": expires,
        },
        _jwt_secret(),
        algorithm="HS256",
    )
    return token, expires


def decode_token(token: str) -> Principal:
    payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    username = str(payload.get("sub") or "").strip()
    role = str(payload.get("role") or "").strip()
    if not username or role not in {ROLE_USER, ROLE_ADMIN}:
        raise jwt.InvalidTokenError("Invalid session payload.")
    return Principal(username=username, role=role)


def _upsert_account(
    db: Session,
    *,
    username: str,
    password: str,
    role: str,
) -> None:
    username = username.strip()
    if not username or not password:
        return
    row = db.execute(
        select(AppUser).where(AppUser.username == username)
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        db.add(
            AppUser(
                username=username,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
                created_at=now,
            )
        )
        print(f"[accounts] created {role} account {username!r}", flush=True)
        return
    row.password_hash = hash_password(password)
    row.role = role
    row.is_active = True
    print(f"[accounts] updated {role} account {username!r}", flush=True)


def seed_accounts(db: Session) -> None:
    """Create/update farmer and admin logins from env (defaults for first boot)."""
    _upsert_account(
        db,
        username=os.getenv("APP_USER_USERNAME", "farmer"),
        password=os.getenv("APP_USER_PASSWORD", "farmer123"),
        role=ROLE_USER,
    )
    _upsert_account(
        db,
        username=os.getenv("APP_ADMIN_USERNAME", "admin"),
        password=os.getenv("APP_ADMIN_PASSWORD", "admin123"),
        role=ROLE_ADMIN,
    )
    db.commit()


def register_user(db: Session, username: str, password: str) -> Principal:
    """Create a farmer (user) account. Never grants admin."""
    username = (username or "").strip()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username must start with a letter and be 3–32 letters, numbers, or underscores."
        )
    if username.lower() in RESERVED_USERNAMES:
        raise ValueError("That username is reserved. Choose another.")
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters.")

    existing = db.execute(
        select(AppUser).where(func.lower(AppUser.username) == username.lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise LookupError("That username is already registered.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(
        AppUser(
            username=username,
            password_hash=hash_password(password),
            role=ROLE_USER,
            is_active=True,
            created_at=now,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise LookupError("That username is already registered.") from exc
    return Principal(username=username, role=ROLE_USER)


def authenticate(db: Session, username: str, password: str) -> Principal | None:
    username = (username or "").strip()
    if not username or not password:
        return None
    row = db.execute(
        select(AppUser).where(AppUser.username == username)
    ).scalar_one_or_none()
    if row is None or not row.is_active:
        return None
    if not verify_password(password, str(row.password_hash)):
        return None
    role = str(row.role)
    if role not in {ROLE_USER, ROLE_ADMIN}:
        return None
    return Principal(username=str(row.username), role=role)
