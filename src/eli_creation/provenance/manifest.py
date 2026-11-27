"""The manifest written beside every asset."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from eli_creation import TITLE, __version__
from eli_creation.models import licences

SCHEMA = "eli-creation/manifest/1"

# IPTC NewsCodes for digital source type (https://cv.iptc.org/newscodes/digitalsourcetype/).
IPTC_BASE = "http://cv.iptc.org/newscodes/digitalsourcetype/"
TRAINED = "trainedAlgorithmicMedia"  # made by a trained model
COMPOSITE_TRAINED = "compositeWithTrainedAlgorithmicMedia"  # an edit that includes a model's output
ALGORITHMIC = "algorithmicMedia"  # made by an algorithm with no trained model (the procedural renderer)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build(
    *,
    kind: str,
    engine: str,
    models: list[dict[str, Any]],
    request: dict[str, Any],
    digital_source_type: str | None,
    sources: list[str] | None = None,
    edits: list[dict[str, Any]] | None = None,
    source_classes: list[str] | None = None,
    project: str = "",
) -> dict[str, Any]:
    """``models`` are the catalogue entries (or descriptions) of every model the asset passed
    through; ``source_classes`` the licence classes of the assets it was made from."""
    classes = [str(m.get("licence_class") or licences.licence_class(str(m.get("licence", "")))) for m in models]
    classes += list(source_classes or [])
    cls = licences.output_class(classes) if classes else "permissive"
    return {
        "schema": SCHEMA,
        "kind": kind,
        "project": project,
        "created": now(),
        "generator": {"name": TITLE, "version": __version__, "engine": engine},
        "models": [
            {
                "id": m.get("id", ""),
                "title": m.get("title", ""),
                "licence": m.get("licence", ""),
                "licence_class": m.get("licence_class") or licences.licence_class(str(m.get("licence", ""))),
                "revision": m.get("revision", ""),
            }
            for m in models
        ],
        "request": request,
        "digital_source_type": (IPTC_BASE + digital_source_type) if digital_source_type else None,
        "ai_generated": digital_source_type in (TRAINED, COMPOSITE_TRAINED),
        "sources": list(sources or []),
        "edits": list(edits or []),
        "output_licence_class": cls,
        "output_warning": licences.output_warning(cls),
    }


def digest(manifest: dict[str, Any]) -> str:
    body = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()
