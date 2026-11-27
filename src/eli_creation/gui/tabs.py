"""The creative tabs: Socials, Images, Videos, Games, Editing, Coding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
)

from eli_creation.engines.writing import PLATFORMS
from eli_creation.gui.studio_tab import StudioTab
from eli_creation.gui.widgets import button, row


def _text(lines: int = 4, hint: str = "") -> QPlainTextEdit:
    edit = QPlainTextEdit()
    edit.setPlaceholderText(hint)
    edit.setFixedHeight(22 * lines + 12)
    return edit


def _combo(items: list[tuple[str, str]], default: str = "") -> QComboBox:
    box = QComboBox()
    for text, data in items:
        box.addItem(text, data)
    if default:
        box.setCurrentIndex(max(0, box.findData(default)))
    return box


def _spin(low: int, high: int, value: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


ASPECTS = [("Square 1:1", "square"), ("Portrait 2:3", "portrait"), ("Landscape 3:2", "landscape"),
           ("Wide 16:9", "wide"), ("Story 9:16", "story")]


class SocialsTab(StudioTab):
    key = "socials"
    heading = "Socials"
    blurb = "Posts for each platform from one brief, in your voice, within each platform's limit."

    def build_form(self, form: QFormLayout) -> None:
        self.brief = _text(4, "What is the post about? A launch, an episode, a sale, a milestone...")
        self.platforms = QListWidget()
        for key, (name, limit) in PLATFORMS.items():
            item = QListWidgetItem(f"{name} ({limit})")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in ("x", "instagram") else Qt.CheckState.Unchecked)
            self.platforms.addItem(item)
        self.platforms.setFixedHeight(170)
        self.audience = QLineEdit()
        self.tone = _combo([(t.capitalize(), t) for t in ("natural", "playful", "professional", "bold", "warm", "witty")])
        self.voice = _text(2, "Brand voice: words you use, words you never use")
        self.variants = _spin(1, 5, 3)
        self.hashtags = QCheckBox("Hashtags")
        self.hashtags.setChecked(True)
        form.addRow("Brief", self.brief)
        form.addRow("Platforms", self.platforms)
        form.addRow("Audience", self.audience)
        form.addRow("Tone", self.tone)
        form.addRow("Voice", self.voice)
        form.addRow("Drafts each", self.variants)
        form.addRow("", self.hashtags)

    def request(self) -> dict[str, Any]:
        chosen = [self.platforms.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.platforms.count())
                  if self.platforms.item(i).checkState() == Qt.CheckState.Checked]
        if not self.brief.toPlainText().strip():
            raise ValueError("Write what the post is about first.")
        return {"brief": self.brief.toPlainText().strip(), "platforms": chosen, "audience": self.audience.text(),
                "tone": self.tone.currentData(), "voice": self.voice.toPlainText(), "variants": self.variants.value(),
                "hashtags": self.hashtags.isChecked()}


class ImagesTab(StudioTab):
    key = "images"
    heading = "Images"
    blurb = ("An image model when this machine has one (loaded for the job, unloaded after), or ELI v3's "
             "procedural renderer on any machine. Every image carries its AI-content marking.")

    def build_form(self, form: QFormLayout) -> None:
        from eli_creation.engines.image_engine import visual_core

        self.prompt = _text(4, "Describe the image")
        self.negative = QLineEdit()
        self.negative.setPlaceholderText("What it must not have")
        self.aspect = _combo(ASPECTS)
        self.count = _spin(1, 8, 2)
        self.seed = _spin(0, 2_000_000_000, 77)
        styles = sorted(getattr(visual_core, "STYLE_KEYWORDS", {}).keys()) or ["cinematic", "neon", "minimal"]
        self.style_box = _combo([("Automatic", "auto")] + [(s.capitalize(), s) for s in styles])
        form.addRow("Prompt", self.prompt)
        form.addRow("Leave out", self.negative)
        form.addRow("Shape", self.aspect)
        form.addRow("How many", self.count)
        form.addRow("Seed", self.seed)
        form.addRow("Style", self.style_box)

    def request(self) -> dict[str, Any]:
        if not self.prompt.toPlainText().strip():
            raise ValueError("Describe the image first.")
        return {"prompt": self.prompt.toPlainText().strip(), "negative": self.negative.text(),
                "aspect": self.aspect.currentData(), "count": self.count.value(), "seed": self.seed.value(),
                "style": self.style_box.currentData()}


class VideosTab(StudioTab):
    key = "videos"
    heading = "Videos"
    blurb = ("Animatics on any machine today; text-to-video, narration, captions and music as their models "
             "arrive, each shown here with what this machine needs for it.")

    def build_form(self, form: QFormLayout) -> None:
        self.images = QListWidget()
        self.images.setFixedHeight(160)
        add = button("Add images…", self._add)
        recent = button("Add the latest images", self._recent)
        clear = button("Clear", self.images.clear)
        self.title_edit = QLineEdit("Animatic")
        self.seconds = QDoubleSpinBox()
        self.seconds.setRange(0.2, 20.0)
        self.seconds.setValue(2.0)
        self.aspect = _combo(ASPECTS, "landscape")
        form.addRow("Images, in order", self.images)
        form.addRow("", row(add, recent, clear))
        form.addRow("Title", self.title_edit)
        form.addRow("Seconds each", self.seconds)
        form.addRow("Shape", self.aspect)

    def _add(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Images", "", "Images (*.png *.jpg *.jpeg *.webp)")
        for path in files:
            self.images.addItem(path)

    def _recent(self) -> None:
        for asset in reversed(self.studio.library.recent(kind="image", limit=6)):
            self.images.addItem(str(asset.path))

    def request(self) -> dict[str, Any]:
        paths = [self.images.item(i).text() for i in range(self.images.count())]
        return {"images": paths, "title": self.title_edit.text(), "seconds": self.seconds.value(),
                "aspect": self.aspect.currentData()}


class GamesTab(StudioTab):
    key = "games"
    heading = "Games"
    blurb = ("Design a game from a pitch, then play it in a browser. Its kinds are the ones ELI VR plays, "
             "so a design made here can be set in ELI's rooms.")

    def build_form(self, form: QFormLayout) -> None:
        self.pitch = _text(4, "Catch falling stars before they hit the ground, faster each round...")
        self.design = QLineEdit()
        self.design.setPlaceholderText("A .game.json design (the latest one is used when this is empty)")
        pick = button("Choose…", self._pick)
        form.addRow("Pitch", self.pitch)
        form.addRow("Design to play", row(self.design, pick, stretch_last=False))

    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Game design", "", "Game designs (*.game.json)")
        if path:
            self.design.setText(path)

    def request(self) -> dict[str, Any]:
        if self.engine_id == "games.browser":
            design = self.design.text().strip() or self.selected_path()
            if not design.endswith(".game.json"):
                latest = [a for a in self.studio.library.recent(kind="game", limit=20) if a.path.name.endswith(".game.json")]
                design = str(latest[0].path) if latest else ""
            if not design:
                raise ValueError("Design a game first, or choose a design.")
            return {"design": design}
        if not self.pitch.toPlainText().strip():
            raise ValueError("Write the pitch first.")
        return {"pitch": self.pitch.toPlainText().strip()}


class EditingTab(StudioTab):
    key = "editing"
    heading = "Editing"
    blurb = ("Edit any image: crop to a platform's shape, resize, adjust, caption. An edit of AI output stays "
             "marked as AI; an edit of your own photo does not claim to be AI.")

    def build_form(self, form: QFormLayout) -> None:
        self.path = QLineEdit()
        pick = button("Choose…", self._pick)
        self.crop = _combo([("Keep", ""), ("1:1", "1:1"), ("4:5", "4:5"), ("9:16", "9:16"), ("16:9", "16:9"), ("3:2", "3:2")])
        self.width_box = _spin(0, 8192, 0)
        self.upscale = QDoubleSpinBox()
        self.upscale.setRange(1.0, 4.0)
        self.upscale.setValue(1.0)
        self.rotate = _combo([("No", "0"), ("90°", "90"), ("180°", "180"), ("270°", "270")])
        self.brightness, self.contrast, self.saturation = (QDoubleSpinBox() for _ in range(3))
        for box in (self.brightness, self.contrast, self.saturation):
            box.setRange(0.2, 2.5)
            box.setSingleStep(0.05)
            box.setValue(1.0)
        self.sharpen = QCheckBox("Sharpen")
        self.grey = QCheckBox("Black and white")
        self.caption = QLineEdit()
        self.format = _combo([("PNG", "png"), ("WebP", "webp"), ("JPEG", "jpg")])
        form.addRow("Image", row(self.path, pick, stretch_last=False))
        form.addRow("Crop to", self.crop)
        form.addRow("Width (0: keep)", self.width_box)
        form.addRow("Enlarge ×", self.upscale)
        form.addRow("Turn", self.rotate)
        form.addRow("Brightness", self.brightness)
        form.addRow("Contrast", self.contrast)
        form.addRow("Colour", self.saturation)
        form.addRow("", row(self.sharpen, self.grey))
        form.addRow("Caption", self.caption)
        form.addRow("Save as", self.format)

    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Image", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.path.setText(path)

    def request(self) -> dict[str, Any]:
        path = self.path.text().strip() or self.selected_path()
        if not path or not Path(path).is_file():
            raise ValueError("Choose an image first.")
        ops: list[dict[str, Any]] = []
        if self.crop.currentData():
            ops.append({"op": "crop_aspect", "aspect": self.crop.currentData()})
        if self.width_box.value():
            ops.append({"op": "resize", "width": self.width_box.value()})
        if self.upscale.value() > 1.0:
            ops.append({"op": "upscale", "factor": self.upscale.value()})
        if self.rotate.currentData() != "0":
            ops.append({"op": "rotate", "degrees": int(self.rotate.currentData())})
        if any(b.value() != 1.0 for b in (self.brightness, self.contrast, self.saturation)):
            ops.append({"op": "adjust", "brightness": self.brightness.value(), "contrast": self.contrast.value(),
                        "saturation": self.saturation.value()})
        if self.sharpen.isChecked():
            ops.append({"op": "sharpen"})
        if self.grey.isChecked():
            ops.append({"op": "grayscale"})
        if self.caption.text().strip():
            ops.append({"op": "caption", "text": self.caption.text().strip()})
        return {"path": path, "ops": ops, "format": self.format.currentData()}


class CodingTab(StudioTab):
    key = "coding"
    heading = "Coding"
    blurb = ("ELI v3's coding agent on the main model: it plans, writes, runs and repairs code against tests "
             "it writes for it. Scripts, tools, web pages, game logic.")

    def build_form(self, form: QFormLayout) -> None:
        self.task = _text(6, "What should the code do?")
        self.language = _combo([(n, n.lower()) for n in ("Python", "JavaScript", "TypeScript", "HTML", "GDScript")])
        self.tests = QCheckBox("Write and run tests")
        self.tests.setChecked(True)
        self.seconds = _spin(30, 1800, 240)
        form.addRow("Task", self.task)
        form.addRow("Language", self.language)
        form.addRow("", self.tests)
        form.addRow("Time allowed (s)", self.seconds)

    def request(self) -> dict[str, Any]:
        if not self.task.toPlainText().strip():
            raise ValueError("Describe the task first.")
        return {"task": self.task.toPlainText().strip(), "language": self.language.currentData(),
                "tests": self.tests.isChecked(), "seconds": self.seconds.value()}


TABS = (SocialsTab, ImagesTab, VideosTab, GamesTab, EditingTab, CodingTab)
