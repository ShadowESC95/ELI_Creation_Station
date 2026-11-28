"""The library: every asset Creation Station made, findable by project, kind and when.

An asset is a normal file in the outputs folder, named so a person recognises it, that any other
program can open. Beside it is its manifest (``<file>.manifest.json``). This index (SQLite, in the
library folder) holds where each one is, its SHA-256 and what it was made with; the provenance
ledger holds the tamper-evident record of the same.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eli_creation.layout import Layout
from eli_creation.provenance import manifest as manifests
from eli_creation.provenance.ledger import ProvenanceLedger

KINDS = ("post", "image", "video", "audio", "game", "code", "edit", "note")


@dataclass(frozen=True)
class Asset:
    sha256: str
    kind: str
    path: Path
    project: str
    title: str
    created: str
    engine: str
    licence_class: str
    ai_generated: bool

    @property
    def manifest_path(self) -> Path:
        return self.path.with_name(self.path.name + ".manifest.json")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def slug(text: str, fallback: str = "asset", limit: int = 48) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return value[:limit].strip("-") or fallback


class Library:
    def __init__(self, layout: Layout, ledger: ProvenanceLedger) -> None:
        self.layout = layout
        self.ledger = ledger
        layout.library.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(layout.library / "index.sqlite3", check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS assets (sha256 TEXT, kind TEXT, path TEXT PRIMARY KEY, project TEXT,"
                " title TEXT, created TEXT, engine TEXT, licence_class TEXT, ai_generated INTEGER)"
            )
            self._db.commit()

    def folder(self, kind: str, project: str = "") -> Path:
        path = self.layout.outputs / (slug(project, "studio") if project else "studio") / kind
        path.mkdir(parents=True, exist_ok=True)
        return path

    def add(self, path: Path, *, manifest: dict[str, Any], title: str = "", job: str | None = None) -> Asset:
        """Index a file already written in the outputs folder, write its manifest beside it, and
        record it in the ledger."""
        path = Path(path)
        digest = sha256_of(path)
        asset = Asset(
            sha256=digest,
            kind=str(manifest.get("kind", "note")),
            path=path,
            project=str(manifest.get("project", "")),
            title=title or path.stem,
            created=str(manifest.get("created", manifests.now())),
            engine=str(manifest.get("generator", {}).get("engine", "")),
            licence_class=str(manifest.get("output_licence_class", "permissive")),
            ai_generated=bool(manifest.get("ai_generated")),
        )
        record = {**manifest, "file": path.name, "sha256": digest}
        asset.manifest_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO assets VALUES (?,?,?,?,?,?,?,?,?)",
                (asset.sha256, asset.kind, str(path), asset.project, asset.title, asset.created, asset.engine,
                 asset.licence_class, int(asset.ai_generated)),
            )
            self._db.commit()
        self.ledger.record(
            "asset.created",
            subject=digest,
            project=asset.project,
            job=job,
            model=",".join(m.get("id", "") for m in manifest.get("models", [])) or None,
            payload={
                "kind": asset.kind,
                "engine": asset.engine,
                "manifest_sha256": manifests.digest(record),
                "licence_class": asset.licence_class,
                "ai_generated": asset.ai_generated,
            },
            output_hash=digest,
        )
        return asset

    def recent(self, *, kind: str = "", project: str = "", limit: int = 50) -> list[Asset]:
        query = "SELECT * FROM assets"
        clauses: list[str] = []
        args: list[Any] = []
        if kind:
            clauses.append("kind = ?")
            args.append(kind)
        if project:
            clauses.append("project = ?")
            args.append(project)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._db.execute(query, args).fetchall()
        return [Asset(r[0], r[1], Path(r[2]), r[3], r[4], r[5], r[6], r[7], bool(r[8])) for r in rows]

    def projects(self) -> list[str]:
        """Every project something was made for, most recently used first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT project, MAX(created) AS last FROM assets WHERE project != '' GROUP BY project"
                " ORDER BY last DESC"
            ).fetchall()
        return [str(r[0]) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._db.close()
