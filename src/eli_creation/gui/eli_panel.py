"""ELI beside the tabs: what ELI noticed, its requests to pause and talk, and a box to ask it."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from eli_creation.companion.companion import Raised
from eli_creation.gui import theme
from eli_creation.gui.widgets import button, label, row

if TYPE_CHECKING:
    from eli_creation.services import Studio


class _Said(QObject):
    said = Signal(object)


class EliPanel(QWidget):
    LOOK_EVERY_MS = 5 * 60 * 1000

    def __init__(self, studio: Studio, project: QLineEdit) -> None:
        super().__init__()
        self.studio, self.project = studio, project
        self.folder: Path | None = None
        self._said = _Said()
        self._said.said.connect(self._show)
        lay = QVBoxLayout(self)
        lay.addWidget(label("ELI", "title"))
        self.state = label("", "muted", wrap=True)
        lay.addWidget(self.state)
        self.discuss = QLabel()
        self.discuss.setWordWrap(True)
        self.discuss.setStyleSheet(f"border: 2px solid {theme.ACCENT}; border-radius: 8px; padding: 8px;")
        self.discuss.hide()
        self.talk = button("Talk it through now", self._talk_now, kind="primary")
        self.later = button("Later", self._later)
        self.talk.hide()
        self.later.hide()
        lay.addWidget(self.discuss)
        lay.addWidget(row(self.talk, self.later))
        lay.addWidget(label("Noticed", "navname"))
        self.items = QListWidget()
        lay.addWidget(self.items, 1)
        self.ask = QLineEdit()
        self.ask.setPlaceholderText("Ask ELI about this project…")
        self.ask.returnPressed.connect(self._ask)
        lay.addWidget(self.ask)
        lay.addWidget(row(button("Look now", lambda: self._look(asked=True)),
                          button("Project folder…", self._choose_folder)))
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self._look(asked=False))
        self.timer.start(self.LOOK_EVERY_MS)
        self.refresh()

    def refresh(self) -> None:
        ok, why = self.studio.companion.may_speak_now()
        level = self.studio.companion.level
        self.state.setText(f"Level: {level}. " + ("Watching for what matters." if ok else why))
        self.items.clear()
        for item in self.studio.companion.waiting(12):
            text = f"{item.get('title', '')}\n{(item.get('metadata') or {}).get('why', '')}"
            self.items.addItem(QListWidgetItem(text))

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
        project = self.project.text().strip()

        def work() -> None:
            try:
                ctx = self.studio.companion.context(project, self.folder)
                answer = self.studio.main.generate(
                    system="You are ELI, beside a creator on their project. Answer briefly and specifically.",
                    prompt=f"Project context: {ctx}\n\nThey ask: {question}", max_tokens=600, temperature=0.5)
                self._said.said.emit(("answer", question, answer))
            except Exception as exc:
                self._said.said.emit(exc)

        threading.Thread(target=work, name="eli-creation-ask", daemon=True).start()

    def _show(self, raised: object) -> None:
        if isinstance(raised, Exception):
            self.state.setText(f"ELI could not look: {raised}")
        elif isinstance(raised, tuple) and raised[0] == "answer":
            self.items.insertItem(0, QListWidgetItem(f"You: {raised[1]}\nELI: {raised[2]}"))
        elif isinstance(raised, Raised) and raised.kind == "discuss":
            self.discuss.setText(f"<b>ELI would like to pause and talk:</b> {raised.title}<br>{raised.why}")
            self.discuss.show()
            self.talk.show()
            self.later.show()
        self.refresh()

    def _talk_now(self) -> None:
        self.ask.setText(f"Let's talk about: {self.discuss.text().split('</b>', 1)[-1].split('<br>')[0].strip()}")
        self.ask.setFocus()
        self._later()

    def _later(self) -> None:
        self.discuss.hide()
        self.talk.hide()
        self.later.hide()
