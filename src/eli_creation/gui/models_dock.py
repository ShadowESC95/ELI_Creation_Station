"""The models dock: ELI's main model and every specialist, what each is doing now, and the means to
load or let go of them.

ELI's main model stays with the person (it answers, plans and writes). Specialists (a picture model,
a voice, a listener) are loaded by the model manager when a job needs one and let go when idle, so
the machine's memory goes to the work in hand. Here the person sees that, and can let go of any of
them at once.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from eli_creation.gui import components as ui
from eli_creation.gui import design

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow

STATE_COLOURS = {"ready": design.GOOD, "busy": design.BRAND_B, "loading": design.BRAND_B, "unloading": design.WARN,
                 "stepped_aside": design.WARN, "failed": design.BAD, "unavailable": design.BAD,
                 "unloaded": design.FAINT}
VIA = {"eli_v3": "ELI v3 (this window runs inside it)", "eli_v3_server": "ELI v3, running on this machine",
       "gguf": "a model file on this machine", "openai": "a model server you chose", "none": "none chosen"}


class ModelsDock(QFrame):
    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell, Qt.WindowType.Popup)
        self.shell = shell
        self.setObjectName("dock")
        self.setStyleSheet(f"QFrame#dock {{ background: {design.SURFACE}; border: 1px solid {design.HAIRLINE}; "
                           "border-radius: 14px; }")
        self.setFixedWidth(440)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(10)

    def refresh(self) -> None:
        from eli_creation.gui.socials_tools import clear

        clear(self.body)
        studio = self.shell.studio
        main = studio.main
        self.body.addWidget(ui.eyebrow("ELI's main model"))
        card = ui.Card(soft=True, padding=12, spacing=6)
        head = QHBoxLayout()
        dot = ui.StatusDot()
        dot.set(STATE_COLOURS.get(main.state, design.MUTED), pulse=main.state in ("loading", "busy"))
        head.addWidget(dot)
        head.addWidget(ui.text(main.name, "small"), 1)
        head.addWidget(ui.text(main.state.replace("_", " "), "tiny", tone="muted"))
        card.add(head, ui.text(f"From {VIA.get(getattr(main, 'via', main.source), main.source)}", "tiny",
                               tone="subtle", wrap=True))
        if not main.available:
            why = ui.text(main.why_unavailable, "tiny", tone="warn", wrap=True)
            why.setFixedWidth(self.width() - 60)  # its height is known before the dock is shown
            why.setMinimumHeight(why.heightForWidth(self.width() - 60))
            card.add(why)
        if main.memory_mb:
            card.add(ui.text(f"{main.memory_mb / 1024:.1f} GB on {main.device or 'this machine'}", "tiny",
                             tone="muted"))
        tools = QHBoxLayout()
        if main.source == "gguf" and main.state in ("unloaded", "failed"):
            tools.addWidget(ui.button("Load it", self._load_main, icon="cpu", variant="flat"))
        if main.source == "gguf" and main.state == "ready":
            tools.addWidget(ui.button("Let it go", self._unload_main, icon="x", variant="flat"))
        tools.addWidget(ui.button("Choose in Settings", lambda: self._go("settings"), icon="settings", variant="flat"))
        tools.addStretch(1)
        card.add(tools)
        self.body.addWidget(card)

        self.body.addWidget(ui.eyebrow("Specialists, loaded when a job needs them"))
        specialists = [s for s in studio.manager.status() if s.role == "specialist"]
        if not specialists:
            self.body.addWidget(ui.text("None in the catalogue.", "tiny", tone="faint"))
        for status in specialists:
            self.body.addWidget(self._row(status))
        foot = QHBoxLayout()
        foot.addWidget(ui.button("Let go of every idle one", self._unload_idle, icon="cpu", variant="flat"))
        foot.addStretch(1)
        self.body.addLayout(foot)
        self.adjustSize()

    def _row(self, status: Any) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(4, 2, 4, 2)
        dot = ui.StatusDot()
        dot.set(STATE_COLOURS.get(status.state, design.MUTED), pulse=status.state in ("loading", "busy"))
        lay.addWidget(dot)
        words = QVBoxLayout()
        words.setSpacing(0)
        words.addWidget(ui.text(status.title, "small"))
        what = status.state if status.state != "unloaded" else "not loaded: loads when a job needs it"
        if status.memory_mb:
            what += f" · {status.memory_mb / 1024:.1f} GB on {status.device}"
        if status.state == "ready" and status.idle_seconds > 5:
            what += f" · idle {int(status.idle_seconds)} s"
        if status.detail:
            what += f" · {status.detail[:90]}"
        words.addWidget(ui.text(what, "tiny", tone="muted", wrap=True))
        lay.addLayout(words, 1)
        if status.state in ("ready", "failed"):
            lay.addWidget(ui.icon_button("x", "Let it go now", partial(self._unload, status.id), size=14))
        return row

    def _go(self, key: str) -> None:
        self.hide()
        self.shell.go(key)

    def _load_main(self) -> None:
        self.shell.studio.main.load_in_background()
        self.shell.toast("Loading ELI's main model", "info")
        self.hide()

    def _unload_main(self) -> None:
        self.shell.studio.main.unload()
        self.refresh()

    def _unload(self, model_id: str) -> None:
        self.shell.studio.manager.unload(model_id)
        self.refresh()

    def _unload_idle(self) -> None:
        gone = self.shell.studio.manager.unload_idle()
        self.shell.toast(f"Let go of {len(gone)} model(s)" if gone else "No idle model to let go of", "good")
        self.refresh()

    def show_at(self, widget: QWidget, *, above: bool = False) -> None:
        self.refresh()
        at = widget.mapToGlobal(widget.rect().bottomLeft() if not above else widget.rect().topLeft())
        x = max(0, min(at.x(), self.shell.mapToGlobal(self.shell.rect().topRight()).x() - self.width() - 8))
        y = at.y() - self.height() - 6 if above else at.y() + 6
        self.move(x, y)
        self.show()
