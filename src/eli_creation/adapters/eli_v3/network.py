# Reused from ELI_Legal: src/eli_legal/adapters/eli_v3/network.py @ 2abede02bc. Do not edit here: change it in ELI_Legal and run scripts/sync_reused.py.
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from eli_creation.adapters.eli_v3.compat import import_attr
from eli_creation.adapters.local.network import NetworkGuard


class EliV3Network:
    """Both gates must open: ELI Creation Station's per-host window and the host's own network gate.

    ELI Creation Station's guard decides *whether* a host is approved. The host's gate is opened only for
    the same scope, so being hosted never widens what the legal runtime may reach, and the
    host's toggles alone (including any full-control mode) never open a legal source.
    """

    def __init__(self, guard: NetworkGuard) -> None:
        self.guard = guard

    @contextmanager
    def allow(self, *, host: str, reason: str) -> Iterator[None]:
        allow_network = import_attr("eli.core.netguard", "allow_network")
        with self.guard.allow(host=host, reason=reason):
            with allow_network(f"ELI Creation Station approved source {host}: {reason}"):
                yield
