"""What the studio's words mean, for the hover boxes the reused widgets show (gui/widgets.py).

The same shape as ELI Legal's ``domain.glossary`` (``explain`` and ``tooltip``), with
Creation Station's terms.
"""

from __future__ import annotations

TERMS: dict[str, str] = {
    "main model": "The one language model that stays loaded while Creation Station runs. It writes, "
    "plans, codes and talks with you. Opened by ELI v3, it is ELI v3's own model.",
    "specialist": "A model for one kind of work (images, video, music, 3D, upscaling, reading the "
    "screen). It is loaded when a job needs it and unloaded when it has been idle.",
    "tier": "What this machine can run, from T0 (processor only) to T4 (workstation). A feature "
    "this machine cannot run is shown greyed, with the reason.",
    "licence class": "What a model's licence allows: permissive models can be used for paid work; "
    "non-commercial, custom and territory-limited ones carry their limits onto what they make.",
    "provenance": "The record of how an asset was made: the models and their licences, the request, "
    "the seed, the assets it came from. It is kept in the library and in a tamper-evident ledger.",
    "marking": "The machine-readable note inside a file that says it was made by AI. It is always "
    "written; a visible label is your choice.",
    "project": "A piece of work: a client job, a channel, a game. Its brief, assets and ELI's notes "
    "on it are kept together.",
    "companion": "ELI in the studio: it follows the project you are working on, with your "
    "permission, and offers what it notices; it can ask to pause and talk it through.",
}
_KEYS = {k.lower(): k for k in TERMS}


def explain(word: str) -> str:
    text = (word or "").strip().strip(" :?").lower()
    if text in _KEYS:
        return TERMS[_KEYS[text]]
    singular = text[:-1] if text.endswith("s") else text
    return TERMS.get(_KEYS.get(singular, ""), "")


def tooltip(word: str, extra: str = "") -> str:
    said = explain(word) or extra
    if not said:
        return ""
    if extra and extra != said:
        said = f"{said}<br><br>{extra}"
    return f"<p style='white-space:pre-wrap; max-width: 420px'>{said}</p>"
