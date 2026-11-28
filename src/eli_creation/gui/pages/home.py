"""Home: where to start. A line to say what to make and where, the studios with what this machine
can do in each, what was made last, and the state of the machine and its models."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from eli_creation.engines import registry
from eli_creation.gui import components as ui
from eli_creation.gui import design, icons
from eli_creation.gui.gallery import Gallery, Tile, open_lightbox
from eli_creation.gui.pages.base import Page, scrolled
from eli_creation.tiers import TIER_EXAMPLES, TIER_LABELS

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job

QUICK = [("Image", "images"), ("Posts", "socials"), ("Game", "games"), ("Code", "coding")]
STUDIO_KEYS = ("socials", "images", "videos", "games", "editing", "coding")


def greeting(now: dt.datetime | None = None) -> str:
    hour = (now or dt.datetime.now()).hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"


class StudioCard(QFrame):
    clicked = Signal(str)

    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key
        info = design.STUDIOS[key]
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("studiocard")
        self.setStyleSheet(
            f"QFrame#studiocard {{ background: {design.RAISED}; border: 1px solid {design.LINE}; border-radius: 18px; }}"
            f" QFrame#studiocard:hover {{ border-color: {design.alpha(info.accent, 0.6)};"
            f" background: {design.mix(design.RAISED, info.accent, 0.05)}; }}"
            " QLabel { background: transparent; border: none; }")
        mark = QLabel()
        mark.setFixedSize(46, 46)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(icons.pixmap(info.icon, info.accent, 24))
        mark.setStyleSheet(f"background: {design.alpha(info.accent, 0.14)}; border-radius: 13px;")
        arrow = QLabel()
        arrow.setPixmap(icons.pixmap("chevron_right", design.FAINT, 18))
        head = QHBoxLayout()
        head.addWidget(mark)
        head.addStretch(1)
        head.addWidget(arrow, 0, Qt.AlignmentFlag.AlignTop)
        self.state = ui.text("", "tiny", tone="muted", wrap=True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 16)
        lay.setSpacing(6)
        lay.addLayout(head)
        lay.addSpacing(6)
        lay.addWidget(ui.text(info.name, "h3"))
        lay.addWidget(ui.text(info.blurb, "small", tone="subtle", wrap=True))
        lay.addStretch(1)
        lay.addWidget(self.state)
        self.setMinimumHeight(178)

    def update_state(self, studio: Any) -> None:
        engines = registry.for_tab(self.key)
        ready = [e for e in engines if e.availability(studio).ok]
        planned = [e for e in engines if e.planned]
        if ready:
            names = ", ".join(e.title for e in ready[:2])
            colour, words = design.GOOD, f"● Ready: {names}"
        else:
            reason = next((e.availability(studio).reason for e in engines if not e.planned), "")
            colour, words = design.WARN, f"● {reason or 'Nothing this machine can run yet'}"
        if planned:
            words += f"\n{len(planned)} more coming"
        self.state.setText(words)
        self.state.setStyleSheet(f"color: {colour};")

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self.clicked.emit(self.key)


class HomePage(Page):
    key = "home"

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(36, 30, 36, 36)
        lay.setSpacing(26)

        # the hero
        hero = ui.Glow()
        hero.setMinimumHeight(250)
        inner = QVBoxLayout(hero)
        inner.setContentsMargins(40, 34, 40, 34)
        inner.setSpacing(10)
        self.hello = ui.text("", "small", tone="subtle")
        inner.addWidget(self.hello)
        inner.addWidget(ui.text("What will you make today?", "display"))
        inner.addWidget(ui.text("Posts, pictures, animatics, games and code, made on this machine with ELI beside "
                                "you. Nothing leaves it.", "body", tone="subtle", wrap=True))
        inner.addSpacing(10)
        box = QFrame()
        box.setObjectName("quick")
        box.setStyleSheet(f"QFrame#quick {{ background: {design.alpha(design.INK, 0.72)}; border: 1px solid "
                          f"{design.LINE_STRONG}; border-radius: 16px; }}")
        quick = QHBoxLayout(box)
        quick.setContentsMargins(16, 8, 8, 8)
        quick.setSpacing(10)
        spark = QLabel()
        spark.setPixmap(icons.pixmap("sparkles", design.BRAND_B, 20))
        self.quick = QLineEdit()
        self.quick.setProperty("bare", True)
        self.quick.setPlaceholderText("A neon city at night… a launch post… a game where you catch stars…")
        design.set_type(self.quick, "h3")
        self.quick.returnPressed.connect(self._go)
        self.where = ui.Segmented(QUICK, "images", accent=design.BRAND_A)
        self.where.setFixedWidth(320)
        self.go_button = ui.GlowButton("Create", "sparkles")
        self.go_button.clicked.connect(self._go)
        quick.addWidget(spark)
        quick.addWidget(self.quick, 1)
        quick.addWidget(self.where)
        quick.addWidget(self.go_button)
        inner.addWidget(box)
        lay.addWidget(hero)

        # the studios
        lay.addLayout(self._section("Studios", "Each says what this machine can make in it now"))
        grid = QGridLayout()
        grid.setSpacing(14)
        self.cards: list[StudioCard] = []
        for n, key in enumerate(STUDIO_KEYS):
            card = StudioCard(key)
            card.clicked.connect(lambda k: self.shell.go(k))
            self.cards.append(card)
            grid.addWidget(card, n // 3, n % 3)
        lay.addLayout(grid)

        # recent work and the machine, side by side
        row = QHBoxLayout()
        row.setSpacing(18)
        recent = QVBoxLayout()
        recent.setSpacing(12)
        see_all = ui.button("Open the library", lambda: self.shell.go("library"), icon="library", variant="flat")
        recent.addLayout(self._section("Recently made", "", right=see_all))
        self.recent = Gallery(size="small")
        self.recent.fit_to_content(max_rows=2)
        self.recent.opened.connect(lambda t: open_lightbox(self.shell, self.recent.tiles(), t))
        self.empty = ui.EmptyState("sparkles", "Nothing made yet",
                                   "Describe something above and press Create: it appears here, filed with "
                                   "its record of how it was made.", accent=design.BRAND_A)
        recent.addWidget(self.recent)
        recent.addWidget(self.empty)
        recent.addStretch(1)
        row.addLayout(recent, 3)
        side = QVBoxLayout()
        side.setSpacing(14)
        side.addWidget(self._machine_card())
        side.addWidget(self._keys_card())
        side.addStretch(1)
        row.addLayout(side, 2)
        row.setAlignment(side, Qt.AlignmentFlag.AlignTop)
        row.setAlignment(recent, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(row)
        lay.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(body))

    def _section(self, title: str, note: str, *, right: QWidget | None = None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(ui.text(title, "h2"))
        if note:
            row.addSpacing(8)
            row.addWidget(ui.text(note, "small", tone="muted"), 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        if right is not None:
            row.addWidget(right)
        return row

    def _machine_card(self) -> ui.Card:
        m = self.studio.machine
        card = ui.Card(padding=20)
        head = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(icons.pixmap("cpu", design.BRAND_B, 22))
        head.addWidget(mark)
        head.addWidget(ui.text("This machine", "h3"))
        head.addStretch(1)
        head.addWidget(ui.Badge(f"Tier {m.tier}", design.BRAND_B))
        card.add(head)
        card.add(ui.text(f"{TIER_LABELS[m.tier]} · like {TIER_EXAMPLES[m.tier]}", "small", tone="subtle", wrap=True))
        cards = [f"{a.name} ({a.memory_mb / 1024:.0f} GB)" for a in m.accelerators]
        gpu = ", ".join(cards) if cards else "No graphics card: the processor does the work"
        card.add(ui.text(f"{gpu} · {m.ram_mb / 1024:.0f} GB memory · {m.cpu_threads} threads", "small",
                         tone="muted", wrap=True))
        card.add(ui.hairline())
        self.main_line = ui.text("", "small", wrap=True)
        self.main_dot = ui.StatusDot()
        line = QHBoxLayout()
        line.addWidget(self.main_dot)
        line.addWidget(self.main_line, 1)
        card.add(line)
        card.add(ui.button("Models and this machine", lambda: self.shell.go("settings"), icon="settings",
                           variant="flat"))
        return card

    def _keys_card(self) -> ui.Card:
        card = ui.Card(soft=True, padding=18, spacing=8)
        card.add(ui.text("Quicker with the keyboard", "h3"))
        for keys, what in (("Ctrl K", "find a studio, an action or anything made"),
                           ("Ctrl Enter", "create in the studio you are in"),
                           ("Ctrl 1–9", "open a studio"), ("Ctrl .", "show or hide ELI")):
            row = QHBoxLayout()
            row.addWidget(ui.Badge(ui.shortcut_hint(keys), design.SUBTLE))
            row.addWidget(ui.text(what, "small", tone="muted"), 1)
            card.add(row)
        return card

    def shown(self, **wanted: Any) -> None:
        self.refresh()
        self.quick.setFocus()

    def refresh(self) -> None:
        self.hello.setText(f"{greeting()}.  {dt.date.today():%A %d %B}")
        for card in self.cards:
            card.update_state(self.studio)
        tiles = [Tile.from_asset(a) for a in self.studio.library.recent(limit=12)]
        self.recent.set_tiles(tiles)
        self.recent.setVisible(bool(tiles))
        self.empty.setVisible(not tiles)
        main = self.studio.main
        ok = main.available
        self.main_dot.set(design.GOOD if ok else design.WARN)
        self.main_line.setText(f"Main model: {main.name}" if ok else
                               f"No main model yet: {main.why_unavailable}. Posts, games and code need one; "
                               "images, animatics and edits do not.")

    def _go(self) -> None:
        words = self.quick.text().strip()
        target = self.where.value()
        if not words:
            self.shell.go(target, focus=True)
            return
        self.quick.clear()
        self.shell.go(target, prompt=words, create=True)

    def on_job(self, job: Job) -> None:
        if job.finished and self.shell.current == "home":
            self.refresh()
