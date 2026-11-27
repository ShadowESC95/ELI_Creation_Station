"""The provenance ledger: ELI Legal's tamper-evident audit ledger (reused,
adapters/local/hmac_audit.py), holding one entry per asset made, edit, export and model load.

It records identifiers and digests (an asset's SHA-256, its manifest's SHA-256, the engine, the
models and their licence classes), never the words of a prompt, a post or a script: the ledger
refuses a payload carrying them, as ELI Legal's does.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from eli_creation.adapters.local.hmac_audit import HmacAuditLedger
from eli_creation.domain.models import AuditEvent
from eli_creation.layout import Layout
from eli_creation.security.files import private_dir


def _ensure_key(path: Path) -> None:
    """Make the ledger's key on first use, readable only by this account (as ELI Legal's first run)."""
    if path.exists():
        return
    private_dir(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(secrets.token_hex(32))


class ProvenanceLedger:
    def __init__(self, layout: Layout) -> None:
        key = layout.secrets / "provenance.key"
        _ensure_key(key)
        self.chain = HmacAuditLedger(layout.provenance / "ledger.sqlite3", key)

    def record(
        self,
        action: str,
        *,
        subject: str,
        project: str = "",
        job: str | None = None,
        outcome: str = "done",
        model: str | None = None,
        payload: dict[str, Any] | None = None,
        output_hash: str | None = None,
    ) -> int:
        event = AuditEvent(
            event_type=f"creation.{action}",
            actor_id="system",
            matter_id=project or "studio",
            run_id=job,
            action=action,
            subject_id=subject,
            outcome=outcome,
            payload=dict(payload or {}),
            model_id=model,
            output_hash=output_hash,
        )
        return self.chain.append(event)

    def verify(self) -> tuple[bool, str]:
        report = self.chain.report()
        return bool(report.ok), report.error

    def count(self) -> int:
        return int(self.chain.count())
