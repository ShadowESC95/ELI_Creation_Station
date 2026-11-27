# Adapted from ELI_Legal: src/eli_legal/domain/models.py @ 3b05ccd88f. Only the record the audit ledger writes, and the two helpers it uses, taken word for word; ELI Legal's matter, finding and authority models are not needed here.
"""The audit record ELI Legal's ledger (adapters/local/hmac_audit.py) writes.

In Creation Station ``matter_id`` holds the project an event belongs to, and ``subject_id`` the
asset (its SHA-256) or the model it concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class AuditEvent:
    event_type: str
    actor_id: str
    matter_id: str
    run_id: str | None
    action: str
    subject_id: str
    outcome: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
    event_id: str = field(default_factory=lambda: new_id("evt"))
    object_type: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    tool_id: str | None = None
    source_ids: list[str] = field(default_factory=list)
    input_hash: str | None = None
    output_hash: str | None = None
    verification_status: str | None = None
    reviewer_id: str | None = None
