"""The studio's icons, drawn as vector paths on a 24-unit grid.

Drawn by the program itself rather than loaded from files: they are sharp at every size and zoom,
take any colour (each studio's accent, a disabled grey), need no image format or icon font, and
carry no third party's licence. ``icon(name, colour)`` gives a QIcon; ``pixmap`` a picture.
"""

# The drawing table builds paths in one-line lambdas; their values are not used.
# mypy: disable-error-code="func-returns-value"
from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication


class _Draw:
    """What one icon is made of: lines to stroke and shapes to fill."""

    def __init__(self) -> None:
        self.stroke = QPainterPath()
        self.fill = QPainterPath()

    def poly(self, *points: tuple[float, float], closed: bool = False) -> _Draw:
        self.stroke.moveTo(*points[0])
        for p in points[1:]:
            self.stroke.lineTo(*p)
        if closed:
            self.stroke.closeSubpath()
        return self

    def line(self, x0: float, y0: float, x1: float, y1: float) -> _Draw:
        return self.poly((x0, y0), (x1, y1))

    def rect(self, x: float, y: float, w: float, h: float, r: float = 0.0, *, filled: bool = False) -> _Draw:
        (self.fill if filled else self.stroke).addRoundedRect(QRectF(x, y, w, h), r, r)
        return self

    def circle(self, cx: float, cy: float, r: float, *, filled: bool = False) -> _Draw:
        (self.fill if filled else self.stroke).addEllipse(QPointF(cx, cy), r, r)
        return self

    def path(self, build: Callable[[QPainterPath], object], *, filled: bool = False) -> _Draw:
        path = QPainterPath()
        build(path)
        (self.fill if filled else self.stroke).addPath(path)
        return self

    def arc(self, cx: float, cy: float, r: float, start: float, span: float) -> _Draw:
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        self.stroke.arcMoveTo(rect, start)
        self.stroke.arcTo(rect, start, span)
        return self

    def rays(self, cx: float, cy: float, r0: float, r1: float, n: int, offset: float = 0.0) -> _Draw:
        for k in range(n):
            a = math.radians(offset + k * 360 / n)
            self.line(cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r1 * math.cos(a), cy + r1 * math.sin(a))
        return self


def _star(p: QPainterPath, cx: float, cy: float, r: float, pinch: float = 0.18) -> None:
    """A four-pointed spark."""
    k = r * pinch
    p.moveTo(cx, cy - r)
    p.quadTo(cx + k, cy - k, cx + r, cy)
    p.quadTo(cx + k, cy + k, cx, cy + r)
    p.quadTo(cx - k, cy + k, cx - r, cy)
    p.quadTo(cx - k, cy - k, cx, cy - r)
    p.closeSubpath()


def _five_star(p: QPainterPath, cx: float, cy: float, r: float) -> None:
    for k in range(10):
        a = math.radians(-90 + k * 36)
        rr = r if k % 2 == 0 else r * 0.45
        pt = (cx + rr * math.cos(a), cy + rr * math.sin(a))
        p.moveTo(*pt) if k == 0 else p.lineTo(*pt)
    p.closeSubpath()


def _gear(d: _Draw) -> None:
    d.circle(12, 12, 3)
    d.circle(12, 12, 6.6)
    d.rays(12, 12, 6.6, 9.3, 8, 22.5)


def _arrow_arc(d: _Draw, clockwise: bool) -> None:
    if clockwise:
        d.arc(12, 12, 7, 120, -250)
        d.poly((16.5, 3.2), (19.8, 6.6), (15.6, 8.4))
    else:
        d.arc(12, 12, 7, 60, 250)
        d.poly((7.5, 3.2), (4.2, 6.6), (8.4, 8.4))


ICONS: dict[str, Callable[[_Draw], object]] = {
    "home": lambda d: d.poly((3, 10.5), (12, 3.5), (21, 10.5)).poly((5.5, 9), (5.5, 20), (18.5, 20), (18.5, 9))
    .poly((10, 20), (10, 14.5), (14, 14.5), (14, 20)),
    "message": lambda d: d.path(lambda p: (p.moveTo(7, 17), p.lineTo(7, 21), p.lineTo(11.5, 17), p.lineTo(18, 17),
                                           p.quadTo(21, 17, 21, 14), p.lineTo(21, 7), p.quadTo(21, 4, 18, 4),
                                           p.lineTo(6, 4), p.quadTo(3, 4, 3, 7), p.lineTo(3, 14),
                                           p.quadTo(3, 17, 6, 17), p.closeSubpath()))
    .line(7.5, 9, 16.5, 9).line(7.5, 12.5, 13.5, 12.5),
    "image": lambda d: d.rect(3, 4, 18, 16, 3).circle(8.5, 9.5, 1.8).poly((3.5, 17), (9, 12), (13, 16), (16, 13), (20.5, 17.5)),
    "film": lambda d: d.rect(3, 4, 18, 16, 2.5).line(7.5, 4, 7.5, 20).line(16.5, 4, 16.5, 20)
    .line(3, 9, 7.5, 9).line(3, 15, 7.5, 15).line(16.5, 9, 21, 9).line(16.5, 15, 21, 15),
    "gamepad": lambda d: d.rect(2.5, 6.5, 19, 11.5, 5.5).line(7.5, 10, 7.5, 14.5).line(5.25, 12.25, 9.75, 12.25)
    .circle(15.5, 11, 1.1, filled=True).circle(17.8, 13.6, 1.1, filled=True),
    "sliders": lambda d: d.line(4, 6, 7, 6).line(11, 6, 20, 6).circle(9, 6, 2).line(4, 12, 13, 12).line(17, 12, 20, 12)
    .circle(15, 12, 2).line(4, 18, 5, 18).line(9, 18, 20, 18).circle(7, 18, 2),
    "code": lambda d: d.poly((8, 7), (3, 12), (8, 17)).poly((16, 7), (21, 12), (16, 17)).line(13.5, 5, 10.5, 19),
    "library": lambda d: d.rect(4, 4, 7, 7, 2).rect(13, 4, 7, 7, 2).rect(4, 13, 7, 7, 2).rect(13, 13, 7, 7, 2),
    "settings": _gear,
    "search": lambda d: d.circle(10.5, 10.5, 6.5).line(15.5, 15.5, 20.5, 20.5),
    "plus": lambda d: d.line(12, 5, 12, 19).line(5, 12, 19, 12),
    "minus": lambda d: d.line(5, 12, 19, 12),
    "sparkles": lambda d: d.path(lambda p: _star(p, 10.5, 12.5, 8)).path(lambda p: _star(p, 18.5, 5, 2.8)),
    "wand": lambda d: d.line(4, 20, 14.5, 9.5).path(lambda p: _star(p, 17.5, 6.5, 3.6)).circle(20, 12, 0.9, filled=True)
    .circle(12, 3.5, 0.9, filled=True),
    "play": lambda d: d.path(lambda p: (p.moveTo(8, 5), p.lineTo(19, 12), p.lineTo(8, 19), p.closeSubpath()), filled=True),
    "pause": lambda d: d.rect(6.5, 5, 3.8, 14, 1.2, filled=True).rect(13.7, 5, 3.8, 14, 1.2, filled=True),
    "stop": lambda d: d.rect(6, 6, 12, 12, 2.5, filled=True),
    "download": lambda d: d.line(12, 4, 12, 15).poly((7.5, 10.5), (12, 15), (16.5, 10.5)).line(5, 19.5, 19, 19.5),
    "folder": lambda d: d.path(lambda p: (p.moveTo(3, 7), p.quadTo(3, 5, 5, 5), p.lineTo(9.5, 5), p.lineTo(11.5, 7),
                                          p.lineTo(19, 7), p.quadTo(21, 7, 21, 9), p.lineTo(21, 17),
                                          p.quadTo(21, 19, 19, 19), p.lineTo(5, 19), p.quadTo(3, 19, 3, 17),
                                          p.closeSubpath())),
    "copy": lambda d: d.rect(8.5, 8.5, 11.5, 11.5, 2.5).poly((15.5, 8.5), (15.5, 6), (13.5, 4), (6, 4), (4, 6), (4, 13.5),
                                                              (6, 15.5), (8.5, 15.5)),
    "trash": lambda d: d.line(4, 7, 20, 7).poly((9, 7), (9, 4.5), (15, 4.5), (15, 7)).poly((6, 7), (7, 20), (17, 20), (18, 7))
    .line(10, 11, 10, 16).line(14, 11, 14, 16),
    "external": lambda d: d.poly((14, 4), (20, 4), (20, 10)).line(20, 4, 11, 13)
    .poly((18, 14), (18, 19), (17, 20), (5, 20), (4, 19), (4, 7), (5, 6), (10, 6)),
    "x": lambda d: d.line(6, 6, 18, 18).line(18, 6, 6, 18),
    "check": lambda d: d.poly((5, 12.5), (10, 17.5), (19, 7)),
    "chevron_right": lambda d: d.poly((9, 6), (15, 12), (9, 18)),
    "chevron_left": lambda d: d.poly((15, 6), (9, 12), (15, 18)),
    "chevron_down": lambda d: d.poly((6, 9), (12, 15), (18, 9)),
    "chevron_up": lambda d: d.poly((6, 15), (12, 9), (18, 15)),
    "dice": lambda d: d.rect(4, 4, 16, 16, 3.5).circle(8.6, 8.6, 1.3, filled=True).circle(12, 12, 1.3, filled=True)
    .circle(15.4, 15.4, 1.3, filled=True),
    "lock": lambda d: d.rect(5, 11, 14, 10, 2.5).path(lambda p: (p.moveTo(8, 11), p.lineTo(8, 8), p.quadTo(8, 4, 12, 4),
                                                                  p.quadTo(16, 4, 16, 8), p.lineTo(16, 11))),
    "unlock": lambda d: d.rect(5, 11, 14, 10, 2.5).path(lambda p: (p.moveTo(8, 11), p.lineTo(8, 8), p.quadTo(8, 4, 12, 4),
                                                                    p.quadTo(15.6, 4, 16, 7))),
    "bolt": lambda d: d.poly((13, 3), (5, 13.5), (11.5, 13.5), (10.5, 21), (19, 10.5), (12.5, 10.5), closed=True),
    "cpu": lambda d: d.rect(6.5, 6.5, 11, 11, 2).rect(10, 10, 4, 4, 0.8).line(10, 3, 10, 6.5).line(14, 3, 14, 6.5)
    .line(10, 17.5, 10, 21).line(14, 17.5, 14, 21).line(3, 10, 6.5, 10).line(3, 14, 6.5, 14).line(17.5, 10, 21, 10)
    .line(17.5, 14, 21, 14),
    "clock": lambda d: d.circle(12, 12, 9).poly((12, 7), (12, 12), (15.5, 14)),
    "star": lambda d: d.path(lambda p: _five_star(p, 12, 12.6, 9)),
    "star_filled": lambda d: d.path(lambda p: _five_star(p, 12, 12.6, 9), filled=True),
    "layers": lambda d: d.poly((12, 3), (21, 8), (12, 13), (3, 8), closed=True).poly((3, 12.5), (12, 17.5), (21, 12.5))
    .poly((3, 16.5), (12, 21.5), (21, 16.5)),
    "crop": lambda d: d.poly((6.5, 3), (6.5, 17.5), (21, 17.5)).poly((3, 6.5), (17.5, 6.5), (17.5, 21)),
    "rotate_left": lambda d: _arrow_arc(d, False),
    "rotate_right": lambda d: _arrow_arc(d, True),
    "refresh": lambda d: _arrow_arc(d, True),
    "flip": lambda d: d.line(12, 3, 12, 21).poly((9.5, 7), (3.5, 17), (9.5, 17), closed=True)
    .poly((14.5, 7), (20.5, 17), (14.5, 17), closed=True),
    "sun": lambda d: d.circle(12, 12, 3.8).rays(12, 12, 6.6, 9.2, 8),
    "contrast": lambda d: d.circle(12, 12, 8.5).path(lambda p: (p.moveTo(12, 3.5), p.arcTo(QRectF(3.5, 3.5, 17, 17), 90, -180),
                                                                  p.closeSubpath()), filled=True),
    "droplet": lambda d: d.path(lambda p: (p.moveTo(12, 3), p.cubicTo(9, 7, 5.5, 11, 5.5, 15), p.cubicTo(5.5, 18.6, 8.4, 21, 12, 21),
                                           p.cubicTo(15.6, 21, 18.5, 18.6, 18.5, 15), p.cubicTo(18.5, 11, 15, 7, 12, 3),
                                           p.closeSubpath())),
    "type": lambda d: d.poly((5, 7), (5, 5), (19, 5), (19, 7)).line(12, 5, 12, 19).line(9, 19, 15, 19),
    "maximize": lambda d: d.poly((4, 9), (4, 4), (9, 4)).poly((15, 4), (20, 4), (20, 9)).poly((20, 15), (20, 20), (15, 20))
    .poly((9, 20), (4, 20), (4, 15)),
    "sidebar": lambda d: d.rect(3, 4, 18, 16, 2.5).line(9.5, 4, 9.5, 20),
    "send": lambda d: d.poly((4, 11.5), (20, 4), (13.5, 20), (11, 13), closed=True).line(11, 13, 20, 4),
    "eye": lambda d: d.path(lambda p: (p.moveTo(2.5, 12), p.cubicTo(5, 7, 8.5, 5, 12, 5), p.cubicTo(15.5, 5, 19, 7, 21.5, 12),
                                       p.cubicTo(19, 17, 15.5, 19, 12, 19), p.cubicTo(8.5, 19, 5, 17, 2.5, 12),
                                       p.closeSubpath())).circle(12, 12, 3),
    "info": lambda d: d.circle(12, 12, 9).line(12, 11, 12, 16.5).circle(12, 7.8, 1.1, filled=True),
    "warning": lambda d: d.poly((12, 3.5), (21.5, 19.5), (2.5, 19.5), closed=True).line(12, 9.5, 12, 14)
    .circle(12, 16.9, 1.05, filled=True),
    "filter": lambda d: d.poly((3.5, 5), (20.5, 5), (14, 12.5), (14, 19), (10, 21), (10, 12.5), closed=True),
    "calendar": lambda d: d.rect(3.5, 5, 17, 15, 2.5).line(3.5, 10, 20.5, 10).line(8, 3, 8, 7).line(16, 3, 16, 7),
    "music": lambda d: d.circle(8.5, 18, 2.5).circle(17.5, 16, 2.5).poly((11, 18), (11, 5), (20, 3), (20, 16)),
    "mic": lambda d: d.rect(9, 3, 6, 11, 3).path(lambda p: (p.moveTo(5.5, 11), p.quadTo(5.5, 17.5, 12, 17.5),
                                                             p.quadTo(18.5, 17.5, 18.5, 11))).line(12, 17.5, 12, 21),
    "captions": lambda d: d.rect(3, 5, 18, 14, 3).line(6.5, 11, 10.5, 11).line(6.5, 14.5, 9, 14.5).line(12, 14.5, 17.5, 14.5)
    .line(13.5, 11, 17.5, 11),
    "cube": lambda d: d.poly((12, 3), (20, 7.5), (20, 16.5), (12, 21), (4, 16.5), (4, 7.5), closed=True)
    .poly((4, 7.5), (12, 12), (20, 7.5)).line(12, 12, 12, 21),
    "heart": lambda d: d.path(lambda p: (p.moveTo(12, 20), p.cubicTo(5, 15, 3, 12, 3, 8.6), p.cubicTo(3, 6, 5, 4, 7.5, 4),
                                         p.cubicTo(9.5, 4, 11, 5.2, 12, 6.8), p.cubicTo(13, 5.2, 14.5, 4, 16.5, 4),
                                         p.cubicTo(19, 4, 21, 6, 21, 8.6), p.cubicTo(21, 12, 19, 15, 12, 20),
                                         p.closeSubpath())),
    "palette": lambda d: d.path(lambda p: (p.moveTo(12, 3), p.cubicTo(17, 3, 21, 6.5, 21, 11), p.cubicTo(21, 14, 18.5, 15, 16.5, 15),
                                           p.lineTo(15, 15), p.cubicTo(13.5, 15, 13, 16.5, 13.8, 17.6),
                                           p.cubicTo(14.6, 18.8, 14, 21, 12, 21), p.cubicTo(7, 21, 3, 17, 3, 12),
                                           p.cubicTo(3, 7, 7, 3, 12, 3), p.closeSubpath()))
    .circle(7.8, 11, 1.25, filled=True).circle(10.5, 7.2, 1.25, filled=True).circle(15.2, 7.6, 1.25, filled=True),
    "hash": lambda d: d.line(9.5, 4, 7.5, 20).line(16.5, 4, 14.5, 20).line(4.5, 9, 20, 9).line(4, 15, 19.5, 15),
    "users": lambda d: d.circle(9, 8, 3.5).path(lambda p: (p.moveTo(2.5, 20), p.quadTo(2.5, 14, 9, 14), p.quadTo(15.5, 14, 15.5, 20)))
    .circle(17, 9, 2.5).path(lambda p: (p.moveTo(17.5, 14), p.quadTo(21.5, 14.2, 21.5, 19))),
    "target": lambda d: d.circle(12, 12, 9).circle(12, 12, 5.5).circle(12, 12, 2, filled=True),
    "grid": lambda d: d.rect(4, 4, 7, 7, 2).rect(13, 4, 7, 7, 2).rect(4, 13, 7, 7, 2).rect(13, 13, 7, 7, 2),
    "list": lambda d: d.line(9, 6, 20, 6).line(9, 12, 20, 12).line(9, 18, 20, 18).circle(5, 6, 1.1, filled=True)
    .circle(5, 12, 1.1, filled=True).circle(5, 18, 1.1, filled=True),
    "command": lambda d: d.path(lambda p: (p.moveTo(9, 9), p.lineTo(9, 6.5), p.arcTo(QRectF(4, 4, 5, 5), 0, 270), p.lineTo(15, 9),
                                           p.arcTo(QRectF(15, 4, 5, 5), 270, 270), p.lineTo(15, 15), p.arcTo(QRectF(15, 15, 5, 5), 180, 270),
                                           p.lineTo(9, 15), p.arcTo(QRectF(4, 15, 5, 5), 90, 270), p.lineTo(9, 9))),
    "dot": lambda d: d.circle(12, 12, 5, filled=True),
    "pin": lambda d: d.path(lambda p: (p.moveTo(12, 21), p.cubicTo(7, 15.5, 5, 12.5, 5, 9.5), p.cubicTo(5, 5.5, 8, 3, 12, 3),
                                       p.cubicTo(16, 3, 19, 5.5, 19, 9.5), p.cubicTo(19, 12.5, 17, 15.5, 12, 21),
                                       p.closeSubpath())).circle(12, 9.5, 2.5),
    "upload": lambda d: d.line(12, 15, 12, 4).poly((7.5, 8.5), (12, 4), (16.5, 8.5)).line(5, 19.5, 19, 19.5),
    "shield": lambda d: d.path(lambda p: (p.moveTo(12, 3), p.lineTo(19.5, 6), p.lineTo(19.5, 11.5), p.cubicTo(19.5, 16, 16.5, 19.3, 12, 21),
                                          p.cubicTo(7.5, 19.3, 4.5, 16, 4.5, 11.5), p.lineTo(4.5, 6), p.closeSubpath()))
    .poly((8.8, 12), (11, 14.2), (15.4, 9.6)),
}


def _render(name: str, colour: str, size: int, dpr: float, weight: float) -> QPixmap:
    draw = _Draw()
    ICONS.get(name, ICONS["dot"])(draw)
    pix = QPixmap(round(size * dpr), round(size * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    colour_q = QColor(colour)
    pen = QPen(colour_q, weight)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(draw.stroke)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(colour_q)
    p.drawPath(draw.fill)
    p.end()
    return pix


def _dpr() -> float:
    app = QApplication.instance()
    screen = app.primaryScreen() if isinstance(app, QApplication) else None
    return max(1.0, float(screen.devicePixelRatio())) if screen is not None else 1.0


@lru_cache(maxsize=1024)
def pixmap(name: str, colour: str = "#eceef5", size: int = 20, weight: float = 1.8) -> QPixmap:
    return _render(name, colour, size, max(2.0, _dpr()), weight)


@lru_cache(maxsize=512)
def icon(name: str, colour: str = "#b6bdcc", size: int = 20, *, active: str = "", disabled: str = "#5b6377") -> QIcon:
    """An icon in ``colour``; ``active`` is its colour when checked or hovered, if different."""
    result = QIcon()
    result.addPixmap(pixmap(name, colour, size), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(pixmap(name, active or colour, size), QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(pixmap(name, active or colour, size), QIcon.Mode.Active, QIcon.State.Off)
    result.addPixmap(pixmap(name, disabled, size), QIcon.Mode.Disabled, QIcon.State.Off)
    return result


def brand_mark(size: int = 32) -> QPixmap:
    """ELI's mark: a luminous orb with a spark in it, in the brand's two colours."""
    dpr = max(2.0, _dpr())
    pix = QPixmap(round(size * dpr), round(size * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = size / 2
    glow = QRadialGradient(QPointF(r * 0.7, r * 0.6), r * 1.3)
    glow.setColorAt(0.0, QColor("#c4b5fd"))
    glow.setColorAt(0.45, QColor("#8b5cf6"))
    glow.setColorAt(1.0, QColor("#0e7490"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.3, size * 0.3)
    spark = QPainterPath()
    _star(spark, r, r, r * 0.58, 0.2)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawPath(spark)
    p.end()
    return pix


def size(n: int) -> QSize:
    return QSize(n, n)
