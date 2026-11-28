"""The library: everything made here, found by kind, project and words in its name, each with its
record of how it was made."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QVBoxLayout

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons
from eli_creation.gui.gallery import Gallery, Tile, open_lightbox
from eli_creation.gui.pages.base import Page

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job

KINDS = [("Everything", ""), ("Images", "image"), ("Films", "video"), ("Sound", "audio"), ("Posts", "post"),
         ("Games", "game"), ("Code", "code"), ("Captions and notes", "note")]
ACTIONS = [("edit", "Edit it", "sliders"), ("to_video", "Add it to a film", "film")]


class LibraryPage(Page):
    key = "library"

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find by name…")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icons.icon("search", design.MUTED, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda _t: self.refresh())
        self.search.setMinimumWidth(280)
        self.kinds = ui.ChipGroup(KINDS, chosen=[""], accent=self.accent)
        self.kinds.changed.connect(self.refresh)
        self.project = QComboBox()
        self.project.currentIndexChanged.connect(lambda _i: self.refresh())
        self.project.setMinimumWidth(200)
        self.size_choice = ui.Segmented([("S", "small"), ("M", "medium"), ("L", "large")],
                                 str(shell.recall("library_size", "medium")), accent=self.accent)
        self.size_choice.setFixedWidth(130)
        self.size_choice.changed.connect(self._size)
        self.count = ui.text("", "small", tone="muted")
        self.gallery = Gallery(size=str(shell.recall("library_size", "medium")), actions=ACTIONS)
        self.gallery.opened.connect(self.view)
        self.gallery.asked.connect(lambda name, tile: self.shell.act_on(name, tile))
        self.empty = ui.EmptyState("library", "Nothing here yet",
                                   "Everything made in any studio is filed here, by project, with a record of the "
                                   "models that made it and their licences.", accent=self.accent)
        filters = QHBoxLayout()
        filters.setSpacing(12)
        filters.addWidget(self.search)
        filters.addWidget(self.project)
        filters.addStretch(1)
        filters.addWidget(self.count)
        filters.addWidget(self.size_choice)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(16)
        lay.addLayout(self.header("Library", "Everything made here, as ordinary files any program opens, each with "
                                             "its record: what made it, under what licence, and whether a model did."))
        lay.addLayout(filters)
        lay.addWidget(self.kinds)
        lay.addWidget(self.gallery, 1)
        lay.addWidget(self.empty, 1)

    def _size(self, name: str) -> None:
        self.gallery.set_size(name)
        self.shell.remember("library_size", name)

    def _projects(self) -> None:
        current = self.project.currentData()
        self.project.blockSignals(True)
        self.project.clear()
        self.project.addItem("Every project", "")
        for name in self.studio.library.projects():
            self.project.addItem(name, name)
        index = self.project.findData(current)
        self.project.setCurrentIndex(max(0, index))
        self.project.blockSignals(False)

    def shown(self, **wanted: Any) -> None:
        self._projects()
        self.refresh()
        self.search.setFocus()

    def refresh(self) -> None:
        words = self.search.text().strip().lower()
        assets = self.studio.library.recent(kind=self.kinds.value(), project=str(self.project.currentData() or ""),
                                            limit=2000)
        tiles = [Tile.from_asset(a) for a in assets if not words or words in f"{a.title} {a.path.name}".lower()]
        self.gallery.set_tiles(tiles)
        self.count.setText(f"{len(tiles)} item{'s' if len(tiles) != 1 else ''}")
        self.gallery.setVisible(bool(tiles))
        self.empty.setVisible(not tiles)

    def view(self, tile: Tile) -> None:
        box = open_lightbox(self.shell, self.gallery.tiles(), tile, ACTIONS)
        box.acted.connect(lambda name, t: self.shell.act_on(name, t))

    def on_job(self, job: Job) -> None:
        if job.finished and self.shell.current == "library":
            self.refresh()

