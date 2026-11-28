"""The Film studio's working parts: the storyboard strip, the preview that plays the film as it will
be written, and the timeline of picture, voice, music, effects and captions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QWidget,
)

from eli_creation.gui import design, icons, imaging
from eli_creation.production.audio import peaks
from eli_creation.production.compositor import Compositor
from eli_creation.production.formats import CAMERA, FORMATS, TRANSITIONS
from eli_creation.production.project import Project

TRACKS = (("video", "Picture", "film", "#fb923c"), ("narration", "Voice", "mic", "#22d3ee"),
          ("music", "Music", "music", "#a78bfa"), ("sfx", "Effects", "bolt", "#facc15"),
          ("captions", "Captions", "captions", "#f637ec"))


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds // 60):02d}:{seconds % 60:05.2f}"


# ── the storyboard ───────────────────────────────────────────────────────
class _SceneDelegate(QStyledItemDelegate):
    def __init__(self, strip: SceneStrip) -> None:
        super().__init__(strip)
        self.strip = strip

    def sizeHint(self, option: Any, index: Any) -> QSize:  # noqa: N802
        return QSize(170, 140)

    def paint(self, p: QPainter, option: Any, index: Any) -> None:
        from PySide6.QtWidgets import QStyle

        r = QRectF(option.rect).adjusted(6, 6, -6, -6)
        scene_id = index.data(Qt.ItemDataRole.UserRole)
        scene = next((s for s in self.strip.project.scenes if s.id == scene_id), None) if self.strip.project else None
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.fillPath(path, QColor(design.RAISED))
        if scene is None:
            p.restore()
            return
        thumb = QRectF(r.left(), r.top(), r.width(), r.height() - 48)
        clip = QPainterPath()
        clip.addRoundedRect(thumb, 12, 12)
        p.setClipPath(clip)
        image = imaging.thumbnails().get(scene.image, 360) if scene.image else None
        if image is not None and not image.isNull():
            scale = max(thumb.width() / image.width(), thumb.height() / image.height())
            w, h = image.width() * scale, image.height() * scale
            p.drawImage(QRectF(thumb.center().x() - w / 2, thumb.center().y() - h / 2, w, h), image)
        else:
            p.fillRect(thumb, QColor(design.SURFACE))
            p.drawPixmap(int(thumb.center().x() - 14), int(thumb.center().y() - 14), icons.pixmap("image", design.FAINT, 28))
        p.setClipping(False)
        number = f"{index.row() + 1:02d}"
        font = QFont(p.font())
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        badge = QRectF(thumb.left() + 8, thumb.top() + 8, QFontMetrics(font).horizontalAdvance(number) + 14, 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(5, 7, 13, 200))
        p.drawRoundedRect(badge, 10, 10)
        p.setPen(QColor(design.BRAND_A))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, number)
        seconds = f"{scene.seconds:.1f}s · {CAMERA.get(scene.camera, ('',))[0]}"
        p.setPen(QColor(design.TEXT))
        p.drawText(QRectF(r.left() + 10, thumb.bottom() + 4, r.width() - 20, 20), Qt.AlignmentFlag.AlignLeft,
                   QFontMetrics(font).elidedText(scene.title or "Scene", Qt.TextElideMode.ElideRight, int(r.width() - 20)))
        small = QFont(p.font())
        small.setWeight(QFont.Weight.Normal)
        small.setPointSizeF(max(6.0, small.pointSizeF() * 0.85))
        p.setFont(small)
        p.setPen(QColor(design.MUTED))
        p.drawText(QRectF(r.left() + 10, thumb.bottom() + 22, r.width() - 20, 18), Qt.AlignmentFlag.AlignLeft,
                   QFontMetrics(small).elidedText(seconds, Qt.TextElideMode.ElideRight, int(r.width() - 20)))
        p.setPen(QPen(QColor(design.BRAND_A if selected else design.LINE_STRONG), 2 if selected else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 12, 12)
        p.restore()


class SceneStrip(QListWidget):
    """The scenes in order, as cards; drag one to move it."""

    reordered = Signal(list)  # scene ids in their new order
    chosen = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListView.Movement.Snap)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setGridSize(QSize(174, 144))
        self.setFixedHeight(160)
        self.setItemDelegate(_SceneDelegate(self))
        self.setStyleSheet("QListWidget { background: transparent; border: none; }")
        self.model().rowsMoved.connect(lambda *_: self.reordered.emit(self.ids()))
        self.currentItemChanged.connect(self._current)
        imaging.thumbnails().ready.connect(lambda _p: self.viewport().update())

    def _current(self, item: QListWidgetItem | None, _old: object) -> None:
        if item is not None:
            self.chosen.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    def show_project(self, project: Project | None, keep: str = "") -> None:
        self.project = project
        self.blockSignals(True)
        self.clear()
        for scene in (project.scenes if project else []):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, scene.id)
            item.setSizeHint(QSize(170, 140))
            self.addItem(item)
        self.blockSignals(False)
        for row in range(self.count()):
            if self.item(row).data(Qt.ItemDataRole.UserRole) == keep:
                self.setCurrentRow(row)
                return
        if self.count():
            self.setCurrentRow(0)

    def ids(self) -> list[str]:
        return [str(self.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.count())]


# ── the preview ──────────────────────────────────────────────────────────
class Preview(QWidget):
    """The film as it will be written, drawn live at the size of the window."""

    moved = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.compositor: Compositor | None = None
        self.t = 0.0
        self.playing = False
        self._frame: QImage | None = None
        self._clock = QElapsedTimer()
        self._from = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.source: Callable[[], float] | None = None  # where the sound is, when it plays
        self.setMinimumSize(420, 240)

    def show_project(self, project: Project | None) -> None:
        self.project = project
        self.compositor = None
        if project is not None:
            fmt = FORMATS.get(project.format, FORMATS["youtube"])
            self.compositor = Compositor(project, fmt.scaled(720))
        self.seek(min(self.t, project.length() if project else 0.0))

    def refresh(self) -> None:
        if self.compositor is not None:
            self.compositor.forget()
        self.seek(self.t)

    def seek(self, t: float) -> None:
        self.t = max(0.0, t)
        self._frame = self.compositor.frame(self.t) if self.compositor is not None and self.project and \
            self.project.scenes else None
        self.update()
        self.moved.emit(self.t)

    def play(self, source: Callable[[], float] | None = None) -> None:
        if self.project is None or not self.project.scenes:
            return
        if self.t >= self.project.length() - 0.05:
            self.t = 0.0
        self.source = source
        self._from = self.t
        self._clock.start()
        self.playing = True
        self._timer.start(33)

    def stop(self) -> None:
        self.playing = False
        self._timer.stop()
        self.source = None

    def _tick(self) -> None:
        if self.project is None:
            return
        t = self.source() if self.source is not None else self._from + self._clock.elapsed() / 1000.0
        if t >= self.project.length():
            self.stop()
            t = self.project.length()
        self.seek(t)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        p.fillRect(r, QColor("#020409"))
        if self._frame is None:
            p.setPen(QColor(design.FAINT))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Add a scene and give it a picture: the film plays here")
            p.end()
            return
        fw, fh = self._frame.width(), self._frame.height()
        scale = min(r.width() / fw, r.height() / fh)
        w, h = fw * scale, fh * scale
        p.drawImage(QRectF((r.width() - w) / 2, (r.height() - h) / 2, w, h), self._frame)
        p.end()


# ── the timeline ─────────────────────────────────────────────────────────
class Timeline(QWidget):
    """Picture, voice, music, effects and captions against time, with a playhead to drag."""

    seeked = Signal(float)
    picked = Signal(str, str)  # track, id (a scene's or a clip's)
    clip_moved = Signal(str, float)  # clip id, new start

    LABEL = 112
    RULER = 26
    ROW = 38

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.t = 0.0
        self.zoom = 60.0  # pixels a second
        self.selected = ("", "")
        self._drag: tuple[str, str, float, float] | None = None  # kind, id, grab offset, original start
        self._peaks: dict[str, list[float]] = {}
        self.setMinimumHeight(self.RULER + self.ROW * len(TRACKS) + 8)
        self.setMouseTracking(True)
        imaging.thumbnails().ready.connect(lambda _p: self.update())

    def show_project(self, project: Project | None) -> None:
        self.project = project
        self._peaks.clear()
        self._fit()
        self.update()

    def _fit(self) -> None:
        length = self.project.length() if self.project else 10.0
        self.setMinimumWidth(int(self.LABEL + max(10.0, length + 4) * self.zoom))

    def set_zoom(self, pixels_a_second: float) -> None:
        self.zoom = max(10.0, min(300.0, pixels_a_second))
        self._fit()
        self.update()

    def set_time(self, t: float) -> None:
        self.t = t
        self.update()

    def x_of(self, t: float) -> float:
        return self.LABEL + t * self.zoom

    def t_of(self, x: float) -> float:
        return max(0.0, (x - self.LABEL) / self.zoom)

    def _row(self, y: float) -> int:
        return int((y - self.RULER) // self.ROW)

    def _clip_rects(self) -> list[tuple[str, str, QRectF]]:
        """(track, id, rect) of everything drawn on a track."""
        out: list[tuple[str, str, QRectF]] = []
        if self.project is None:
            return out
        for scene, start, end in self.project.scene_times():
            out.append(("video", scene.id, QRectF(self.x_of(start), self.RULER + 4, (end - start) * self.zoom,
                                                   self.ROW - 8)))
        rows = {key: n for n, (key, *_rest) in enumerate(TRACKS)}
        for clip in self.project.clips:
            row = rows.get(clip.kind, 2)
            length = clip.duration or 1.0
            out.append((clip.kind, clip.id, QRectF(self.x_of(clip.start), self.RULER + row * self.ROW + 4,
                                                   length * self.zoom, self.ROW - 8)))
        for n, cue in enumerate(self.project.cues):
            out.append(("captions", str(n), QRectF(self.x_of(cue.start), self.RULER + rows["captions"] * self.ROW + 8,
                                                   (cue.end - cue.start) * self.zoom, self.ROW - 16)))
        return out

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        pos = event.position()
        if pos.y() < self.RULER or pos.x() < self.LABEL:
            self._drag = ("playhead", "", 0.0, 0.0)
            self.seeked.emit(self.t_of(pos.x()))
            return
        for track, item_id, rect in reversed(self._clip_rects()):
            if rect.contains(pos):
                self.selected = (track, item_id)
                self.picked.emit(track, item_id)
                if track in ("narration", "music", "sfx"):
                    clip = next(c for c in self.project.clips if c.id == item_id)  # type: ignore[union-attr]
                    self._drag = ("clip", item_id, self.t_of(pos.x()) - clip.start, clip.start)
                self.update()
                return
        self._drag = ("playhead", "", 0.0, 0.0)
        self.seeked.emit(self.t_of(pos.x()))

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if self._drag is None:
            return
        kind, item_id, grab, _original = self._drag
        if kind == "playhead":
            self.seeked.emit(self.t_of(event.position().x()))
        elif kind == "clip" and self.project is not None:
            clip = next((c for c in self.project.clips if c.id == item_id), None)
            if clip is not None:
                clip.start = round(max(0.0, self.t_of(event.position().x()) - grab), 2)
                self.update()

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        if self._drag is not None and self._drag[0] == "clip" and self.project is not None:
            clip = next((c for c in self.project.clips if c.id == self._drag[1]), None)
            if clip is not None and abs(clip.start - self._drag[3]) > 0.01:
                self.clip_moved.emit(clip.id, clip.start)
        self._drag = None

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(5, 9, 16, 210))
        # the ruler
        p.setPen(QColor(design.FAINT))
        small = QFont(p.font())
        small.setPointSizeF(max(6.0, small.pointSizeF() * 0.8))
        p.setFont(small)
        step = 1 if self.zoom >= 80 else 2 if self.zoom >= 40 else 5 if self.zoom >= 16 else 10
        t = 0
        while self.x_of(t) < r.width():
            x = self.x_of(t)
            p.drawLine(QPointF(x, self.RULER - 6), QPointF(x, self.RULER))
            p.drawText(QRectF(x + 3, 2, 60, self.RULER - 6), Qt.AlignmentFlag.AlignLeft, fmt_time(t)[:5])
            t += step
        # the tracks
        for n, (_key, name, icon, colour) in enumerate(TRACKS):
            y = self.RULER + n * self.ROW
            p.fillRect(QRectF(0, y, r.width(), self.ROW), QColor(255, 255, 255, 6 if n % 2 else 0))
            p.setPen(QPen(QColor(design.LINE), 1))
            p.drawLine(QPointF(0, y + self.ROW), QPointF(r.width(), y + self.ROW))
            p.drawPixmap(10, int(y + self.ROW / 2 - 8), icons.pixmap(icon, colour, 16))
            p.setPen(QColor(design.SUBTLE))
            p.setFont(self.font())
            p.drawText(QRectF(32, y, self.LABEL - 36, self.ROW), Qt.AlignmentFlag.AlignVCenter, name)
        p.fillRect(QRectF(self.LABEL - 1, 0, 1, r.height()), QColor(design.LINE_STRONG))
        colours = {key: colour for key, _n, _i, colour in TRACKS}
        if self.project is not None:
            for track, item_id, rect in self._clip_rects():
                self._block(p, track, item_id, rect, colours.get(track, design.MUTED))
        # the playhead
        x = self.x_of(self.t)
        p.setPen(QPen(QColor(design.BRAND_B), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, r.height()))
        p.setBrush(QColor(design.BRAND_B))
        p.setPen(Qt.PenStyle.NoPen)
        head = QPainterPath()
        head.moveTo(x - 6, 0)
        head.lineTo(x + 6, 0)
        head.lineTo(x, 9)
        head.closeSubpath()
        p.drawPath(head)
        p.end()

    def _block(self, p: QPainter, track: str, item_id: str, rect: QRectF, colour: str) -> None:
        selected = self.selected == (track, item_id)
        p.save()
        path = QPainterPath()
        path.addRoundedRect(rect, 7, 7)
        p.setClipPath(path)
        p.fillRect(rect, design.alpha_q(colour, 0.22))
        assert self.project is not None
        if track == "video":
            scene = next((s for s in self.project.scenes if s.id == item_id), None)
            image = imaging.thumbnails().get(scene.image, 160) if scene is not None and scene.image else None
            if image is not None and not image.isNull():
                h = rect.height()
                w = image.width() * h / max(1, image.height())
                x = rect.left()
                while x < rect.right():
                    p.setOpacity(0.85)
                    p.drawImage(QRectF(x, rect.top(), w, h), image)
                    x += w
                p.setOpacity(1.0)
            label = scene.title if scene is not None else ""
            if scene is not None and scene.transition != "cut":
                p.setPen(QColor(design.TEXT))
                p.drawText(rect.adjusted(0, 0, -6, 0), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
                           "⟩ " + TRANSITIONS.get(scene.transition, "")[:10])
        elif track == "captions":
            cue = self.project.cues[int(item_id)] if item_id.isdigit() and int(item_id) < len(self.project.cues) else None
            label = cue.text if cue is not None else ""
        else:
            clip = next((c for c in self.project.clips if c.id == item_id), None)
            label = (clip.label or Path(clip.path).stem) if clip is not None else ""
            if clip is not None and clip.path:
                found = self._peaks.get(clip.path)
                if found is None:
                    found = peaks(Path(clip.path), 600) if Path(clip.path).is_file() else []
                    self._peaks[clip.path] = found
                if found:
                    p.setPen(QPen(design.alpha_q(colour, 0.75), 1))
                    mid = rect.center().y()
                    for i, value in enumerate(found):
                        x = rect.left() + rect.width() * i / len(found)
                        h = value * (rect.height() / 2 - 3)
                        p.drawLine(QPointF(x, mid - h), QPointF(x, mid + h))
        p.setClipping(False)
        p.setPen(QPen(QColor(colour), 2 if selected else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 7, 7)
        p.setPen(QColor(design.TEXT))
        p.drawText(rect.adjusted(8, 3, -6, -3), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                   QFontMetrics(p.font()).elidedText(label, Qt.TextElideMode.ElideRight, int(max(0, rect.width() - 14))))
        p.restore()
