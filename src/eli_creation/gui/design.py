"""The studio's design system: colours, the accent of each studio, type, and the stylesheet.

It is layered over the look shared with the other ELI applications (theme.py, kept in step with
ELI Legal): the same dark ground, made deeper, with glass-like surfaces, a violet-to-cyan brand
gradient and one accent per studio, so a person knows where they are by colour alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient
from PySide6.QtWidgets import QApplication, QWidget

# ── colour: ELI's own (ELI v3's interface), so every ELI product looks like one family ──
INK = "#05070d"  # the window's ground
SURFACE = "#0a1019"  # panels
RAISED = "#0d1421"  # cards (drawn as glass over the ground where the stylesheet allows)
HOVER = "#111b2b"
PRESSED = "#16233a"
LINE = "#11232f"  # cyan-tinted hairlines
LINE_STRONG = "#173444"
TEXT = "#dbeafe"
SUBTLE = "#a9bfdc"
MUTED = "#8aa4c8"
FAINT = "#5b6b86"
BRAND_A = "#22d3ee"  # ELI's cyan
BRAND_B = "#f637ec"  # ELI's magenta
ON_BRAND = "#04121a"  # text on the brand's colours
GOOD = "#34f5c5"
WARN = "#ffd166"
BAD = "#ff5d73"
GLASS = "rgba(13,20,33,0.62)"
GLASS_SOFT = "rgba(20,28,44,0.55)"
HAIRLINE = "rgba(64,224,255,0.15)"


@dataclass(frozen=True)
class Studio:
    key: str
    name: str
    blurb: str
    accent: str
    icon: str


STUDIOS: dict[str, Studio] = {
    s.key: s
    for s in (
        Studio("home", "Home", "Start something new", "#22d3ee", "home"),
        Studio("socials", "Socials", "Posts, cards and a calendar", "#f637ec", "message"),
        Studio("images", "Images", "Pictures from your words", "#a78bfa", "image"),
        Studio("videos", "Film", "Films and ads with sound", "#fb923c", "film"),
        Studio("audio", "Audio", "Voices, music and effects", "#facc15", "music"),
        Studio("games", "Games", "Design it, then play it", "#34f5c5", "gamepad"),
        Studio("editing", "Editing", "Looks, crops, words, logos", "#38bdf8", "sliders"),
        Studio("coding", "Coding", "Code written and tested", "#60a5fa", "code"),
        Studio("library", "Library", "Everything you have made", "#ffd166", "library"),
        Studio("settings", "Settings", "This machine and its models", "#8aa4c8", "settings"),
    )
}


def accent(key: str) -> str:
    return STUDIOS[key].accent if key in STUDIOS else BRAND_A


def mix(a: str, b: str, t: float) -> str:
    """The colour ``t`` of the way from ``a`` to ``b``."""
    ca, cb = QColor(a), QColor(b)
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
    ).name()


def alpha_q(colour: str, a: float) -> QColor:
    c = QColor(colour)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


def alpha(colour: str, a: float) -> str:
    c = QColor(colour)
    return f"rgba({c.red()},{c.green()},{c.blue()},{max(0.0, min(1.0, a)):.3f})"


def brand_gradient(x0: float, y0: float, x1: float, y1: float, a: str = BRAND_A, b: str = BRAND_B) -> QLinearGradient:
    g = QLinearGradient(QPointF(x0, y0), QPointF(x1, y1))
    g.setColorAt(0.0, QColor(a))
    g.setColorAt(1.0, QColor(b))
    return g


# ── type ─────────────────────────────────────────────────────────────────
# Sizes are factors of the application's font, so zooming (Ctrl and +/−) scales them with it.
TYPE = {"display": 2.3, "h1": 1.75, "h2": 1.3, "h3": 1.1, "body": 1.0, "small": 0.9, "tiny": 0.8}
WEIGHT = {"display": QFont.Weight.Bold, "h1": QFont.Weight.Bold, "h2": QFont.Weight.DemiBold,
          "h3": QFont.Weight.DemiBold}


def set_type(widget: QWidget, kind: str) -> QWidget:
    """Give a widget a size from the type scale; it follows the zoom from then on."""
    widget.setProperty("typeKind", kind)
    _apply_type(widget)
    return widget


def _apply_type(widget: QWidget) -> None:
    kind = str(widget.property("typeKind") or "body")
    base = QApplication.font()
    font = QFont(widget.font())
    font.setPointSizeF(max(6.0, base.pointSizeF() * TYPE.get(kind, 1.0)))
    font.setWeight(WEIGHT.get(kind, QFont.Weight.Normal))
    if kind == "display":
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 98)
    widget.setFont(font)


def retype_all() -> None:
    """After a zoom: every widget given a size from the scale takes it again."""
    for widget in QApplication.allWidgets():
        if widget.property("typeKind"):
            _apply_type(widget)


def follow_zoom() -> None:
    from eli_creation.gui import zoom

    control = zoom.current()
    if control is not None:
        control.changed.connect(lambda _level: retype_all(), Qt.ConnectionType.QueuedConnection)


# ── the stylesheet ───────────────────────────────────────────────────────
def stylesheet(zoom: float = 1.0) -> str:
    def px(size: float) -> int:
        return max(1, round(size * zoom))

    return f"""
QWidget {{ color: {TEXT}; background: transparent; }}
QMainWindow, QDialog {{ background: {INK}; }}
QLabel {{ background: transparent; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QFrame[card="true"] {{
    background: {GLASS}; border: 1px solid {HAIRLINE}; border-radius: {px(16)}px;
}}
QFrame[card="soft"] {{ background: {GLASS_SOFT}; border: 1px solid {HAIRLINE}; border-radius: {px(14)}px; }}
QFrame[card="true"] QLabel, QFrame[card="soft"] QLabel {{ background: transparent; }}
QFrame[hairline="true"] {{ background: {LINE}; max-height: 1px; min-height: 1px; border: none; }}
QLabel[tone="muted"] {{ color: {MUTED}; }}
QLabel[tone="subtle"] {{ color: {SUBTLE}; }}
QLabel[tone="faint"] {{ color: {FAINT}; }}
QLabel[tone="good"] {{ color: {GOOD}; }}
QLabel[tone="warn"] {{ color: {WARN}; }}
QLabel[tone="bad"] {{ color: {BAD}; }}
QLabel[eyebrow="true"] {{ color: {MUTED}; letter-spacing: 1px; font-weight: 600; }}

QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {LINE_STRONG}; border-radius: {px(10)}px;
    padding: {px(7)}px {px(10)}px; selection-background-color: {alpha(BRAND_A, 0.55)};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus {{ border: 1px solid {alpha(BRAND_A, 0.9)}; }}
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {{ color: {FAINT}; }}
QPlainTextEdit[prompt="true"], QPlainTextEdit[prompt="true"]:focus {{
    background: transparent; border: none; padding: 0; font-size: {px(14)}px;
}}
QLineEdit[bare="true"], QLineEdit[bare="true"]:focus {{ background: transparent; border: none; padding: 0; }}
QComboBox::drop-down {{ border: none; width: {px(22)}px; }}
QComboBox QAbstractItemView {{
    background: {RAISED}; border: 1px solid {LINE_STRONG}; border-radius: 8px; padding: 4px;
    selection-background-color: {HOVER}; outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0; border: none;
}}

QPushButton {{
    background: {HOVER}; color: {TEXT}; border: 1px solid {LINE_STRONG}; border-radius: {px(10)}px;
    padding: {px(7)}px {px(14)}px; font-weight: 500;
}}
QPushButton:hover {{ background: {PRESSED}; border-color: #3b4560; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {FAINT}; background: {SURFACE}; border-color: {LINE}; }}
QPushButton[variant="flat"] {{ background: transparent; border: 1px solid transparent; color: {SUBTLE}; }}
QPushButton[variant="flat"]:hover {{ background: {HOVER}; color: {TEXT}; }}
QPushButton[variant="danger"] {{ background: {alpha(BAD, 0.12)}; border-color: {alpha(BAD, 0.4)}; color: {BAD}; }}
QPushButton[variant="danger"]:hover {{ background: {alpha(BAD, 0.22)}; }}
QPushButton[kind="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {BRAND_A}, stop:1 {BRAND_B});
    border: none; color: {ON_BRAND}; font-weight: 700;
}}
QPushButton[kind="primary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {mix(BRAND_A, '#ffffff', 0.12)},
                                stop:1 {mix(BRAND_B, '#ffffff', 0.12)});
}}
QPushButton[kind="primary"]:disabled {{ background: {HOVER}; color: {FAINT}; }}

QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: {px(9)}px;
    padding: {px(5)}px; color: {SUBTLE}; }}
QToolButton:hover {{ background: {HOVER}; color: {TEXT}; }}
QToolButton:checked {{ background: {PRESSED}; color: {TEXT}; }}

QCheckBox {{ spacing: {px(8)}px; color: {SUBTLE}; }}
QCheckBox::indicator {{ width: {px(16)}px; height: {px(16)}px; border-radius: 5px;
    border: 1px solid {LINE_STRONG}; background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {BRAND_A}; border-color: {BRAND_A}; }}

QSlider::groove:horizontal {{ height: {px(4)}px; background: {LINE_STRONG}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B});
    border-radius: 2px;
}}
QSlider::handle:horizontal {{ background: white; width: {px(14)}px; height: {px(14)}px;
    margin: -{px(5)}px 0; border-radius: {px(7)}px; }}

QProgressBar {{ background: {SURFACE}; border: none; border-radius: {px(4)}px; height: {px(6)}px;
    color: transparent; }}
QProgressBar::chunk {{ border-radius: {px(4)}px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B}); }}

QListWidget, QListView, QTreeView, QTableView {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-radius: 8px; padding: 4px; }}
QListWidget::item:selected {{ background: {HOVER}; color: {TEXT}; }}
QListWidget::item:hover {{ background: {alpha('#ffffff', 0.03)}; }}
QTableWidget {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px;
    gridline-color: {LINE}; alternate-background-color: {RAISED}; }}
QHeaderView::section {{ background: {RAISED}; color: {MUTED}; border: none;
    border-bottom: 1px solid {LINE}; padding: {px(6)}px {px(8)}px; }}

QGroupBox {{
    background: {RAISED}; border: 1px solid {LINE}; border-radius: {px(16)}px;
    margin-top: {px(18)}px; padding: {px(16)}px {px(14)}px {px(12)}px {px(14)}px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: {px(16)}px; padding: 0 {px(4)}px;
    color: {SUBTLE}; font-weight: 600; letter-spacing: 1px; }}

QScrollBar:vertical {{ background: transparent; width: {px(10)}px; margin: {px(3)}px; }}
QScrollBar::handle:vertical {{ background: {alpha('#ffffff', 0.12)}; border-radius: {px(4)}px;
    min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {alpha('#ffffff', 0.22)}; }}
QScrollBar:horizontal {{ background: transparent; height: {px(10)}px; margin: {px(3)}px; }}
QScrollBar::handle:horizontal {{ background: {alpha('#ffffff', 0.12)}; border-radius: {px(4)}px;
    min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    width: 0; height: 0; background: none; }}

QMenuBar {{ background: {INK}; color: {SUBTLE}; border-bottom: 1px solid {LINE}; }}
QMenuBar::item {{ padding: {px(6)}px {px(10)}px; background: transparent; }}
QMenuBar::item:selected {{ background: {HOVER}; border-radius: 6px; color: {TEXT}; }}
QMenu {{ background: {RAISED}; border: 1px solid {LINE_STRONG}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: {px(7)}px {px(24)}px {px(7)}px {px(12)}px; border-radius: 6px; color: {SUBTLE}; }}
QMenu::item:selected {{ background: {HOVER}; color: {TEXT}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 5px 8px; }}
QToolTip {{ background: {RAISED}; color: {TEXT}; border: 1px solid {LINE_STRONG}; border-radius: 6px;
    padding: {px(6)}px {px(8)}px; }}
QStatusBar {{ background: {INK}; color: {MUTED}; border-top: 1px solid {LINE}; }}
QStatusBar QLabel {{ color: {MUTED}; padding: 0 {px(8)}px; }}
QSplitter::handle {{ background: transparent; }}
QDockWidget {{ color: {MUTED}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; border: none; padding: {px(8)}px {px(14)}px;
    margin-right: {px(4)}px; border-radius: {px(8)}px; }}
QTabBar::tab:selected {{ background: {HOVER}; color: {TEXT}; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QGraphicsView {{ background: transparent; border: none; }}
"""
