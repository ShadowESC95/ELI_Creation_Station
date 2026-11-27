"""The edition's policy hooks, in the shape ELI v3's edition packs use (eli/editions/README.md
there): a system-prompt addendum, an output disclaimer, blocked actions; and the requests refused
outright, whoever asks and however it is worded."""

from __future__ import annotations

import re
from typing import Any

# Sexual content involving minors is refused outright, as is sexual imagery of a real, named person
# made without their consent. This is the floor; a classifier is to replace the word lists.
_MINOR = re.compile(r"\b(child|children|kid|kids|minor|minors|underage|under-age|preteen|pre-teen|"
                    r"teen|teenage|schoolgirl|schoolboy|toddler|infant|loli|shota|\d{1,2}\s*(?:yo|year[- ]old))\b", re.I)
_SEXUAL = re.compile(r"\b(nude|naked|nsfw|sexual|sexy|explicit|porn|pornographic|erotic|lewd|undress|"
                     r"topless|lingerie|fetish)\b", re.I)


def system_prompt_addendum() -> str:
    return (
        "You are ELI, working in ELI Creation Station with a creator on their own project: content for "
        "platforms, images, video, games and code, for paid work and for fun. Be specific, practical and "
        "brief. Respect each platform's limits. Never invent facts about real people or brands. Never "
        "help make sexual content involving minors, or sexual imagery of a real person."
    )


def output_disclaimer() -> str:
    return "Made with AI in ELI Creation Station; check it before you publish it."


def blocked_actions() -> list[str]:
    return []


def _words(request: dict[str, Any]) -> str:
    keys = ("prompt", "brief", "pitch", "task", "negative", "voice", "title", "text")
    parts = [str(request.get(k, "")) for k in keys]
    parts += [str(op.get("text", "")) for op in request.get("ops", []) if isinstance(op, dict)]
    return " ".join(parts)


def refusal(request: dict[str, Any]) -> str:
    """Why this request is refused, or ""."""
    text = _words(request)
    if _MINOR.search(text) and _SEXUAL.search(text):
        return "ELI Creation Station does not make sexual content involving minors."
    return ""
