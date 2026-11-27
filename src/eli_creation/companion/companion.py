"""The companion: what ELI notices about the project and when it may say so."""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from eli_creation.companion import attention_queue

if TYPE_CHECKING:
    from eli_creation.services import Studio

log = logging.getLogger("eli_creation.companion")

# off: says nothing unasked · quiet: keeps notes for when you look · helpful: offers an insight now
# and then · active: also asks to pause and talk the project through
LEVELS = ("off", "quiet", "helpful", "active")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist", ".godot", ".cache"}
MAX_FILES = 5000


@dataclass
class ProjectWatcher:
    """What changed in a project's folder since it was last looked at: polled, not watched, so it
    behaves the same on every system and holds no handle open on the person's files."""

    folder: Path
    _seen: dict[str, tuple[float, int]] = field(default_factory=dict)

    def snapshot(self) -> dict[str, tuple[float, int]]:
        out: dict[str, tuple[float, int]] = {}
        for root, dirs, files in os.walk(self.folder):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for name in files:
                if name.startswith("."):
                    continue
                path = Path(root) / name
                try:
                    st = path.stat()
                except OSError:
                    continue
                out[str(path.relative_to(self.folder))] = (st.st_mtime, st.st_size)
                if len(out) >= MAX_FILES:
                    return out
        return out

    def changes(self) -> dict[str, list[str]]:
        now = self.snapshot()
        before, self._seen = self._seen, now
        if not before:
            return {"added": [], "changed": [], "removed": []}
        return {
            "added": sorted(set(now) - set(before)),
            "changed": sorted(k for k in set(now) & set(before) if now[k] != before[k]),
            "removed": sorted(set(before) - set(now)),
        }


@dataclass(frozen=True)
class ScreenRead:
    text: str
    source: str  # eli_v3 | pillow | none
    why_not: str = ""


def read_screen(hosted: bool) -> ScreenRead:
    """What is on the screen, as text: a screenshot read by Tesseract, on this machine."""
    from eli_creation.adapters.local.ocr import TesseractOcr

    ocr = TesseractOcr.find()
    if not ocr.can_read_images:
        return ScreenRead("", "none", ocr.image_reason)
    raw, source = b"", "none"
    if hosted:
        try:
            from eli_creation.adapters.eli_v3.compat import import_attr

            shot = import_attr("eli.perception.os_controller", "take_screenshot")("full", keep=False)
            if shot.get("ok") and shot.get("path"):
                raw, source = Path(shot["path"]).read_bytes(), "eli_v3"
        except Exception:
            log.debug("ELI v3's screenshot failed", exc_info=True)
    if not raw:
        if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland":
            return ScreenRead("", "none", "on Wayland the screen is read through ELI v3's portal capture: "
                                          "open Creation Station from ELI v3 to let ELI read it")
        try:
            from PIL import ImageGrab

            buffer = io.BytesIO()
            ImageGrab.grab(all_screens=True).save(buffer, "PNG")
            raw, source = buffer.getvalue(), "pillow"
        except Exception as exc:
            return ScreenRead("", "none", f"the screen could not be captured here: {exc}")
    pages = ocr.read_image(raw, ".png")
    text = "\n".join(p for page in pages for p in page.paragraphs)
    return ScreenRead(text[:6000], source)


@dataclass(frozen=True)
class Raised:
    kind: str  # insight | question | discuss
    title: str
    why: str
    severity: str = "medium"


class Companion:
    def __init__(self, studio: Studio) -> None:
        self.studio = studio
        self._watchers: dict[str, ProjectWatcher] = {}
        self._last_raised = 0.0

    @property
    def level(self) -> str:
        level = self.studio.settings.companion_level
        return level if level in LEVELS else "helpful"

    def watcher(self, folder: Path) -> ProjectWatcher:
        key = str(Path(folder).resolve())
        if key not in self._watchers:
            self._watchers[key] = ProjectWatcher(Path(folder))
            self._watchers[key].changes()  # the first look only learns the folder
        return self._watchers[key]

    def may_speak_now(self) -> tuple[bool, str]:
        if self.level == "off":
            return False, "ELI is set to say nothing unasked"
        if not self.studio.main.available:
            return False, self.studio.main.why_unavailable
        gap = max(1, self.studio.settings.companion_min_gap_minutes) * 60
        if time.time() - self._last_raised < gap:
            return False, "ELI raised something a short while ago"
        busy = [j for j in self.studio.queue.jobs() if j.lane == "main" and not j.finished]
        if busy:
            return False, "the main model is working on your request"
        return True, ""

    def context(self, project: str, folder: Path | None) -> dict[str, Any]:
        recent = self.studio.library.recent(project=project, limit=12)
        out: dict[str, Any] = {
            "project": project,
            "recent_assets": [{"kind": a.kind, "title": a.title, "licence_class": a.licence_class} for a in recent],
        }
        if folder is not None and self.studio.settings.companion_watch_project:
            out["changes"] = {k: v[:20] for k, v in self.watcher(folder).changes().items()}
        if self.studio.settings.companion_read_screen:
            screen = read_screen(self.studio.hosted)
            out["screen"] = screen.text[:2500] if screen.text else f"(not read: {screen.why_not})"
        return out

    def think(self, project: str = "", folder: Path | None = None, *, asked: bool = False) -> Raised | None:
        """One look at the project. Returns what ELI would raise, and keeps it in the attention
        queue; None when there is nothing worth saying, or it is not the moment."""
        if not asked:
            ok, _why = self.may_speak_now()
            if not ok:
                return None
        from eli_creation.edition import policy
        from eli_creation.engines.writing import parse_json

        ctx = self.context(project, folder)
        allow_discuss = asked or self.level == "active"
        prompt = (
            "You are ELI, working beside a creator on their project. From what they are doing now, say "
            "the single most useful thing, or nothing. Never praise for its own sake; never repeat what "
            "they can see. Kinds: insight (something they may have missed: a platform limit, a licence "
            "warning on an asset, consistency of look or voice, a missing piece), question (one thing to "
            "decide)" + (", discuss (ask to pause and talk the project through, only when a real choice "
            "is coming up)" if allow_discuss else "") + ".\n"
            f"What they are doing: {json.dumps(ctx, ensure_ascii=False)[:5000]}\n"
            'Answer with JSON only: {"kind": "...", "title": "one sentence", "why": "one sentence", '
            '"severity": "low|medium|high"} or {"kind": "none"}'
        )
        # never waits: while the main model has stepped aside for a job, ELI keeps its thoughts
        answer = self.studio.main.generate(system=policy.system_prompt_addendum(), prompt=prompt,
                                           max_tokens=300, temperature=0.4, json_mode=True, wait=0)
        try:
            said = parse_json(answer)
        except ValueError:
            return None
        kind = str(said.get("kind", "none"))
        if kind not in ("insight", "question", "discuss") or (kind == "discuss" and not allow_discuss):
            return None
        raised = Raised(kind, str(said.get("title", ""))[:200], str(said.get("why", ""))[:300],
                        str(said.get("severity", "medium")))
        self.keep(raised, project)
        return raised

    def ask_to_discuss(self, topic: str, why: str, project: str = "") -> Raised:
        """ELI asks to pause and talk the project through: kept, and shown as a request the person
        can take now, later, or decline."""
        raised = Raised("discuss", topic, why, "high")
        self.keep(raised, project)
        return raised

    def keep(self, raised: Raised, project: str) -> None:
        self._last_raised = time.time()
        attention_queue.append_attention(
            raised.kind, raised.title, severity=raised.severity, source="companion",
            metadata={"why": raised.why, "project": project},
            suppression_key=f"{project}:{raised.kind}:{raised.title.lower()}", suppression_window_sec=6 * 3600,
        )

    def waiting(self, limit: int = 10) -> list[dict[str, Any]]:
        items = attention_queue.top_attention(limit).get("items", [])
        return [i for i in items if i.get("source") == "companion" and i.get("state", "pending") == "pending"]
