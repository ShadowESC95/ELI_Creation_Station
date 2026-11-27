"""How each state reads at a glance: its tone, which the reused theme (gui/theme.py) colours.

ELI Legal's own ``domain.plain`` holds its legal states; this holds Creation Station's, in the
same shape (``TONE`` and ``tone``), so the theme is shared unchanged.
"""

from __future__ import annotations

_TONES: dict[str, set[str]] = {
    "good": {"ready", "done", "granted", "licensed", "available", "runs_here", "permissive", "on"},
    "warn": {"trial", "slow", "planned", "waiting", "queued", "custom", "territory", "copyleft",
             "suggestion", "paused"},
    "bad": {"failed", "refused", "unavailable", "not_licensed", "non-commercial", "unknown", "cancelled"},
    "active": {"loading", "busy", "running", "unloading", "listening", "watching", "discussing"},
    "idle": {"unloaded", "off", "idle", "none"},
}
TONE = {code: tone for tone, codes in _TONES.items() for code in codes}


def tone(value: object) -> str:
    """good | warn | bad | active | idle | "" for a state code."""
    raw = str(getattr(value, "value", value) or "").strip().lower().replace(" ", "_")
    return TONE.get(raw, "")
