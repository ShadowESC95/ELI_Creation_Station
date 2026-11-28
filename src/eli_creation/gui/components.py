"""The studio's building blocks: cards, chips, segmented choices, switches, steppers, sliders,
collapsible sections, the Create button, empty states, toasts and a spinner.

Each is painted by the studio rather than left to the platform's style, so the window looks the
same on Windows, macOS and Linux, and every control speaks the same visual language.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QLineF,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from eli_creation.gui import design, icons
from eli_creation.gui.widgets import FlowLayout


# ── text and layout ──────────────────────────────────────────────────────
def text(value: str = "", kind: str = "body", *, tone: str = "", wrap: bool = False,
         selectable: bool = False, rich: bool = False) -> QLabel:
    label = QLabel(value)
    design.set_type(label, kind)
    if tone:
        label.setProperty("tone", tone)
    label.setWordWrap(wrap)
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    if rich:
        label.setOpenExternalLinks(True)
    if selectable:
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def eyebrow(value: str) -> QLabel:
    label = text(value.upper(), "tiny", tone="muted")
    label.setProperty("eyebrow", True)
    return label


def hbox(*items: QWidget | QLayout | int | None, spacing: int = 8, margins: int = 0) -> QHBoxLayout:
    """A row: widgets, layouts, a number for fixed space, None for elastic space."""
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(margins, margins, margins, margins)
    for item in items:
        _add(lay, item)
    return lay


def vbox(*items: QWidget | QLayout | int | None, spacing: int = 8, margins: int = 0) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(margins, margins, margins, margins)
    for item in items:
        _add(lay, item)
    return lay


def _add(lay: QHBoxLayout | QVBoxLayout, item: QWidget | QLayout | int | None) -> None:
    if item is None:
        lay.addStretch(1)
    elif isinstance(item, int):
        lay.addSpacing(item)
    elif isinstance(item, QLayout):
        lay.addLayout(item)
    else:
        lay.addWidget(item)


def holder(layout: QLayout) -> QWidget:
    widget = QWidget()
    widget.setLayout(layout)
    return widget


class Card(QFrame):
    """A raised panel. ``body`` is its layout."""

    def __init__(self, *, soft: bool = False, padding: int = 18, spacing: int = 12, shadow: bool = False) -> None:
        super().__init__()
        self.setProperty("card", "soft" if soft else "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)
        if shadow:
            add_shadow(self)

    def add(self, *items: QWidget | QLayout | int | None) -> Card:
        for item in items:
            _add(self.body, item)
        return self


def add_shadow(widget: QWidget, blur: int = 36, y: int = 10, opacity: int = 110) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(effect)


def hairline() -> QFrame:
    line = QFrame()
    line.setProperty("hairline", True)
    return line


def fade_in(widget: QWidget, ms: int = 220) -> None:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))  # type: ignore[arg-type]
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# ── buttons ──────────────────────────────────────────────────────────────
def button(label: str, on_click: Callable[[], Any] | None = None, *, icon: str = "", variant: str = "",
           tip: str = "", primary: bool = False) -> QPushButton:
    widget = QPushButton(label)
    if icon:
        widget.setIcon(icons.icon(icon, design.ON_BRAND if primary else design.SUBTLE, 18,
                                  active=design.ON_BRAND if primary else design.TEXT))
        widget.setIconSize(QSize(16, 16))
    if primary:
        widget.setProperty("kind", "primary")
    if variant:
        widget.setProperty("variant", variant)
    if tip:
        widget.setToolTip(tip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click is not None:
        widget.clicked.connect(lambda _c=False: on_click())
    return widget


def icon_button(name: str, tip: str, on_click: Callable[[], Any] | None = None, *, size: int = 18,
                checkable: bool = False, colour: str = design.SUBTLE) -> QToolButton:
    widget = QToolButton()
    widget.setIcon(icons.icon(name, colour, size, active=design.TEXT))
    widget.setIconSize(QSize(size, size))
    widget.setToolTip(tip)
    widget.setCheckable(checkable)
    widget.setAutoRaise(True)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click is not None:
        widget.clicked.connect(lambda _c=False: on_click())
    return widget


class GlowButton(QPushButton):
    """The Create button: the brand gradient, a soft glow, and a spinner while work runs."""

    def __init__(self, label: str = "Create", icon: str = "sparkles", *, accent: str = "", hint: str = "") -> None:
        super().__init__(label)
        self._icon = icon
        self._accent = accent or design.BRAND_A
        self._hint = hint
        self._busy = False
        self._angle = 0.0
        self._hover = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._spin)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        add_shadow(self, blur=30, y=8, opacity=90)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt's name
        fm = QFontMetrics(self._font())
        hint = QFontMetrics(self.font()).horizontalAdvance(self._hint) + 16 if self._hint else 0
        return QSize(fm.horizontalAdvance(self.text()) + 74 + hint, 46)

    def _font(self) -> QFont:
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(self.font().pointSizeF() * 1.08)
        return font

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._timer.start(16) if busy else self._timer.stop()
        self.update()

    def _spin(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    def enterEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = 1.0
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = 0.0
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = 12
        if self.isEnabled():
            g = design.brand_gradient(r.left(), r.top(), r.right(), r.bottom(), self._accent, design.BRAND_B)
            p.setBrush(g)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, radius, radius)
            if self._hover:
                p.setBrush(QColor(255, 255, 255, 26))
                p.drawRoundedRect(r, radius, radius)
            sheen = QRectF(r.left(), r.top(), r.width(), r.height() / 2)
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawRoundedRect(sheen, radius, radius)
            fg = QColor(design.ON_BRAND)
        else:
            p.setBrush(QColor(design.HOVER))
            p.setPen(QPen(QColor(design.LINE_STRONG), 1))
            p.drawRoundedRect(r, radius, radius)
            fg = QColor(design.FAINT)
        font = self._font()
        fm = QFontMetrics(font)
        label = "Working…" if self._busy else self.text()
        width = 22 + 10 + fm.horizontalAdvance(label)
        x = r.center().x() - width / 2 - (self._hint_width() / 2 if self._hint and not self._busy else 0)
        cy = r.center().y()
        if self._busy:
            p.setPen(QPen(fg, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(x + 2, cy - 9, 18, 18), int(-self._angle * 16), 270 * 16)
        else:
            p.drawPixmap(int(x), int(cy - 11), icons.pixmap(self._icon, fg.name(), 22))
        p.setFont(font)
        p.setPen(fg)
        p.drawText(QRectF(x + 32, r.top(), fm.horizontalAdvance(label) + 4, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        if self._hint and not self._busy:
            p.setFont(self.font())
            p.setPen(QColor(4, 18, 26, 150) if self.isEnabled() else QColor(design.FAINT))
            hx = x + 32 + fm.horizontalAdvance(label) + 14
            p.drawText(QRectF(hx, r.top(), self._hint_width(), r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._hint)
        p.end()

    def _hint_width(self) -> int:
        return QFontMetrics(self.font()).horizontalAdvance(self._hint) + 4


class Chip(QAbstractButton):
    """A rounded, checkable choice, with an icon or a coloured dot and an optional note."""

    def __init__(self, label: str, *, icon: str = "", dot: str = "", note: str = "", accent: str = "",
                 checkable: bool = True) -> None:
        super().__init__()
        self.setText(label)
        self.setCheckable(checkable)
        self._icon, self._dot, self._note = icon, dot, note
        self._accent = accent or design.BRAND_A
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_note(self, note: str) -> None:
        self._note = note
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetrics(self.font())
        width = fm.horizontalAdvance(self.text()) + 28
        if self._icon or self._dot:
            width += 22
        if self._note:
            width += fm.horizontalAdvance(self._note) + 10
        return QSize(width, max(32, fm.height() + 14))

    def enterEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        on = self.isChecked()
        enabled = self.isEnabled()
        if on:
            p.setBrush(QColor(design.alpha_q(self._accent, 0.18)))
            p.setPen(QPen(QColor(self._accent), 1.2))
        else:
            p.setBrush(QColor(design.HOVER if self._hover and enabled else design.SURFACE))
            p.setPen(QPen(QColor(design.LINE_STRONG), 1))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        fg = QColor(design.TEXT if on else design.SUBTLE) if enabled else QColor(design.FAINT)
        x = 14.0
        if self._dot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self._dot if enabled else design.FAINT))
            p.drawEllipse(QPointF(x + 5, r.center().y()), 5, 5)
            x += 20
        elif self._icon:
            colour = self._accent if on else (design.SUBTLE if enabled else design.FAINT)
            p.drawPixmap(int(x), int(r.center().y() - 8), icons.pixmap(self._icon, colour, 16))
            x += 22
        fm = QFontMetrics(self.font())
        p.setPen(fg)
        p.setFont(self.font())
        p.drawText(QRectF(x, 0, fm.horizontalAdvance(self.text()) + 2, r.height()),
                   Qt.AlignmentFlag.AlignVCenter, self.text())
        if self._note:
            x += fm.horizontalAdvance(self.text()) + 8
            p.setPen(QColor(design.MUTED if enabled else design.FAINT))
            p.drawText(QRectF(x, 0, fm.horizontalAdvance(self._note) + 4, r.height()),
                       Qt.AlignmentFlag.AlignVCenter, self._note)
        p.end()


class ChipGroup(QWidget):
    """Chips that wrap onto the next line. ``exclusive``: exactly one is chosen."""

    changed = Signal()

    def __init__(self, options: Sequence[tuple[str, str]], *, exclusive: bool = True, chosen: Sequence[str] = (),
                 icons_for: dict[str, str] | None = None, dots: dict[str, str] | None = None,
                 notes: dict[str, str] | None = None, accent: str = "") -> None:
        super().__init__()
        self.exclusive = exclusive
        self.chips: dict[str, Chip] = {}
        flow = FlowLayout(self, 8)
        flow.setContentsMargins(0, 0, 0, 0)
        for label_text, key in options:
            chip = Chip(label_text, icon=(icons_for or {}).get(key, ""), dot=(dots or {}).get(key, ""),
                        note=(notes or {}).get(key, ""), accent=accent)
            chip.setChecked(key in chosen)
            chip.clicked.connect(lambda _c=False, k=key: self._clicked(k))
            self.chips[key] = chip
            flow.addWidget(chip)
        if exclusive and not any(c.isChecked() for c in self.chips.values()) and self.chips:
            next(iter(self.chips.values())).setChecked(True)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _clicked(self, key: str) -> None:
        if self.exclusive:
            for k, chip in self.chips.items():
                chip.setChecked(k == key)
        self.changed.emit()

    def value(self) -> str:
        return next((k for k, c in self.chips.items() if c.isChecked()), "")

    def values(self) -> list[str]:
        return [k for k, c in self.chips.items() if c.isChecked()]

    def set_value(self, key: str) -> None:
        for k, chip in self.chips.items():
            chip.setChecked(k == key if self.exclusive else (chip.isChecked() or k == key))
        self.changed.emit()

    def set_values(self, keys: Sequence[str]) -> None:
        for k, chip in self.chips.items():
            chip.setChecked(k in keys)
        self.changed.emit()


def aspect_glyph(ratio: float, colour: str, size: int = 18) -> QPixmap:
    """A small outline of a frame of the given width:height."""
    dpr = icons.pixmap("dot", "#000000", size).devicePixelRatio()
    pix = QPixmap(round(size * dpr), round(size * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    w, h = (size - 3, (size - 3) / ratio) if ratio >= 1 else ((size - 3) * ratio, size - 3)
    p.setPen(QPen(QColor(colour), 1.6))
    p.drawRoundedRect(QRectF((size - w) / 2, (size - h) / 2, w, h), 2.5, 2.5)
    p.end()
    return pix


class Segmented(QWidget):
    """Choices side by side in one rounded track; the chosen one slides under a highlight."""

    changed = Signal(str)

    def __init__(self, options: Sequence[tuple[str, str]], value: str = "", *,
                 glyphs: Mapping[str, Callable[..., QPixmap]] | None = None, accent: str = "") -> None:
        super().__init__()
        self.options = list(options)
        self.glyphs = glyphs or {}
        self.accent = accent or design.BRAND_A
        self._index = max(0, next((i for i, (_, k) in enumerate(self.options) if k == value), 0))
        self._pos = float(self._index)
        self._hover = -1
        self._anim = QPropertyAnimation(self, b"slide", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, value: float) -> None:
        self._pos = value
        self.update()

    slide = Property(float, _get_pos, _set_pos)

    def value(self) -> str:
        return self.options[self._index][1] if self.options else ""

    def set_value(self, key: str) -> None:
        for i, (_, k) in enumerate(self.options):
            if k == key:
                self._choose(i)

    def _segment_width(self) -> float:
        return (self.width() - 6) / max(1, len(self.options))

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetrics(self.font())
        widest = max((fm.horizontalAdvance(t) for t, _ in self.options), default=40)
        extra = 24 if self.glyphs else 0
        return QSize(int((widest + 24 + extra) * len(self.options) + 6), max(36, fm.height() + 18))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = int((event.position().x() - 3) // max(1.0, self._segment_width()))
        self.update()

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        self._hover = -1
        self.update()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        index = int((event.position().x() - 3) // max(1.0, self._segment_width()))
        if 0 <= index < len(self.options):
            self._choose(index)

    def _choose(self, index: int) -> None:
        if index == self._index:
            return
        self._index = index
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(float(index))
        self._anim.start()
        self.changed.emit(self.value())

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(design.LINE_STRONG), 1))
        p.setBrush(QColor(design.SURFACE))
        p.drawRoundedRect(r, 11, 11)
        w = self._segment_width()
        hi = QRectF(3 + self._pos * w, 3, w, r.height() - 5)
        p.setPen(QPen(QColor(design.alpha_q(self.accent, 0.7)), 1))
        p.setBrush(QColor(design.alpha_q(self.accent, 0.20)))
        p.drawRoundedRect(hi, 8, 8)
        p.setFont(self.font())
        fm = QFontMetrics(self.font())
        for i, (label_text, key) in enumerate(self.options):
            cell = QRectF(3 + i * w, 3, w, r.height() - 5)
            chosen = i == self._index
            colour = design.TEXT if chosen else (design.SUBTLE if i == self._hover else design.MUTED)
            glyph = self.glyphs.get(key)
            content = fm.horizontalAdvance(label_text) + (22 if glyph else 0)
            x = cell.center().x() - content / 2
            if glyph:
                pix = glyph(self.accent if chosen else colour)
                p.drawPixmap(int(x), int(cell.center().y() - 9), pix)
                x += 22
            p.setPen(QColor(colour))
            p.drawText(QRectF(x, cell.top(), content, cell.height()), Qt.AlignmentFlag.AlignVCenter, label_text)
        p.end()


class Switch(QAbstractButton):
    """An on/off toggle with a sliding knob."""

    def __init__(self, label: str = "", checked: bool = False) -> None:
        super().__init__()
        self.setText(label)
        self.setCheckable(True)
        self.setChecked(checked)
        self._knob = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(150)
        self.toggled.connect(self._animate)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _get_knob(self) -> float:
        return self._knob

    def _set_knob(self, value: float) -> None:
        self._knob = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetrics(self.font())
        return QSize(40 + (fm.horizontalAdvance(self.text()) + 10 if self.text() else 0), max(24, fm.height() + 6))

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = 20.0
        track = QRectF(0, (self.height() - h) / 2, 36, h)
        on = QColor(design.BRAND_A)
        off = QColor(design.LINE_STRONG)
        t = self._knob
        colour = QColor(round(off.red() + (on.red() - off.red()) * t), round(off.green() + (on.green() - off.green()) * t),
                        round(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour if self.isEnabled() else QColor(design.HOVER))
        p.drawRoundedRect(track, h / 2, h / 2)
        p.setBrush(QColor("#ffffff") if self.isEnabled() else QColor(design.FAINT))
        p.drawEllipse(QPointF(track.left() + h / 2 + t * (track.width() - h), track.center().y()), h / 2 - 3, h / 2 - 3)
        if self.text():
            p.setPen(QColor(design.SUBTLE if self.isEnabled() else design.FAINT))
            p.setFont(self.font())
            p.drawText(QRectF(46, 0, self.width() - 46, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())
        p.end()


class Stepper(QWidget):
    """A whole number with − and + either side."""

    changed = Signal(int)

    def __init__(self, low: int, high: int, value: int, *, suffix: str = "") -> None:
        super().__init__()
        self.low, self.high, self._value, self.suffix = low, high, value, suffix
        self.minus = icon_button("minus", "Fewer", lambda: self.set_value(self._value - 1), size=14)
        self.plus = icon_button("plus", "More", lambda: self.set_value(self._value + 1), size=14)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumWidth(QFontMetrics(self.font()).horizontalAdvance(f"{high}{suffix}") + 14)
        frame = QFrame()
        frame.setProperty("card", "soft")
        row = QHBoxLayout(frame)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(2)
        row.addWidget(self.minus)
        row.addWidget(self.label)
        row.addWidget(self.plus)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        self.set_value(value)

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        self._value = max(self.low, min(self.high, int(value)))
        self.label.setText(f"{self._value}{self.suffix}")
        self.minus.setEnabled(self._value > self.low)
        self.plus.setEnabled(self._value < self.high)
        self.changed.emit(self._value)


class SliderField(QWidget):
    """A named value on a slider, shown beside it; a double-click on the name puts it back."""

    changed = Signal(float)

    def __init__(self, name: str, low: float, high: float, value: float, *, step: float = 0.01,
                 fmt: str = "{:.2f}", icon: str = "") -> None:
        super().__init__()
        self.low, self.high, self.step, self.fmt, self.default = low, high, step, fmt, value
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, round((high - low) / step))
        self.slider.valueChanged.connect(self._moved)
        self.name = text(name, "small", tone="subtle")
        self.name.setToolTip("Double-click to put it back")
        self.name.mouseDoubleClickEvent = lambda _e: self.set_value(self.default)  # type: ignore[method-assign]
        self.shown = text("", "small", tone="muted")
        self.shown.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        if icon:
            mark = QLabel()
            mark.setPixmap(icons.pixmap(icon, design.MUTED, 15))
            head.addWidget(mark)
        head.addWidget(self.name)
        head.addStretch(1)
        head.addWidget(self.shown)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addLayout(head)
        lay.addWidget(self.slider)
        self.set_value(value)

    def value(self) -> float:
        return round(self.low + self.slider.value() * self.step, 4)

    def set_value(self, value: float) -> None:
        self.slider.setValue(round((max(self.low, min(self.high, value)) - self.low) / self.step))
        self._moved()

    def _moved(self, *_: Any) -> None:
        self.shown.setText(self.fmt.format(self.value()))
        self.changed.emit(self.value())


class Section(QWidget):
    """A titled part that opens and closes."""

    def __init__(self, title: str, *, opened: bool = True, icon: str = "") -> None:
        super().__init__()
        self.head = QToolButton()
        self.head.setText(title)
        self.head.setCheckable(True)
        self.head.setChecked(opened)
        self.head.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.head.setStyleSheet(f"QToolButton {{ color: {design.SUBTLE}; font-weight: 600; padding: 4px 2px; }}")
        self.head.setCursor(Qt.CursorShape.PointingHandCursor)
        self.head.toggled.connect(self._toggle)
        self.body_widget = QWidget()
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(2, 4, 2, 6)
        self.body.setSpacing(10)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.head)
        lay.addWidget(self.body_widget)
        self._icon = icon
        self._toggle(opened)

    def _toggle(self, opened: bool) -> None:
        self.head.setIcon(icons.icon("chevron_down" if opened else "chevron_right", design.MUTED, 14))
        self.body_widget.setVisible(opened)

    def add(self, *items: QWidget | QLayout | int | None) -> Section:
        for item in items:
            _add(self.body, item)
        return self


class Field(QWidget):
    """A small label above a control."""

    def __init__(self, label_text: str, control: QWidget | QLayout, *, hint: str = "") -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.addWidget(text(label_text, "small", tone="subtle"))
        head.addStretch(1)
        if hint:
            head.addWidget(text(hint, "tiny", tone="faint"))
        lay.addLayout(head)
        _add(lay, control)


class Badge(QLabel):
    def __init__(self, value: str, colour: str = design.MUTED) -> None:
        super().__init__(value)
        design.set_type(self, "tiny")
        self.set_colour(colour)

    def set_colour(self, colour: str) -> None:
        self.setStyleSheet(
            f"QLabel {{ color: {colour}; background: {design.alpha(colour, 0.14)};"
            f" border: 1px solid {design.alpha(colour, 0.35)}; border-radius: 8px; padding: 2px 8px; }}")


class StatusDot(QWidget):
    """A coloured dot; it pulses while ``pulse`` is on."""

    def __init__(self, colour: str = design.MUTED, size: int = 10) -> None:
        super().__init__()
        self._colour = colour
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size + 8, size + 8)

    def set(self, colour: str, pulse: bool = False) -> None:
        self._colour = colour
        self._timer.start(40) if pulse else self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.05) % 1.0
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = (self.width() - 8) / 2
        if self._timer.isActive():
            halo = QColor(self._colour)
            halo.setAlphaF(0.45 * (1 - self._phase))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(c, r + 4 * self._phase, r + 4 * self._phase)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._colour))
        p.drawEllipse(c, r, r)
        p.end()


class Spinner(QWidget):
    def __init__(self, size: int = 22, colour: str = design.BRAND_B) -> None:
        super().__init__()
        self._angle = 0
        self._colour = colour
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self) -> None:
        self._angle = (self._angle + 7) % 360
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(self._colour), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(self.rect()).adjusted(3, 3, -3, -3), -self._angle * 16, 270 * 16)
        p.end()


class EmptyState(QWidget):
    """What a place shows before there is anything in it: an icon, a line, what to do."""

    def __init__(self, icon: str, headline: str, hint: str = "", *, accent: str = design.BRAND_A,
                 action: QWidget | None = None) -> None:
        super().__init__()
        self._accent = accent
        self.mark = QLabel()
        self.mark.setFixedSize(72, 72)
        self.mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mark.setPixmap(icons.pixmap(icon, accent, 30))
        self.mark.setStyleSheet(f"background: {design.alpha(accent, 0.12)}; border: 1px solid {design.alpha(accent, 0.3)};"
                                " border-radius: 36px;")
        self.headline = text(headline, "h3")
        self.headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = text(hint, "small", tone="muted", wrap=True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setFixedWidth(400)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addStretch(1)
        lay.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(4)
        lay.addWidget(self.headline, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.hint, 0, Qt.AlignmentFlag.AlignHCenter)
        if action is not None:
            lay.addSpacing(6)
            lay.addWidget(action, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)


class Glow(QWidget):
    """A soft field of the brand's colours behind a hero: two blurred orbs on a dark ground."""

    def __init__(self, a: str = design.BRAND_A, b: str = design.BRAND_B) -> None:
        super().__init__()
        self.a, self.b = a, b
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 20, 20)
        p.setClipPath(path)
        p.fillRect(r, QColor(design.RAISED))
        for colour, cx, cy, rad in ((self.a, 0.15, 0.1, 0.75), (self.b, 0.95, 1.0, 0.65), (self.a, 0.7, -0.2, 0.4)):
            g = QRadialGradient(QPointF(r.width() * cx, r.height() * cy), r.width() * rad)
            c0 = QColor(colour)
            c0.setAlpha(80)
            c1 = QColor(colour)
            c1.setAlpha(0)
            g.setColorAt(0.0, c0)
            g.setColorAt(1.0, c1)
            p.fillRect(r, g)
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()


class Backdrop(QWidget):
    """ELI's ground: near-black, a faint cyan grid, a cyan glow above and a magenta glow below."""

    GRID = 34

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(design.INK))
        for colour, cx, cy, rx, alpha in ((design.BRAND_A, 0.82, -0.12, 0.75, 22), (design.BRAND_B, -0.12, 1.12, 0.65, 16)):
            g = QRadialGradient(QPointF(r.width() * cx, r.height() * cy), max(r.width(), r.height()) * rx)
            c0 = QColor(colour)
            c0.setAlpha(alpha)
            c1 = QColor(colour)
            c1.setAlpha(0)
            g.setColorAt(0.0, c0)
            g.setColorAt(1.0, c1)
            p.fillRect(r, g)
        p.setPen(QPen(QColor(34, 211, 238, 12), 1))
        lines = [QLineF(x, 0.0, x, r.height()) for x in range(0, int(r.width()) + 1, self.GRID)]
        lines += [QLineF(0.0, y, r.width(), y) for y in range(0, int(r.height()) + 1, self.GRID)]
        p.drawLines(lines)  # one call for the whole grid, not one a line
        p.end()


# ── toasts ───────────────────────────────────────────────────────────────
class Toasts(QWidget):
    """Short notes that rise in the window's corner and leave by themselves."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._stack = QVBoxLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.setSpacing(10)
        self._stack.addStretch(1)
        self.history: list[str] = []
        parent.installEventFilter(self)
        self._place()

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802
        if watched is self.parent() and event.type() == event.Type.Resize:
            self._place()
        return False

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = 380
        self.setGeometry(parent.width() - width - 24, 80, width, parent.height() - 120)
        self.raise_()

    def show_toast(self, message: str, kind: str = "info", *, action: tuple[str, Callable[[], Any]] | None = None,
                   ms: int = 4500) -> QFrame:
        colour = {"good": design.GOOD, "warn": design.WARN, "bad": design.BAD}.get(kind, design.BRAND_B)
        icon_name = {"good": "check", "warn": "warning", "bad": "warning"}.get(kind, "info")
        box = QFrame()
        box.setStyleSheet(f"QFrame {{ background: {design.RAISED}; border: 1px solid {design.alpha(colour, 0.45)};"
                          " border-radius: 14px; } QLabel { background: transparent; border: none; }")
        add_shadow(box, blur=40, y=12, opacity=140)
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 12, 12, 12)
        mark = QLabel()
        mark.setPixmap(icons.pixmap(icon_name, colour, 18))
        row.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        words = text(message, "small", wrap=True)
        row.addWidget(words, 1)
        if action is not None:
            go = button(action[0], action[1], variant="flat")
            row.addWidget(go)
        close = icon_button("x", "Dismiss", lambda: self._remove(box), size=14)
        row.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        self._stack.addWidget(box)
        self.history.append(message)
        self.show()
        self.raise_()
        fade_in(box)
        QTimer.singleShot(ms, lambda: self._remove(box))
        return box

    def _remove(self, box: QFrame) -> None:
        try:
            box.hide()
            box.deleteLater()
        except RuntimeError:  # already gone
            pass


def shortcut_hint(keys: str) -> str:
    import sys

    return keys.replace("Ctrl", "⌘") if sys.platform == "darwin" else keys
