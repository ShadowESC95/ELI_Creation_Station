"""The gallery: what was made, as tiles, and a lightbox to look at one closely.

Tiles fill the width at the size chosen; pictures are shown cropped to the tile, and the other
kinds (posts, game designs, code, animations) as tiles of their own with a line of what they hold.
A job still running has a tile too, shimmering, with its progress, so the work appears where its
result will be.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QListView,
    QMenu,
    QPlainTextEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons, imaging

KIND_ICON = {"post": "message", "image": "image", "edit": "sliders", "video": "film", "game": "gamepad",
             "code": "code", "audio": "music", "note": "info"}
KIND_ACCENT = {"post": design.accent("socials"), "image": design.accent("images"), "edit": design.accent("editing"),
               "video": design.accent("videos"), "game": design.accent("games"), "code": design.accent("coding"),
               "audio": design.accent("videos"), "note": design.MUTED}


@dataclass
class Tile:
    path: str = ""
    title: str = ""
    kind: str = "image"
    project: str = ""
    created: str = ""
    engine: str = ""
    licence: str = ""
    ai: bool = False
    snippet: str = ""
    # a job's tile, while it runs
    job: str = ""
    progress: float = -1.0
    message: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def pending(self) -> bool:
        return bool(self.job) and not self.path

    @classmethod
    def from_asset(cls, asset: Any) -> Tile:
        path = Path(asset.path)
        return cls(path=str(path), title=asset.title, kind=asset.kind, project=asset.project, created=asset.created,
                   engine=asset.engine, licence=asset.licence_class, ai=bool(asset.ai_generated),
                   snippet=snippet_of(path) if not imaging.is_picture(path) else "")


def snippet_of(path: Path, limit: int = 220) -> str:
    """A few lines of what a written asset holds, for its tile."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return ""
    if path.name.endswith(".game.json"):
        try:
            spec = json.loads(raw)
            return f"{spec.get('title', '')}: {spec.get('goal', '')}"[:limit]
        except ValueError:
            pass
    lines = [ln.strip("# ").strip() for ln in raw.splitlines() if ln.strip() and not ln.startswith("## Draft")]
    return " ".join(lines)[:limit]


class GalleryModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self.tiles: list[Tile] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self.tiles)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self.tiles):
            return None
        tile = self.tiles[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return tile.title
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{tile.title}\n{Path(tile.path).name}" if tile.path else tile.message
        if role == Qt.ItemDataRole.UserRole:
            return tile
        return None

    def set_tiles(self, tiles: list[Tile]) -> None:
        self.beginResetModel()
        self.tiles = list(tiles)
        self.endResetModel()

    def put_front(self, tiles: list[Tile]) -> None:
        if not tiles:
            return
        self.beginInsertRows(QModelIndex(), 0, len(tiles) - 1)
        self.tiles[0:0] = tiles
        self.endInsertRows()

    def update_job(self, job_id: str, progress: float, message: str) -> None:
        for row, tile in enumerate(self.tiles):
            if tile.job == job_id and tile.pending:
                tile.progress, tile.message = progress, message
                idx = self.index(row)
                self.dataChanged.emit(idx, idx)

    def finish_job(self, job_id: str, made: list[Tile]) -> None:
        rows = [r for r, t in enumerate(self.tiles) if t.job == job_id and t.pending]
        for row in reversed(rows):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.tiles[row]
            self.endRemoveRows()
        known = {t.path for t in self.tiles}
        self.put_front([t for t in made if t.path not in known])

    def has_pending(self) -> bool:
        return any(t.pending for t in self.tiles)


class TileDelegate(QStyledItemDelegate):
    RADIUS = 14

    def __init__(self, view: Gallery) -> None:
        super().__init__(view)
        self.view = view
        self.phase = 0.0

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> QSize:  # noqa: N802
        return self.view.cell_size()

    def paint(self, p: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex) -> None:
        tile: Tile = index.data(Qt.ItemDataRole.UserRole)
        if tile is None:
            return
        rect = QRectF(option.rect).adjusted(5, 5, -5, -5)  # type: ignore[attr-defined]
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)  # type: ignore[attr-defined]
        selected = bool(option.state & QStyle.StateFlag.State_Selected)  # type: ignore[attr-defined]
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addRoundedRect(rect, self.RADIUS, self.RADIUS)
        p.setClipPath(clip)
        if tile.pending:
            self._pending(p, rect, tile)
        elif imaging.is_picture(tile.path):
            self._picture(p, rect, tile)
        else:
            self._written(p, rect, tile)
        if not tile.pending and (hover or selected):
            shade = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            shade.setColorAt(0.45, QColor(0, 0, 0, 0))
            shade.setColorAt(1.0, QColor(0, 0, 0, 200))
            p.fillRect(rect, shade)
            self._caption(p, rect, tile)
        p.setClipping(False)
        border = QColor(design.BRAND_B if selected else ("#ffffff" if hover else design.LINE))
        border.setAlpha(230 if selected else (60 if hover else 255))
        p.setPen(QPen(border, 2 if selected else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, self.RADIUS, self.RADIUS)
        if tile.ai and not tile.pending:
            at = QPointF(rect.left() + 10, rect.top() + 10) if imaging.is_picture(tile.path) else \
                QPointF(rect.right() - 40, rect.top() + 12)
            self._chip(p, at, "AI", design.BRAND_A)
        p.restore()

    def _picture(self, p: QPainter, rect: QRectF, tile: Tile) -> None:
        image = imaging.thumbnails().get(tile.path, self.view.thumb_side())
        p.fillRect(rect, QColor(design.SURFACE))
        if image is None or image.isNull():
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPixmap(int(rect.center().x() - 14), int(rect.center().y() - 14),
                         icons.pixmap(KIND_ICON.get(tile.kind, "image"), design.FAINT, 28))
            return
        scale = max(rect.width() / max(1, image.width()), rect.height() / max(1, image.height()))
        w, h = image.width() * scale, image.height() * scale
        target = QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h)
        p.drawImage(target, image)
        if tile.kind == "video":
            self._chip(p, QPointF(rect.right() - 60, rect.top() + 10), "▶ Play", design.accent("videos"))

    def _written(self, p: QPainter, rect: QRectF, tile: Tile) -> None:
        accent = KIND_ACCENT.get(tile.kind, design.MUTED)
        bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg.setColorAt(0.0, design.alpha_q(accent, 0.20))
        bg.setColorAt(1.0, QColor(design.RAISED))
        p.fillRect(rect, QColor(design.RAISED))
        p.fillRect(rect, bg)
        p.drawPixmap(int(rect.left() + 16), int(rect.top() + 16), icons.pixmap(KIND_ICON.get(tile.kind, "info"), accent, 26))
        font = QFont(p.font())
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor(design.TEXT))
        fm = QFontMetrics(font)
        title_rect = QRectF(rect.left() + 16, rect.top() + 52, rect.width() - 32, fm.height() * 2 + 2)
        p.drawText(title_rect, int(Qt.TextFlag.TextWordWrap), fm.elidedText(tile.title, Qt.TextElideMode.ElideRight,
                                                                              int(title_rect.width() * 2 - 20)))
        small = QFont(p.font())
        small.setWeight(QFont.Weight.Normal)
        small.setPointSizeF(max(6.0, small.pointSizeF() * 0.88))
        p.setFont(small)
        p.setPen(QColor(design.MUTED))
        body = QRectF(rect.left() + 16, title_rect.bottom() + 6, rect.width() - 32, rect.bottom() - title_rect.bottom() - 22)
        p.drawText(body, int(Qt.TextFlag.TextWordWrap), tile.snippet)

    def _pending(self, p: QPainter, rect: QRectF, tile: Tile) -> None:
        p.fillRect(rect, QColor(design.SURFACE))
        x = rect.left() + (rect.width() * 2.2) * self.phase - rect.width() * 0.6
        sheen = QLinearGradient(QPointF(x, rect.top()), QPointF(x + rect.width() * 0.6, rect.bottom()))
        sheen.setColorAt(0.0, QColor(255, 255, 255, 0))
        sheen.setColorAt(0.5, design.alpha_q(design.BRAND_A, 0.16))
        sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(rect, sheen)
        c = rect.center()
        ring = QRectF(c.x() - 22, c.y() - 34, 44, 44)
        p.setPen(QPen(QColor(design.LINE_STRONG), 4))
        p.drawEllipse(ring)
        pen = QPen(QColor(design.BRAND_B), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        if tile.progress > 0:
            p.drawArc(ring, 90 * 16, int(-360 * 16 * min(1.0, tile.progress)))
        else:
            p.drawArc(ring, int(-self.phase * 360 * 16), 90 * 16)
        p.setPen(QColor(design.SUBTLE))
        p.drawText(QRectF(rect.left() + 10, c.y() + 18, rect.width() - 20, 40),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap),
                   tile.message or "Waiting its turn")

    def _caption(self, p: QPainter, rect: QRectF, tile: Tile) -> None:
        font = QFont(p.font())
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        fm = QFontMetrics(font)
        p.setPen(QColor("#ffffff"))
        line = fm.elidedText(tile.title, Qt.TextElideMode.ElideRight, int(rect.width() - 24))
        p.drawText(QRectF(rect.left() + 12, rect.bottom() - 46, rect.width() - 24, 22), int(Qt.AlignmentFlag.AlignLeft), line)
        small = QFont(font)
        small.setWeight(QFont.Weight.Normal)
        small.setPointSizeF(max(6.0, small.pointSizeF() * 0.85))
        p.setFont(small)
        p.setPen(QColor(255, 255, 255, 170))
        meta = " · ".join(x for x in (tile.kind.capitalize(), tile.project, (tile.created or "")[:10]) if x)
        p.drawText(QRectF(rect.left() + 12, rect.bottom() - 26, rect.width() - 24, 20), int(Qt.AlignmentFlag.AlignLeft), meta)

    def _chip(self, p: QPainter, at: QPointF, label: str, colour: str) -> None:
        font = QFont(p.font())
        font.setPointSizeF(max(6.0, font.pointSizeF() * 0.78))
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        fm = QFontMetrics(font)
        box = QRectF(at.x(), at.y(), fm.horizontalAdvance(label) + 14, fm.height() + 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(10, 12, 17, 190))
        p.drawRoundedRect(box, box.height() / 2, box.height() / 2)
        p.setPen(QColor(colour))
        p.drawText(box, int(Qt.AlignmentFlag.AlignCenter), label)


class Gallery(QListView):
    """Tiles of what was made. Double-click or Enter opens one in the lightbox."""

    opened = Signal(object)  # Tile
    asked = Signal(str, object)  # an action's name, the Tile

    SIZES = {"small": 150, "medium": 210, "large": 300}

    def __init__(self, *, size: str = "medium", actions: list[tuple[str, str, str]] | None = None) -> None:
        super().__init__()
        self.model_ = GalleryModel()
        self.setModel(self.model_)
        self.delegate = TileDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSpacing(0)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.size_name = size if size in self.SIZES else "medium"
        # extra actions offered on a tile's menu: (name, label, icon)
        self.extra_actions = actions or []
        self.doubleClicked.connect(self._double)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self._shimmer = QTimer(self)
        self._shimmer.timeout.connect(self._tick)
        imaging.thumbnails().ready.connect(lambda _p: self.viewport().update())
        self.model_.rowsInserted.connect(self._rows_added)
        self.model_.rowsRemoved.connect(lambda *_: self._fit_height())
        self.model_.modelReset.connect(self._fit_height)
        enter = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter.setContext(Qt.ShortcutContext.WidgetShortcut)
        enter.activated.connect(lambda: self._double(self.currentIndex()))

    empty_text = "Nothing here yet"

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.model_.rowCount() == 0 and self.empty_text:
            p = QPainter(self.viewport())
            p.setPen(QColor(design.FAINT))
            p.drawText(self.viewport().rect(), int(Qt.AlignmentFlag.AlignCenter), self.empty_text)
            p.end()

    # ── size ──
    def thumb_side(self) -> int:
        return 512 if self.SIZES[self.size_name] > 220 else 360

    def cell_size(self) -> QSize:
        target = self.SIZES[self.size_name]
        width = max(100, self.viewport().width() - 8)
        columns = max(1, round(width / target))
        side = (width - columns) // columns
        return QSize(side, side)

    def columns(self) -> int:
        return max(1, (self.viewport().width() - 8) // max(1, self.cell_size().width()))

    def fit_to_content(self, on: bool = True, *, max_rows: int = 0) -> None:
        """Grow to show every tile rather than scroll (for a gallery on a page that scrolls)."""
        self._fit = on
        self._max_rows = max_rows
        if on:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fit_height()

    _fit = False
    _max_rows = 0

    def _fit_height(self) -> None:
        if not self._fit:
            return
        rows = max(1, -(-self.model_.rowCount() // self.columns()))
        if self._max_rows:
            rows = min(rows, self._max_rows)
        self.setFixedHeight(rows * self.cell_size().height() + 8)

    def set_size(self, name: str) -> None:
        self.size_name = name if name in self.SIZES else "medium"
        self._relayout()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        self.setGridSize(self.cell_size())
        self.doItemsLayout()
        self._fit_height()

    # ── content ──
    def set_tiles(self, tiles: list[Tile]) -> None:
        self.model_.set_tiles(tiles)
        self._watch()

    def tiles(self) -> list[Tile]:
        return list(self.model_.tiles)

    def selected_tiles(self) -> list[Tile]:
        return [i.data(Qt.ItemDataRole.UserRole) for i in self.selectedIndexes() if i.data(Qt.ItemDataRole.UserRole)]

    def add_pending(self, job_id: str, count: int, message: str = "Waiting its turn") -> None:
        self.model_.put_front([Tile(job=job_id, title="", message=message, progress=0.0) for _ in range(max(1, count))])
        self.scrollToTop()
        self._watch()

    def _rows_added(self, *_: Any) -> None:
        self._watch()
        self._fit_height()

    def _watch(self) -> None:
        if self.model_.has_pending():
            if not self._shimmer.isActive():
                self._shimmer.start(33)
        else:
            self._shimmer.stop()

    def _tick(self) -> None:
        self.delegate.phase = (self.delegate.phase + 0.012) % 1.0
        self.viewport().update()
        self._watch()

    # ── acting on a tile ──
    def _double(self, index: QModelIndex) -> None:
        tile = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None
        if tile is not None and not tile.pending:
            self.opened.emit(tile)

    def _menu(self, at: Any) -> None:
        index = self.indexAt(at)
        tile = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None
        if tile is None or tile.pending:
            return
        menu = QMenu(self)
        entries = [("view", "Open in the viewer", "eye"), ("open", "Open with its program", "external"),
                   ("folder", "Show in its folder", "folder"), ("copy_path", "Copy its location", "copy")]
        entries += self.extra_actions
        for name, label, icon_name in entries:
            action = menu.addAction(icons.icon(icon_name, design.SUBTLE, 16), label)
            action.setData(name)
        chosen = menu.exec(self.viewport().mapToGlobal(at))
        if chosen is not None:
            run_action(str(chosen.data()), tile, self)
            self.asked.emit(str(chosen.data()), tile)


def run_action(name: str, tile: Tile, parent: QWidget | None = None) -> None:
    """The actions every tile has, wherever it is shown."""
    if name == "open":
        QDesktopServices.openUrl(QUrl.fromLocalFile(tile.path))
    elif name == "folder":
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(tile.path).parent)))
    elif name == "copy_path":
        QGuiApplication.clipboard().setText(tile.path)


# ── the lightbox ─────────────────────────────────────────────────────────
class _Zoomable(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.item = QGraphicsPixmapItem()
        self.item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene_.addItem(self.item)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor(design.INK))
        self._fitted = True

    def show_image(self, image: QImage) -> None:
        self.item.setPixmap(QPixmap.fromImage(image))
        self.scene_.setSceneRect(self.item.boundingRect())
        self.fit()

    def fit(self) -> None:
        self._fitted = True
        self.resetTransform()
        if not self.item.pixmap().isNull():
            self.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        self._fitted = False
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._fitted:
            self.fit()


class Lightbox(QDialog):
    """One thing made, large: a picture to zoom into, an animation playing, or what a written
    asset says; beside it, its record (what made it, its licence, whether a model made it)."""

    acted = Signal(str, object)

    def __init__(self, parent: QWidget | None, tiles: list[Tile], index: int, *,
                 actions: list[tuple[str, str, str]] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Viewer")
        self.tiles = [t for t in tiles if not t.pending]
        self.index = max(0, min(index, len(self.tiles) - 1))
        self.extra_actions = actions or []
        self.resize(1280, 820)
        self.view = _Zoomable()
        self.textview = QPlainTextEdit()
        self.textview.setReadOnly(True)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        self.textview.setFont(mono)
        self._frames: list[tuple[QImage, int]] = []
        self._frame = 0
        self._player = QTimer(self)
        self._player.timeout.connect(self._next_frame)

        self.title = ui.text("", "h2", wrap=True)
        self.meta = ui.text("", "small", tone="muted", wrap=True, selectable=True, rich=True)
        self.position = ui.text("", "small", tone="faint")
        side = QVBoxLayout()
        side.setSpacing(10)
        side.addWidget(self.position)
        side.addWidget(self.title)
        side.addWidget(self.meta)
        side.addStretch(1)
        acts = [("open", "Open with its program", "external"), ("folder", "Show in its folder", "folder"),
                ("copy_path", "Copy its location", "copy")] + self.extra_actions
        for name, label, icon_name in acts:
            side.addWidget(ui.button(label, partial(self._act, name), icon=icon_name))
        side_box = QWidget()
        side_box.setLayout(side)
        side_box.setFixedWidth(330)
        side_box.setStyleSheet(f"background: {design.SURFACE}; border-left: 1px solid {design.LINE};")
        side.setContentsMargins(22, 22, 22, 22)

        bar = QHBoxLayout()
        bar.setContentsMargins(16, 10, 16, 10)
        bar.addWidget(ui.icon_button("chevron_left", "Previous (←)", lambda: self.step(-1)))
        bar.addWidget(ui.icon_button("chevron_right", "Next (→)", lambda: self.step(1)))
        bar.addWidget(ui.icon_button("maximize", "Fit to the window (F)", self.view.fit))
        bar.addStretch(1)
        bar.addWidget(ui.icon_button("x", "Close (Esc)", self.close))
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)
        left.addLayout(bar)
        left.addWidget(self.view, 1)
        left.addWidget(self.textview, 1)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(left, 1)
        outer.addWidget(side_box)
        for key, step in ((Qt.Key.Key_Left, -1), (Qt.Key.Key_Right, 1)):
            QShortcut(QKeySequence(key), self).activated.connect(lambda s=step: self.step(s))
        QShortcut(QKeySequence(Qt.Key.Key_F), self).activated.connect(self.view.fit)
        self.show_current()

    def current(self) -> Tile | None:
        return self.tiles[self.index] if self.tiles else None

    def step(self, delta: int) -> None:
        if self.tiles:
            self.index = (self.index + delta) % len(self.tiles)
            self.show_current()

    def show_current(self) -> None:
        tile = self.current()
        self._player.stop()
        if tile is None:
            return
        self.position.setText(f"{self.index + 1} of {len(self.tiles)}")
        self.title.setText(tile.title)
        self.meta.setText(describe(tile))
        if imaging.is_picture(tile.path):
            self.textview.hide()
            self.view.show()
            try:
                self._frames = imaging.frames(tile.path, 2048) if tile.kind == "video" else []
                image = self._frames[0][0] if self._frames else imaging.load(tile.path, 4096)
            except Exception:
                image = QImage()
            self.view.show_image(image)
            if len(self._frames) > 1:
                self._frame = 0
                self._player.start(self._frames[0][1])
        else:
            self.view.hide()
            self.textview.show()
            try:
                self.textview.setPlainText(Path(tile.path).read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                self.textview.setPlainText(str(exc))

    def _next_frame(self) -> None:
        if not self._frames:
            return
        self._frame = (self._frame + 1) % len(self._frames)
        image, ms = self._frames[self._frame]
        self.view.item.setPixmap(QPixmap.fromImage(image))
        self._player.setInterval(max(20, ms))

    def _act(self, name: str) -> None:
        tile = self.current()
        if tile is None:
            return
        run_action(name, tile, self)
        self.acted.emit(name, tile)
        if name not in ("open", "folder", "copy_path"):
            self.accept()

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        self._player.stop()
        super().closeEvent(event)


def manifest_of(path: str) -> dict[str, Any]:
    try:
        return dict(json.loads(Path(path + ".manifest.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return {}


def describe(tile: Tile) -> str:
    """A tile's record, from its manifest: what made it, under what licence, whether AI."""
    man = manifest_of(tile.path)
    models = ", ".join(f"{m.get('title') or m.get('id')} ({m.get('licence', '?')})" for m in man.get("models", [])) or "none"
    gen = man.get("generator", {})
    rows = [
        ("Kind", tile.kind.capitalize()),
        ("Project", tile.project or "—"),
        ("Made", (tile.created or man.get("created", ""))[:19].replace("T", " ")),
        ("Engine", gen.get("engine", tile.engine) or "—"),
        ("Models", models),
        ("Made by a model", "Yes, and marked as such in the file" if tile.ai else "No"),
        ("Licence of the output", tile.licence or man.get("output_licence_class", "—")),
        ("SHA-256", (man.get("sha256", "") or "")[:16] + "…" if man.get("sha256") else "—"),
        ("File", Path(tile.path).name),
    ]
    if man.get("edits"):
        rows.append(("Edits", ", ".join(str(e.get("op")) for e in man["edits"])))
    return "".join(f"<p style='margin:0 0 8px 0'><span style='color:{design.FAINT}'>{k}</span><br>"
                   f"<span style='color:{design.SUBTLE}'>{v}</span></p>" for k, v in rows)


def open_lightbox(parent: QWidget, tiles: list[Tile], tile: Tile,
                  actions: list[tuple[str, str, str]] | None = None) -> Lightbox:
    pictures = [t for t in tiles if not t.pending]
    index = next((i for i, t in enumerate(pictures) if t.path == tile.path), 0)
    box = Lightbox(parent, pictures, index, actions=actions)
    box.setModal(True)
    box.show()
    return box


def kind_pixmap(kind: str, size: int = 22) -> QPixmap:
    return icons.pixmap(KIND_ICON.get(kind, "info"), KIND_ACCENT.get(kind, design.MUTED), size)
