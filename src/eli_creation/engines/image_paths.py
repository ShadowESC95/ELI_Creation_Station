"""Where ELI v3's image engine (engines/image_engine, reused) writes, inside Creation Station's
own data folder. It stands in for ELI v3's ``eli/tools/image_engine/runtime_paths.py``, which
places the same folders inside ELI v3's tree."""

from __future__ import annotations

from pathlib import Path

from eli_creation.layout import Layout, layout

_active: Layout | None = None


def use(where: Layout) -> None:
    """The studio's own folders: a studio made for a test or the self-test keeps its images there."""
    global _active
    _active = where


def _root() -> Layout:
    return _active or layout()


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_outputs_dir() -> Path:
    return _ensure(_root().outputs / "images")


def image_logs_dir() -> Path:
    return _ensure(_root().logs / "images")


def image_jobs_dir() -> Path:
    return _ensure(_root().jobs / "images")


def image_index_db() -> Path:
    return _ensure(_root().library) / "image_memory.sqlite3"
