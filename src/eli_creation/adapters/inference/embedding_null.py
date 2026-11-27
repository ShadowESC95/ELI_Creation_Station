# Reused from ELI_Legal: src/eli_legal/adapters/inference/embedding_null.py @ 3b05ccd88f. Do not edit here: change it in ELI_Legal and run scripts/sync_reused.py.
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from eli_creation.domain.errors import InferenceUnavailable
from eli_creation.ports.embedding import Kind


@dataclass
class NullEmbedder:
    """No embedding model: research ranks passages by their words alone."""

    reason: str = "no embedding model is set up"
    model_id: str = "none"
    available: bool = False

    def embed(self, texts: Sequence[str], *, kind: Kind) -> list[list[float]]:
        raise InferenceUnavailable(f"searching by meaning is off: {self.reason}")
