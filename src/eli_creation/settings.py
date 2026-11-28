"""The settings a person changes, kept as one JSON file in the data folder.

Unknown keys (written by a newer release) are kept when the file is saved again, so going back a
version never loses a setting.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

# Where the main model comes from.
MAIN_SOURCES = ("auto", "eli_v3", "gguf", "openai", "none")


@dataclass
class Settings:
    # The main model: the one model that stays loaded. "auto" is ELI v3's when ELI v3 opened
    # Creation Station, otherwise the GGUF file below when one is set, otherwise none.
    main_model_source: str = "auto"
    main_model_path: str = ""
    # An OpenAI-compatible server on this machine (Ollama, LM Studio, llama.cpp's server).
    main_model_url: str = "http://127.0.0.1:11434/v1"
    main_model_name: str = ""
    main_context: int = 8192
    # The main model's licence (an SPDX id such as Apache-2.0), as its card states it. A model of
    # your own whose licence is not given makes outputs marked "licence unknown".
    main_model_licence: str = ""
    # A server on another machine is refused unless this is on: prompts would leave the machine.
    allow_remote_main_model: bool = False

    # Specialist models: loaded for a job, unloaded after this many idle seconds (0: at once).
    idle_unload_seconds: int = 120
    # How many specialists may be loaded at the same time. 0: decided by the machine's tier.
    max_resident_specialists: int = 0
    # Off: the main model always stays loaded, and a specialist that cannot fit beside it is
    # refused with the reason. On: on a machine with too little memory for both, the main model
    # steps aside for that one job and is loaded again straight after.
    # the main model steps aside for a job that cannot fit beside it, and comes back after
    allow_main_swap: bool = True
    # Memory kept free on every device beyond what the models are expected to take.
    memory_reserve_mb: int = 768

    # The machine-readable AI-content marking is always written. This adds a visible label.
    visible_ai_label: bool = False

    # ELI in the studio (companion/): off | quiet | helpful | active. What it may look at is the
    # person's choice, each off until turned on, and never more than the project's own folder.
    companion_level: str = "helpful"
    companion_watch_project: bool = False
    companion_read_screen: bool = False
    # The least time between two things ELI raises unasked, in minutes.
    companion_min_gap_minutes: int = 20
    # When ELI v3 runs on this machine, tell it what is made here and keep the brand kits there,
    # so ELI knows them everywhere (eli_share.py). Off: ELI v3 is told nothing.
    share_with_eli_v3: bool = True
    theme: str = "dark"
    last_tab: str = "socials"

    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, path: Path) -> Settings:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = {f.name for f in fields(cls)} - {"extra"}
        values: dict[str, Any] = {}
        defaults = cls()
        for key in known:
            if key in raw:
                wanted = type(getattr(defaults, key))
                value = raw[key]
                if wanted is bool:
                    values[key] = bool(value)
                elif wanted is int:
                    try:
                        values[key] = int(value)
                    except (TypeError, ValueError):
                        continue
                else:
                    values[key] = str(value)
        settings = cls(**values)
        if settings.main_model_source not in MAIN_SOURCES:
            settings.main_model_source = "auto"
        settings.extra = {k: v for k, v in raw.items() if k not in known}
        return settings

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(self).items() if k != "extra"}
        data = {**self.extra, **data}
        # written beside the file and moved over it, so a crash never leaves half a file
        fd, tmp = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
