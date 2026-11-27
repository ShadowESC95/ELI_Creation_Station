"""How long specialist models stay loaded, and how many at once, for this machine."""

from __future__ import annotations

from dataclasses import dataclass

from eli_creation.settings import Settings

# How many specialists may be loaded together, by tier, when the person has not said.
DEFAULT_MAX_RESIDENT = {"T0": 1, "T1": 1, "T2": 1, "T3": 2, "T4": 3}


@dataclass(frozen=True)
class Policy:
    idle_unload_seconds: float = 120.0  # 0: unloaded as soon as its job ends
    max_resident_specialists: int = 1
    allow_main_swap: bool = False
    reserve_mb: int = 768

    @classmethod
    def from_settings(cls, settings: Settings, tier: str) -> Policy:
        most = settings.max_resident_specialists or DEFAULT_MAX_RESIDENT.get(tier, 1)
        return cls(
            idle_unload_seconds=max(0.0, float(settings.idle_unload_seconds)),
            max_resident_specialists=max(1, int(most)),
            allow_main_swap=bool(settings.allow_main_swap),
            reserve_mb=max(0, int(settings.memory_reserve_mb)),
        )
