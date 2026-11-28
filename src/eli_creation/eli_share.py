"""What Creation Station tells ELI v3 of the work done here, when ELI v3 runs on this machine, so
ELI knows it on every surface ("what did I make yesterday?", "what is Northwind's brand voice?").

Creation Station is complete without ELI v3: nothing here is needed, nothing waits for it, and a
missing or older ELI v3 (one without the shared store) is simply not told. ELI v3 keeps what it is
told in Creation Station's own database there, which the person can read and forget
(ELI v3: eli/bundles/shared_memory.py, /v1/bundles/creation/shared). Settings → share_with_eli_v3
turns it off.

    work(studio, job)                       something was made: what, in which studio, for which project
    preference(studio, key, title, text)    something kept up to date there: a brand kit
"""

from __future__ import annotations

import threading
from typing import Any

BUNDLE = "creation"
KINDS = {"image": "a picture", "video": "a film", "audio": "a sound", "post": "posts", "game": "a game",
         "code": "code", "note": "captions"}


def _send(payload: dict[str, Any]) -> None:
    from eli_creation import eli_link

    link = eli_link.find()
    if link is None:
        return
    try:
        link.json(f"/v1/bundles/{BUNDLE}/shared", payload, timeout=10)
    except Exception:
        pass  # an ELI v3 without the shared store, or one that is busy: Creation Station goes on


def _later(payload: dict[str, Any]) -> None:
    threading.Thread(target=_send, args=(payload,), name="eli-creation-share", daemon=True).start()


def describe(job: Any) -> dict[str, Any] | None:
    """The record of a finished job, or None when it made nothing."""
    assets = list(getattr(job, "assets", None) or [])
    if getattr(job, "state", "") != "done" or not assets:
        return None
    first = assets[0]
    what = KINDS.get(str(first.kind), str(first.kind))
    count = f"{len(assets)} " if len(assets) > 1 and first.kind == "image" else ""
    project = str(job.request.get("project") or first.project or "")
    title = f"Made {count + ('pictures' if count else what)}: {first.title}"[:200]
    text = f"In the {job.tab} studio ({job.engine})" + (f", for the project {project}" if project else "") + "."
    return {"category": "work", "kind": str(first.kind), "title": title, "text": text,
            "refs": {"paths": [str(a.path) for a in assets[:12]], "engine": job.engine, "project": project}}


def work(studio: Any, job: Any) -> None:
    if not getattr(studio.settings, "share_with_eli_v3", True):
        return
    record = describe(job)
    if record is not None:
        _later(record)


def preference(studio: Any, key: str, title: str, text: str) -> None:
    if not getattr(studio.settings, "share_with_eli_v3", True):
        return
    _later({"category": "preferences", "kind": "kept", "key": key, "title": title[:200], "text": text[:2000]})
