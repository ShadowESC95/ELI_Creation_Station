"""The Socials studio's other rooms: the content calendar, cards for each platform, and the brand kit.

Creation Station does not post for anyone or read their accounts. The calendar is the plan: the
person posts and marks it posted, and can take the plan to any calendar app as an .ics file.
"""

from __future__ import annotations

import calendar as months
import json
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QDate, QRectF, Qt, QTime, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from eli_creation.engines.writing import PLATFORMS
from eli_creation.gui import components as ui
from eli_creation.gui import design, imaging
from eli_creation.gui.gallery import Gallery, Tile, open_lightbox
from eli_creation.library import slug
from eli_creation.production import grade as grading
from eli_creation.production.social import GOOD_TIMES, Brand, Calendar, Planned

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job

COLOURS = {"x": "#e7e9ea", "threads": "#f5f5f5", "bluesky": "#1185fe", "instagram": "#e1306c", "tiktok": "#25f4ee",
           "linkedin": "#0a66c2", "facebook": "#1877f2", "youtube": "#ff3d3d"}

WEEK_SYSTEM = ("You are ELI, a social media planner. Plan posts that suit each platform, in the brand's voice. "
               "Answer with JSON only.")


def brand_path(shell: MainWindow) -> Path:
    return shell.studio.layout.projects / "brands" / f"{slug(shell.project_name(), 'studio')}.json"


def load_brand(shell: MainWindow) -> Brand:
    try:
        return Brand.from_dict(json.loads(brand_path(shell).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return Brand()


def calendar_of(shell: MainWindow) -> Calendar:
    return Calendar(shell.studio.layout.projects / "calendars" / f"{slug(shell.project_name(), 'studio')}.json")


def clear(layout: Any) -> None:
    """Empty a layout, letting its widgets go."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.hide()
            widget.deleteLater()


# ── the calendar ─────────────────────────────────────────────────────────
class MonthView(QWidget):
    """A month: each day with its planned posts as coloured lines; click a day to see it."""

    chosen = Signal(object)  # date

    def __init__(self) -> None:
        super().__init__()
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected = today
        self.items: dict[str, list[Planned]] = {}
        self.setMinimumSize(560, 420)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def show_month(self, year: int, month: int, items: dict[str, list[Planned]]) -> None:
        self.year, self.month, self.items = year, month, items
        self.update()

    def _days(self) -> list[date]:
        first = date(self.year, self.month, 1)
        start = first - timedelta(days=first.weekday())
        return [start + timedelta(days=n) for n in range(42)]

    def _cell(self, n: int) -> QRectF:
        head = 26
        w = self.width() / 7
        h = (self.height() - head) / 6
        return QRectF((n % 7) * w, head + (n // 7) * h, w, h).adjusted(3, 3, -3, -3)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        for n, day in enumerate(self._days()):
            if self._cell(n).contains(event.position()):
                self.selected = day
                self.update()
                self.chosen.emit(day)
                return

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() / 7
        small = QFont(self.font())
        small.setPointSizeF(max(6.5, small.pointSizeF() * 0.82))
        p.setFont(small)
        p.setPen(QColor(design.MUTED))
        for n, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            p.drawText(QRectF(n * w, 0, w, 24), Qt.AlignmentFlag.AlignCenter, name)
        today = date.today()
        for n, day in enumerate(self._days()):
            r = self._cell(n)
            inside = day.month == self.month
            path = QPainterPath()
            path.addRoundedRect(r, 10, 10)
            p.fillPath(path, QColor(13, 20, 33, 170 if inside else 70))
            border = design.BRAND_A if day == self.selected else (design.BRAND_B if day == today else design.LINE)
            p.setPen(QPen(QColor(border), 1.5 if day in (self.selected, today) else 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            p.setPen(QColor(design.TEXT if inside else design.FAINT))
            p.drawText(r.adjusted(8, 5, -6, 0), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), str(day.day))
            posts = self.items.get(day.isoformat(), [])
            y = r.top() + 24
            fm = QFontMetrics(small)
            for item in posts[:3]:
                if y + 16 > r.bottom():
                    break
                colour = COLOURS.get(item.platform, design.BRAND_A)
                line = QRectF(r.left() + 5, y, r.width() - 10, 16)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(design.alpha_q(colour, 0.12 if item.status == "posted" else 0.24))
                p.drawRoundedRect(line, 5, 5)
                p.setBrush(QColor(colour))
                p.drawRoundedRect(QRectF(line.left(), line.top(), 3, line.height()), 1.5, 1.5)
                p.setPen(QColor(design.MUTED if item.status == "posted" else design.TEXT))
                words = f"{'✓ ' if item.status == 'posted' else ''}{item.time} {item.title or item.text}"
                p.drawText(line.adjusted(7, 0, -3, 0), int(Qt.AlignmentFlag.AlignVCenter),
                           fm.elidedText(words, Qt.TextElideMode.ElideRight, int(line.width() - 10)))
                y += 19
            if len(posts) > 3:
                p.setPen(QColor(design.MUTED))
                p.drawText(QRectF(r.left() + 8, r.bottom() - 16, r.width() - 12, 14), int(Qt.AlignmentFlag.AlignLeft),
                           f"+{len(posts) - 3} more")
        p.end()


class PlanDialog(QDialog):
    """A post in the plan: when, where, what, with what picture or film."""

    def __init__(self, parent: QWidget, item: Planned, studio: Any) -> None:
        super().__init__(parent)
        self.setWindowTitle("A post in the plan")
        self.setMinimumWidth(560)
        self.item = item
        self.studio = studio
        self.day = QDateEdit(QDate.fromString(item.day, "yyyy-MM-dd"))
        self.day.setCalendarPopup(True)
        self.time = QTimeEdit(QTime.fromString(item.time, "HH:mm"))
        self.platform = QComboBox()
        for key, (name, limit) in PLATFORMS.items():
            self.platform.addItem(f"{name} ({limit})", key)
        self.platform.setCurrentIndex(max(0, self.platform.findData(item.platform)))
        self.good = ui.text("", "tiny", tone="muted", wrap=True)
        self.platform.currentIndexChanged.connect(self._good)
        self.title = QLineEdit(item.title)
        self.title.setPlaceholderText("A short name for the calendar")
        self.text = QPlainTextEdit(item.text)
        self.text.setMinimumHeight(130)
        self.count = ui.text("", "tiny", tone="muted")
        self.text.textChanged.connect(self._count)
        self.asset = item.asset
        self.asset_label = ui.text(Path(item.asset).name if item.asset else "No picture or film", "small", tone="muted")
        attach = QHBoxLayout()
        attach.addWidget(self.asset_label, 1)
        attach.addWidget(ui.button("From the library…", self._attach, icon="library", variant="flat"))
        attach.addWidget(ui.icon_button("x", "No attachment", self._detach))
        when = QHBoxLayout()
        when.addWidget(self.day)
        when.addWidget(self.time)
        when.addStretch(1)
        form = QFormLayout()
        form.addRow("When", when)
        form.addRow("Where", self.platform)
        form.addRow("", self.good)
        form.addRow("Name", self.title)
        form.addRow("Post", self.text)
        form.addRow("", self.count)
        form.addRow("With", attach)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)
        self._good()
        self._count()

    def _good(self) -> None:
        key = str(self.platform.currentData())
        self.good.setText(f"Often a good time: {GOOD_TIMES.get(key, 'test what works for your audience')} "
                          "(a starting point; your own results are the guide).")
        self._count()

    def _count(self) -> None:
        limit = PLATFORMS.get(str(self.platform.currentData()), ("", 280))[1]
        used = len(self.text.toPlainText())
        self.count.setText(f"{used} / {limit}" + (f" · {used - limit} over" if used > limit else ""))

    def _attach(self) -> None:
        from eli_creation.gui.pages.film import PickPictures

        dialog = PickPictures(self, self.studio)
        if dialog.exec() and dialog.chosen():
            self.asset = dialog.chosen()[0]
            self.asset_label.setText(Path(self.asset).name)

    def _detach(self) -> None:
        self.asset = ""
        self.asset_label.setText("No picture or film")

    def result_item(self) -> Planned:
        self.item.day = self.day.date().toString("yyyy-MM-dd")
        self.item.time = self.time.time().toString("HH:mm")
        self.item.platform = str(self.platform.currentData())
        self.item.title = self.title.text().strip()
        self.item.text = self.text.toPlainText().strip()
        self.item.asset = self.asset
        return self.item


class PostLine(ui.Card):
    """A planned post on the chosen day."""

    def __init__(self, panel: CalendarPanel, item: Planned) -> None:
        super().__init__(soft=True, padding=12, spacing=6)
        self.panel, self.item = panel, item
        colour = COLOURS.get(item.platform, design.BRAND_A)
        name = PLATFORMS.get(item.platform, (item.platform, 0))[0].split(" ")[0]
        head = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {colour};")
        head.addWidget(dot)
        head.addWidget(ui.text(f"{item.time} · {name}", "small"))
        head.addStretch(1)
        if item.status == "posted":
            head.addWidget(ui.Badge("Posted", design.GOOD))
        self.add(head)
        if item.title:
            self.add(ui.text(item.title, "small", tone="subtle"))
        self.add(ui.text(item.text[:280] + ("…" if len(item.text) > 280 else ""), "small", wrap=True, selectable=True))
        if item.asset:
            self.add(ui.text(f"With {Path(item.asset).name}", "tiny", tone="muted"))
        tools = QHBoxLayout()
        tools.addWidget(ui.icon_button("copy", "Copy the post", self._copy, size=16))
        tools.addWidget(ui.icon_button("check", "Mark it posted (or not)", self._posted, size=16))
        tools.addWidget(ui.icon_button("sliders", "Change it", lambda: panel.edit(item), size=16))
        tools.addWidget(ui.icon_button("trash", "Take it out of the plan", lambda: panel.remove(item), size=16))
        tools.addStretch(1)
        self.add(tools)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.item.text)
        self.panel.shell.toast("Copied: paste it where you post", "good")

    def _posted(self) -> None:
        self.item.status = "planned" if self.item.status == "posted" else "posted"
        self.panel.calendar().put(self.item)
        self.panel.refresh()


class CalendarPanel(QWidget):
    def __init__(self, shell: MainWindow, accent: str) -> None:
        super().__init__()
        self.shell = shell
        self.accent = accent
        self.view = MonthView()
        self.view.chosen.connect(lambda _d: self._show_day())
        self.title = ui.text("", "h3")
        self.stats = QHBoxLayout()
        self.day_title = ui.text("", "h3")
        self.day_box = QVBoxLayout()
        self.day_box.setSpacing(8)
        self.plan_button = ui.button("ELI: plan the week", self.plan_week, icon="sparkles")
        nav = QHBoxLayout()
        nav.addWidget(ui.icon_button("chevron_left", "The month before", lambda: self._step(-1)))
        nav.addWidget(self.title)
        nav.addWidget(ui.icon_button("chevron_right", "The month after", lambda: self._step(1)))
        nav.addWidget(ui.button("Today", self._today, variant="flat"))
        nav.addSpacing(12)
        nav.addLayout(self.stats)
        nav.addStretch(1)
        nav.addWidget(self.plan_button)
        nav.addWidget(ui.button("Plan a post", lambda: self.add(), icon="plus", primary=True))
        nav.addWidget(ui.icon_button("calendar", "Save the plan as a calendar file (.ics) for any calendar app",
                                     self.export))
        day_card = ui.Card(padding=14, spacing=8)
        day_holder = QWidget()
        day_holder.setLayout(self.day_box)
        from eli_creation.gui.pages.base import scrolled

        day_card.add(self.day_title, scrolled(day_holder))
        day_card.setFixedWidth(360)
        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self.view, 1)
        body.addWidget(day_card)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addLayout(nav)
        lay.addLayout(body, 1)
        lay.addWidget(ui.text("Creation Station never posts for you or reads your accounts: this is your plan. Post, "
                              "then mark it posted.", "tiny", tone="faint"))

    def calendar(self) -> Calendar:
        return calendar_of(self.shell)

    def refresh(self) -> None:
        cal = self.calendar()
        self.view.show_month(self.view.year, self.view.month, cal.month(self.view.year, self.view.month))
        self.title.setText(f"{months.month_name[self.view.month]} {self.view.year}")
        clear(self.stats)
        found = cal.stats()
        for label_text, key, colour in (("planned", "planned", design.BRAND_A), ("this week", "this_week", design.BRAND_B),
                                        ("posted this month", "posted_month", design.GOOD),
                                        ("overdue", "overdue", design.WARN)):
            if found[key] or key in ("planned", "this_week"):
                self.stats.addWidget(ui.Badge(f"{found[key]} {label_text}", colour))
        self._show_day()

    def _step(self, by: int) -> None:
        month = self.view.month + by
        year = self.view.year + (month - 1) // 12
        self.view.year, self.view.month = year, (month - 1) % 12 + 1
        self.refresh()

    def _today(self) -> None:
        today = date.today()
        self.view.year, self.view.month, self.view.selected = today.year, today.month, today
        self.refresh()

    def _show_day(self) -> None:
        day = self.view.selected
        clear(self.day_box)
        self.day_title.setText(day.strftime("%A %d %B"))
        items = [i for i in self.calendar().all() if i.day == day.isoformat()]
        for item in items:
            self.day_box.addWidget(PostLine(self, item))
        if not items:
            self.day_box.addWidget(ui.text("Nothing planned on this day.", "small", tone="muted"))
            self.day_box.addWidget(ui.button("Plan a post here", lambda: self.add(), icon="plus", variant="flat"))
        self.day_box.addStretch(1)

    def add(self, text: str = "", platform: str = "instagram", asset: str = "") -> None:
        time = GOOD_TIMES.get(platform, "09:00").split()[-1][:5] if platform in GOOD_TIMES else "09:00"
        time = time if len(time) == 5 and time[2] == ":" else "09:00"
        item = Planned(day=max(self.view.selected, date.today()).isoformat(), platform=platform, text=text,
                       time=time, asset=asset)
        self.edit(item)

    def edit(self, item: Planned) -> None:
        dialog = PlanDialog(self, item, self.shell.studio)
        if dialog.exec():
            saved = self.calendar().put(dialog.result_item())
            self.view.selected = date.fromisoformat(saved.day)
            self.view.year, self.view.month = self.view.selected.year, self.view.selected.month
            self.refresh()

    def remove(self, item: Planned) -> None:
        self.calendar().remove(item.id)
        self.refresh()

    def export(self) -> None:
        name = f"{slug(self.shell.project_name(), 'studio')}-plan.ics"
        path, _ = QFileDialog.getSaveFileName(self, "Save the plan as a calendar file", name, "Calendar (*.ics)")
        if path:
            self.calendar().ics(Path(path))
            self.shell.toast("Saved: open it in any calendar app", "good")

    def plan_week(self) -> None:
        studio = self.shell.studio
        if not studio.main.available:
            self.shell.toast(f"ELI needs the main model to plan: {studio.main.why_unavailable}", "warn")
            return
        brand = load_brand(self.shell)
        platforms = self.shell.recall("socials_platforms", ["x", "instagram", "linkedin"])
        about = self.shell.project_name() or brand.name or "the brand"
        start = max(self.view.selected, date.today())
        prompt = (f"Brand: {brand.name or about}. Voice: {brand.voice or 'natural'}. Hashtags it uses: "
                  f"{' '.join(brand.hashtags)}.\nPlatforms: {', '.join(platforms)}.\nPlan one week of posts starting "
                  f"{start.isoformat()} ({start.strftime('%A')}): 5 to 8 posts, spread across the platforms and days, "
                  "each within the platform's length limit. For each: 'day' (YYYY-MM-DD), 'time' (HH:MM, a good time "
                  "for that platform), 'platform' (one of the platforms), 'title' (2-5 words), 'text' (the post). "
                  'Answer as {"posts": [...]}')
        self.plan_button.setEnabled(False)
        self.plan_button.setText("ELI is planning…")

        def work() -> Any:
            from eli_creation.engines.writing import parse_json

            return parse_json(studio.main.generate(system=WEEK_SYSTEM, prompt=prompt, max_tokens=2000,
                                                   temperature=0.7, json_mode=True))

        self.shell.run_in_background(work, self._planned)

    def _planned(self, result: Any) -> None:
        self.plan_button.setEnabled(True)
        self.plan_button.setText("ELI: plan the week")
        posts = result.get("posts") if isinstance(result, dict) else None
        if not isinstance(posts, list):
            self.shell.toast(f"ELI could not plan the week: {result}", "warn")
            return
        cal = self.calendar()
        added = 0
        for raw in posts:
            if not isinstance(raw, dict) or raw.get("platform") not in PLATFORMS or not raw.get("text"):
                continue
            try:
                day = date.fromisoformat(str(raw.get("day")))
            except ValueError:
                continue
            time = str(raw.get("time") or "09:00")[:5]
            cal.put(Planned(day=day.isoformat(), platform=str(raw["platform"]), text=str(raw["text"]).strip(),
                            time=time if len(time) == 5 and time[2] == ":" else "09:00",
                            title=str(raw.get("title") or "")[:60]))
            added += 1
        self.refresh()
        self.shell.toast(f"ELI planned {added} post(s): change any of them, then post and mark them", "good")


# ── cards for each platform ──────────────────────────────────────────────
class CardsPanel(QWidget):
    """One picture, cut to each platform's shape, with words and the brand's logo."""

    def __init__(self, shell: MainWindow, accent: str) -> None:
        super().__init__()
        from eli_creation.engines.production import PlatformCards

        self.shell = shell
        self.jobs: dict[str, Job] = {}
        self.picture = ""
        self.thumb = QLabel()
        self.thumb.setFixedSize(300, 200)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet(f"background: {design.SURFACE}; border: 1px dashed {design.LINE_STRONG}; "
                                 "border-radius: 12px;")
        self.thumb.setText("Choose a picture")
        pick = QHBoxLayout()
        pick.addWidget(ui.button("From the library…", self._from_library, icon="library"))
        pick.addWidget(ui.button("A file…", self._from_file, icon="upload", variant="flat"))
        pick.addStretch(1)
        self.platforms = ui.ChipGroup([(label_text, key) for key, (_shape, label_text) in PlatformCards.SHAPES.items()],
                                      exclusive=False, chosen=("instagram", "story", "x"), accent=accent)
        self.words = QLineEdit()
        self.words.setPlaceholderText("Words on the card: a headline, an offer, a date")
        self.position = ui.Segmented([("Top", "top"), ("Middle", "middle"), ("Bottom", "bottom")], "bottom",
                                     accent=accent)
        self.box = ui.Switch("A box behind the words", True)
        self.look = QComboBox()
        for key, (name, _blurb) in grading.LOOKS.items():
            self.look.addItem(name, key)
        self.logo = ui.Switch("The brand kit's logo", True)
        self.make = ui.GlowButton("Make the cards", "layers", accent=accent)
        self.make.clicked.connect(self.submit)
        form = ui.Card(padding=18, spacing=12)
        form.add(self.thumb, pick, ui.Field("For", self.platforms), ui.Field("Words", self.words),
                 ui.Field("Where", self.position), self.box, ui.Field("Look", self.look), self.logo, None, self.make)
        form.setFixedWidth(440)
        self.gallery = Gallery(size="medium")
        self.gallery.opened.connect(lambda tile: open_lightbox(shell, self.gallery.tiles(), tile))
        right = QVBoxLayout()
        right.addWidget(ui.text("Cards", "h3"))
        right.addWidget(self.gallery, 1)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)
        lay.addWidget(form, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(right, 1)

    def load(self) -> None:
        pending = [t for t in self.gallery.tiles() if t.pending]
        made = [a for a in self.shell.studio.library.recent(kind="image", limit=200) if a.engine == "socials.cards"]
        self.gallery.set_tiles(pending + [Tile.from_asset(a) for a in made])

    def use(self, path: str) -> None:
        self.picture = path
        image = imaging.load(path, 600)
        self.thumb.setPixmap(QPixmap.fromImage(image).scaled(self.thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation))

    def _from_library(self) -> None:
        from eli_creation.gui.pages.film import PickPictures

        dialog = PickPictures(self, self.shell.studio)
        if dialog.exec() and dialog.chosen():
            self.use(dialog.chosen()[0])

    def _from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "A picture", "", "Pictures (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.use(path)

    def submit(self) -> None:
        if not self.picture:
            self.shell.toast("Choose a picture first.", "warn")
            return
        brand = load_brand(self.shell)
        request: dict[str, Any] = {"path": self.picture, "platforms": self.platforms.values(),
                                   "text": self.words.text().strip(), "position": self.position.value(),
                                   "box": self.box.isChecked(), "look": self.look.currentData(),
                                   "project": self.shell.project_name()}
        if self.logo.isChecked() and brand.logo and Path(brand.logo).is_file():
            request["logo"] = brand.logo
        try:
            job = self.shell.studio.submit("socials.cards", request)
        except Exception as exc:
            self.shell.toast(str(exc), "warn")
            return
        self.jobs[job.id] = job
        self.gallery.add_pending(job.id, len(request["platforms"]) or 3, "Cutting the cards")
        self.make.set_busy(True)

    def on_job(self, job: Job) -> None:
        if job.id not in self.jobs:
            return
        self.gallery.model_.update_job(job.id, job.progress, job.message or job.state)
        if job.finished:
            self.gallery.model_.finish_job(job.id, [Tile.from_asset(a) for a in job.assets])
            self.jobs.pop(job.id, None)
            self.make.set_busy(False)
            if job.state == "failed":
                self.shell.toast(f"Cards: {job.error}", "bad")
            elif job.state == "done":
                self.shell.toast(f"{len(job.assets)} card(s) made", "good")


# ── the brand kit ────────────────────────────────────────────────────────
class Swatch(QPushButton):
    def __init__(self, colour: str) -> None:
        super().__init__()
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.colour = colour
        self.clicked.connect(self._choose)
        self._paint()

    def _paint(self) -> None:
        self.setStyleSheet(f"QPushButton {{ background: {self.colour}; border: 2px solid {design.LINE_STRONG}; "
                           "border-radius: 12px; }")
        self.setToolTip(self.colour)

    def _choose(self) -> None:
        found = QColorDialog.getColor(QColor(self.colour), self, "A brand colour")
        if found.isValid():
            self.colour = found.name()
            self._paint()


class BrandPanel(QWidget):
    """The brand's name, voice, colours, logo, hashtags and website: used by posts, cards, films and ELI."""

    saved = Signal()

    def __init__(self, shell: MainWindow, accent: str) -> None:
        super().__init__()
        self.shell = shell
        self.name = QLineEdit()
        self.website = QLineEdit()
        self.website.setPlaceholderText("https://")
        self.voice = QPlainTextEdit()
        self.voice.setPlaceholderText("How the brand sounds: words it uses, words it never uses, how it signs off")
        self.voice.setFixedHeight(100)
        self.hashtags = QLineEdit()
        self.hashtags.setPlaceholderText("#roastedfresh #northwind")
        self.swatches = [Swatch("#22d3ee"), Swatch("#f637ec"), Swatch("#05070d")]
        colours = QHBoxLayout()
        for swatch in self.swatches:
            colours.addWidget(swatch)
        colours.addStretch(1)
        self.logo = ""
        self.logo_view = QLabel("No logo")
        self.logo_view.setFixedSize(140, 140)
        self.logo_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_view.setStyleSheet(f"background: {design.SURFACE}; border: 1px dashed {design.LINE_STRONG}; "
                                     "border-radius: 12px;")
        logo_row = QHBoxLayout()
        logo_row.addWidget(self.logo_view)
        logo_tools = QVBoxLayout()
        logo_tools.addWidget(ui.button("Choose a logo…", self._choose_logo, icon="upload"))
        logo_tools.addWidget(ui.button("No logo", self._no_logo, variant="flat"))
        logo_tools.addWidget(ui.text("A PNG with a clear background works best on cards.", "tiny", tone="muted",
                                     wrap=True))
        logo_tools.addStretch(1)
        logo_row.addLayout(logo_tools)
        logo_row.addStretch(1)
        self.where = ui.text("", "tiny", tone="faint")
        save = ui.GlowButton("Save the brand kit", "check", accent=accent)
        save.clicked.connect(self.save)
        card = ui.Card(padding=20, spacing=12)
        card.add(ui.Field("Name", self.name), ui.Field("Website", self.website), ui.Field("Voice", self.voice),
                 ui.Field("Colours", colours), ui.Field("Logo", logo_row), ui.Field("Hashtags", self.hashtags),
                 self.where, save)
        card.setMaximumWidth(720)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(ui.text("One kit for each project: posts, cards, films and ELI use it.", "small", tone="muted"))
        lay.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        lay.addStretch(1)

    def load(self) -> None:
        brand = load_brand(self.shell)
        self.name.setText(brand.name or self.shell.project_name())
        self.website.setText(brand.website)
        self.voice.setPlainText(brand.voice)
        self.hashtags.setText(" ".join(brand.hashtags))
        for swatch, colour in zip(self.swatches, (brand.colours + ["#22d3ee", "#f637ec", "#05070d"])[:3], strict=True):
            swatch.colour = colour
            swatch._paint()
        self._show_logo(brand.logo)
        self.where.setText(f"For the project “{self.shell.project_name() or 'Studio'}”")

    def _show_logo(self, path: str) -> None:
        self.logo = path if path and Path(path).is_file() else ""
        if self.logo:
            image = imaging.load(self.logo, 280)
            self.logo_view.setPixmap(QPixmap.fromImage(image).scaled(
                self.logo_view.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.logo_view.setPixmap(QPixmap())
            self.logo_view.setText("No logo")

    def _choose_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "The logo", "", "Pictures (*.png *.jpg *.jpeg *.webp *.svg)")
        if path:
            self._show_logo(path)

    def _no_logo(self) -> None:
        self._show_logo("")

    def brand(self) -> Brand:
        tags = [t if t.startswith("#") else f"#{t}" for t in self.hashtags.text().replace(",", " ").split() if t.strip("#")]
        return Brand(name=self.name.text().strip(), voice=self.voice.toPlainText().strip(),
                     colours=[s.colour for s in self.swatches], logo=self.logo, hashtags=tags,
                     website=self.website.text().strip())

    def save(self) -> None:
        from dataclasses import asdict

        path = brand_path(self.shell)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self.brand()), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.saved.emit()
        from eli_creation import eli_share

        brand = self.brand()
        project = self.shell.project_name() or "Studio"
        eli_share.preference(self.shell.studio, f"brand:{project.lower()}", f"Brand kit: {brand.name or project}",
                             f"Voice: {brand.voice or '-'}. Colours: {', '.join(brand.colours)}. Hashtags: "
                             f"{' '.join(brand.hashtags) or '-'}. Website: {brand.website or '-'}.")
        self.shell.toast("The brand kit is saved", "good")

