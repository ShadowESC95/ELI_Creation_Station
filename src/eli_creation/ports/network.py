# Reused from ELI_Legal: src/eli_legal/ports/network.py @ 3b05ccd88f. Do not edit here: change it in ELI_Legal and run scripts/sync_reused.py.
from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol


class NetworkPort(Protocol):
    def allow(self, *, host: str, reason: str) -> AbstractContextManager[None]: ...
