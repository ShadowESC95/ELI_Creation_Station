"""A film or an ad as a project: its plan (goal, look, key moments, next steps), its ingredients
(characters, places, props, references), its scenes in order, the sound under it (narration,
music, effects) and its captions. Kept as one JSON file per project, written whole each time."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STAGES = ("plan", "produce", "review")
INGREDIENT_KINDS = ("character", "location", "object", "prop", "reference")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Grade:
    """The look of a shot: each 0 is as it was; -1…1 either way."""

    warmth: float = 0.0
    light: float = 0.0
    contrast: float = 0.0
    colour: float = 0.0
    mood: float = 0.0  # darker and moodier below 0, brighter and airier above
    vignette: float = 0.0  # 0…1
    grain: float = 0.0  # 0…1
    look: str = "none"  # a named filter (production.grade.LOOKS)

    def is_plain(self) -> bool:
        return self == Grade()


@dataclass
class Scene:
    title: str = ""
    description: str = ""
    image: str = ""  # a picture's path
    camera: str = "push_in"
    seconds: float = 4.0
    transition: str = "crossfade"  # into the next scene
    transition_seconds: float = 0.6
    title_text: str = ""  # words on screen in this scene
    grade: Grade = field(default_factory=Grade)
    id: str = field(default_factory=lambda: _id("scene"))


@dataclass
class Ingredient:
    kind: str = "character"
    name: str = ""
    role: str = ""
    description: str = ""
    image: str = ""
    id: str = field(default_factory=lambda: _id("ing"))


@dataclass
class Clip:
    """A sound on the timeline."""

    kind: str = "music"  # narration | music | sfx
    path: str = ""
    start: float = 0.0
    gain: float = 1.0
    label: str = ""
    text: str = ""  # what narration says
    voice: str = ""
    duration: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    id: str = field(default_factory=lambda: _id("clip"))


@dataclass
class Cue:
    start: float
    end: float
    text: str


@dataclass
class Step:
    text: str
    done: bool = False


@dataclass
class Project:
    title: str = "Untitled film"
    format: str = "youtube"
    stage: str = "plan"
    logline: str = ""
    goal: str = ""
    direction: str = ""
    moments: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    ingredients: list[Ingredient] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)
    cues: list[Cue] = field(default_factory=list)
    captions_on: bool = True
    caption_size: float = 1.0
    duck: float = 0.35  # how far music dips under narration
    library_project: str = ""  # the studio project its outputs are filed under
    template: str = ""
    id: str = field(default_factory=lambda: _id("film"))
    created: str = field(default_factory=_now)
    updated: str = field(default_factory=_now)

    # ── timing ──
    def scene_times(self) -> list[tuple[Scene, float, float]]:
        """Each scene with when it starts and ends; a transition overlaps the next scene's start."""
        out: list[tuple[Scene, float, float]] = []
        t = 0.0
        for n, scene in enumerate(self.scenes):
            start = t
            end = start + max(0.3, scene.seconds)
            out.append((scene, start, end))
            overlap = 0.0
            if n + 1 < len(self.scenes) and scene.transition != "cut":
                overlap = min(scene.transition_seconds, scene.seconds / 2, self.scenes[n + 1].seconds / 2)
            t = end - overlap
        return out

    def length(self) -> float:
        times = self.scene_times()
        picture = times[-1][2] if times else 0.0
        sound = max((c.start + c.duration for c in self.clips if c.kind == "narration"), default=0.0)
        return max(picture, sound)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        def build(kind: Any, raw: Any) -> Any:
            if not isinstance(raw, dict):
                return kind()
            known = {f.name for f in fields(kind)}
            values = {k: v for k, v in raw.items() if k in known}
            if kind is Scene and isinstance(values.get("grade"), dict):
                values["grade"] = build(Grade, values["grade"])
            return kind(**values)

        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        values["scenes"] = [build(Scene, s) for s in data.get("scenes", [])]
        values["ingredients"] = [build(Ingredient, i) for i in data.get("ingredients", [])]
        values["clips"] = [build(Clip, c) for c in data.get("clips", [])]
        values["cues"] = [build(Cue, c) for c in data.get("cues", []) if isinstance(c, dict) and "start" in c]
        values["steps"] = [build(Step, s) for s in data.get("steps", [])]
        values["moments"] = [str(m) for m in data.get("moments", [])]
        return cls(**values)


class ProjectStore:
    """Every film project, one file each, under the studio's projects folder."""

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, project_id: str) -> Path:
        return self.folder / f"{project_id}.film.json"

    def save(self, project: Project) -> Project:
        project.updated = _now()
        data = json.dumps(project.to_dict(), indent=2, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(prefix=".film-", suffix=".json", dir=self.folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data + "\n")
            os.replace(tmp, self.path(project.id))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return project

    def load(self, project_id: str) -> Project:
        return Project.from_dict(json.loads(self.path(project_id).read_text(encoding="utf-8")))

    def all(self) -> list[Project]:
        out = []
        for path in self.folder.glob("*.film.json"):
            try:
                out.append(Project.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, TypeError):
                continue
        return sorted(out, key=lambda p: p.updated, reverse=True)

    def delete(self, project_id: str) -> None:
        self.path(project_id).unlink(missing_ok=True)
