"""Socials: one brief, drafts for each platform, each shown as it would read there, with how much of
the platform's limit it uses and a button to copy it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from eli_creation.engines.writing import PLATFORMS
from eli_creation.gui import components as ui
from eli_creation.gui import design
from eli_creation.gui.pages.base import PromptHistory, StudioPage, scrolled

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job

COLOURS = {"x": "#e7e9ea", "threads": "#f5f5f5", "bluesky": "#1185fe", "instagram": "#e1306c", "tiktok": "#25f4ee",
           "linkedin": "#0a66c2", "facebook": "#1877f2", "youtube": "#ff3d3d"}
TONES = [("Natural", "natural"), ("Playful", "playful"), ("Professional", "professional"), ("Bold", "bold"),
         ("Warm", "warm"), ("Witty", "witty")]
_DRAFT = re.compile(r"^## Draft (\d+) \((\d+)/(\d+) characters[^)]*\)\s*$", re.M)


@dataclass
class Draft:
    platform: str
    number: int
    text: str
    limit: int


def platform_of(path: str | Path) -> str:
    stem = Path(path).stem
    for key in PLATFORMS:
        if f"-{key}-" in stem:
            return key
    return "x"


def parse_drafts(markdown: str, platform: str) -> list[Draft]:
    """The drafts in a posts file, as the posts engine writes them."""
    limit = PLATFORMS.get(platform, ("", 280))[1]
    marks = list(_DRAFT.finditer(markdown))
    out: list[Draft] = []
    for n, mark in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(markdown)
        out.append(Draft(platform, int(mark.group(1)), markdown[mark.end():end].strip(), int(mark.group(3)) or limit))
    if not out and markdown.strip():
        body = "\n".join(ln for ln in markdown.splitlines() if not ln.startswith("# ")).strip()
        out.append(Draft(platform, 1, body, limit))
    return out


class Meter(QWidget):
    """How much of the platform's limit a draft uses."""

    def __init__(self, used: int, limit: int, colour: str) -> None:
        super().__init__()
        self.used, self.limit, self.colour = used, limit, colour
        self.setFixedHeight(6)
        self.setMinimumWidth(80)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(design.LINE_STRONG))
        p.drawRoundedRect(r, 3, 3)
        share = min(1.0, self.used / max(1, self.limit))
        over = self.used > self.limit
        p.setBrush(QColor(design.BAD if over else (design.WARN if share > 0.9 else self.colour)))
        p.drawRoundedRect(QRectF(r.left(), r.top(), r.width() * share, r.height()), 3, 3)
        p.end()


class Avatar(QWidget):
    def __init__(self, platform: str) -> None:
        super().__init__()
        self.platform = platform
        self.setFixedSize(34, 34)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = COLOURS.get(self.platform, design.BRAND_A)
        p.setPen(QPen(QColor(colour), 1.5))
        p.setBrush(design.alpha_q(colour, 0.16))
        p.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        font = QFont(self.font())
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(colour))
        letter = {"x": "X", "youtube": "▶", "tiktok": "♪"}.get(self.platform, PLATFORMS[self.platform][0][:1])
        p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, letter)
        p.end()


class PostCard(ui.Card):
    def __init__(self, draft: Draft, brand: str) -> None:
        super().__init__(padding=16, spacing=10)
        name = PLATFORMS.get(draft.platform, ("Post", 0))[0]
        colour = COLOURS.get(draft.platform, design.BRAND_A)
        who = QVBoxLayout()
        who.setSpacing(0)
        who.addWidget(ui.text(brand or "Your brand", "small"))
        who.addWidget(ui.text(f"{name} · draft {draft.number}", "tiny", tone="muted"))
        head = QHBoxLayout()
        head.addWidget(Avatar(draft.platform))
        head.addLayout(who, 1)
        copy = ui.icon_button("copy", "Copy this draft", lambda: self._copy(draft.text), size=16)
        head.addWidget(copy)
        self.add(head)
        body = ui.text(draft.text, "body", wrap=True, selectable=True)
        self.add(body)
        used = len(draft.text)
        over = used - draft.limit
        foot = QHBoxLayout()
        foot.addWidget(Meter(used, draft.limit, colour), 1)
        words = ui.text(f"{used} / {draft.limit}" + (f" · {over} over" if over > 0 else ""), "tiny",
                        tone="bad" if over > 0 else "muted")
        foot.addWidget(words)
        self.add(foot)
        self.copy_button = copy

    def _copy(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        window = self.window()
        toast = getattr(window, "toast", None)
        if callable(toast):
            toast("Copied: paste it where you post", "good")


class SocialsPage(StudioPage):
    key = "socials"
    gallery_kind = ""

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.history = PromptHistory(shell, "socials")
        self.brief = QPlainTextEdit()
        self.brief.setProperty("prompt", True)
        self.brief.setPlaceholderText("What is the post about? A launch, an episode, a sale, a milestone…")
        self.brief.setFixedHeight(96)
        design.set_type(self.brief, "h3")
        recent = ui.button("Recent briefs", lambda: self.history.menu(recent, self._use), icon="clock", variant="flat")
        chosen = shell.recall("socials_platforms", ["x", "instagram", "linkedin"])
        self.platforms = ui.ChipGroup([(PLATFORMS[k][0].split(" ")[0], k) for k in PLATFORMS], exclusive=False,
                                      chosen=chosen, dots=COLOURS, notes={k: str(v[1]) for k, v in PLATFORMS.items()},
                                      accent=self.accent)
        self.platforms.changed.connect(lambda: shell.remember("socials_platforms", self.platforms.values()))
        self.audience = QLineEdit(str(shell.recall("socials_audience", "")))
        self.audience.setPlaceholderText("Who it is for: founders, gamers, parents of toddlers…")
        self.tone = ui.ChipGroup(TONES, chosen=[str(shell.recall("socials_tone", "natural"))], accent=self.accent)
        self.voice = QPlainTextEdit(str(shell.recall("socials_voice", "")))
        self.voice.setPlaceholderText("Your voice: words you use, words you never use, how you sign off")
        self.voice.setFixedHeight(70)
        self.brand = QLineEdit(str(shell.recall("socials_brand", "")))
        self.brand.setPlaceholderText("The name the posts are shown under")
        self.drafts = ui.Stepper(1, 5, int(shell.recall("socials_drafts", 3)))
        self.hashtags = ui.Switch("Hashtags", bool(shell.recall("socials_hashtags", True)))
        options = QHBoxLayout()
        options.addWidget(ui.Field("Drafts for each", self.drafts))
        options.addSpacing(18)
        options.addWidget(self.hashtags, 0, Qt.AlignmentFlag.AlignBottom)
        options.addStretch(1)

        composer = ui.Card(padding=20, spacing=14)
        composer.add(ui.Field("Brief", self.brief), ui.hbox(recent, None), ui.Field("Platforms", self.platforms),
                     ui.Field("Audience", self.audience), ui.Field("Tone", self.tone),
                     ui.Field("Brand voice", self.voice, hint="kept for next time"), ui.Field("Shown as", self.brand),
                     options, self.reason, self.create_button)
        composer.setFixedWidth(460)

        self.results = QVBoxLayout()
        self.results.setSpacing(14)
        self.results.addStretch(1)
        results_box = QWidget()
        results_box.setLayout(self.results)
        self.empty = ui.EmptyState("message", "Your drafts appear here",
                                   "Each platform's drafts are shown as they would read there, with how much of its "
                                   "limit they use. Posts need the main model (Settings).", accent=self.accent)
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(ui.text("Drafts", "h3"))
        right.addWidget(self.empty, 1)
        right.addWidget(scrolled(results_box), 4)

        columns = QHBoxLayout()
        columns.setSpacing(22)
        columns.addWidget(composer, 0, Qt.AlignmentFlag.AlignTop)
        columns.addLayout(right, 1)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(18)
        lay.addLayout(self.header("Socials", "One brief, a post for every platform: in your voice, within each "
                                              "platform's limit, ready to copy."))
        lay.addWidget(self.engines)
        lay.addLayout(columns, 1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(body))
        self.shown_paths: set[str] = set()
        self.running: QLabel | None = None

    def request(self) -> dict[str, Any]:
        brief = self.brief.toPlainText().strip()
        if not brief:
            raise ValueError("Write what the post is about first.")
        platforms = self.platforms.values()
        if not platforms:
            raise ValueError("Choose at least one platform.")
        for key, value in (("socials_audience", self.audience.text()), ("socials_tone", self.tone.value()),
                           ("socials_voice", self.voice.toPlainText()), ("socials_brand", self.brand.text()),
                           ("socials_drafts", self.drafts.value()), ("socials_hashtags", self.hashtags.isChecked())):
            self.shell.remember(key, value)
        return {"brief": brief, "platforms": platforms, "audience": self.audience.text().strip(),
                "tone": self.tone.value(), "voice": self.voice.toPlainText().strip(), "variants": self.drafts.value(),
                "hashtags": self.hashtags.isChecked()}

    def after_submit(self, request: dict[str, Any]) -> None:
        self.history.add(request["brief"])
        self.empty.hide()
        self.running = ui.text(f"Writing for {len(request['platforms'])} platform(s)…", "small", tone="muted")
        self.results.insertWidget(0, self.running)

    def finished(self, job: Job) -> None:
        running = self.running
        if running is not None:
            running.deleteLater()
            self.running = None
        for asset in reversed(job.assets):
            self._show_file(Path(asset.path), str(job.request.get("brief", "")), top=True)

    def _show_file(self, path: Path, brief: str = "", *, top: bool = False) -> None:
        if str(path) in self.shown_paths or not path.is_file():
            return
        self.shown_paths.add(str(path))
        platform = platform_of(path)
        drafts = parse_drafts(path.read_text(encoding="utf-8", errors="replace"), platform)
        if not drafts:
            return
        group = QVBoxLayout()
        group.setSpacing(10)
        title = brief or path.read_text(encoding="utf-8", errors="replace").splitlines()[0].lstrip("# ")
        group.addWidget(ui.text(title, "small", tone="subtle"))
        row = QHBoxLayout()
        row.setSpacing(12)
        for draft in drafts:
            row.addWidget(PostCard(draft, self.brand.text().strip()), 1, Qt.AlignmentFlag.AlignTop)
        group.addLayout(row)
        box = QWidget()
        box.setLayout(group)
        self.results.insertWidget(0 if top else max(0, self.results.count() - 1), box)
        self.empty.hide()

    def _use(self, brief: str) -> None:
        self.brief.setPlainText(brief)
        self.brief.setFocus()

    def shown(self, **wanted: Any) -> None:
        self.refresh()
        if not self.shown_paths:
            for asset in self.studio.library.recent(kind="post", limit=6):
                self._show_file(Path(asset.path))
        self.empty.setVisible(not self.shown_paths)
        if wanted.get("prompt"):
            self.brief.setPlainText(str(wanted["prompt"]))
        if wanted.get("create"):
            self.submit()
        elif wanted.get("focus") or wanted.get("prompt"):
            self.brief.setFocus()

    def on_job(self, job: Job) -> None:
        if job.id in self.jobs:
            if job.finished:
                self.finished(job)
                if job.state == "failed":
                    self.shell.toast(f"Socials: {job.error}", "bad")
                elif job.state == "done":
                    self.shell.toast(f"Socials: drafts for {len(job.assets)} platform(s) are ready", "good")
                self.jobs.pop(job.id, None)
            self.update_create()

