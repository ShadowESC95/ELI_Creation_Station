"""ELI beside the studio: how much it may say, what it noticed, its asks to pause and talk, and a
conversation about the project.

What ELI may look at is chosen in Settings (the project's folder, the screen) and nothing is looked
at until it is allowed. The level here (off, quiet, helpful, active) is how much it says unasked.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from eli_creation.companion.companion import LEVELS, Raised
from eli_creation.gui import components as ui
from eli_creation.gui import design, icons

if TYPE_CHECKING:
    from eli_creation.services import Studio

SEVERITY = {"high": design.BAD, "medium": design.WARN, "low": design.BRAND_B}


class _Said(QObject):
    said = Signal(object)


class Bubble(QFrame):
    """One turn of the conversation."""

    def __init__(self, words: str, mine: bool) -> None:
        super().__init__()
        colour = design.alpha(design.BRAND_A, 0.22) if mine else design.RAISED
        border = design.alpha(design.BRAND_A, 0.45) if mine else design.LINE
        self.setStyleSheet(f"QFrame {{ background: {colour}; border: 1px solid {border}; border-radius: 14px; }}"
                           " QLabel { background: transparent; border: none; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 10)
        lay.addWidget(ui.text(words, "small", wrap=True, selectable=True))
        self.setMaximumWidth(300)


class Noticed(QFrame):
    def __init__(self, title: str, why: str, severity: str = "medium") -> None:
        super().__init__()
        colour = SEVERITY.get(severity, design.BRAND_B)
        self.setStyleSheet(f"QFrame {{ background: {design.SURFACE}; border: 1px solid {design.LINE};"
                           f" border-left: 3px solid {colour}; border-radius: 10px; }}"
                           " QLabel { background: transparent; border: none; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 10)
        lay.setSpacing(3)
        lay.addWidget(ui.text(title, "small", wrap=True))
        if why:
            lay.addWidget(ui.text(why, "tiny", tone="muted", wrap=True))


class EliPanel(QFrame):
    LOOK_EVERY_MS = 5 * 60 * 1000

    def __init__(self, studio: Studio, project: Any) -> None:
        super().__init__()
        self.studio, self.project = studio, project
        self.folder: Path | None = None
        self._said = _Said()
        self._said.said.connect(self._show)
        self.setObjectName("eli")
        self.setStyleSheet(f"QFrame#eli {{ background: {design.SURFACE}; border-left: 1px solid {design.LINE}; }}")

        mark = QLabel()
        mark.setPixmap(icons.brand_mark(38))
        who = QVBoxLayout()
        who.setSpacing(0)
        who.addWidget(ui.text("ELI", "h2"))
        self.dot = ui.StatusDot()
        self.state = ui.text("", "tiny", tone="muted", wrap=True)
        line = QHBoxLayout()
        line.setSpacing(2)
        line.addWidget(self.dot)
        line.addWidget(self.state, 1)
        who.addLayout(line)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(mark)
        head.addLayout(who, 1)

        self.level = ui.Segmented([(lv.capitalize(), lv) for lv in LEVELS], studio.companion.level)
        self.level.setToolTip("How much ELI says without being asked")
        self.level.changed.connect(self._level)

        self.discuss = QFrame()
        self.discuss.setStyleSheet(f"QFrame {{ background: {design.alpha(design.BRAND_A, 0.14)}; border: 1px solid "
                                   f"{design.alpha(design.BRAND_A, 0.5)}; border-radius: 14px; }}"
                                   " QLabel { background: transparent; border: none; }")
        self.discuss_text = ui.text("", "small", wrap=True, rich=True)
        self.talk = ui.button("Talk it through now", self._talk_now, primary=True)
        self.later = ui.button("Later", self._later, variant="flat")
        d = QVBoxLayout(self.discuss)
        d.setContentsMargins(14, 12, 14, 12)
        d.addWidget(self.discuss_text)
        row = QHBoxLayout()
        row.addWidget(self.talk)
        row.addWidget(self.later)
        row.addStretch(1)
        d.addLayout(row)
        self.discuss.hide()

        self.feed = QVBoxLayout()
        self.feed.setSpacing(10)
        self.feed.addStretch(1)
        feed_box = QWidget()
        feed_box.setLayout(self.feed)
        self.feed_scroll = QScrollArea()
        self.feed_scroll.setWidgetResizable(True)
        self.feed_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.feed_scroll.setWidget(feed_box)
        self.items = QVBoxLayout()
        self.items.setSpacing(8)
        self.intro = ui.text("Ask about the project: what to post next, why a picture works, how to pitch a game. "
                             "ELI also notices what matters (a platform's limit, a licence on an asset) and says so, "
                             "as much as the level allows.", "small", tone="muted", wrap=True)

        self.ask = QLineEdit()
        self.ask.setProperty("bare", True)
        self.ask.setPlaceholderText("Ask ELI about this project…")
        self.ask.returnPressed.connect(self._ask)
        send = ui.icon_button("send", "Ask (Enter)", self._ask, colour=design.BRAND_B)
        box = QFrame()
        box.setStyleSheet(f"QFrame {{ background: {design.RAISED}; border: 1px solid {design.LINE_STRONG};"
                          " border-radius: 14px; }")
        ask_row = QHBoxLayout(box)
        ask_row.setContentsMargins(14, 6, 6, 6)
        ask_row.addWidget(self.ask, 1)
        ask_row.addWidget(send)
        tools = QHBoxLayout()
        tools.addWidget(ui.button("Look now", lambda: self._look(asked=True), icon="eye", variant="flat"))
        tools.addWidget(ui.button("Project folder…", self._choose_folder, icon="folder", variant="flat"))
        tools.addStretch(1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 14)
        lay.setSpacing(12)
        lay.addLayout(head)
        lay.addWidget(self.level)
        lay.addWidget(self.discuss)
        lay.addWidget(ui.eyebrow("Noticed"))
        lay.addLayout(self.items)
        lay.addWidget(ui.eyebrow("Conversation"))
        lay.addWidget(self.intro)
        lay.addWidget(self.feed_scroll, 1)
        lay.addWidget(box)
        lay.addLayout(tools)

        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self._look(asked=False))
        self.timer.start(self.LOOK_EVERY_MS)
        self.refresh()

    def refresh(self) -> None:
        ok, why = self.studio.companion.may_speak_now()
        level = self.studio.companion.level
        if level == "off":
            self.dot.set(design.FAINT)
            self.state.setText("Off: ELI says nothing unasked")
        elif ok:
            self.dot.set(design.GOOD, pulse=True)
            self.state.setText("Watching for what matters")
        else:
            self.dot.set(design.WARN)
            self.state.setText(why)
        while self.items.count():
            item = self.items.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        waiting = self.studio.companion.waiting(4)
        if not waiting:
            self.items.addWidget(ui.text("Nothing yet.", "tiny", tone="faint"))
        for raised in waiting:
            meta = raised.get("metadata") or {}
            self.items.addWidget(Noticed(str(raised.get("title", "")), str(meta.get("why", "")),
                                         str(meta.get("severity", "medium"))))

    def _level(self, level: str) -> None:
        self.studio.settings.companion_level = level
        self.studio.save_settings()
        self.refresh()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "The project's folder")
        if folder:
            self.folder = Path(folder)
            self.studio.companion.watcher(self.folder)

    def _look(self, *, asked: bool) -> None:
        project = self.project.text().strip()

        def work() -> None:
            raised: object
            try:
                raised = self.studio.companion.think(project, self.folder, asked=asked)
            except Exception as exc:
                raised = exc
            self._said.said.emit(raised)

        threading.Thread(target=work, name="eli-creation-companion", daemon=True).start()

    def _ask(self) -> None:
        question = self.ask.text().strip()
        if not question:
            return
        self.ask.clear()
        self._bubble(question, mine=True)
        if not self.studio.main.available:
            self._bubble(f"I need the main model to answer: {self.studio.main.why_unavailable}. Choose one in "
                         "Settings and ask again.", mine=False)
            return
        thinking = self._bubble("Thinking…", mine=False)
        project = self.project.text().strip()

        def work() -> None:
            try:
                ctx = self.studio.companion.context(project, self.folder)
                answer = self.studio.main.generate(
                    system="You are ELI, beside a creator on their project. Answer briefly and specifically.",
                    prompt=f"Project context: {ctx}\n\nThey ask: {question}", max_tokens=600, temperature=0.5)
                self._said.said.emit(("answer", thinking, answer))
            except Exception as exc:
                self._said.said.emit(("answer", thinking, f"I could not answer: {exc}"))

        threading.Thread(target=work, name="eli-creation-ask", daemon=True).start()

    def _bubble(self, words: str, *, mine: bool) -> Bubble:
        self.intro.hide()
        bubble = Bubble(words, mine)
        row = QHBoxLayout()
        if mine:
            row.addStretch(1)
        row.addWidget(bubble)
        if not mine:
            row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        self.feed.insertWidget(self.feed.count() - 1, holder)
        QTimer.singleShot(30, lambda: self.feed_scroll.verticalScrollBar().setValue(self.feed_scroll.verticalScrollBar().maximum()))
        return bubble

    def _show(self, raised: object) -> None:
        if isinstance(raised, Exception):
            self.state.setText(f"ELI could not look: {raised}")
        elif isinstance(raised, tuple) and raised[0] == "answer":
            bubble = raised[1]
            try:
                bubble.findChild(QLabel).setText(str(raised[2]))
            except (AttributeError, RuntimeError):
                self._bubble(str(raised[2]), mine=False)
        elif isinstance(raised, Raised) and raised.kind == "discuss":
            self.discuss_text.setText(f"<b>ELI would like to pause and talk:</b> {raised.title}<br>{raised.why}")
            self._topic = raised.title
            self.discuss.show()
        self.refresh()

    _topic = ""

    def _talk_now(self) -> None:
        self.ask.setText(f"Let's talk about: {self._topic}")
        self.ask.setFocus()
        self._later()

    def _later(self) -> None:
        self.discuss.hide()

