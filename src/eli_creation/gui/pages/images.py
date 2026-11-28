"""Images: say what to picture; choose its shape, how many, its style and seed; then the gallery
of what was made. The styles are shown as small pictures rendered on this machine, once."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons, imaging
from eli_creation.gui.gallery import Tile, manifest_of
from eli_creation.gui.pages.base import PromptHistory, StudioPage, new_seed, scrolled

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow

ASPECTS = [("1:1", "square", 1.0), ("2:3", "portrait", 2 / 3), ("3:2", "landscape", 3 / 2),
           ("16:9", "wide", 16 / 9), ("9:16", "story", 9 / 16)]
STYLES = [("Auto", "auto"), ("Cinematic", "cinematic"), ("Neon", "neon"), ("Minimal", "minimal"),
          ("Luxury", "luxury"), ("Fantasy", "fantasy"), ("Balanced", "balanced")]
# What each style's preview shows: a subject that style suits, so the previews differ at a glance.
STYLE_SUBJECTS = {
    "auto": "an astronaut resting in a garden of glowing flowers",
    "cinematic": "a lone figure on a rainy city street at dusk, film still",
    "neon": "a neon city street at night with signs and reflections",
    "minimal": "a single red sphere on a pale wall, soft shadow",
    "luxury": "a gold watch on black marble, product photograph",
    "fantasy": "a dragon over misty mountains and a castle",
    "balanced": "a sunny meadow with a lake and distant mountains",
}
PREVIEW_VERSION = 2
BUILDER = (
    ("Shot", ("close-up", "portrait", "wide shot", "aerial view", "macro", "overhead flat lay", "low angle")),
    ("Light", ("golden hour", "soft studio light", "neon glow", "moonlight", "dramatic rim light", "overcast",
               "candlelight")),
    ("Medium", ("photograph", "3D render", "watercolour", "oil painting", "pencil sketch", "isometric illustration",
                "paper cut-out")),
    ("Mood", ("calm", "energetic", "mysterious", "joyful", "epic", "cosy", "futuristic")),
)
IDEAS_SYSTEM = ("You are ELI, an art director. Suggest varied, concrete image prompts: subject, setting, light, "
                "composition, mood. Answer with JSON only.")
ENHANCE_SYSTEM = ("You improve prompts for an image generator. Keep the person's idea; add subject detail, "
                  "setting, light, composition and mood in one vivid sentence of at most 60 words. "
                  "Answer with the prompt only.")


class StylePreviews(QObject):
    """A small picture of each style, rendered by the procedural engine the first time Images is
    opened and kept in the cache folder."""

    ready = Signal(str)

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.folder = folder
        self._started = False

    def path(self, style: str) -> Path:
        return self.folder / f"{style}-v{PREVIEW_VERSION}.png"

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        missing = [s for _, s in STYLES if not self.path(s).is_file()]
        if missing:
            threading.Thread(target=self._render, args=(missing,), name="eli-creation-styles", daemon=True).start()

    def _render(self, styles: list[str]) -> None:
        try:
            from eli_creation.engines.image_engine.contracts import JobRequest
            from eli_creation.engines.image_engine.service import ImageEngine

            self.folder.mkdir(parents=True, exist_ok=True)
            engine = ImageEngine()
            for style in styles:
                result = engine.generate_images(JobRequest(prompt=STYLE_SUBJECTS[style], count=1, width=384, height=288,
                                                           seed=11, style=style, backend="procedural"))
                made = [a for a in result.artifacts if a.artifact_type == "image"]
                if made:
                    shutil.copyfile(made[0].path, self.path(style))
                    self.ready.emit(style)
        except Exception:  # a preview is a nicety: its card shows the style's colours instead
            return


class StyleCard(QAbstractButton):
    TINTS = {"auto": ("#8b5cf6", "#22d3ee"), "cinematic": ("#f59e0b", "#7c2d12"), "neon": ("#ec4899", "#06b6d4"),
             "minimal": ("#e5e7eb", "#6b7280"), "luxury": ("#d4af37", "#1f2937"), "fantasy": ("#a78bfa", "#10b981"),
             "balanced": ("#60a5fa", "#34d399")}

    def __init__(self, label: str, key: str, accent: str) -> None:
        super().__init__()
        self.setText(label)
        self.key = key
        self.accent = accent
        self.image: QImage | None = None
        self.setCheckable(True)
        self.setFixedSize(QSize(118, 92))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{label} style")

    def set_image(self, path: Path) -> None:
        try:
            self.image = imaging.load(path, 256)
        except Exception:
            self.image = None
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        clip = QPainterPath()
        clip.addRoundedRect(r, 12, 12)
        p.setClipPath(clip)
        if self.image is not None and not self.image.isNull():
            scale = max(r.width() / self.image.width(), r.height() / self.image.height())
            w, h = self.image.width() * scale, self.image.height() * scale
            p.drawImage(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), self.image)
        else:
            a, b = self.TINTS.get(self.key, ("#8b5cf6", "#22d3ee"))
            p.fillRect(r, design.brand_gradient(r.left(), r.top(), r.right(), r.bottom(), a, b))
        shade = QLinearGradient(r.topLeft(), r.bottomLeft())
        shade.setColorAt(0.5, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(0, 0, 0, 190))
        p.fillRect(r, shade)
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor("#ffffff"))
        p.drawText(r.adjusted(10, 0, -8, -8), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft), self.text())
        p.setClipping(False)
        on = self.isChecked()
        p.setPen(QPen(QColor(self.accent if on else design.LINE_STRONG), 2.2 if on else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 12, 12)
        p.end()


class Enhancer(QObject):
    done = Signal(str, str)  # the better prompt, or "", and why not

    def run(self, studio: Any, prompt: str) -> None:
        def work() -> None:
            try:
                better = studio.main.generate(system=ENHANCE_SYSTEM, prompt=prompt, max_tokens=160, temperature=0.7)
                self.done.emit(better.strip().strip('"').strip(), "")
            except Exception as exc:
                self.done.emit("", str(exc))

        threading.Thread(target=work, name="eli-creation-enhance", daemon=True).start()


class ImagesPage(StudioPage):
    key = "images"
    gallery_kind = "image"
    tile_actions = [("variations", "Variations of it", "layers"), ("edit", "Edit it", "sliders"),
                    ("to_video", "Add it to a film", "film"), ("cards", "Cards for socials", "message"),
                    ("reuse", "Use its seed and style", "dice")]

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.history = PromptHistory(shell, "images")
        self.previews = StylePreviews(self.studio.layout.cache / "styles")
        self.previews.ready.connect(self._preview_ready)
        self.enhancer = Enhancer()
        self.enhancer.done.connect(self._enhanced)

        # the prompt
        self.prompt = QPlainTextEdit()
        self.prompt.setProperty("prompt", True)
        self.prompt.setPlaceholderText("Describe the image: the subject, where it is, the light, the mood…")
        self.prompt.setFixedHeight(84)
        design.set_type(self.prompt, "h3")
        self.prompt.textChanged.connect(self._counted)
        self.count_label = ui.text("", "tiny", tone="faint")
        self.enhance = ui.button("Improve with ELI", self._enhance, icon="wand", variant="flat",
                                 tip="ELI rewrites the prompt with more detail (needs the main model)")
        self.recent = ui.button("Recent", lambda: self.history.menu(self.recent, self._use_prompt), icon="clock",
                                variant="flat")
        self.ideas_button = ui.button("Ideas from ELI", self._ideas, icon="sparkles", variant="flat",
                                      tip="Five directions to take it (needs the main model)")
        self.ideas_box = QVBoxLayout()
        self.ideas_box.setSpacing(6)
        tools = QHBoxLayout()
        tools.addWidget(self.enhance)
        tools.addWidget(self.ideas_button)
        tools.addWidget(self.recent)
        tools.addStretch(1)
        tools.addWidget(self.count_label)
        tools.addSpacing(10)
        tools.addWidget(self.create_button)

        # the settings
        glyphs = {key: (lambda c, r=ratio: ui.aspect_glyph(r, c)) for _, key, ratio in ASPECTS}
        self.aspect = ui.Segmented([(n, k) for n, k, _ in ASPECTS], str(shell.recall("images_aspect", "square")),
                                   glyphs=glyphs, accent=self.accent)
        self.aspect.changed.connect(lambda v: shell.remember("images_aspect", v))
        self.count = ui.Stepper(1, 8, int(shell.recall("images_count", 2)))
        self.count.changed.connect(lambda v: shell.remember("images_count", v))
        self.seed = QSpinBox()
        self.seed.setRange(0, 2_000_000_000)
        self.seed.setValue(new_seed())
        self.seed.setFixedWidth(130)
        self.dice = ui.icon_button("dice", "A new seed", lambda: self.seed.setValue(new_seed()))
        self.lock = ui.icon_button("unlock", "Keep this seed for the next images too", self._locked, checkable=True)
        seed_row = QHBoxLayout()
        seed_row.setSpacing(4)
        seed_row.addWidget(self.seed)
        seed_row.addWidget(self.dice)
        seed_row.addWidget(self.lock)
        settings = QHBoxLayout()
        settings.setSpacing(22)
        settings.addWidget(ui.Field("Shape", self.aspect))
        settings.addWidget(ui.Field("How many", self.count))
        settings.addWidget(ui.Field("Seed", seed_row))
        settings.addStretch(1)

        # the styles
        self.styles: dict[str, StyleCard] = {}
        style_row = QHBoxLayout()
        style_row.setSpacing(10)
        chosen = str(shell.recall("images_style", "auto"))
        for label, key in STYLES:
            card = StyleCard(label, key, self.accent)
            card.setChecked(key == chosen)
            card.clicked.connect(lambda _c=False, k=key: self._style(k))
            self.styles[key] = card
            style_row.addWidget(card)
            if self.previews.path(key).is_file():
                card.set_image(self.previews.path(key))
        style_row.addStretch(1)

        self.negative = QLineEdit()
        self.negative.setPlaceholderText("What the image must not have: text, watermarks, extra hands…")
        leave_out = ui.Section("Leave out", opened=False)
        leave_out.add(self.negative)

        builder = ui.Section("Build the prompt", opened=False)
        for title, words in BUILDER:
            group = ui.ChipGroup([(w, w) for w in words], exclusive=False, accent=self.accent)
            group.changed.connect(lambda g=group: self._built(g))
            builder.add(ui.Field(title, group))
        self._ideas_holder = QWidget()
        self._ideas_holder.setLayout(self.ideas_box)
        self._ideas_holder.hide()

        composer = ui.Card(padding=20, spacing=12)
        composer.add(self.prompt, tools, self._ideas_holder, builder, ui.hairline(), settings,
                     ui.Field("Style", style_row), leave_out, self.reason)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 20)
        lay.setSpacing(18)
        lay.addLayout(self.header("Images", "Pictures from your words: an image model when this machine has one, "
                                            "or ELI's procedural renderer on any machine. Every image is marked as "
                                            "made by a model, in the file."))
        lay.addWidget(self.engines)
        lay.addWidget(composer)
        lay.addLayout(self.gallery_bar("Your images"))
        self.gallery.fit_to_content()
        lay.addWidget(self.gallery, 1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(body))
        self._counted()

    # ── the request ──
    def request(self) -> dict[str, Any]:
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            raise ValueError("Describe the image first.")
        if not self.lock.isChecked() and self._used_seed == self.seed.value():
            self.seed.setValue(new_seed())
        self._used_seed = self.seed.value()
        return {"prompt": prompt, "negative": self.negative.text().strip(), "aspect": self.aspect.value(),
                "count": self.count.value(), "seed": self.seed.value(), "style": self._chosen_style()}

    _used_seed = -1

    def expected(self, request: dict[str, Any]) -> int:
        cap = 4 if self.engines.current == "images.diffusion" else 8
        return max(1, min(cap, int(request.get("count", 1))))

    def after_submit(self, request: dict[str, Any]) -> None:
        self.history.add(request["prompt"])

    def _chosen_style(self) -> str:
        return next((k for k, c in self.styles.items() if c.isChecked()), "auto")

    def _style(self, key: str) -> None:
        for k, card in self.styles.items():
            card.setChecked(k == key)
        self.shell.remember("images_style", key)

    def _locked(self) -> None:
        on = self.lock.isChecked()
        self.lock.setIcon(icons.icon("lock" if on else "unlock", design.TEXT if on else design.SUBTLE, 18))
        self.lock.setToolTip("The seed stays as it is" if on else "Keep this seed for the next images too")

    def _counted(self) -> None:
        n = len(self.prompt.toPlainText())
        self.count_label.setText(f"{n} characters" if n else "")

    def _use_prompt(self, prompt: str) -> None:
        self.prompt.setPlainText(prompt)
        self.prompt.setFocus()

    # ── ELI's help with the prompt ──
    def _enhance(self) -> None:
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            self.shell.toast("Write a few words first: ELI builds on them.", "warn")
            return
        if not self.studio.main.available:
            self.shell.toast(f"ELI needs the main model to help with prompts: {self.studio.main.why_unavailable}",
                             "warn")
            return
        self.enhance.setEnabled(False)
        self.enhance.setText("Improving…")
        self.enhancer.run(self.studio, prompt)

    def _enhanced(self, better: str, why: str) -> None:
        self.enhance.setEnabled(True)
        self.enhance.setText("Improve with ELI")
        if better:
            self.prompt.setPlainText(better)
            self.shell.toast("ELI improved the prompt. Ctrl+Z puts yours back.", "good")
        else:
            self.shell.toast(f"ELI could not improve it: {why}", "warn")

    def _built(self, group: ui.ChipGroup) -> None:
        """A builder chip adds its words to the prompt, or takes them out again."""
        text = self.prompt.toPlainText().strip()
        parts = [p.strip() for p in text.split(",") if p.strip()]
        for word in group.chips:
            if group.chips[word].isChecked() and word not in parts:
                parts.append(word)
            elif not group.chips[word].isChecked() and word in parts:
                parts.remove(word)
        self.prompt.setPlainText(", ".join(parts))

    def _ideas(self) -> None:
        if not self.studio.main.available:
            self.shell.toast(f"ELI needs the main model for ideas: {self.studio.main.why_unavailable}", "warn")
            return
        seed_words = self.prompt.toPlainText().strip() or self.shell.project_name() or "something striking"
        self.ideas_button.setEnabled(False)
        self.ideas_button.setText("Thinking…")

        def work() -> Any:
            from eli_creation.engines.writing import parse_json

            return parse_json(self.studio.main.generate(
                system=IDEAS_SYSTEM, prompt=f"Starting from: {seed_words}\nGive five different image prompts, each "
                                            'one vivid sentence. Answer as {"ideas": ["...", ...]}',
                max_tokens=700, temperature=0.9, json_mode=True))

        self.shell.run_in_background(work, self._ideas_back)

    def _ideas_back(self, result: Any) -> None:
        self.ideas_button.setEnabled(True)
        self.ideas_button.setText("Ideas from ELI")
        ideas = [str(i) for i in (result.get("ideas") if isinstance(result, dict) else None) or [] if str(i).strip()]
        if not ideas:
            self.shell.toast(f"ELI had no ideas this time: {result}", "warn")
            return
        while self.ideas_box.count():
            item = self.ideas_box.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.ideas_box.addWidget(ui.text("ELI's ideas: choose one to use it", "tiny", tone="muted"))
        for idea in ideas[:5]:
            line = ui.button(idea[:150], None, icon="sparkles", variant="flat")
            line.setStyleSheet("text-align: left;")
            line.clicked.connect(lambda _c=False, i=idea: self._use_prompt(i))
            self.ideas_box.addWidget(line)
        self._ideas_holder.show()

    def variations(self, tile: Tile) -> None:
        req = manifest_of(tile.path).get("request") or {}
        prompt = str(req.get("prompt") or "").strip()
        if not prompt:
            self.shell.toast("That picture has no prompt to vary.", "warn")
            return
        self.prompt.setPlainText(prompt)
        if req.get("style") in self.styles:
            self._style(str(req["style"]))
        if req.get("aspect"):
            self.aspect.set_value(str(req["aspect"]))
        self.count.set_value(4)
        self.lock.setChecked(False)
        self._locked()
        self.seed.setValue(new_seed())
        self.submit()

    # ── the style previews ──
    def _preview_ready(self, style: str) -> None:
        if style in self.styles:
            self.styles[style].set_image(self.previews.path(style))

    # ── being shown ──
    def shown(self, **wanted: Any) -> None:
        self.refresh()
        self.load_gallery()
        if self.shell.recall("style_previews", True):
            self.previews.start()
        if wanted.get("prompt"):
            self.prompt.setPlainText(str(wanted["prompt"]))
        if wanted.get("create"):
            self.submit()
        elif wanted.get("focus") or wanted.get("prompt"):
            self.prompt.setFocus()

    def act(self, name: str, tile: Tile) -> None:
        if name == "variations":
            self.variations(tile)
            return
        if name == "cards":
            self.shell.go("socials", card=tile.path)
            return
        if name == "reuse":
            req = (manifest_of(tile.path).get("request") or {})
            if req.get("seed") is not None:
                self.seed.setValue(int(req["seed"]))
                self.lock.setChecked(True)
                self._locked()
            if req.get("style") in self.styles:
                self._style(str(req["style"]))
            self.shell.toast("Its seed and style are set: change the prompt and create.", "good")
            return
        super().act(name, tile)

