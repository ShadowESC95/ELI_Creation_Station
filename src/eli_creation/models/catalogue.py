"""The models Creation Station knows, read from catalogue.json beside this file."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from eli_creation.models import licences
from eli_creation.tiers import Machine, Need, can_run


@dataclass(frozen=True)
class ModelSpec:
    id: str
    title: str
    role: str  # main | specialist
    tasks: tuple[str, ...]
    licence: str
    verified: bool = False
    source: str = ""
    revision: str = ""
    format: str = ""  # gguf | diffusers | sdcpp | onnx | torch
    size_mb: int = 0
    memory_mb: int = 0  # accelerator memory it takes once loaded
    ram_mb: int = 0  # system memory it takes on the processor
    min_tier: str = "T0"
    backends: tuple[str, ...] = ()
    cpu_ok: bool = False
    adapter: str = ""  # "module:Class" the worker loads it with
    runtime: str = "same"  # same | torch | sdcpp | onnx: the worker environment it runs in
    status: str = "available"  # available | planned
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def licence_class(self) -> str:
        return licences.licence_class(self.licence)

    @property
    def need(self) -> Need:
        return Need(
            min_tier=self.min_tier,
            accelerator_mb=self.memory_mb,
            backends=self.backends,
            ram_mb=0,
            cpu_ok=self.cpu_ok,
        )

    @property
    def planned(self) -> bool:
        return self.status == "planned" or not self.adapter and self.role == "specialist"

    def may_fetch(self) -> tuple[bool, str]:
        return licences.may_fetch(self.licence, verified=self.verified, revision=self.revision)

    def runs_here(self, machine: Machine) -> tuple[bool, str]:
        return can_run(self.need, machine)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "role": self.role,
            "tasks": list(self.tasks),
            "licence": self.licence,
            "licence_class": self.licence_class,
            "verified": self.verified,
            "source": self.source,
            "revision": self.revision,
            "format": self.format,
            "size_mb": self.size_mb,
            "memory_mb": self.memory_mb,
            "ram_mb": self.ram_mb,
            "min_tier": self.min_tier,
            "backends": list(self.backends),
            "cpu_ok": self.cpu_ok,
            "adapter": self.adapter,
            "runtime": self.runtime,
            "status": "planned" if self.planned else self.status,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ModelSpec:
        known = {f for f in cls.__dataclass_fields__ if f != "extra"}
        values = {k: raw[k] for k in known if k in raw}
        for key in ("tasks", "backends"):
            if key in values:
                values[key] = tuple(values[key])
        return cls(**values, extra={k: v for k, v in raw.items() if k not in known})


@dataclass(frozen=True)
class Excluded:
    match: str
    licence: str
    cls: str
    why: str


@dataclass(frozen=True)
class Catalogue:
    models: tuple[ModelSpec, ...]
    excluded: tuple[Excluded, ...] = ()

    def get(self, model_id: str) -> ModelSpec:
        for spec in self.models:
            if spec.id == model_id:
                return spec
        raise KeyError(model_id)

    def for_task(self, task: str, *, role: str = "specialist") -> list[ModelSpec]:
        return [m for m in self.models if task in m.tasks and m.role == role]

    def best_for(self, task: str, machine: Machine) -> tuple[ModelSpec | None, str]:
        """The first model for this task (catalogue order is preference) this machine can run,
        or None with the reason the nearest one cannot."""
        candidates = [m for m in self.for_task(task) if not m.planned]
        if not candidates:
            planned = self.for_task(task)
            if planned:
                return None, f"{planned[0].title} is planned for a later release"
            return None, f"no model for {task} is known"
        reasons = []
        for spec in candidates:
            ok, why = spec.runs_here(machine)
            if ok:
                return spec, why
            reasons.append(f"{spec.title}: {why}")
        return None, "; ".join(reasons)

    def excluded_reason(self, source: str) -> str:
        """Why a model at this source is never fetched, or ""."""
        for ex in self.excluded:
            if ex.match.lower() in (source or "").lower():
                return f"{ex.licence} ({ex.cls}): {ex.why}"
        return ""


def load(path: Path | None = None) -> Catalogue:
    if path is None:
        text = resources.files("eli_creation.models").joinpath("catalogue.json").read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    raw = json.loads(text)
    models = tuple(ModelSpec.from_dict(m) for m in raw.get("models", []))
    excluded = tuple(
        Excluded(str(e["match"]), str(e.get("licence", "")), str(e.get("class", "")), str(e.get("why", "")))
        for e in raw.get("excluded", [])
    )
    return Catalogue(models, excluded)
