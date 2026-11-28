"""Coding: describe the task; ELI v3's coding agent plans, writes, runs and repairs the code against
tests it writes for it, on the main model. The code is shown highlighted, with whether it passed."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from eli_creation.gui import components as ui
from eli_creation.gui import design
from eli_creation.gui.gallery import Tile
from eli_creation.gui.pages.base import PromptHistory, StudioPage, scrolled

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job

LANGUAGES = [("Python", "python"), ("JavaScript", "javascript"), ("TypeScript", "typescript"), ("HTML", "html"),
             ("GDScript", "gdscript")]
KEYWORDS = (
    "and as assert async await break case catch class const continue def default del do elif else enum except export "
    "extends false finally for from func function if import in interface is lambda let match new nonlocal not null or "
    "pass raise return self signal static super switch this throw true try type var void while with yield None True "
    "False"
).split()


def _format(colour: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(colour))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    fmt.setFontItalic(italic)
    return fmt


class Highlighter(QSyntaxHighlighter):
    """Enough colour to read code at a glance: keywords, strings, numbers, comments, calls."""

    RULES = [
        (re.compile(r"\b(" + "|".join(KEYWORDS) + r")\b"), _format("#c4b5fd", bold=True)),
        (re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\()"), _format("#7dd3fc")),
        (re.compile(r"\b\d+(\.\d+)?\b"), _format("#fca5a5")),
        (re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|`[^`\n]*`"), _format("#86efac")),
        (re.compile(r"</?[A-Za-z][^>]*>"), _format("#7dd3fc")),
        (re.compile(r"(#|//).*$"), _format("#6b7280", italic=True)),
    ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for pattern, fmt in self.RULES:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


def split_notes(text: str) -> tuple[str, dict[str, Any]]:
    """The code, and the agent's notes the engine appends as a last comment line."""
    lines = text.rstrip().splitlines()
    if lines and lines[-1].startswith("# {"):
        try:
            return "\n".join(lines[:-1]).rstrip() + "\n", dict(json.loads(lines[-1][2:]))
        except ValueError:
            pass
    return text, {}


class CodingPage(StudioPage):
    key = "coding"
    gallery_kind = "code"
    tile_actions = [("view_code", "Show it here", "code")]

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.history = PromptHistory(shell, "coding")
        self.task = QPlainTextEdit()
        self.task.setProperty("prompt", True)
        self.task.setPlaceholderText("What should the code do? Its inputs, what it gives back, any edge cases…")
        self.task.setFixedHeight(120)
        design.set_type(self.task, "h3")
        recent = ui.button("Recent tasks", lambda: self.history.menu(recent, self._use), icon="clock", variant="flat")
        self.language = ui.ChipGroup(LANGUAGES, chosen=[str(shell.recall("coding_language", "python"))],
                                     accent=self.accent)
        self.tests = ui.Switch("Write and run tests", bool(shell.recall("coding_tests", True)))
        self.seconds = ui.SliderField("Time allowed", 30, 1800, float(shell.recall("coding_seconds", 240)), step=30,
                                      fmt="{:.0f} s", icon="clock")
        composer = ui.Card(padding=20, spacing=14)
        composer.add(ui.Field("Task", self.task), ui.hbox(recent, None), ui.Field("Language", self.language), self.tests,
                     self.seconds, self.reason, self.create_button)
        composer.setFixedWidth(460)

        self.code = QPlainTextEdit()
        self.code.setReadOnly(True)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        self.code.setFont(mono)
        self.code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code.setPlaceholderText("The code appears here, with whether it passed the tests the agent wrote.")
        self.code.setStyleSheet(f"QPlainTextEdit {{ background: {design.INK}; border: 1px solid {design.LINE};"
                                " border-radius: 14px; padding: 14px; }")
        self.highlighter = Highlighter(self.code.document())
        self.file_name = ui.text("", "small", tone="subtle")
        self.verdict = ui.Badge("", design.MUTED)
        self.verdict.hide()
        self.code_path = ""
        head = QHBoxLayout()
        head.addWidget(ui.text("Code", "h3"))
        head.addWidget(self.file_name)
        head.addWidget(self.verdict)
        head.addStretch(1)
        head.addWidget(ui.button("Copy", self._copy, icon="copy", variant="flat"))
        head.addWidget(ui.button("Open", self._open, icon="external", variant="flat"))
        right = QVBoxLayout()
        right.addLayout(head)
        right.addWidget(self.code, 1)
        columns = QHBoxLayout()
        columns.setSpacing(22)
        columns.addWidget(composer, 0, Qt.AlignmentFlag.AlignTop)
        columns.addLayout(right, 1)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(18)
        lay.addLayout(self.header("Coding", "ELI v3's coding agent on the main model: it plans, writes, runs and "
                                            "repairs code against tests it writes. Scripts, tools, web pages, "
                                            "game logic."))
        lay.addWidget(self.engines)
        lay.addLayout(columns)
        lay.addLayout(self.gallery_bar("Your code"))
        self.gallery.set_size("small")
        self.gallery.fit_to_content()
        lay.addWidget(self.gallery)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(body))

    def request(self) -> dict[str, Any]:
        task = self.task.toPlainText().strip()
        if not task:
            raise ValueError("Describe the task first.")
        self.shell.remember("coding_language", self.language.value())
        self.shell.remember("coding_tests", self.tests.isChecked())
        self.shell.remember("coding_seconds", self.seconds.value())
        return {"task": task, "language": self.language.value(), "tests": self.tests.isChecked(),
                "seconds": int(self.seconds.value())}

    def after_submit(self, request: dict[str, Any]) -> None:
        self.history.add(request["task"])

    def show_code(self, path: str, text: str | None = None) -> None:
        try:
            raw = text if text is not None else Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.shell.toast(str(exc), "warn")
            return
        code, notes = split_notes(raw)
        self.code.setPlainText(code)
        self.code_path = path
        self.file_name.setText(Path(path).name if path else "")
        if notes:
            solved = bool(notes.get("solved"))
            self.verdict.setText("Passed its tests" if solved else f"Not solved: {notes.get('message', '')}"[:60])
            self.verdict.set_colour(design.GOOD if solved else design.WARN)
            self.verdict.show()
        else:
            self.verdict.hide()

    def finished(self, job: Job) -> None:
        path = str(job.assets[0].path) if job.assets else ""
        if job.text or path:
            self.show_code(path, job.text or None)

    def view(self, tile: Tile) -> None:
        self.show_code(tile.path)

    def act(self, name: str, tile: Tile) -> None:
        if name == "view_code":
            self.show_code(tile.path)
            return
        super().act(name, tile)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.code.toPlainText())
        self.shell.toast("Code copied", "good")

    def _open(self) -> None:
        if self.code_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.code_path))

    def _use(self, task: str) -> None:
        self.task.setPlainText(task)
        self.task.setFocus()

    def shown(self, **wanted: Any) -> None:
        self.refresh()
        self.load_gallery()
        if wanted.get("path"):
            self.show_code(str(wanted["path"]))
        if wanted.get("prompt"):
            self.task.setPlainText(str(wanted["prompt"]))
        if wanted.get("create"):
            self.submit()
        elif wanted.get("focus") or wanted.get("prompt"):
            self.task.setFocus()
