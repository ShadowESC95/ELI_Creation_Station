"""Videos: a storyboard of pictures in order, played here as it will move (each held for its time,
crossfading into the next) before it is made, and the animatics made, played in the viewer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons, imaging
from eli_creation.gui.gallery import Gallery, Tile
from eli_creation.gui.pages.base import StudioPage, scrolled

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow

SHAPES = [("3:2", "landscape", 3 / 2), ("16:9", "wide", 16 / 9), ("1:1", "square", 1.0),
          ("2:3", "portrait", 2 / 3), ("9:16", "story", 9 / 16)]
RATIO = {key: ratio for _, key, ratio in SHAPES}


class Player(QWidget):
    """Plays the storyboard as the animatic will: each picture held, then crossfaded."""

    def __init__(self) -> None:
        super().__init__()
        self.images: list[QImage] = []
        self.hold_ms = 2000
        self.fade_ms = 400
        self.ratio = 3 / 2
        self.t = 0
        self.playing = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setMinimumSize(420, 260)

    def set_frames(self, paths: list[str], hold_s: float, ratio: float) -> None:
        self.images = []
        for path in paths:
            try:
                self.images.append(imaging.load(path, 960))
            except Exception:
                continue
        self.hold_ms = max(200, int(hold_s * 1000))
        self.ratio = ratio
        self.t = min(self.t, self.length())
        self.update()

    def length(self) -> int:
        return len(self.images) * self.hold_ms

    def play(self) -> None:
        self.playing = not self.playing
        self._timer.start(33) if self.playing else self._timer.stop()
        self.update()

    def _tick(self) -> None:
        if not self.images:
            return
        self.t = (self.t + 33) % max(1, self.length())
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(0, 0, 0, -26)
        w = min(area.width(), area.height() * self.ratio)
        h = w / self.ratio
        frame = QRectF(area.center().x() - w / 2, area.center().y() - h / 2, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#000000"))
        p.drawRoundedRect(frame, 12, 12)
        if self.images:
            n = len(self.images)
            index = min(n - 1, self.t // self.hold_ms)
            into = self.t - index * self.hold_ms
            self._cover(p, frame, self.images[index], 1.0)
            fade_from = self.hold_ms - self.fade_ms
            if into > fade_from and n > 1:
                self._cover(p, frame, self.images[(index + 1) % n], (into - fade_from) / self.fade_ms)
        else:
            p.setPen(QColor(design.FAINT))
            p.drawText(frame, Qt.AlignmentFlag.AlignCenter, "Add pictures to the storyboard to see it move")
        bar = QRectF(frame.left(), self.height() - 12, frame.width(), 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(design.LINE_STRONG))
        p.drawRoundedRect(bar, 2, 2)
        if self.length():
            p.setBrush(design.brand_gradient(bar.left(), 0, bar.right(), 0, design.accent("videos"), design.BRAND_B))
            p.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * self.t / self.length(), 4), 2, 2)
        p.end()

    @staticmethod
    def _cover(p: QPainter, frame: QRectF, image: QImage, opacity: float) -> None:
        scale = max(frame.width() / max(1, image.width()), frame.height() / max(1, image.height()))
        w, h = image.width() * scale, image.height() * scale
        p.save()
        p.setOpacity(opacity)
        clip = frame
        p.setClipRect(clip)
        p.drawImage(QRectF(frame.center().x() - w / 2, frame.center().y() - h / 2, w, h), image)
        p.restore()


class Storyboard(QListWidget):
    """The pictures in order; drag one to move it."""

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setIconSize(QSize(150, 100))
        self.setGridSize(QSize(166, 136))
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setMovement(QListView.Movement.Snap)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setFixedHeight(156)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setStyleSheet(f"QListWidget {{ background: {design.SURFACE}; border: 1px dashed {design.LINE_STRONG};"
                           " border-radius: 14px; padding: 8px; }")

    def add(self, path: str) -> None:
        if not Path(path).is_file():
            return
        try:
            image = imaging.load(path, 300)
        except Exception:
            return
        pix = QPixmap(150, 100)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scale = max(150 / image.width(), 100 / image.height())
        w, h = image.width() * scale, image.height() * scale
        p.drawImage(QRectF((150 - w) / 2, (100 - h) / 2, w, h), image)
        p.end()
        item = QListWidgetItem(QIcon(pix), f"{self.count() + 1}")
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(Path(path).name)
        self.addItem(item)

    def paths(self) -> list[str]:
        return [str(self.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.count())]

    def renumber(self) -> None:
        for i in range(self.count()):
            self.item(i).setText(str(i + 1))


class PickPictures(QDialog):
    """Choose pictures from the library."""

    def __init__(self, parent: QWidget, studio: Any) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pictures from the library")
        self.resize(900, 640)
        self.gallery = Gallery(size="small")
        self.gallery.set_tiles([Tile.from_asset(a) for a in studio.library.recent(kind="image", limit=300)])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.text("Choose the pictures, in the order they should play (Ctrl-click for several)",
                              "small", tone="muted"))
        lay.addWidget(self.gallery, 1)
        lay.addWidget(buttons)

    def chosen(self) -> list[str]:
        return [t.path for t in self.gallery.selected_tiles()]


class VideosPage(StudioPage):
    key = "videos"
    gallery_kind = "video"
    tile_actions = [("play", "Play it in its program", "play")]

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.board = Storyboard()
        self.board.model().rowsMoved.connect(lambda *_: self._changed())
        self.board.model().rowsInserted.connect(lambda *_: self._changed())
        self.board.model().rowsRemoved.connect(lambda *_: self._changed())
        self.player = Player()
        self.play_button = ui.button("Play", self._play, icon="play")
        self.title = QLineEdit(str(shell.recall("videos_title", "Animatic")))
        self.seconds = ui.SliderField("Each picture holds", 0.5, 8.0, float(shell.recall("videos_seconds", 2.0)),
                                      step=0.1, fmt="{:.1f} s", icon="clock")
        self.seconds.changed.connect(lambda _v: self._changed())
        glyphs = {key: (lambda c, r=ratio: ui.aspect_glyph(r, c)) for _, key, ratio in SHAPES}
        self.shape = ui.Segmented([(n, k) for n, k, _ in SHAPES], str(shell.recall("videos_shape", "landscape")),
                                  glyphs=glyphs, accent=self.accent)
        self.shape.changed.connect(lambda _v: self._changed())
        self.length = ui.text("", "small", tone="muted")

        tools = QHBoxLayout()
        tools.addWidget(ui.button("From the library", self._pick, icon="library"))
        tools.addWidget(ui.button("Files…", self._files, icon="upload"))
        tools.addWidget(ui.button("The latest images", self._latest, icon="sparkles", variant="flat"))
        tools.addStretch(1)
        tools.addWidget(ui.button("Remove", self._remove, icon="trash", variant="flat"))
        tools.addWidget(ui.button("Clear", self.board.clear, icon="x", variant="flat"))
        board_card = ui.Card(padding=18)
        board_card.add(ui.text("Storyboard", "h3"), ui.text("Drag the pictures into the order they play in.",
                                                             "small", tone="muted"), self.board, tools)

        settings = ui.Card(padding=18, spacing=14)
        settings.add(ui.Field("Title", self.title), self.seconds, ui.Field("Shape", self.shape), self.length, None,
                     self.reason, self.create_button)
        settings.setFixedWidth(400)
        preview = ui.Card(padding=18)
        head = QHBoxLayout()
        head.addWidget(ui.text("Preview", "h3"))
        head.addStretch(1)
        head.addWidget(self.play_button)
        preview.add(head, self.player)
        middle = QHBoxLayout()
        middle.setSpacing(18)
        middle.addWidget(preview, 1)
        middle.addWidget(settings)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(18)
        lay.addLayout(self.header("Videos", "Animatics on any machine: pictures in order, each held and crossfaded. "
                                            "Text-to-video, narration, captions and music arrive as their models do."))
        lay.addWidget(self.engines)
        lay.addWidget(board_card)
        lay.addLayout(middle)
        lay.addLayout(self.gallery_bar("Your animatics"))
        self.gallery.fit_to_content()
        lay.addWidget(self.gallery)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(body))
        self._changed()

    def _changed(self) -> None:
        self.board.renumber()
        paths = self.board.paths()
        self.player.set_frames(paths, self.seconds.value(), RATIO.get(self.shape.value(), 1.5))
        total = len(paths) * self.seconds.value()
        self.length.setText(f"{len(paths)} picture(s) · {total:.1f} seconds" if paths else "No pictures yet")
        self.shell.remember("videos_seconds", self.seconds.value())
        self.shell.remember("videos_shape", self.shape.value())

    def _play(self) -> None:
        self.player.play()
        self.play_button.setText("Pause" if self.player.playing else "Play")
        self.play_button.setIcon(icons.icon("pause" if self.player.playing else "play", design.SUBTLE, 18))

    def _pick(self) -> None:
        dialog = PickPictures(self, self.studio)
        if dialog.exec():
            for path in dialog.chosen():
                self.board.add(path)

    def _files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Pictures", "", "Pictures (*.png *.jpg *.jpeg *.webp)")
        for path in files:
            self.board.add(path)

    def _latest(self) -> None:
        for asset in reversed(self.studio.library.recent(kind="image", limit=6)):
            self.board.add(str(asset.path))

    def _remove(self) -> None:
        for item in self.board.selectedItems():
            self.board.takeItem(self.board.row(item))

    def request(self) -> dict[str, Any]:
        paths = self.board.paths()
        if not paths:
            raise ValueError("Add pictures to the storyboard first.")
        self.shell.remember("videos_title", self.title.text())
        return {"images": paths, "title": self.title.text().strip() or "Animatic", "seconds": self.seconds.value(),
                "aspect": self.shape.value()}

    def shown(self, **wanted: Any) -> None:
        self.refresh()
        self.load_gallery()
        for path in wanted.get("add") or []:
            self.board.add(str(path))
        if wanted.get("add"):
            self.shell.toast(f"Added to the storyboard: {len(wanted['add'])} picture(s)", "good")

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        if self.player.playing:
            self._play()
        super().hideEvent(event)
