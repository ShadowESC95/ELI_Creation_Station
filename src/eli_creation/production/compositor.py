"""One frame of a film at any moment: each scene's picture graded, the camera moving over it, the
transition into the next, its words on screen and the captions.

Drawn with Qt's painter on an image, which works off the window's thread too, so the preview in
the window and the exported video are drawn by exactly the same code.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen

from eli_creation.production import grade as grading
from eli_creation.production.formats import CAMERA, FORMATS, ease
from eli_creation.production.project import Project, Scene


class Compositor:
    def __init__(self, project: Project, size: tuple[int, int] | None = None) -> None:
        self.project = project
        fmt = FORMATS.get(project.format, FORMATS["youtube"])
        self.size = size or (fmt.width, fmt.height)
        self._pictures: dict[tuple[str, str], QImage] = {}
        self._lock = threading.Lock()

    # ── pictures ──
    def _picture(self, scene: Scene) -> QImage | None:
        if not scene.image or not Path(scene.image).is_file():
            return None
        key = (scene.image, repr(scene.grade))
        with self._lock:
            found = self._pictures.get(key)
        if found is not None:
            return found
        from eli_creation.gui import imaging

        try:
            pil = imaging.load_pil(scene.image, int(max(self.size) * 1.4))
            if not scene.grade.is_plain():
                pil = grading.apply(pil, scene.grade)
            picture = imaging.to_qimage(pil)
        except Exception:
            return None
        with self._lock:
            self._pictures[key] = picture
        return picture

    def forget(self) -> None:
        with self._lock:
            self._pictures.clear()

    # ── a frame ──
    def frame(self, t: float) -> QImage:
        w, h = self.size
        image = QImage(w, h, QImage.Format.Format_RGB32)
        image.fill(QColor("#000000"))
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        times = self.project.scene_times()
        for n, (scene, start, end) in enumerate(times):
            if not start <= t < end + 1e-6:
                continue
            local = (t - start) / max(0.001, end - start)
            opacity, shift, zoom = 1.0, 0.0, 1.0
            nxt = times[n + 1] if n + 1 < len(times) else None
            if nxt is not None and t >= nxt[1] and scene.transition != "cut":
                span = max(0.001, end - nxt[1])
                into = (t - nxt[1]) / span  # 0 → 1 across the overlap
                if scene.transition == "crossfade":
                    opacity = 1.0  # the next scene fades in over this one
                elif scene.transition == "slide_left":
                    shift = -ease(into) * w
                elif scene.transition == "zoom":
                    zoom = 1 + ease(into) * 0.6
                    opacity = 1 - into
            prev = times[n - 1] if n > 0 else None
            if prev is not None and t < end and prev[0].transition != "cut" and t < prev[2]:
                span = max(0.001, prev[2] - start)
                into = (t - start) / span
                kind = prev[0].transition
                if kind in ("crossfade", "zoom"):
                    opacity = ease(into)
                elif kind == "slide_left":
                    shift = (1 - ease(into)) * w
                elif kind in ("fade_black", "fade_white"):
                    opacity = 1.0 if into > 0.5 else 0.0
            self._draw_scene(p, scene, local, opacity, shift, zoom)
            if scene.title_text and opacity > 0.5:
                self._title(p, scene.title_text, local)
        self._fades(p, times, t)
        if self.project.captions_on:
            for cue in self.project.cues:
                if cue.start <= t < cue.end:
                    self._caption(p, cue.text)
                    break
        p.end()
        return image

    def _draw_scene(self, p: QPainter, scene: Scene, local: float, opacity: float, shift: float, zoom_extra: float) -> None:
        w, h = self.size
        picture = self._picture(scene)
        p.save()
        p.setOpacity(max(0.0, min(1.0, opacity)))
        if picture is None:
            p.fillRect(QRectF(0, 0, w, h), QColor("#0b1220"))
            p.setPen(QColor("#5b6b86"))
            p.setFont(QFont(p.font().family(), max(10, h // 30)))
            p.drawText(QRectF(0, 0, w, h), int(Qt.AlignmentFlag.AlignCenter), scene.title or "A scene with no picture yet")
            p.restore()
            return
        _, a, b = CAMERA.get(scene.camera, CAMERA["static"])
        k = ease(local)
        zoom = (a[0] + (b[0] - a[0]) * k) * zoom_extra
        px = a[1] + (b[1] - a[1]) * k
        py = a[2] + (b[2] - a[2]) * k
        cover = max(w / picture.width(), h / picture.height()) * zoom
        dw, dh = picture.width() * cover, picture.height() * cover
        room_x, room_y = (dw - w) / 2, (dh - h) / 2
        x = (w - dw) / 2 - px * room_x + shift
        y = (h - dh) / 2 - py * room_y
        p.drawImage(QRectF(x, y, dw, dh), picture)
        p.restore()

    def _fades(self, p: QPainter, times: list[tuple[Scene, float, float]], t: float) -> None:
        """Fade through black or white over the overlap of a scene with the next."""
        for n, (scene, _start, end) in enumerate(times[:-1]):
            if scene.transition not in ("fade_black", "fade_white"):
                continue
            nxt_start = times[n + 1][1]
            if nxt_start <= t < end:
                into = (t - nxt_start) / max(0.001, end - nxt_start)
                strength = 1 - abs(into - 0.5) * 2
                colour = QColor("#000000" if scene.transition == "fade_black" else "#ffffff")
                colour.setAlphaF(max(0.0, min(1.0, strength)))
                p.fillRect(QRectF(0, 0, *self.size), colour)

    def _font(self, share: float, bold: bool = True) -> QFont:
        font = QFont()
        font.setPixelSize(max(12, int(self.size[1] * share * self.project.caption_size)))
        font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Medium)
        return font

    def _title(self, p: QPainter, words: str, local: float) -> None:
        w, h = self.size
        font = self._font(0.075 if w >= h else 0.05)
        p.save()
        p.setOpacity(min(1.0, local * 4, (1 - local) * 4 + 0.2))
        p.setFont(font)
        box = QRectF(w * 0.08, h * 0.30, w * 0.84, h * 0.4)
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, words)
        p.setPen(QPen(QColor(0, 0, 0, 170), max(2.0, font.pixelSize() / 14)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        flags = int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap)
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(box.translated(2, 3), flags, words)
        p.setPen(QColor("#ffffff"))
        p.drawText(box, flags, words)
        p.restore()

    def _caption(self, p: QPainter, words: str) -> None:
        w, h = self.size
        font = self._font(0.042 if w >= h else 0.032, bold=False)
        p.save()
        p.setFont(font)
        metrics = QFontMetricsF(font)
        width = min(w * 0.86, metrics.horizontalAdvance(words) + font.pixelSize() * 1.4)
        lines = max(1, int(metrics.horizontalAdvance(words) // (w * 0.82)) + 1)
        height = lines * metrics.lineSpacing() + font.pixelSize() * 0.7
        box = QRectF((w - width) / 2, h * 0.88 - height, width, height)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 165))
        p.drawRoundedRect(box, font.pixelSize() * 0.35, font.pixelSize() * 0.35)
        p.setPen(QColor("#ffffff"))
        p.drawText(box.adjusted(font.pixelSize() * 0.5, 0, -font.pixelSize() * 0.5, 0),
                   int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), words)
        p.restore()
