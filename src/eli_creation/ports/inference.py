# Reused from ELI_Legal: src/eli_legal/ports/inference.py @ 2abede02bc. Do not edit here: change it in ELI_Legal and run scripts/sync_reused.py.
from __future__ import annotations

from typing import Protocol


class InferencePort(Protocol):
    model_id: str
    available: bool

    def generate(
        self, *, system: str, prompt: str, max_tokens: int = 2048, json_mode: bool = False
    ) -> str: ...
