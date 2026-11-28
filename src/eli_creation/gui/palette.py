"""The command palette (Ctrl+K) and the activity list.

The palette finds anything by a few letters of it: a studio to open, a thing to do, something made.
The activity list shows every job, running or done, with its progress, and stops one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons

if TYPE_CHECKING:
    from eli_creation.jobs import Job


@dataclass
class Command:
    title: str
    run: Callable[[], Any]
    group: str = "Go to"
    icon: str = "chevron_right"
    hint: str = ""
    keywords: str = ""
    accent: str = ""


def score(query: str, command: Command) -> float:
    """How well a few typed letters match a command: in order, earlier and closer is better."""
    query = query.lower().strip()
    if not query:
        return 1.0
    hay = f"{command.title} {command.keywords} {command.group}".lower()
    if query in hay:
        return 100.0 - hay.index(query) + (20 if command.title.lower().startswith(query) else 0)
    if command.group == "Made":  # something made is found by words in its name, not stray letters
        return 0.0
    pos, total, last = 0, 0.0, -1
    for ch in query:
        found = hay.find(ch, pos)
        if found < 0:
            return 0.0
        total += 3.0 if found == last + 1 else 1.0
        last, pos = found, found + 1
    return total


class CommandPalette(QDialog):
    def __init__(self, parent: QWidget, commands: list[Command]) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.commands = commands
        self.chosen: Command | None = None
        panel = QFrame()
        panel.setObjectName("palette")
        panel.setStyleSheet(f"QFrame#palette {{ background: {design.RAISED}; border: 1px solid {design.LINE_STRONG};"
                            " border-radius: 18px; }")
        ui.add_shadow(panel, blur=60, y=18, opacity=170)
        self.search = QLineEdit()
        self.search.setProperty("bare", True)
        self.search.setPlaceholderText("Search studios, actions and what you made…")
        design.set_type(self.search, "h3")
        self.search.textChanged.connect(self._filter)
        self.search.installEventFilter(self)
        head = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(icons.pixmap("search", design.MUTED, 20))
        head.addWidget(mark)
        head.addWidget(self.search, 1)
        head.addWidget(ui.text("Esc", "tiny", tone="faint"))
        self.list = QListWidget()
        self.list.setIconSize(QSize(18, 18))
        self.list.itemActivated.connect(self._run)
        self.list.itemClicked.connect(self._run)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 16, 18, 12)
        lay.addLayout(head)
        lay.addWidget(ui.hairline())
        lay.addWidget(self.list, 1)
        lay.addWidget(ui.text("↑ ↓ to move · Enter to run", "tiny", tone="faint"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 30, 30, 30)
        outer.addWidget(panel)
        self.resize(680, 520)
        if parent is not None:
            geo = parent.geometry()
            self.move(geo.center().x() - 340, geo.top() + 90)
        self._filter("")

    def _filter(self, query: str) -> None:
        self.list.clear()
        ranked = sorted(((score(query, c), i, c) for i, c in enumerate(self.commands)), key=lambda t: (-t[0], t[1]))
        for value, _i, command in ranked:
            if value <= 0:
                continue
            item = QListWidgetItem(icons.icon(command.icon, command.accent or design.SUBTLE, 18),
                                   f"{command.title}" + (f"    {command.hint}" if command.hint else ""))
            item.setData(Qt.ItemDataRole.UserRole, command)
            item.setToolTip(command.group)
            item.setSizeHint(QSize(0, 38))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802
        if watched is self.search and isinstance(event, QKeyEvent) and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                step = 1 if event.key() == Qt.Key.Key_Down else -1
                self.list.setCurrentRow(max(0, min(self.list.count() - 1, self.list.currentRow() + step)))
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                item = self.list.currentItem()
                if item is not None:
                    self._run(item)
                return True
        return super().eventFilter(watched, event)

    def _run(self, item: QListWidgetItem) -> None:
        command = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(command, Command):
            self.chosen = command
            self.accept()
            command.run()


class JobRow(QFrame):
    cancel_asked = Signal(str)

    def __init__(self, job: Job, title: str, accent: str) -> None:
        super().__init__()
        self.job_id = job.id
        self.setProperty("card", "soft")
        self.title = ui.text(title, "small")
        self.state = ui.text("", "tiny", tone="muted", wrap=True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(6)
        self.stop = ui.icon_button("x", "Stop it", lambda: self.cancel_asked.emit(self.job_id), size=14)
        mark = QLabel()
        mark.setPixmap(icons.pixmap("bolt", accent, 16))
        head = QHBoxLayout()
        head.addWidget(mark)
        head.addWidget(self.title, 1)
        head.addWidget(self.stop)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        lay.addLayout(head)
        lay.addWidget(self.bar)
        lay.addWidget(self.state)
        self.update_from(job)

    def update_from(self, job: Job) -> None:
        self.bar.setValue(int(job.progress * 100))
        self.bar.setVisible(not job.finished)
        self.stop.setVisible(not job.finished)
        colour = {"done": design.GOOD, "failed": design.BAD, "cancelled": design.MUTED}.get(job.state, design.SUBTLE)
        words = {"queued": "Waiting its turn", "running": job.message or "Working", "done": "Done",
                 "failed": f"Failed: {job.error}", "cancelled": "Stopped"}.get(job.state, job.state)
        self.state.setText(words)
        self.state.setStyleSheet(f"color: {colour};")


class ActivityPanel(QFrame):
    """Every job of this session, newest first."""

    def __init__(self, studio: Any, titles: Callable[[Job], tuple[str, str]]) -> None:
        super().__init__(None, Qt.WindowType.Popup)
        self.studio = studio
        self.titles = titles
        self.rows: dict[str, JobRow] = {}
        self.setObjectName("activity")
        self.setStyleSheet(f"QFrame#activity {{ background: {design.RAISED}; border: 1px solid {design.LINE_STRONG};"
                           " border-radius: 16px; }")
        self.setFixedWidth(380)
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        self.list.addStretch(1)
        inner = QWidget()
        inner.setLayout(self.list)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        self.empty = ui.text("Nothing has run yet. What you create shows here while it works.", "small",
                             tone="muted", wrap=True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.addWidget(ui.text("Activity", "h3"))
        lay.addWidget(self.empty)
        lay.addWidget(scroll, 1)
        self.setMinimumHeight(140)
        self.resize(380, 460)

    def refresh(self) -> None:
        jobs = self.studio.queue.jobs()[:30]
        self.empty.setVisible(not jobs)
        for job in reversed(jobs):
            self.on_job(job)

    def on_job(self, job: Job) -> None:
        row = self.rows.get(job.id)
        if row is None:
            title, accent = self.titles(job)
            row = JobRow(job, title, accent)
            row.cancel_asked.connect(self.studio.queue.cancel)
            self.rows[job.id] = row
            self.list.insertWidget(0, row)
            self.empty.hide()
        else:
            row.update_from(job)

    def running(self) -> int:
        return sum(1 for j in self.studio.queue.jobs() if not j.finished)


def badge_colour(count: int) -> QColor:
    return QColor(design.BRAND_B if count else design.FAINT)
