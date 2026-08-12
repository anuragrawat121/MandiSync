"""Append-only + rewrite store for farmer agent-intro lead requests."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUESTS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "agent_intro_requests.jsonl"
)

VALID_STATUSES = frozenset({"pending", "contacted", "closed"})


def save_agent_intro_request(payload: dict[str, object]) -> dict[str, Any]:
    """Persist one lead request; returns the saved record with id + timestamp."""
    REQUESTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        **payload,
    }
    # Ensure status is always set even if payload tried to override oddly.
    if record.get("status") not in VALID_STATUSES:
        record["status"] = "pending"
    with REQUESTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def list_agent_intro_requests(*, status: str | None = None) -> list[dict[str, Any]]:
    """Newest-first list of lead requests. Optional status filter."""
    if not REQUESTS_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with REQUESTS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            row.setdefault("status", "pending")
            if status and row.get("status") != status:
                continue
            rows.append(row)
    rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return rows


def update_agent_intro_status(
    request_id: str,
    *,
    status: str,
    admin_note: str = "",
) -> dict[str, Any] | None:
    """Rewrite the JSONL file with one lead's status updated. Returns the row or None."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")

    rows = list_agent_intro_requests()
    found: dict[str, Any] | None = None
    updated: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("id")) == request_id:
            row = {
                **row,
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if admin_note.strip():
                row["admin_note"] = admin_note.strip()
            found = row
        updated.append(row)

    if found is None:
        return None

    REQUESTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Keep chronological append order (oldest first) after rewrite.
    updated.sort(key=lambda item: str(item.get("created_at") or ""))
    with REQUESTS_PATH.open("w", encoding="utf-8") as handle:
        for row in updated:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return found
