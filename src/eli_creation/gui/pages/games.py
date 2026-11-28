"""Games: a pitch becomes a design (its kind, goal, rules, look), shown as a card; a design becomes
one HTML page anyone can play, opened in the browser from here."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from eli_creation.engines.writing import GameDesign
from eli_creation.gui import components as ui
from eli_creation.gui import design
from eli_creation.gui.gallery import Tile
from eli_creation.gui.pages.base import PromptHistory, StudioPage, scrolled

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job

KIND_WORDS = {"targets": "Tap the targets", "catch": "Catch what falls", "sort": "Sort them", "order": "Put in order",
              "hide": "Find what hides", "range": "Hit the range"}


class Swatches(QWidget):
    def __init__(self, colours: list[str]) -> None:
        super().__init__()
        self.colours = [c for c in colours if isinstance(c, str) and c.startswith("#")][:6]
        self.setFixedHeight(26)
        self.setMinimumWidth(30 * max(1, len(self.colours)))

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for n, colour in enumerate(self.colours):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(colour))
            p.drawRoundedRect(QRectF(n * 30, 1, 24, 24), 7, 7)
        p.end()


class DesignCard(ui.Card):
    def __init__(self, path: Path, spec: dict[str, Any], page: GamesPage) -> None:
        super().__init__(padding=20, spacing=10)
        kind = str(spec.get("kind", "catch"))
        head = QHBoxLayout()
        head.addWidget(ui.text(str(spec.get("title") or "A game"), "h2"), 1)
        head.addWidget(ui.Badge(KIND_WORDS.get(kind, kind).upper(), design.accent("games")))
        self.add(head)
        if spec.get("goal"):
            self.add(ui.text(str(spec["goal"]), "body", tone="subtle", wrap=True))
        rules = [str(r) for r in spec.get("rules", []) if r][:6]
        if rules:
            self.add(ui.text("\n".join(f"•  {r}" for r in rules), "small", wrap=True))
        facts = QHBoxLayout()
        facts.addWidget(Swatches(list(spec.get("palette", []))))
        facts.addSpacing(10)
        for label_text in (f"{spec.get('seconds', 45)} s a round", f"{spec.get('pieces', 12)} pieces"):
            facts.addWidget(ui.Badge(label_text, design.SUBTLE))
        facts.addStretch(1)
        self.add(facts)
        for key, name in (("player", "You"), ("pieces_look", "Pieces"), ("design_notes", "Notes")):
            if spec.get(key):
                self.add(ui.text(f"{name}: {spec[key]}", "small", tone="muted", wrap=True))
        actions = QHBoxLayout()
        playable = kind in GameDesign.BROWSER_KINDS
        make = ui.button("Make it playable", lambda: page.make_playable(str(path)), icon="play", primary=playable)
        make.setEnabled(True)
        make.setToolTip("" if playable else "A browser game of this kind plays as a catching game")
        actions.addWidget(make)
        actions.addWidget(ui.button("Show the design file", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(path.parent))), icon="folder", variant="flat"))
        actions.addStretch(1)
        self.add(actions)


class GamesPage(StudioPage):
    key = "games"
    gallery_kind = "game"
    tile_actions = [("play", "Play it in the browser", "play"), ("playable", "Make it playable", "gamepad")]

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.history = PromptHistory(shell, "games")
        self.pitch = QPlainTextEdit()
        self.pitch.setProperty("prompt", True)
        self.pitch.setPlaceholderText("Catch falling stars before they hit the ground, faster each round…")
        self.pitch.setFixedHeight(96)
        design.set_type(self.pitch, "h3")
        self.kinds = ui.ChipGroup([("Let ELI choose", "")] + [(v, k) for k, v in KIND_WORDS.items()],
                                  chosen=[""], accent=self.accent)
        recent = ui.button("Recent pitches", lambda: self.history.menu(recent, self._use), icon="clock", variant="flat")
        composer = ui.Card(padding=20, spacing=14)
        composer.add(ui.Field("Pitch", self.pitch), ui.hbox(recent, None), ui.Field("Kind of game", self.kinds), self.reason,
                     self.create_button)
        composer.setFixedWidth(460)
        self.design_box = QVBoxLayout()
        self.empty = ui.EmptyState("gamepad", "Your game's design appears here",
                                   "Pitch it in a sentence. ELI designs its rules and look on the main model; "
                                   "then make it playable in any browser.", accent=self.accent)
        self.design_box.addWidget(self.empty)
        right = QVBoxLayout()
        right.addWidget(ui.text("Design", "h3"))
        right.addLayout(self.design_box, 1)
        columns = QHBoxLayout()
        columns.setSpacing(22)
        columns.addWidget(composer, 0, Qt.AlignmentFlag.AlignTop)
        columns.addLayout(right, 1)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(18)
        lay.addLayout(self.header("Games", "Design a game from a pitch, then play it in a browser. Its kinds are "
                                           "the ones ELI VR plays, so a design made here can be set in ELI's rooms."))
        lay.addWidget(self.engines)
        lay.addLayout(columns)
        lay.addLayout(self.gallery_bar("Your games"))
        self.gallery.fit_to_content()
        lay.addWidget(self.gallery)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(body))
        self._design_path = ""

    def request(self) -> dict[str, Any]:
        if self.engines.current == "games.browser":
            design_path = self._design_path or self._latest_design()
            if not design_path:
                raise ValueError("Design a game first, or choose a design in the gallery.")
            return {"design": design_path}
        pitch = self.pitch.toPlainText().strip()
        if not pitch:
            raise ValueError("Write the pitch first.")
        kind = self.kinds.value()
        return {"pitch": pitch + (f"\nMake it a '{kind}' game." if kind else "")}

    def after_submit(self, request: dict[str, Any]) -> None:
        if "pitch" in request:
            self.history.add(self.pitch.toPlainText().strip())

    def _latest_design(self) -> str:
        found = [a for a in self.studio.library.recent(kind="game", limit=30) if a.path.name.endswith(".game.json")]
        return str(found[0].path) if found else ""

    def make_playable(self, design_path: str) -> None:
        self._design_path = design_path
        self.engines.choose("games.browser")
        self.submit()
        self.engines.choose("games.design")

    def show_design(self, path: Path) -> None:
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        while self.design_box.count():
            item = self.design_box.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None and widget is not self.empty:
                widget.deleteLater()
        self.empty.hide()
        self.design_box.addWidget(DesignCard(path, spec, self))
        self._design_path = str(path)

    def finished(self, job: Job) -> None:
        for asset in job.assets:
            path = Path(asset.path)
            if path.name.endswith(".game.json"):
                self.show_design(path)
            elif path.suffix == ".html":
                self.shell.toast("The game is ready to play", "good",
                                 action=("Play", lambda p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))))

    def view(self, tile: Tile) -> None:
        if tile.path.endswith(".game.json"):
            self.show_design(Path(tile.path))
        elif tile.path.endswith(".html"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(tile.path))
        else:
            super().view(tile)

    def act(self, name: str, tile: Tile) -> None:
        if name == "playable":
            if tile.path.endswith(".game.json"):
                self.make_playable(tile.path)
            else:
                self.shell.toast("That one is already a game: choose its design to build it again.", "info")
            return
        super().act(name, tile)

    def _use(self, pitch: str) -> None:
        self.pitch.setPlainText(pitch)
        self.pitch.setFocus()

    def shown(self, **wanted: Any) -> None:
        self.refresh()
        self.load_gallery()
        if self._design_path == "":
            latest = self._latest_design()
            if latest:
                self.show_design(Path(latest))
        if wanted.get("prompt"):
            self.pitch.setPlainText(str(wanted["prompt"]))
        if wanted.get("design"):
            self.show_design(Path(str(wanted["design"])))
            if wanted.get("make_playable"):
                self.make_playable(str(wanted["design"]))
        if wanted.get("create"):
            self.submit()
        elif wanted.get("focus") or wanted.get("prompt"):
            self.pitch.setFocus()
