"""The window: a rail of studios on the left, the project and the palette above, the studio in
the middle, ELI beside it on the right, and what is loaded along the bottom.

Shortcuts: Ctrl+K finds anything; Ctrl+1 … Ctrl+9 open the studios in order; Ctrl+Enter creates;
Ctrl+. shows or hides ELI; Ctrl+B narrows the rail; F11 fills the screen.
"""

from __future__ import annotations

import threading
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from eli_creation import TITLE, __version__
from eli_creation.gui import components as ui
from eli_creation.gui import design, icons
from eli_creation.gui.bridge import Bridge
from eli_creation.gui.eli_panel import EliPanel
from eli_creation.gui.gallery import Tile
from eli_creation.gui.palette import ActivityPanel, Command, CommandPalette
from eli_creation.tiers import TIER_LABELS

if TYPE_CHECKING:
    from eli_creation.gui.pages.base import Page
    from eli_creation.jobs import Job
    from eli_creation.services import Studio

# The studios in the rail, in order; Library and Settings sit at its foot.
ORDER = ("home", "socials", "images", "videos", "audio", "games", "editing", "coding", "library", "settings")
FOOT = ("library", "settings")


class NavButton(QAbstractButton):
    """A studio in the rail: its icon in its colour when chosen, its name when the rail is wide,
    and a pulsing mark while something of it is running."""

    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key
        self.info = design.STUDIOS[key]
        self.setCheckable(True)
        self.setToolTip(f"{self.info.name}: {self.info.blurb}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wide = True
        self.busy = False
        self._hover = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200 if self.wide else 56, 44)

    def set_busy(self, busy: bool) -> None:
        if busy != self.busy:
            self.busy = busy
            self._timer.start(40) if busy else self._timer.stop()
            self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.04) % 1.0
        self.update()

    def enterEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 2, -8, -2)
        on = self.isChecked()
        if on or self._hover:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(design.alpha_q(self.info.accent, 0.14) if on else QColor(design.HOVER))
            p.drawRoundedRect(r, 11, 11)
        if on:
            bar = design.brand_gradient(0, r.top(), 0, r.bottom(), self.info.accent,
                                        design.mix(self.info.accent, "#ffffff", 0.3))
            p.setBrush(bar)
            p.drawRoundedRect(QRectF(r.left() - 8, r.top() + 10, 3.5, r.height() - 20), 2, 2)
        colour = self.info.accent if on else (design.TEXT if self._hover else design.MUTED)
        x = r.left() + 12 if self.wide else r.center().x() - 10
        p.drawPixmap(int(x), int(r.center().y() - 10), icons.pixmap(self.info.icon, colour, 20))
        if self.wide:
            font = QFont(self.font())
            font.setWeight(QFont.Weight.DemiBold if on else QFont.Weight.Medium)
            p.setFont(font)
            p.setPen(QColor(design.TEXT if on else design.SUBTLE))
            p.drawText(QRectF(x + 32, r.top(), r.width() - 60, r.height()), Qt.AlignmentFlag.AlignVCenter,
                       self.info.name)
        if self.busy:
            c = QPointF(r.right() - 14, r.center().y()) if self.wide else QPointF(r.center().x() + 13, r.top() + 9)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(design.alpha_q(design.BRAND_B, 0.5 * (1 - self._phase)))
            p.drawEllipse(c, 4 + 5 * self._phase, 4 + 5 * self._phase)
            p.setBrush(QColor(design.BRAND_B))
            p.drawEllipse(c, 4, 4)
        p.end()


class Rail(QFrame):
    """The studios, down the left."""

    def __init__(self, choose: Any, wide: bool) -> None:
        super().__init__()
        self.setObjectName("rail")
        self.setStyleSheet(f"QFrame#rail {{ background: rgba(8,12,20,0.78); border-right: 1px solid {design.HAIRLINE}; }}")
        self.buttons: dict[str, NavButton] = {}
        self.mark = QLabel()
        self.mark.setPixmap(icons.brand_mark(34))
        self.name = ui.text("Creation Station", "h3")
        self.sub = ui.text("ELI", "tiny", tone="muted")
        words = QVBoxLayout()
        words.setSpacing(0)
        words.addWidget(self.name)
        words.addWidget(self.sub)
        brand = QHBoxLayout()
        brand.setContentsMargins(18, 18, 12, 18)
        brand.setSpacing(10)
        brand.addWidget(self.mark)
        brand.addLayout(words, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 12)
        lay.setSpacing(2)
        lay.addLayout(brand)
        for key in ORDER:
            if key not in FOOT:
                lay.addWidget(self._add(key, choose))
        lay.addStretch(1)
        for key in FOOT:
            lay.addWidget(self._add(key, choose))
        self.toggle = ui.icon_button("sidebar", "Narrow or widen the rail (Ctrl+B)", self.flip, size=18)
        foot = QHBoxLayout()
        foot.setContentsMargins(18, 8, 14, 0)
        foot.addWidget(self.toggle)
        foot.addStretch(1)
        lay.addLayout(foot)
        self.wide = not wide
        self.flip()

    def _add(self, key: str, choose: Any) -> NavButton:
        button = NavButton(key)
        button.clicked.connect(partial(choose, key))
        self.buttons[key] = button
        return button

    def flip(self) -> None:
        self.wide = not self.wide
        self.name.setVisible(self.wide)
        self.sub.setVisible(self.wide)
        for button in self.buttons.values():
            button.wide = self.wide
            button.updateGeometry()
            button.update()
        self.setFixedWidth(224 if self.wide else 72)

    def choose(self, key: str) -> None:
        for k, button in self.buttons.items():
            button.setChecked(k == key)


class ActivityButton(QAbstractButton):
    """How many jobs are running, at a glance."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0
        self.setToolTip("Activity: what is running and what has finished")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 36)

    def set_count(self, count: int) -> None:
        self.count = count
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 3, -3, -1)
        p.setPen(QPen(QColor(design.LINE_STRONG), 1))
        p.setBrush(QColor(design.HOVER if self.underMouse() else design.SURFACE))
        p.drawRoundedRect(r, 10, 10)
        p.drawPixmap(int(r.center().x() - 9), int(r.center().y() - 9),
                     icons.pixmap("bolt", design.BRAND_B if self.count else design.SUBTLE, 18))
        if self.count:
            font = QFont(self.font())
            font.setPointSizeF(max(6.0, font.pointSizeF() * 0.72))
            font.setWeight(QFont.Weight.Bold)
            p.setFont(font)
            badge = QRectF(r.right() - 12, r.top() - 3, 15, 15)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(design.BRAND_A))
            p.drawEllipse(badge)
            p.setPen(QColor("#ffffff"))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(min(self.count, 9)))
        p.end()


class SearchPill(QAbstractButton):
    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Find a studio, an action or something you made (Ctrl+K)")
        self.setMinimumWidth(200)
        self.setMaximumWidth(380)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor("#3b4560" if self.underMouse() else design.LINE_STRONG), 1))
        p.setBrush(QColor(design.SURFACE))
        p.drawRoundedRect(r, 10, 10)
        p.drawPixmap(int(r.left() + 12), int(r.center().y() - 8), icons.pixmap("search", design.MUTED, 16))
        p.setPen(QColor(design.MUTED))
        p.drawText(QRectF(r.left() + 38, r.top(), r.width() - 100, r.height()), Qt.AlignmentFlag.AlignVCenter,
                   "Search or jump to…")
        keys = ui.shortcut_hint("Ctrl K")
        fm = QFontMetrics(self.font())
        box = QRectF(r.right() - fm.horizontalAdvance(keys) - 22, r.top() + 7, fm.horizontalAdvance(keys) + 14,
                     r.height() - 14)
        p.setPen(QPen(QColor(design.LINE_STRONG), 1))
        p.setBrush(QColor(design.RAISED))
        p.drawRoundedRect(box, 6, 6)
        p.setPen(QColor(design.FAINT))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, keys)
        p.end()


class ProjectBox(QComboBox):
    """The project the work is for: chosen from those used before, or a new name typed in."""

    def __init__(self, projects: list[str], current: str = "") -> None:
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
        line = self.lineEdit()
        if line is not None:
            line.setPlaceholderText("Project: a client, a channel, a game…")
        self.addItem("")
        self.addItems(projects)
        self.setCurrentText(current)
        self.setToolTip("What you make is filed under this project, and ELI follows it")

    def text(self) -> str:
        return self.currentText().strip()


class _Later(QObject):
    """Brings work done on another thread back to the window's."""

    back = Signal(object, object)

    def __init__(self) -> None:
        super().__init__()
        self.back.connect(self._run)

    @Slot(object, object)
    def _run(self, then: Any, value: Any) -> None:
        then(value)


class MainWindow(QMainWindow):
    def __init__(self, studio: Studio, *, licence_line: str = "") -> None:
        super().__init__()
        self.studio = studio
        self.setWindowTitle(f"{TITLE} {__version__}")
        self.resize(1480, 920)
        self.setMinimumSize(1100, 700)
        self.bridge = Bridge()
        self._later = _Later()
        self.current: str = ""
        studio.queue.on_change(self.bridge.job_changed.emit)
        studio.manager.on_change(self.bridge.models_changed.emit)
        design.follow_zoom()

        # ── the top bar ──
        self.project = ProjectBox(studio.library.projects(), str(self.recall("project", "")))
        self.project.currentTextChanged.connect(lambda t: self.remember("project", t.strip()))
        self.search = SearchPill()
        self.search.clicked.connect(self.open_palette)
        self.activity = ActivityButton()
        self.activity.clicked.connect(self._show_activity)
        self.activity_panel = ActivityPanel(studio, self._job_title)
        self.eli_toggle = ui.icon_button("sparkles", "Show or hide ELI (Ctrl+.)", self._toggle_eli, checkable=True,
                                         size=18)
        self.ask_eli = QLineEdit()
        self.ask_eli.setObjectName("askEli")
        self.ask_eli.setPlaceholderText("Ask ELI, or tell it what to make…")
        self.ask_eli.addAction(icons.icon("sparkles", design.BRAND_A, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.ask_eli.setMinimumWidth(180)
        self.ask_eli.setStyleSheet(f"QLineEdit#askEli {{ background: {design.alpha(design.BRAND_A, 0.07)}; border: 1px "
                                   f"solid {design.alpha(design.BRAND_A, 0.35)}; border-radius: 18px; padding: 7px 12px; }}"
                                   f" QLineEdit#askEli:focus {{ border-color: {design.BRAND_A}; }}")
        self.ask_eli.returnPressed.connect(self._ask_eli)
        self.models_button = ui.icon_button("cpu", "ELI's models: what is loaded, and letting go", self.show_models,
                                            size=18)
        self._dock: Any = None
        self.tier = ui.Badge(f"Tier {studio.machine.tier}", design.BRAND_B)
        self.tier.setToolTip(f"{TIER_LABELS[studio.machine.tier]}: what this machine can run. Settings shows each "
                             "feature's needs")
        self.tier.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tier.mousePressEvent = lambda _e: self.go("settings")  # type: ignore[method-assign]
        top = QFrame()
        top.setObjectName("topbar")
        top.setStyleSheet(f"QFrame#topbar {{ background: rgba(5,7,13,0.6); border-bottom: 1px solid {design.HAIRLINE}; }}")
        bar = QHBoxLayout(top)
        bar.setContentsMargins(20, 10, 16, 10)
        bar.setSpacing(10)
        folder = QLabel()
        folder.setPixmap(icons.pixmap("folder", design.MUTED, 18))
        bar.addWidget(folder)
        bar.addWidget(self.project)
        bar.addStretch(1)
        bar.addWidget(self.search, 2)
        bar.addWidget(self.ask_eli, 3)
        bar.addStretch(1)
        bar.addWidget(self.tier)
        bar.addWidget(self.models_button)
        bar.addWidget(self.activity)
        bar.addWidget(self.eli_toggle)

        # ── the pages ──
        from eli_creation.gui.pages import build_pages

        self.stack = QStackedWidget()
        self.stack.setObjectName("pages")
        self.pages: dict[str, Page] = build_pages(self)
        for key in ORDER:
            self.stack.addWidget(self.pages[key])
        self.rail = Rail(self.go, bool(self.recall("rail_wide", True)))

        # ── ELI ──
        self.eli = EliPanel(studio, self.project)
        self.eli.shell = self
        self.eli.where = self._where
        self.eli.setFixedWidth(360)
        eli_open = bool(self.recall("eli_open", True))
        self.eli.setVisible(eli_open)
        self.eli_toggle.setChecked(eli_open)

        middle = QVBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        middle.addWidget(top)
        middle.addWidget(self.stack, 1)
        body = ui.Backdrop()
        body.setObjectName("shellBody")
        row = QHBoxLayout(body)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.rail)
        row.addLayout(middle, 1)
        row.addWidget(self.eli)
        self.setCentralWidget(body)
        self.toasts = ui.Toasts(body)

        # ── the status line ──
        self.main_dot = ui.StatusDot()
        self.main_chip = QLabel()
        self.models_chip = QLabel()
        self.tier_chip = QLabel(f"Tier {studio.machine.tier}: {TIER_LABELS[studio.machine.tier]}")
        self.licence_chip = QLabel(licence_line)
        status = self.statusBar()
        status.setSizeGripEnabled(False)
        holder = QWidget()
        line = QHBoxLayout(holder)
        line.setContentsMargins(8, 0, 8, 0)
        line.setSpacing(4)
        for chip in (self.main_chip, self.models_chip):
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip("ELI's models: what is loaded, and letting go")
            chip.mousePressEvent = partial(self._models_from, chip)  # type: ignore[method-assign]
        line.addWidget(self.main_dot)
        line.addWidget(self.main_chip)
        line.addWidget(ui.text("·", "small", tone="faint"))
        line.addWidget(self.models_chip)
        line.addStretch(1)
        status.addWidget(holder, 1)
        status.addPermanentWidget(self.tier_chip)
        if licence_line:
            status.addPermanentWidget(self.licence_chip)

        self.bridge.job_changed.connect(self._on_job)
        self.bridge.models_changed.connect(self._models_changed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(2000)
        self._menus()
        self._shortcuts()
        start = str(self.recall("page", "") or "home")
        self.go(start if start in self.pages else "home")
        self.refresh_status()

    # ── what the pages use ────────────────────────────────────────────────
    def project_name(self) -> str:
        return self.project.text()

    def recall(self, key: str, default: Any = None) -> Any:
        prefs = self.studio.settings.extra.get("ui")
        return prefs.get(key, default) if isinstance(prefs, dict) else default

    def remember(self, key: str, value: Any) -> None:
        prefs = self.studio.settings.extra.get("ui")
        if not isinstance(prefs, dict):
            prefs = self.studio.settings.extra["ui"] = {}
        prefs[key] = value

    def toast(self, message: str, kind: str = "info", *, action: tuple[str, Any] | None = None) -> None:
        self.toasts.show_toast(message, kind, action=action)

    def run_in_background(self, work: Any, done: Any, failed: Any | None = None) -> None:
        """Run ``work`` off the window's thread (a model's answer, a long job of the window's own),
        then ``done(result)`` back on it, or ``failed(exception)``."""

        def run() -> None:
            try:
                result = work()
            except Exception as exc:
                self._later.back.emit(failed or done, exc)
                return
            self._later.back.emit(done, result)

        threading.Thread(target=run, name="eli-creation-window-work", daemon=True).start()

    def go(self, key: str, **wanted: Any) -> None:
        if key not in self.pages:
            return
        page = self.pages[key]
        changed = key != self.current
        self.current = key
        self.rail.choose(key)
        self.stack.setCurrentWidget(page)
        self.remember("page", key)
        if key in ("socials", "images", "videos", "audio", "games", "editing", "coding"):
            self.studio.settings.last_tab = key
        page.shown(**wanted)
        if changed:
            self._fade(page)

    def act_on(self, name: str, tile: Tile) -> None:
        """What a tile's menu asks for, wherever it was."""
        if name == "edit":
            self.go("editing", path=tile.path)
        elif name == "to_video":
            self.go("videos", add=[tile.path])
        elif name == "play":
            QDesktopServices.openUrl(QUrl.fromLocalFile(tile.path))
        elif name == "playable":
            self.go("games", design=tile.path, make_playable=True)
        elif name == "view_code":
            self.go("coding", path=tile.path)
        elif name == "view":
            from eli_creation.gui.gallery import open_lightbox

            open_lightbox(self, [tile], tile)

    # ── look and movement ────────────────────────────────────────────────
    def _fade(self, page: QWidget) -> None:
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", page)
        anim.setDuration(170)
        anim.setStartValue(0.35)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: page.setGraphicsEffect(None))  # type: ignore[arg-type]
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _ask_eli(self) -> None:
        question = self.ask_eli.text().strip()
        if not question:
            return
        self.ask_eli.clear()
        if not self.eli.isVisible():
            self._toggle_eli()
        self.eli.ask_now(question)

    def _where(self) -> str:
        return design.STUDIOS.get(self.current, design.STUDIOS["home"]).name

    def _models_from(self, chip: QWidget, _event: object) -> None:
        self.show_models(chip, above=True)

    def show_models(self, near: QWidget | None = None, *, above: bool = False) -> None:
        from eli_creation.gui.models_dock import ModelsDock

        if self._dock is None:
            self._dock = ModelsDock(self)
        self._dock.show_at(near or self.models_button, above=above)

    def _toggle_eli(self) -> None:
        shown = not self.eli.isVisible()
        self.eli.setVisible(shown)
        self.eli_toggle.setChecked(shown)
        self.remember("eli_open", shown)

    def _flip_rail(self) -> None:
        self.rail.flip()
        self.remember("rail_wide", self.rail.wide)

    def _shortcuts(self) -> None:
        def key(seq: str, run: Any) -> None:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(run)

        key("Ctrl+K", self.open_palette)
        key("Ctrl+.", self._toggle_eli)
        key("Ctrl+B", self._flip_rail)
        key("F11", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        key("Ctrl+Return", self._create_here)
        key("Ctrl+Enter", self._create_here)
        for n, page_key in enumerate(ORDER[:9], 1):
            key(f"Ctrl+{n}", partial(self.go, page_key))

    def _create_here(self) -> None:
        create = getattr(self.pages.get(self.current), "submit", None)
        if callable(create):
            create()

    # ── the palette and activity ─────────────────────────────────────────
    def commands(self) -> list[Command]:
        found: list[Command] = []
        for n, key in enumerate(ORDER, 1):
            info = design.STUDIOS[key]
            found.append(Command(info.name, partial(self.go, key), "Go to", info.icon,
                                 ui.shortcut_hint(f"Ctrl+{n}"), info.blurb, info.accent))
        found += [
            Command("Make an image", lambda: self.go("images", focus=True), "Create", "image",
                    keywords="picture draw render", accent=design.accent("images")),
            Command("Write posts for each platform", lambda: self.go("socials", focus=True), "Create", "message",
                    keywords="social x instagram linkedin tiktok", accent=design.accent("socials")),
            Command("Design a game", lambda: self.go("games", focus=True), "Create", "gamepad", keywords="play",
                    accent=design.accent("games")),
            Command("Write code", lambda: self.go("coding", focus=True), "Create", "code",
                    keywords="program script agent", accent=design.accent("coding")),
            Command("Make a film", lambda: self.go("videos"), "Create", "film", keywords="video storyboard movie",
                    accent=design.accent("videos")),
            Command("1-click ad", lambda: self.go("videos", ad=True), "Create", "bolt",
                    keywords="advert commercial promo video", accent=design.accent("videos")),
            Command("Start a film from a template", lambda: self.go("videos", template=True), "Create", "layers",
                    keywords="trailer promo explainer intro event", accent=design.accent("videos")),
            Command("Record a voice-over", lambda: self.go("audio", mode="voice"), "Create", "mic",
                    keywords="narration speech voice tts", accent=design.accent("audio")),
            Command("Compose music", lambda: self.go("audio", mode="music"), "Create", "music",
                    keywords="soundtrack song score bed", accent=design.accent("audio")),
            Command("Make a sound effect", lambda: self.go("audio", mode="sfx"), "Create", "bolt",
                    keywords="whoosh riser impact sfx", accent=design.accent("audio")),
            Command("Edit a picture", lambda: self.go("editing"), "Create", "sliders", keywords="crop resize adjust",
                    accent=design.accent("editing")),
            Command("Show or hide ELI", self._toggle_eli, "View", "sparkles", ui.shortcut_hint("Ctrl+.")),
            Command("Narrow or widen the rail", self._flip_rail, "View", "sidebar", ui.shortcut_hint("Ctrl+B")),
            Command("Open the outputs folder", self._open_outputs, "Files", "folder"),
            Command("Unload idle models now", self._unload, "Models", "cpu", keywords="memory gpu free"),
            Command("ELI's models", self.show_models, "Models", "cpu", keywords="main specialist loaded load"),
            Command("Ask ELI", lambda: self.ask_eli.setFocus(), "ELI", "sparkles", keywords="agent help chat"),
            Command("Licence", self._licence, "Help", "shield", keywords="key trial buy activate"),
        ]
        for asset in self.studio.library.recent(limit=40):
            tile = Tile.from_asset(asset)
            found.append(Command(asset.title, partial(self.act_on, "view", tile), "Made", "eye",
                                 asset.kind.capitalize(), f"{asset.kind} {asset.project}"))
        return found

    def open_palette(self) -> CommandPalette:
        dialog = CommandPalette(self, self.commands())
        dialog.open()
        return dialog

    def _show_activity(self) -> None:
        self.activity_panel.refresh()
        at = self.activity.mapToGlobal(self.activity.rect().bottomRight())
        self.activity_panel.move(at.x() - self.activity_panel.width(), at.y() + 8)
        self.activity_panel.show()

    def _job_title(self, job: Job) -> tuple[str, str]:
        info = design.STUDIOS.get(job.tab, design.STUDIOS["home"])
        what = (job.request.get("prompt") or job.request.get("brief") or job.request.get("pitch")
                or job.request.get("task") or job.request.get("title") or "")
        return f"{info.name}: {str(what)[:48] or job.engine}", info.accent

    def _on_job(self, job: Job) -> None:
        for page in self.pages.values():
            page.on_job(job)
        self.activity_panel.on_job(job)
        running = [j for j in self.studio.queue.jobs() if not j.finished]
        self.activity.set_count(len(running))
        busy = {j.tab for j in running}
        for key, button in self.rail.buttons.items():
            button.set_busy(key in busy)

    def _models_changed(self) -> None:
        for page in self.pages.values():
            page.models_changed()
        self.refresh_status()

    # ── menus ────────────────────────────────────────────────────────────
    def _menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self._action("Find anything…", self.open_palette))
        file_menu.addAction(self._action("Open the outputs folder", self._open_outputs))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Quit", self.close))
        view = self.menuBar().addMenu("&View")
        for key in ORDER:
            view.addAction(self._action(design.STUDIOS[key].name, partial(self.go, key)))
        view.addSeparator()
        view.addAction(self._action("Show or hide ELI", self._toggle_eli))
        view.addAction(self._action("Narrow or widen the rail", self._flip_rail))
        models = self.menuBar().addMenu("&Models")
        models.addAction(self._action("Unload idle specialists now", self._unload))
        models.addAction(self._action("Model settings…", lambda: self.go("settings")))
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self._action("Licence…", self._licence))
        help_menu.addAction(self._action("About", lambda: QMessageBox.about(
            self, TITLE, f"{TITLE} {__version__}\nAn ELI bundle: made on your machine, with ELI beside you.")))

    def _action(self, label: str, run: Any) -> QAction:
        action = QAction(label, self)
        action.triggered.connect(lambda _c=False: run())
        return action

    def _open_outputs(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.studio.layout.outputs)))

    def _unload(self) -> None:
        self.studio.manager.unload_idle(now=float("inf"))
        self.toast("Idle models unloaded: their memory is free again", "good")

    def _licence(self) -> None:
        from eli_creation.gui.licence_dialog import LicenceDialog

        LicenceDialog(self).exec()

    # ── status ───────────────────────────────────────────────────────────
    def refresh_status(self) -> None:
        main = self.studio.main
        colour = {"ready": design.GOOD, "loading": design.BRAND_B, "busy": design.BRAND_B,
                  "stepped_aside": design.WARN, "unavailable": design.BAD}.get(main.state, design.MUTED)
        self.main_dot.set(colour, pulse=main.state in ("loading", "busy"))
        self.main_chip.setText(f"Main model: {main.name} ({main.state.replace('_', ' ')})")
        loaded = [s for s in self.studio.manager.status()
                  if s.role == "specialist" and s.state in ("loading", "ready", "busy", "unloading")]
        self.models_chip.setText("Specialists: " + (", ".join(f"{s.title} ({s.state})" for s in loaded)
                                                     or "none loaded"))

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        from eli_creation.gui import sound

        sound.release_all()
        self.studio.save_settings()
        self.studio.close()
        super().closeEvent(event)


def open_path(path: str | Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
