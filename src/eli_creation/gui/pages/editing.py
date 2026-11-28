"""Editing: a picture on a canvas, the tools beside it, and every change shown as it is made.

The preview is made by the very operations the saved edit uses (engines.visual.ImageEdits.apply),
on a smaller copy and off the window's thread, so what is seen is what is saved. Hold Compare (or
the backslash key) to see the original.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image
from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QSpinBox,
    QVBoxLayout,
)

from eli_creation.engines.visual import ImageEdits
from eli_creation.gui import components as ui
from eli_creation.gui import design, imaging
from eli_creation.gui.gallery import Gallery, Tile, _Zoomable
from eli_creation.gui.pages.base import StudioPage, scrolled

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow

CROPS = [("Keep", "", 0.0), ("1:1", "1:1", 1.0), ("4:5", "4:5", 0.8), ("9:16", "9:16", 9 / 16), ("16:9", "16:9", 16 / 9),
         ("3:2", "3:2", 1.5)]
PREVIEW_SIDE = 1400


class Previewer(QObject):
    """Applies the edits to the smaller copy, the newest request winning."""

    made = Signal(int, QImage)

    def __init__(self) -> None:
        super().__init__()
        self._edits = ImageEdits()
        self._lock = threading.Lock()
        self._wanted = 0

    def run(self, image: Image.Image, ops: list[dict[str, Any]]) -> int:
        with self._lock:
            self._wanted += 1
            ticket = self._wanted

        def work() -> None:
            try:
                result = image
                for op in ops:
                    if op.get("op") in ("resize", "upscale"):
                        continue  # the size changes on saving; the preview shows the look
                    result = self._edits.apply(result, op)
                with self._lock:
                    current = ticket == self._wanted
                if current:
                    self.made.emit(ticket, imaging.to_qimage(result))
            except Exception:
                return

        threading.Thread(target=work, name="eli-creation-preview", daemon=True).start()
        return ticket


class Canvas(_Zoomable):
    dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setStyleSheet(f"QGraphicsView {{ background: {design.SURFACE}; border: 1px solid {design.LINE};"
                           " border-radius: 16px; }")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: Any) -> None:  # noqa: N802
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile() and imaging.is_picture(url.toLocalFile()):
                self.dropped.emit(url.toLocalFile())
                return


class EditingPage(StudioPage):
    key = "editing"
    gallery_kind = ""

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.path = ""
        self.original: Image.Image | None = None
        self.original_q = QImage()
        self.edited_q = QImage()
        self.rotation = 0
        self.flipped = False
        self.previewer = Previewer()
        self.previewer.made.connect(self._preview_made)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(90)
        self._debounce.timeout.connect(self._render)

        # the canvas
        self.canvas = Canvas()
        self.canvas.dropped.connect(self.open_path)
        self.canvas.setMinimumHeight(440)
        self.compare = ui.button("Hold to compare", None, icon="eye", variant="flat",
                                 tip="Hold to see the original (or the \\ key)")
        self.compare.pressed.connect(lambda: self._show(original=True))
        self.compare.released.connect(lambda: self._show(original=False))
        self.size_note = ui.text("", "small", tone="muted")
        canvas_bar = QHBoxLayout()
        canvas_bar.addWidget(ui.button("Open…", self._open, icon="upload"))
        canvas_bar.addWidget(self.compare)
        canvas_bar.addWidget(ui.icon_button("maximize", "Fit to the canvas", self.canvas.fit))
        canvas_bar.addStretch(1)
        canvas_bar.addWidget(self.size_note)
        self.empty = ui.EmptyState("sliders", "Drop a picture here",
                                   "Or open one, or choose from your latest pictures below. Every change shows as "
                                   "you make it.", accent=self.accent,
                                   action=ui.button("Open a picture…", self._open, icon="upload"))
        self.strip = Gallery(size="small")
        self.strip.setFlow(QListView.Flow.LeftToRight)
        self.strip.setWrapping(False)
        self.strip.setFixedHeight(150)
        self.strip.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.strip.cell_size = lambda: QSize(140, 140)  # type: ignore[method-assign]
        self.strip.opened.connect(lambda t: self.open_path(t.path))
        self.strip.clicked.connect(lambda i: self.open_path(i.data(Qt.ItemDataRole.UserRole).path))
        centre = QVBoxLayout()
        centre.setSpacing(10)
        centre.addLayout(canvas_bar)
        centre.addWidget(self.empty, 1)
        centre.addWidget(self.canvas, 1)
        centre.addWidget(ui.text("Your latest pictures", "small", tone="subtle"))
        centre.addWidget(self.strip)

        # the tools
        self.crop = ui.ChipGroup([(n, k) for n, k, _ in CROPS], chosen=[""], accent=self.accent)
        self.crop.changed.connect(self._changed)
        turn = QHBoxLayout()
        turn.addWidget(ui.button("Left", lambda: self._turn(-90), icon="rotate_left"))
        turn.addWidget(ui.button("Right", lambda: self._turn(90), icon="rotate_right"))
        self.flip = ui.button("Mirror", self._mirror, icon="flip")
        self.flip.setCheckable(True)
        turn.addWidget(self.flip)
        turn.addStretch(1)
        self.brightness = ui.SliderField("Brightness", 0.2, 2.5, 1.0, icon="sun")
        self.contrast = ui.SliderField("Contrast", 0.2, 2.5, 1.0, icon="contrast")
        self.saturation = ui.SliderField("Colour", 0.0, 2.5, 1.0, icon="droplet")
        for slider in (self.brightness, self.contrast, self.saturation):
            slider.changed.connect(self._changed)
        self.auto = ui.Switch("Auto contrast")
        self.sharpen = ui.Switch("Sharpen")
        self.grey = ui.Switch("Black and white")
        for switch in (self.auto, self.sharpen, self.grey):
            switch.toggled.connect(self._changed)
        self.caption = QLineEdit()
        self.caption.setPlaceholderText("Words along the bottom")
        self.caption.textChanged.connect(self._changed)
        self.width_box = QSpinBox()
        self.width_box.setRange(0, 8192)
        self.width_box.setSpecialValueText("Keep its width")
        self.width_box.setSuffix(" px")
        self.width_box.valueChanged.connect(self._sized)
        self.enlarge = ui.SliderField("Enlarge", 1.0, 4.0, 1.0, step=0.25, fmt="×{:.2f}", icon="maximize")
        self.enlarge.changed.connect(self._sized)
        self.format = ui.Segmented([("PNG", "png"), ("WebP", "webp"), ("JPEG", "jpg")],
                                   str(shell.recall("editing_format", "png")), accent=self.accent)
        self.format.changed.connect(lambda v: shell.remember("editing_format", v))

        frame = ui.Section("Frame")
        frame.add(self.crop, turn)
        light = ui.Section("Light and colour")
        light.add(self.brightness, self.contrast, self.saturation)
        finish = ui.Section("Finish")
        finish.add(self.auto, self.sharpen, self.grey, ui.Field("Caption", self.caption))
        size = ui.Section("Size and format", opened=False)
        size.add(ui.Field("Width", self.width_box), self.enlarge, ui.Field("Save as", self.format))
        tools = ui.Card(padding=18, spacing=6)
        tools.add(frame, ui.hairline(), light, ui.hairline(), finish, ui.hairline(), size, None,
                  ui.button("Start again", self.reset, icon="refresh", variant="flat"), self.reason, self.create_button)
        self.create_button.setText("Save the edit")
        tools_scroll = scrolled(tools)
        tools_scroll.setFixedWidth(360)

        columns = QHBoxLayout()
        columns.setSpacing(18)
        columns.addLayout(centre, 1)
        columns.addWidget(tools_scroll)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(16)
        lay.addLayout(self.header("Editing", "Crop to a platform's shape, turn, tune the light, caption, resize. "
                                             "An edit of AI output stays marked as AI; an edit of your own photo "
                                             "never claims to be."))
        lay.addLayout(columns, 1)
        compare_key = QShortcut(QKeySequence("\\"), self)
        compare_key.activated.connect(lambda: self._show(original=True))
        self._show_empty(True)

    # ── the picture ──
    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "A picture", "", "Pictures (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        try:
            self.original = imaging.load_pil(path, PREVIEW_SIDE)
            with Image.open(path) as im:
                self._full = im.size
        except Exception as exc:
            self.shell.toast(f"That picture could not be opened: {exc}", "warn")
            return
        self.path = path
        self.original_q = imaging.to_qimage(self.original)
        self.reset(keep_picture=True)
        self._show_empty(False)
        self.canvas.show_image(self.original_q)
        self._render()

    _full: tuple[int, int] = (0, 0)

    def _show_empty(self, empty: bool) -> None:
        self.empty.setVisible(empty)
        self.canvas.setVisible(not empty)
        self.compare.setEnabled(not empty)

    def reset(self, keep_picture: bool = False) -> None:
        self.rotation = 0
        self.flip.setChecked(False)
        for slider in (self.brightness, self.contrast, self.saturation):
            slider.set_value(1.0)
        for switch in (self.auto, self.sharpen, self.grey):
            switch.setChecked(False)
        self.caption.clear()
        self.crop.set_value("")
        self.width_box.setValue(0)
        self.enlarge.set_value(1.0)
        if keep_picture or self.original is not None:
            self._changed()

    # ── the edits ──
    def ops(self) -> list[dict[str, Any]]:
        ops: list[dict[str, Any]] = []
        if self.crop.value():
            ops.append({"op": "crop_aspect", "aspect": self.crop.value()})
        if self.rotation % 360:
            ops.append({"op": "rotate", "degrees": self.rotation % 360})
        if self.flip.isChecked():
            ops.append({"op": "flip"})
        values = {"brightness": self.brightness.value(), "contrast": self.contrast.value(),
                  "saturation": self.saturation.value()}
        if any(abs(v - 1.0) > 1e-6 for v in values.values()):
            ops.append({"op": "adjust", **values})
        if self.auto.isChecked():
            ops.append({"op": "autocontrast"})
        if self.sharpen.isChecked():
            ops.append({"op": "sharpen"})
        if self.grey.isChecked():
            ops.append({"op": "grayscale"})
        if self.width_box.value():
            ops.append({"op": "resize", "width": self.width_box.value()})
        if self.enlarge.value() > 1.0:
            ops.append({"op": "upscale", "factor": self.enlarge.value()})
        if self.caption.text().strip():
            ops.append({"op": "caption", "text": self.caption.text().strip()})
        return ops

    def _turn(self, degrees: int) -> None:
        self.rotation = (self.rotation + degrees) % 360
        self._changed()

    def _mirror(self) -> None:
        self._changed()

    def _sized(self, *_: Any) -> None:
        self._changed()

    def _changed(self, *_: Any) -> None:
        if self.original is not None:
            self._debounce.start()
        self._note()

    def _render(self) -> None:
        if self.original is not None:
            self.previewer.run(self.original, self.ops())

    def _preview_made(self, ticket: int, image: QImage) -> None:
        self.edited_q = image
        self._show(original=False)

    def _show(self, *, original: bool) -> None:
        if self.original is None:
            return
        picture = self.original_q if original or self.edited_q.isNull() else self.edited_q
        self.canvas.item.setPixmap(imaging_pixmap(picture))
        self.canvas.scene_.setSceneRect(self.canvas.item.boundingRect())
        if self.canvas._fitted:
            self.canvas.fit()
        if original:
            QTimer.singleShot(900, lambda: self._show(original=False)) if not self.compare.isDown() else None

    def _note(self) -> None:
        if not self.path:
            self.size_note.setText("")
            return
        w, h = self._full
        if self.rotation in (90, 270):
            w, h = h, w
        ratio = dict((k, r) for _, k, r in CROPS).get(self.crop.value(), 0.0)
        if ratio:
            w, h = (w, round(w / ratio)) if w / h < ratio else (round(h * ratio), h)
        if self.width_box.value():
            w, h = self.width_box.value(), round(h * self.width_box.value() / max(1, w))
        f = self.enlarge.value()
        name = Path(self.path).name
        name = name if len(name) <= 34 else name[:20] + "…" + name[-12:]
        self.size_note.setText(f"{name}  ·  saved at {round(w * f)} × {round(h * f)}")
        self.size_note.setToolTip(self.path)

    # ── saving ──
    def request(self) -> dict[str, Any]:
        if not self.path:
            raise ValueError("Open a picture first.")
        ops = self.ops()
        if not ops:
            raise ValueError("Change something first: the picture is as it was.")
        return {"path": self.path, "ops": ops, "format": self.format.value()}

    def finished(self, job: Any) -> None:
        self.strip.set_tiles([Tile.from_asset(a) for a in self.studio.library.recent(kind="image", limit=30)])

    def shown(self, **wanted: Any) -> None:
        self.refresh()
        self.strip.set_tiles([Tile.from_asset(a) for a in self.studio.library.recent(kind="image", limit=30)])
        if wanted.get("path"):
            self.open_path(str(wanted["path"]))

    def on_job(self, job: Any) -> None:
        if job.id in self.jobs and job.finished:
            self.finished(job)
            if job.state == "done" and job.assets:
                saved = Tile.from_asset(job.assets[0])
                self.shell.toast("Edit saved, beside the original", "good",
                                 action=("View", lambda: self.view_saved(saved)))
            elif job.state == "failed":
                self.shell.toast(f"The edit failed: {job.error}", "bad")
        self.update_create()

    def view_saved(self, tile: Tile) -> None:
        from eli_creation.gui.gallery import open_lightbox

        open_lightbox(self.shell, [tile], tile)


def imaging_pixmap(image: QImage) -> Any:
    from PySide6.QtGui import QPixmap

    return QPixmap.fromImage(image)

