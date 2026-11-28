"""What every page shares, and what every creative studio shares on top of it.

A page has a header (where you are, in that studio's colour) and is told when it is shown, with
anything the page that sent you there wanted it to have (a prompt, a picture to edit).

A studio also has its engines, shown as cards that say plainly whether this machine can run each
one now, what it would load, or what it still needs. Its jobs run off the window's thread, and
each appears in the studio's gallery as a tile that fills in as it works.
"""

from __future__ import annotations

import random
from functools import partial
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from eli_creation.engines import registry
from eli_creation.engines.base import Engine
from eli_creation.gui import components as ui
from eli_creation.gui import design, icons
from eli_creation.gui.gallery import Gallery, Tile, open_lightbox
from eli_creation.gui.widgets import FlowLayout

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job


class Page(QWidget):
    key = ""

    def __init__(self, shell: MainWindow) -> None:
        super().__init__()
        self.setObjectName("page")
        self.shell = shell
        self.studio = shell.studio
        self.info = design.STUDIOS[self.key]
        self.accent = self.info.accent

    def header(self, title: str = "", blurb: str = "", *, right: list[QWidget] | None = None) -> QHBoxLayout:
        mark = QLabel()
        mark.setFixedSize(44, 44)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(icons.pixmap(self.info.icon, self.accent, 22))
        mark.setStyleSheet(f"background: {design.alpha(self.accent, 0.14)}; border: 1px solid "
                           f"{design.alpha(self.accent, 0.35)}; border-radius: 12px;")
        words = QVBoxLayout()
        words.setSpacing(2)
        words.addWidget(ui.text(title or self.info.name, "h1"))
        if blurb:
            words.addWidget(ui.text(blurb, "small", tone="muted", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(words, 1)
        for widget in right or []:
            row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def shown(self, **wanted: Any) -> None:
        """The page is on screen; ``wanted`` is what the page that opened it asked for."""
        self.refresh()

    def refresh(self) -> None:
        pass

    def on_job(self, job: Job) -> None:
        pass

    def models_changed(self) -> None:
        pass


def scrolled(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(widget)
    return area


# ── engines ──────────────────────────────────────────────────────────────
def state_of(engine: Engine, studio: Any) -> tuple[str, str, str]:
    """(colour, a word, the reason) for an engine on this machine now."""
    got = engine.availability(studio)
    if got.ok and got.loads_on_demand:
        return design.BRAND_B, "Loads when you start", got.reason
    if got.ok:
        return design.GOOD, "Ready", got.reason
    if engine.planned:
        return design.FAINT, "Coming", got.reason
    return design.WARN, "Needs something", got.reason


class EngineCard(QFrame):
    clicked = Signal(str)

    def __init__(self, engine: Engine, accent: str) -> None:
        super().__init__()
        self.engine = engine
        self.accent = accent
        self.chosen = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(216, 86)
        self.dot = ui.StatusDot()
        self.word = ui.text("", "tiny", tone="muted")
        self.name = ui.text(engine.title, "small")
        design.set_type(self.name, "h3")
        self.name.setWordWrap(True)
        head = QHBoxLayout()
        head.setSpacing(4)
        head.addWidget(self.dot)
        head.addWidget(self.word, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(4)
        lay.addLayout(head)
        lay.addWidget(self.name)
        self._paint_frame()

    def update_state(self, studio: Any) -> None:
        colour, word, why = state_of(self.engine, studio)
        self.dot.set(colour)
        self.word.setText(word)
        self.word.setStyleSheet(f"color: {colour};")
        self.setToolTip(f"<b>{self.engine.title}</b><br>{self.engine.summary}" + (f"<br><br>{why}" if why else ""))
        self.setEnabled(not self.engine.planned)
        self._paint_frame()

    def set_chosen(self, chosen: bool) -> None:
        self.chosen = chosen
        self._paint_frame()

    def _paint_frame(self) -> None:
        if self.chosen:
            style = (f"QFrame {{ background: {design.alpha(self.accent, 0.12)}; border: 2px solid {self.accent};"
                     " border-radius: 14px; }")
        else:
            style = (f"QFrame {{ background: {design.SURFACE}; border: 1px solid {design.LINE};"
                     " border-radius: 14px; } QFrame:hover { border-color: #3b4560; }")
        self.setStyleSheet(style + " QLabel { background: transparent; border: none; }")
        if self.engine.planned:
            self.name.setStyleSheet(f"color: {design.FAINT};")

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if not self.engine.planned:
            self.clicked.emit(self.engine.id)


class EngineStrip(QWidget):
    """The studio's engines side by side; the chosen one is the one Create uses."""

    changed = Signal(str)

    def __init__(self, tab: str, accent: str, studio: Any, exclude: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.studio = studio
        self.cards: dict[str, EngineCard] = {}
        flow = FlowLayout(self, 10)
        for engine in registry.for_tab(tab):
            if engine.id in exclude:
                continue
            card = EngineCard(engine, accent)
            card.clicked.connect(self.choose)
            self.cards[engine.id] = card
            flow.addWidget(card)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.current = ""
        self.refresh()
        for engine_id, card in self.cards.items():  # the first this machine can run now
            if card.engine.availability(studio).ok:
                self.choose(engine_id)
                break
        else:
            self.choose(next(iter(self.cards), ""))

    def refresh(self) -> None:
        for card in self.cards.values():
            card.update_state(self.studio)

    def choose(self, engine_id: str) -> None:
        if engine_id not in self.cards:
            return
        self.current = engine_id
        for key, card in self.cards.items():
            card.set_chosen(key == engine_id)
        self.changed.emit(engine_id)

    def engine(self) -> Engine:
        return self.cards[self.current].engine


class StudioPage(Page):
    """A creative studio: engines, a way to say what to make, and a gallery of what was made."""

    gallery_kind = ""  # the library kind the gallery shows
    tile_actions: list[tuple[str, str, str]] = []
    own_engines: tuple[str, ...] = ()  # engines the page drives from its own panels, not the strip

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.jobs: dict[str, Job] = {}
        self.engines = EngineStrip(self.key, self.accent, self.studio, self.own_engines)
        self.engines.changed.connect(lambda _id: self.update_create())
        self.gallery = Gallery(size=shell.recall("gallery_size", "medium"), actions=self.tile_actions)
        self.gallery.opened.connect(self.view)
        self.gallery.asked.connect(self.act)
        self.create_button = ui.GlowButton("Create", "sparkles", accent=self.accent, hint=ui.shortcut_hint("Ctrl+Enter"))
        self.create_button.clicked.connect(self.submit)
        self.reason = ui.text("", "tiny", tone="warn", wrap=True)

    # ── what this studio asks for ──
    def request(self) -> dict[str, Any]:
        raise NotImplementedError

    def expected(self, request: dict[str, Any]) -> int:
        """How many results a request will give (tiles shown while it runs)."""
        return 1

    # ── doing it ──
    def update_create(self) -> None:
        if not self.engines.current:
            self.create_button.setEnabled(False)
            return
        engine = self.engines.engine()
        got = engine.availability(self.studio)
        busy = any(not j.finished for j in self.jobs.values()) and engine.lane == "main"
        self.create_button.setEnabled(got.ok and not busy)
        self.create_button.set_busy(any(not j.finished for j in self.jobs.values()))
        self.reason.setText("" if got.ok else got.reason)
        self.reason.setVisible(not got.ok and bool(got.reason))

    def submit(self) -> None:
        if not self.create_button.isEnabled():
            return
        try:
            request = self.request()
            request.setdefault("project", self.shell.project_name())
            job = self.studio.submit(self.engines.current, request)
        except Exception as exc:  # a missing input, refused by policy, not available now
            self.shell.toast(str(exc), "warn")
            return
        self.jobs[job.id] = job
        self.gallery.add_pending(job.id, self.expected(request), "Waiting its turn")
        self.after_submit(request)
        self.update_create()

    def after_submit(self, request: dict[str, Any]) -> None:
        pass

    def on_job(self, job: Job) -> None:
        if job.id not in self.jobs:
            return
        self.gallery.model_.update_job(job.id, job.progress, job.message or job.state)
        if job.finished:
            made = [Tile.from_asset(a) for a in job.assets]
            self.gallery.model_.finish_job(job.id, made)
            self.finished(job)
            if job.state == "done":
                self.shell.toast(f"{self.info.name}: {len(made)} made" if made else f"{self.info.name}: done", "good",
                                 action=("View", partial(self.view, made[0])) if made else None)
            elif job.state == "failed":
                self.shell.toast(f"{self.info.name}: {job.error}", "bad")
        self.update_create()

    def finished(self, job: Job) -> None:
        pass

    # ── the gallery ──
    def load_gallery(self) -> None:
        if not self.gallery_kind:
            return
        pending = [t for t in self.gallery.tiles() if t.pending]
        only = self.shell.recall(f"{self.key}_this_project", False)
        project = self.shell.project_name() if only else ""
        assets = self.studio.library.recent(kind=self.gallery_kind, project=project, limit=240)
        self.gallery.set_tiles(pending + [Tile.from_asset(a) for a in assets])

    def view(self, tile: Tile) -> None:
        box = open_lightbox(self.shell, self.gallery.tiles(), tile, self.tile_actions)
        box.acted.connect(self.act)

    def act(self, name: str, tile: Tile) -> None:
        """A tile's own action (beyond open, show and copy), by name."""
        self.shell.act_on(name, tile)

    def refresh(self) -> None:
        self.engines.refresh()
        self.update_create()

    def models_changed(self) -> None:
        self.refresh()

    def gallery_bar(self, title: str = "Made here") -> QHBoxLayout:
        size = ui.Segmented([("S", "small"), ("M", "medium"), ("L", "large")], self.gallery.size_name,
                            accent=self.accent)
        size.setFixedWidth(130)
        size.changed.connect(self._size)
        scope = ui.Segmented([("This project", "project"), ("Everything", "all")],
                             "project" if self.shell.recall(f"{self.key}_this_project", False) else "all",
                             accent=self.accent)
        scope.setFixedWidth(240)
        scope.changed.connect(self._scope)
        row = QHBoxLayout()
        row.addWidget(ui.text(title, "h3"))
        row.addStretch(1)
        row.addWidget(scope)
        row.addWidget(size)
        return row

    def _size(self, name: str) -> None:
        self.gallery.set_size(name)
        self.shell.remember("gallery_size", name)

    def _scope(self, which: str) -> None:
        self.shell.remember(f"{self.key}_this_project", which == "project")
        self.load_gallery()


# ── prompts ──────────────────────────────────────────────────────────────
class PromptHistory:
    """The last prompts a studio was given, newest first, kept with the settings."""

    def __init__(self, shell: MainWindow, key: str, keep: int = 25) -> None:
        self.shell, self.key, self.keep = shell, f"history_{key}", keep

    def items(self) -> list[str]:
        found = self.shell.recall(self.key, [])
        return [str(x) for x in found] if isinstance(found, list) else []

    def add(self, prompt: str) -> None:
        prompt = prompt.strip()
        if prompt:
            self.shell.remember(self.key, [prompt] + [p for p in self.items() if p != prompt][: self.keep - 1])

    def menu(self, parent: QWidget, choose: Any) -> None:
        menu = QMenu(parent)
        items = self.items()
        if not items:
            menu.addAction("Nothing yet: what you create from is kept here").setEnabled(False)
        for prompt in items:
            action = menu.addAction(prompt if len(prompt) < 80 else prompt[:77] + "…")
            action.triggered.connect(lambda _c=False, p=prompt: choose(p))
        menu.exec(parent.mapToGlobal(parent.rect().bottomLeft()))


def new_seed() -> int:
    return random.randint(1, 2_000_000_000)
