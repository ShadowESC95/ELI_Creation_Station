"""Film: a film or an ad as a project, from plan to export.

Plan it (its goal, look, key moments, next steps, its characters, places and props), build it
scene by scene (a picture for each, how the camera moves, how long, how it gives way to the next,
its words on screen, its look), put sound under it (a voice, music, effects) and captions over it,
watch it in the preview exactly as it will be written, and write it out as one MP4.
"""

from __future__ import annotations

import copy
import hashlib
import json
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons, imaging
from eli_creation.gui.film_widgets import Preview, SceneStrip, Timeline, fmt_time
from eli_creation.gui.gallery import Gallery, Tile, open_lightbox
from eli_creation.gui.pages.base import Page
from eli_creation.gui.sound import Sound
from eli_creation.production import grade as grading
from eli_creation.production import music as music_lib
from eli_creation.production import sfx as sfx_lib
from eli_creation.production import templates
from eli_creation.production.formats import CAMERA, FORMATS, TRANSITIONS
from eli_creation.production.project import (
    INGREDIENT_KINDS,
    STAGES,
    Clip,
    Ingredient,
    Project,
    ProjectStore,
    Scene,
    Step,
)

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job

SCENES_SYSTEM = ("You are ELI, a film director. Plan short films and ads as concrete, visual scenes. Answer with "
                 "JSON only.")


def best_image_engine(studio: Any) -> str:
    from eli_creation.engines import registry

    return "images.diffusion" if registry.get("images.diffusion").availability(studio).ok else "images.procedural"


# ── dialogs ──────────────────────────────────────────────────────────────
class _Form(QDialog):
    def __init__(self, parent: QWidget, title: str, note: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self.form = QFormLayout()
        lay = QVBoxLayout(self)
        if note:
            lay.addWidget(ui.text(note, "small", tone="muted", wrap=True))
        lay.addLayout(self.form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)


def voice_box(selected: str = "") -> QComboBox:
    from eli_creation.production import speech

    box = QComboBox()
    for voice in speech.voices():
        box.addItem(voice.label, voice.id)
    if not box.count():
        box.addItem("No voice on this computer: start ELI v3, or install Piper or eSpeak NG", "")
    index = box.findData(selected)
    box.setCurrentIndex(max(0, index))
    return box


class VoiceDialog(_Form):
    def __init__(self, parent: QWidget, text: str = "") -> None:
        super().__init__(parent, "Add a voice", "What should be said. It starts at the playhead; captions follow it.")
        self.text = QPlainTextEdit(text)
        self.text.setMinimumHeight(140)
        self.voice = voice_box()
        self.speed = ui.SliderField("Speed", 0.7, 1.4, 1.0, step=0.05, fmt="×{:.2f}")
        self.form.addRow("Words", self.text)
        self.form.addRow("Voice", self.voice)
        self.form.addRow("", self.speed)


class MusicDialog(_Form):
    def __init__(self, parent: QWidget, seconds: float) -> None:
        super().__init__(parent, "Add music", "Composed on this machine for the film's length: no samples, yours to use.")
        self.mood = QComboBox()
        for key, mood in music_lib.MOODS.items():
            self.mood.addItem(f"{mood.name} · {mood.blurb}", key)
        self.seconds = ui.SliderField("Length", 5, 300, max(5.0, round(seconds)), step=1, fmt="{:.0f} s")
        self.intensity = ui.SliderField("Intensity", 0.2, 1.0, 0.7, step=0.05, fmt="{:.2f}")
        self.form.addRow("Mood", self.mood)
        self.form.addRow("", self.seconds)
        self.form.addRow("", self.intensity)


class TemplateDialog(QDialog):
    """Choose a template: each a ready plan of scenes, words and sound."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start from a template")
        self.resize(860, 560)
        self.chosen = ""
        grid = QGridLayout()
        grid.setSpacing(12)
        for n, (key, template) in enumerate(templates.TEMPLATES.items()):
            card = ui.Card(padding=14, spacing=6)
            fmt = FORMATS.get(template.format, FORMATS["youtube"])
            card.add(ui.text(template.name, "h3"), ui.text(template.blurb, "small", tone="subtle", wrap=True),
                     ui.text(f"{template.category} · {fmt.width}×{fmt.height} · {len(template.shots)} scenes · "
                             f"{music_lib.MOODS[template.mood].name} music", "tiny", tone="muted", wrap=True))
            pick = ui.button("Use this", partial(self._pick, key), icon="check")
            card.add(pick)
            grid.addWidget(card, n // 3, n % 3)
        holder = QWidget()
        holder.setLayout(grid)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(holder)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.text("Every template is a plan you can change: its scenes, words, look and sound.",
                              "small", tone="muted"))
        lay.addWidget(area, 1)

    def _pick(self, key: str) -> None:
        self.chosen = key
        self.accept()


class AdDialog(_Form):
    """The 1-click ad maker: a few answers, and the rest is made."""

    FIELDS = (("product", "Product or brand", "Northwind Coffee"), ("tagline", "Its promise", "Roasted this morning"),
              ("point1", "First reason", "Single origin beans"), ("point2", "Second reason", "Delivered in a day"),
              ("point3", "Third reason", "Fair prices"), ("cta", "Call to action", "Order today"),
              ("topic", "What it is about (films, events)", ""))

    def __init__(self, parent: QWidget, studio: Any) -> None:
        note = ("Answer what you can. ELI plans the ad with the main model when there is one; pictures are made for "
                "each scene, a voice reads it over music, captions follow, and it is written out.")
        super().__init__(parent, "1-click ad maker", note)
        self.template = QComboBox()
        for key, template in templates.TEMPLATES.items():
            if template.category in ("Ads", "Social media", "Product", "Promotional", "Event", "Explainer"):
                self.template.addItem(f"{template.name} · {template.blurb}", key)
        self.form.addRow("Kind of ad", self.template)
        self.answers: dict[str, QLineEdit] = {}
        for key, label_text, hint in self.FIELDS:
            edit = QLineEdit()
            edit.setPlaceholderText(hint)
            self.answers[key] = edit
            self.form.addRow(label_text, edit)
        self.format = QComboBox()
        for key, fmt in FORMATS.items():
            if key != "thumbnail":
                self.format.addItem(f"{fmt.name} ({fmt.width}×{fmt.height})", key)
        self.format.insertItem(0, "The template's own shape", "")
        self.format.setCurrentIndex(0)
        self.voice = voice_box()
        self.voice.insertItem(0, "No voice", "none")
        self.mood = QComboBox()
        self.mood.addItem("The template's own music", "")
        for key, mood in music_lib.MOODS.items():
            self.mood.addItem(mood.name, key)
        self.use_eli = ui.Switch("ELI plans it (with the main model)", studio.main.available)
        self.use_eli.setEnabled(studio.main.available)
        self.form.addRow("Shape", self.format)
        self.form.addRow("Voice", self.voice)
        self.form.addRow("Music", self.mood)
        self.form.addRow("", self.use_eli)

    def request(self) -> dict[str, Any]:
        answers = {k: e.text().strip() for k, e in self.answers.items() if e.text().strip()}
        if not answers.get("product"):
            raise ValueError("Name the product or brand first.")
        return {"template": self.template.currentData(), "answers": answers, "format": self.format.currentData(),
                "voice": self.voice.currentData() or "auto", "mood": self.mood.currentData(),
                "use_eli": self.use_eli.isChecked()}


class IngredientDialog(_Form):
    def __init__(self, parent: QWidget, ingredient: Ingredient) -> None:
        super().__init__(parent, "An ingredient", "A character, place, object, prop or reference the scenes draw on.")
        self.kind = QComboBox()
        for k in INGREDIENT_KINDS:
            self.kind.addItem(k.capitalize(), k)
        self.kind.setCurrentIndex(max(0, self.kind.findData(ingredient.kind)))
        self.name = QLineEdit(ingredient.name)
        self.role = QLineEdit(ingredient.role)
        self.role.setPlaceholderText("Lead explorer, ancient guardian, the artifact…")
        self.description = QPlainTextEdit(ingredient.description)
        self.description.setPlaceholderText("How they look: age, clothes, colours, features")
        self.description.setMaximumHeight(90)
        self.form.addRow("Kind", self.kind)
        self.form.addRow("Name", self.name)
        self.form.addRow("Role", self.role)
        self.form.addRow("Looks", self.description)


class PickPictures(QDialog):
    """Choose pictures from the library."""

    def __init__(self, parent: QWidget, studio: Any) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pictures from the library")
        self.resize(900, 640)
        self.gallery = Gallery(size="small")
        self.gallery.set_tiles([Tile.from_asset(a) for a in studio.library.recent(kind="image", limit=300)])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(ui.text("Choose the pictures, in the order they should play (Ctrl-click for several)",
                              "small", tone="muted"))
        lay.addWidget(self.gallery, 1)
        lay.addWidget(buttons)

    def chosen(self) -> list[str]:
        return [t.path for t in self.gallery.selected_tiles()]


# ── the page ─────────────────────────────────────────────────────────────
class FilmPage(Page):
    key = "videos"

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.store = ProjectStore(self.studio.layout.projects / "films")
        self.project: Project | None = None
        self.scene_id = ""
        self.jobs: dict[str, tuple[str, dict[str, Any]]] = {}  # job id: (purpose, details)
        self.sound = Sound()
        self._saver = QTimer(self)
        self._saver.setSingleShot(True)
        self._saver.setInterval(500)
        self._saver.timeout.connect(self._save_now)
        self._loading = False

        # ── the header ──
        self.picker = QComboBox()
        self.picker.setMinimumWidth(260)
        self.picker.currentIndexChanged.connect(self._picked)
        new = ui.button("New", None, icon="plus")
        menu = QMenu(new)
        menu.addAction(icons.icon("film", self.accent, 16), "A blank film", self.new_blank)
        menu.addAction(icons.icon("layers", self.accent, 16), "From a template…", self.new_from_template)
        menu.addAction(icons.icon("bolt", self.accent, 16), "1-click ad…", self.new_ad)
        new.setMenu(menu)
        self.stage = ui.Segmented([("Plan", "plan"), ("Produce", "produce"), ("Review", "review")], "plan",
                                  accent=self.accent)
        self.stage.setFixedWidth(300)
        self.stage.changed.connect(self._stage)
        self.format = QComboBox()
        for key, fmt in FORMATS.items():
            if key != "thumbnail":
                self.format.addItem(f"{fmt.name} · {fmt.width}×{fmt.height}", key)
        self.format.currentIndexChanged.connect(self._format)
        self.export_button = ui.GlowButton("Export film", "download", accent=self.accent)
        self.export_button.clicked.connect(self.export)
        self.status = ui.text("", "tiny", tone="muted")

        # ── the storyboard ──
        self.strip = SceneStrip()
        self.strip.chosen.connect(self._scene_chosen)
        self.strip.reordered.connect(self._reordered)
        strip_tools = QVBoxLayout()
        strip_tools.addWidget(ui.icon_button("plus", "Add a scene", self.add_scene))
        strip_tools.addWidget(ui.icon_button("copy", "Duplicate the scene", self.duplicate_scene))
        strip_tools.addWidget(ui.icon_button("trash", "Remove the scene", self.remove_scene))
        strip_tools.addWidget(ui.icon_button("sparkles", "Picture every scene that has none", self.picture_all))
        strip_tools.addStretch(1)
        story = QHBoxLayout()
        story.addWidget(self.strip, 1)
        story.addLayout(strip_tools)

        # ── left: ingredients and notes ──
        self.ingredients = QListWidget()
        self.ingredients.setViewMode(QListView.ViewMode.IconMode)
        self.ingredients.setIconSize(QSize(92, 92))
        self.ingredients.setGridSize(QSize(112, 138))
        self.ingredients.setWordWrap(True)
        self.ingredients.itemDoubleClicked.connect(self._edit_ingredient)
        self.ingredient_kind = ui.Segmented([(k.capitalize()[:9], k) for k in INGREDIENT_KINDS], "character",
                                            accent=self.accent)
        self.ingredient_kind.changed.connect(lambda _k: self._show_ingredients())
        ing_tools = QHBoxLayout()
        ing_tools.addWidget(ui.button("Add", self.add_ingredient, icon="plus"))
        ing_tools.addWidget(ui.button("Picture it", self.picture_ingredient, icon="sparkles", variant="flat"))
        ing_tools.addWidget(ui.button("Remove", self.remove_ingredient, icon="trash", variant="flat"))
        ing_tools.addStretch(1)
        ing_box = QWidget()
        ing_lay = QVBoxLayout(ing_box)
        ing_lay.addWidget(self.ingredient_kind)
        ing_lay.addWidget(self.ingredients, 1)
        ing_lay.addLayout(ing_tools)
        self.logline = QPlainTextEdit()
        self.logline.setPlaceholderText("The film in a sentence: who, what, why it matters")
        self.logline.setMaximumHeight(70)
        self.goal = QLineEdit()
        self.goal.setPlaceholderText("What it should make people feel or do")
        self.direction = QPlainTextEdit()
        self.direction.setPlaceholderText("The look: realistic landscapes, a touch of sci-fi, warm dawn light…")
        self.direction.setMaximumHeight(70)
        self.moments = QPlainTextEdit()
        self.moments.setPlaceholderText("Key moments, one a line")
        self.moments.setMaximumHeight(80)
        self.steps = QListWidget()
        self.steps.setMaximumHeight(120)
        self.steps.itemChanged.connect(lambda _i: self._notes_changed())
        self.new_step = QLineEdit()
        self.new_step.setPlaceholderText("Add a next step, then Enter")
        self.new_step.returnPressed.connect(self._add_step)
        self.plan_eli = ui.button("ELI: plan the scenes from the logline", self.eli_plan, icon="sparkles")
        for edit in (self.logline, self.direction, self.moments):
            edit.textChanged.connect(self._notes_changed)
        self.goal.textChanged.connect(lambda _t: self._notes_changed())
        notes_box = QWidget()
        notes = QVBoxLayout(notes_box)
        for label_text, widget in (("Logline", self.logline), ("Goal", self.goal), ("Visual direction", self.direction),
                                   ("Key moments", self.moments), ("Next steps", self.steps)):
            notes.addWidget(ui.text(label_text, "small", tone="subtle"))
            notes.addWidget(widget)
        notes.addWidget(self.new_step)
        notes.addWidget(self.plan_eli)
        notes.addStretch(1)
        notes_scroll = QScrollArea()
        notes_scroll.setWidgetResizable(True)
        notes_scroll.setWidget(notes_box)

        # ── centre: the preview ──
        self.preview = Preview()
        self.preview.moved.connect(self._moved)
        self.play_button = ui.icon_button("play", "Play (Space)", self.toggle_play, size=22, colour=design.TEXT)
        self.time_label = ui.text("00:00.00 / 00:00.00", "small", tone="subtle")
        self.captions_on = ui.Switch("Captions", True)
        self.captions_on.toggled.connect(self._captions_toggled)
        transport = QHBoxLayout()
        transport.addWidget(ui.icon_button("chevron_left", "To the start", lambda: self.seek(0.0)))
        transport.addWidget(self.play_button)
        transport.addWidget(self.time_label)
        transport.addStretch(1)
        transport.addWidget(self.captions_on)
        centre_box = ui.Card(padding=10, spacing=8)
        centre_box.add(self.preview, transport)

        # ── right: the scene ──
        self.scene_title = QLineEdit()
        self.scene_title.setPlaceholderText("Scene title")
        self.scene_text = QPlainTextEdit()
        self.scene_text.setPlaceholderText("What the picture shows: subject, place, light, mood")
        self.scene_text.setMaximumHeight(90)
        self.camera = QComboBox()
        for key, (name, _a, _b) in CAMERA.items():
            self.camera.addItem(name, key)
        self.seconds = ui.SliderField("Length", 0.5, 20.0, 4.0, step=0.1, fmt="{:.1f} s", icon="clock")
        self.transition = QComboBox()
        for key, name in TRANSITIONS.items():
            self.transition.addItem(name, key)
        self.words = QLineEdit()
        self.words.setPlaceholderText("Words on screen in this scene (a title, a promise, a call to act)")
        pic_tools = QHBoxLayout()
        pic_tools.addWidget(ui.button("Make the picture", self.picture_scene, icon="sparkles"))
        pic_tools.addWidget(ui.icon_button("library", "Choose from the library", self.choose_picture))
        pic_tools.addWidget(ui.icon_button("upload", "Open a picture file", self.open_picture))
        shot = QWidget()
        shot_form = QFormLayout(shot)
        shot_form.addRow("Title", self.scene_title)
        shot_form.addRow("Picture", self.scene_text)
        shot_form.addRow("", pic_tools)
        shot_form.addRow("Camera", self.camera)
        shot_form.addRow("", self.seconds)
        shot_form.addRow("Into the next", self.transition)
        shot_form.addRow("On screen", self.words)
        self.look = QComboBox()
        for key, (name, blurb) in grading.LOOKS.items():
            self.look.addItem(f"{name} · {blurb}", key)
        self.grades = {name: ui.SliderField(label_text, low, 1.0, 0.0, step=0.05, fmt="{:+.2f}")
                       for name, label_text, low in (("warmth", "Warmth", -1.0), ("light", "Lighting", -1.0),
                                                     ("contrast", "Contrast", -1.0), ("colour", "Colour", -1.0),
                                                     ("mood", "Mood", -1.0), ("vignette", "Vignette", 0.0),
                                                     ("grain", "Film grain", 0.0))}
        look_box = QWidget()
        look_lay = QVBoxLayout(look_box)
        look_lay.addWidget(ui.Field("Look", self.look))
        for slider in self.grades.values():
            look_lay.addWidget(slider)
        look_lay.addWidget(ui.button("Same look on every scene", self.look_everywhere, icon="layers", variant="flat"))
        look_lay.addStretch(1)
        right = QTabWidget()
        shot_scroll = QScrollArea()
        shot_scroll.setWidgetResizable(True)
        shot_scroll.setWidget(shot)
        look_scroll = QScrollArea()
        look_scroll.setWidgetResizable(True)
        look_scroll.setWidget(look_box)
        right.addTab(notes_scroll, "Notes")
        right.addTab(ing_box, "Ingredients")
        right.addTab(shot_scroll, "Shot")
        right.addTab(look_scroll, "Look")
        right.setMinimumWidth(340)
        self.inspector = right
        for widget in (self.scene_title, self.words):
            widget.textChanged.connect(lambda _t: self._scene_changed())
        self.scene_text.textChanged.connect(self._scene_changed)
        for combo in (self.camera, self.transition, self.look):
            combo.currentIndexChanged.connect(lambda _i: self._scene_changed())
        self.seconds.changed.connect(lambda _v: self._scene_changed())
        for slider in self.grades.values():
            slider.changed.connect(lambda _v: self._scene_changed(look=True))

        middle = QSplitter(Qt.Orientation.Horizontal)
        middle.addWidget(centre_box)
        middle.addWidget(right)
        middle.setStretchFactor(0, 3)
        middle.setChildrenCollapsible(False)
        middle.setSizes([900, 380])

        # ── the timeline ──
        self.timeline = Timeline()
        self.timeline.seeked.connect(self.seek)
        self.timeline.picked.connect(self._picked_on_timeline)
        self.timeline.clip_moved.connect(lambda _id, _s: self._sound_changed())
        line_scroll = QScrollArea()
        line_scroll.setWidget(self.timeline)
        line_scroll.setWidgetResizable(True)
        line_scroll.setMinimumHeight(self.timeline.minimumHeight() + 18)
        effects = ui.button("Effect", None, icon="bolt")
        fx_menu = QMenu(effects)
        for key, (name, _s, _f, blurb) in sfx_lib.EFFECTS.items():
            fx_menu.addAction(f"{name} · {blurb}", partial(self.add_effect, key))
        effects.setMenu(fx_menu)
        self.zoom = ui.SliderField("Zoom", 10, 200, 60, step=5, fmt="{:.0f} px/s")
        self.zoom.setFixedWidth(220)
        self.zoom.changed.connect(self.timeline.set_zoom)
        tools = QHBoxLayout()
        tools.addWidget(ui.text("Timeline", "h3"))
        tools.addSpacing(10)
        tools.addWidget(ui.button("Voice", self.add_voice, icon="mic"))
        tools.addWidget(ui.button("Music", self.add_music, icon="music"))
        tools.addWidget(effects)
        tools.addWidget(ui.button("Captions from the voice", self.auto_captions, icon="captions", variant="flat"))
        tools.addWidget(ui.button("Remove", self.remove_clip, icon="trash", variant="flat",
                                   tip="Remove the sound selected on the timeline"))
        tools.addStretch(1)
        tools.addWidget(self.zoom)

        self.empty = ui.EmptyState(
            "film", "Make a film or an ad",
            "Start blank, from a template, or answer a few questions and let the 1-click ad maker make all of it: "
            "pictures, a voice, music, captions, and the finished MP4.", accent=self.accent,
            action=ui.button("1-click ad…", self.new_ad, primary=True, icon="bolt"))

        self.work = QWidget()
        work = QVBoxLayout(self.work)
        work.setContentsMargins(0, 0, 0, 0)
        work.setSpacing(10)
        work.addLayout(story)
        work.addWidget(middle, 1)
        work.addLayout(tools)
        work.addWidget(line_scroll)

        head = QHBoxLayout()
        head.addWidget(self.picker)
        head.addWidget(new)
        head.addSpacing(10)
        head.addWidget(self.stage)
        head.addWidget(self.format)
        head.addStretch(1)
        head.addWidget(self.status)
        head.addWidget(self.export_button)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 20, 26, 14)
        lay.setSpacing(12)
        lay.addLayout(self.header("Film", "Films and ads from plan to export: scenes with camera moves and looks, "
                                          "a voice, music and effects, captions, and one MP4 on any machine."))
        lay.addLayout(head)
        lay.addWidget(self.empty, 1)
        lay.addWidget(self.work, 1)
        self._list()

    # ── projects ──
    def _list(self, select: str = "") -> None:
        films = self.store.all()
        self.picker.blockSignals(True)
        self.picker.clear()
        for film in films:
            self.picker.addItem(f"{film.title}", film.id)
        self.picker.blockSignals(False)
        index = self.picker.findData(select) if select else 0
        if films:
            self.picker.setCurrentIndex(max(0, index))
            self._open(str(self.picker.currentData()))
        else:
            self._open("")

    def _picked(self, _index: int) -> None:
        film_id = str(self.picker.currentData() or "")
        if film_id and (self.project is None or film_id != self.project.id):
            self._open(film_id)

    def _open(self, film_id: str) -> None:
        self._save_now()
        self.stop()
        self.sound.forget()
        try:
            self.project = self.store.load(film_id) if film_id else None
        except (OSError, ValueError):
            self.project = None
        has = self.project is not None
        self.empty.setVisible(not has)
        self.work.setVisible(has)
        self.export_button.setEnabled(has)
        self.stage.setEnabled(has)
        self.format.setEnabled(has)
        if self.project is None:
            return
        self._loading = True
        self.stage.set_value(self.project.stage)
        self.inspector.setCurrentIndex({"plan": 0, "produce": 2, "review": 3}.get(self.project.stage, 2))
        self.format.setCurrentIndex(max(0, self.format.findData(self.project.format)))
        self.logline.setPlainText(self.project.logline)
        self.goal.setText(self.project.goal)
        self.direction.setPlainText(self.project.direction)
        self.moments.setPlainText("\n".join(self.project.moments))
        self.steps.clear()
        for step in self.project.steps:
            item = QListWidgetItem(step.text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if step.done else Qt.CheckState.Unchecked)
            self.steps.addItem(item)
        self.captions_on.setChecked(self.project.captions_on)
        self._loading = False
        self.strip.show_project(self.project, self.scene_id)
        self.preview.show_project(self.project)
        self.timeline.show_project(self.project)
        self._show_ingredients()
        self._update_time()

    def _new(self, project: Project) -> None:
        project.library_project = project.library_project or self.shell.project_name()
        self.store.save(project)
        self._list(project.id)
        self.shell.toast(f"“{project.title}” is ready to build", "good")

    def new_blank(self, fmt: str = "youtube") -> None:
        self._new(Project(title=self.shell.project_name() or "Untitled film", format=fmt if fmt in FORMATS else "youtube",
                          scenes=[Scene(title="Opening", description="")],
                          steps=[Step("Write the logline"), Step("Picture every scene"), Step("Add a voice and music")]))

    def new_from_template(self) -> None:
        dialog = TemplateDialog(self)
        if dialog.exec() and dialog.chosen:
            template = templates.TEMPLATES[dialog.chosen]
            project, narration = templates.build(template, {"product": self.shell.project_name() or "Your brand"})
            project.title = f"{template.name}: {self.shell.project_name() or 'new'}"
            project.logline = narration
            self._new(project)

    def new_ad(self, answers: dict[str, Any] | None = None) -> None:
        dialog = AdDialog(self, self.studio)
        for key, value in (answers or {}).items():
            if key in dialog.answers:
                dialog.answers[key].setText(str(value))
        if not dialog.exec():
            return
        try:
            request = dialog.request()
        except ValueError as exc:
            self.shell.toast(str(exc), "warn")
            return
        request["project"] = self.shell.project_name()
        self._submit("videos.admaker", request, "ad", {})
        self.shell.toast("Making the ad: pictures, voice, music, captions, then the film. Watch the bolt above.")

    # ── saving ──
    def _save_soon(self) -> None:
        if not self._loading:
            self._saver.start()

    def _save_now(self) -> None:
        if self.project is not None and not self._loading:
            self.store.save(self.project)

    def _stage(self, stage: str) -> None:
        if self.project is not None and stage in STAGES:
            self.project.stage = stage
            self.inspector.setCurrentIndex({"plan": 0, "produce": 2, "review": 3}[stage])
            self._save_soon()

    def _format(self, _index: int) -> None:
        if self.project is not None and not self._loading:
            self.project.format = str(self.format.currentData())
            self.preview.show_project(self.project)
            self._save_soon()

    def _notes_changed(self) -> None:
        if self.project is None or self._loading:
            return
        self.project.logline = self.logline.toPlainText().strip()
        self.project.goal = self.goal.text().strip()
        self.project.direction = self.direction.toPlainText().strip()
        self.project.moments = [m.strip() for m in self.moments.toPlainText().splitlines() if m.strip()]
        self.project.steps = [Step(self.steps.item(i).text(), self.steps.item(i).checkState() == Qt.CheckState.Checked)
                              for i in range(self.steps.count())]
        self._save_soon()

    def _add_step(self) -> None:
        words = self.new_step.text().strip()
        if not words:
            return
        item = QListWidgetItem(words)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.steps.addItem(item)
        self.new_step.clear()
        self._notes_changed()

    # ── scenes ──
    def scene(self) -> Scene | None:
        if self.project is None:
            return None
        return next((s for s in self.project.scenes if s.id == self.scene_id), None)

    def _scene_chosen(self, scene_id: str) -> None:
        self.scene_id = scene_id
        scene = self.scene()
        if scene is None:
            return
        self._loading = True
        self.scene_title.setText(scene.title)
        self.scene_text.setPlainText(scene.description)
        self.camera.setCurrentIndex(max(0, self.camera.findData(scene.camera)))
        self.seconds.set_value(scene.seconds)
        self.transition.setCurrentIndex(max(0, self.transition.findData(scene.transition)))
        self.words.setText(scene.title_text)
        self.look.setCurrentIndex(max(0, self.look.findData(scene.grade.look)))
        for name, slider in self.grades.items():
            slider.set_value(float(getattr(scene.grade, name)))
        self._loading = False
        if self.project is not None:
            start = next((s for sc, s, _e in self.project.scene_times() if sc.id == scene_id), 0.0)
            if not self.preview.playing:
                self.seek(start + 0.05)

    def _scene_changed(self, *, look: bool = False) -> None:
        scene = self.scene()
        if scene is None or self._loading:
            return
        scene.title = self.scene_title.text().strip()
        scene.description = self.scene_text.toPlainText().strip()
        scene.camera = str(self.camera.currentData())
        scene.seconds = self.seconds.value()
        scene.transition = str(self.transition.currentData())
        scene.title_text = self.words.text().strip()
        scene.grade.look = str(self.look.currentData())
        for name, slider in self.grades.items():
            setattr(scene.grade, name, slider.value())
        self.strip.viewport().update()
        self.timeline.show_project(self.project)
        self.preview.refresh() if look else self.preview.seek(self.preview.t)
        self._update_time()
        self._save_soon()

    def _reordered(self, ids: list[str]) -> None:
        if self.project is None:
            return
        by_id = {s.id: s for s in self.project.scenes}
        self.project.scenes = [by_id[i] for i in ids if i in by_id]
        self.timeline.show_project(self.project)
        self.preview.seek(self.preview.t)
        self._save_soon()

    def add_scene(self) -> None:
        if self.project is None:
            return
        scene = Scene(title=f"Scene {len(self.project.scenes) + 1}")
        self.project.scenes.append(scene)
        self.scene_id = scene.id
        self.strip.show_project(self.project, scene.id)
        self.timeline.show_project(self.project)
        self._save_soon()

    def duplicate_scene(self) -> None:
        scene = self.scene()
        if self.project is None or scene is None:
            return
        twin = copy.deepcopy(scene)
        from eli_creation.production.project import _id

        twin.id = _id("scene")
        twin.title = f"{scene.title} (again)"
        self.project.scenes.insert(self.project.scenes.index(scene) + 1, twin)
        self.strip.show_project(self.project, twin.id)
        self.timeline.show_project(self.project)
        self._save_soon()

    def remove_scene(self) -> None:
        scene = self.scene()
        if self.project is None or scene is None:
            return
        self.project.scenes.remove(scene)
        self.scene_id = self.project.scenes[0].id if self.project.scenes else ""
        self.strip.show_project(self.project, self.scene_id)
        self.timeline.show_project(self.project)
        self.preview.seek(0.0)
        self._save_soon()

    def look_everywhere(self) -> None:
        scene = self.scene()
        if self.project is None or scene is None:
            return
        for other in self.project.scenes:
            other.grade = copy.deepcopy(scene.grade)
        self.preview.refresh()
        self._save_soon()
        self.shell.toast("Every scene has this look now", "good")

    # ── pictures ──
    def _prompt_for(self, words: str) -> str:
        """A scene's words with the look of the film and its named ingredients' descriptions."""
        assert self.project is not None
        extra = [f"{i.name}: {i.description}" for i in self.project.ingredients
                 if i.name and i.name.lower() in words.lower() and i.description]
        parts = [words] + extra + ([self.project.direction] if self.project.direction else [])
        return ", ".join(p for p in parts if p)[:600]

    def picture_scene(self, scene: Scene | None = None) -> None:
        scene = scene or self.scene()
        if self.project is None or scene is None:
            return
        words = scene.description or scene.title
        if not words:
            self.shell.toast("Say what the picture shows first.", "warn")
            return
        aspect = FORMATS.get(self.project.format, FORMATS["youtube"]).aspect
        self._submit(best_image_engine(self.studio), {"prompt": self._prompt_for(words), "count": 1, "aspect": aspect,
                                                      "seed": abs(hash(scene.id)) % 100000,
                                                      "project": self.project.library_project},
                     "scene_picture", {"film": self.project.id, "scene": scene.id})

    def picture_all(self) -> None:
        if self.project is None:
            return
        waiting = [s for s in self.project.scenes if not s.image and (s.description or s.title)]
        for scene in waiting:
            self.picture_scene(scene)
        self.shell.toast(f"Picturing {len(waiting)} scene(s)" if waiting else "Every scene has a picture", "good")

    def choose_picture(self) -> None:
        dialog = PickPictures(self, self.studio)
        if dialog.exec() and dialog.chosen():
            self._set_picture(dialog.chosen()[0])

    def open_picture(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "A picture", "", "Pictures (*.png *.jpg *.jpeg *.webp)")
        if path:
            self._set_picture(path)

    def _set_picture(self, path: str, scene_id: str = "") -> None:
        scene = next((s for s in self.project.scenes if s.id == (scene_id or self.scene_id)), None) if self.project else None
        if scene is None:
            return
        scene.image = path
        self.strip.viewport().update()
        self.timeline.update()
        self.preview.refresh()
        self._save_soon()

    # ── ingredients ──
    def _show_ingredients(self) -> None:
        self.ingredients.clear()
        if self.project is None:
            return
        kind = self.ingredient_kind.value()
        for ing in self.project.ingredients:
            if ing.kind != kind:
                continue
            item = QListWidgetItem(f"{ing.name}\n{ing.role}")
            item.setData(Qt.ItemDataRole.UserRole, ing.id)
            item.setIcon(self._icon_for(ing.image, ing.kind))
            self.ingredients.addItem(item)

    def _icon_for(self, path: str, kind: str) -> QIcon:
        if path and Path(path).is_file():
            try:
                return QIcon(QPixmap.fromImage(imaging.load(path, 184)))
            except Exception:
                pass
        return icons.icon({"character": "users", "location": "pin", "object": "cube", "prop": "star",
                           "reference": "image"}.get(kind, "image"), self.accent, 64)

    def _ingredient(self) -> Ingredient | None:
        item = self.ingredients.currentItem()
        if item is None or self.project is None:
            return None
        return next((i for i in self.project.ingredients if i.id == item.data(Qt.ItemDataRole.UserRole)), None)

    def add_ingredient(self) -> None:
        if self.project is None:
            return
        ing = Ingredient(kind=self.ingredient_kind.value())
        dialog = IngredientDialog(self, ing)
        if dialog.exec() and dialog.name.text().strip():
            ing.kind, ing.name = str(dialog.kind.currentData()), dialog.name.text().strip()
            ing.role, ing.description = dialog.role.text().strip(), dialog.description.toPlainText().strip()
            self.project.ingredients.append(ing)
            self.ingredient_kind.set_value(ing.kind)
            self._show_ingredients()
            self._save_soon()

    def _edit_ingredient(self, _item: QListWidgetItem) -> None:
        ing = self._ingredient()
        if ing is None:
            return
        dialog = IngredientDialog(self, ing)
        if dialog.exec():
            ing.kind, ing.name = str(dialog.kind.currentData()), dialog.name.text().strip() or ing.name
            ing.role, ing.description = dialog.role.text().strip(), dialog.description.toPlainText().strip()
            self._show_ingredients()
            self._save_soon()

    def remove_ingredient(self) -> None:
        ing = self._ingredient()
        if ing is not None and self.project is not None:
            self.project.ingredients.remove(ing)
            self._show_ingredients()
            self._save_soon()

    def picture_ingredient(self) -> None:
        ing = self._ingredient()
        if ing is None or self.project is None:
            self.shell.toast("Choose an ingredient first.", "warn")
            return
        words = {"character": f"portrait of {ing.name}, {ing.role}, {ing.description}",
                 "location": f"{ing.name}, {ing.description}, wide establishing shot"}.get(
            ing.kind, f"{ing.name}, {ing.description}, product shot on a clean background")
        self._submit(best_image_engine(self.studio), {"prompt": words, "count": 1, "aspect": "square",
                                                      "project": self.project.library_project},
                     "ingredient_picture", {"film": self.project.id, "ingredient": ing.id})

    # ── sound ──
    def add_voice(self, text: str = "") -> None:
        if self.project is None:
            return
        dialog = VoiceDialog(self, text)
        if not dialog.exec() or not dialog.text.toPlainText().strip():
            return
        words = dialog.text.toPlainText().strip()
        self._submit("audio.narration", {"text": words, "voice": dialog.voice.currentData(), "speed": dialog.speed.value(),
                                         "title": f"Voice: {words[:40]}", "project": self.project.library_project},
                     "voice", {"film": self.project.id, "start": self.preview.t, "text": words,
                               "voice": dialog.voice.currentData()})

    def add_music(self) -> None:
        if self.project is None:
            return
        dialog = MusicDialog(self, max(10.0, self.project.length()))
        if not dialog.exec():
            return
        self._submit("audio.music", {"mood": dialog.mood.currentData(), "seconds": dialog.seconds.value(),
                                     "intensity": dialog.intensity.value(), "project": self.project.library_project},
                     "music", {"film": self.project.id, "start": 0.0})

    def add_effect(self, effect: str) -> None:
        if self.project is None:
            return
        self._submit("audio.sfx", {"effect": effect, "project": self.project.library_project}, "sfx",
                     {"film": self.project.id, "start": self.preview.t})

    def auto_captions(self) -> None:
        from eli_creation.production import captions

        if self.project is None:
            return
        cues = []
        for clip in self.project.clips:
            if clip.kind == "narration" and clip.text:
                cues += captions.cues_for(clip)
        self.project.cues = sorted(cues, key=lambda c: c.start)
        self.timeline.show_project(self.project)
        self.preview.seek(self.preview.t)
        self._save_soon()
        self.shell.toast(f"{len(cues)} captions, timed to the voice" if cues else "Add a voice first: captions follow it",
                         "good" if cues else "warn")

    def remove_clip(self) -> None:
        track, item_id = self.timeline.selected
        if self.project is None or track not in ("narration", "music", "sfx"):
            self.shell.toast("Select a sound on the timeline first.", "warn")
            return
        self.project.clips = [c for c in self.project.clips if c.id != item_id]
        self.timeline.selected = ("", "")
        self._sound_changed()

    def _sound_changed(self) -> None:
        self.sound.forget()
        self.timeline.show_project(self.project)
        self._update_time()
        self._save_soon()

    def _picked_on_timeline(self, track: str, item_id: str) -> None:
        if track == "video":
            for row in range(self.strip.count()):
                if self.strip.item(row).data(Qt.ItemDataRole.UserRole) == item_id:
                    self.strip.setCurrentRow(row)

    def _captions_toggled(self, on: bool) -> None:
        if self.project is not None and not self._loading:
            self.project.captions_on = on
            self.preview.seek(self.preview.t)
            self._save_soon()

    # ── playing ──
    def _soundtrack(self) -> Path | None:
        """The film's sound mixed into one file for the preview (made again when the sound changes)."""
        from eli_creation.production.audio import write_wav
        from eli_creation.production.render import soundtrack

        if self.project is None or not any(c.path for c in self.project.clips):
            return None
        key = hashlib.sha256(json.dumps([c.__dict__ for c in self.project.clips], sort_keys=True, default=str).encode()
                             + f"{self.project.length():.2f}{self.project.duck}".encode()).hexdigest()[:16]
        path = self.studio.layout.cache / "previews" / f"{self.project.id}-{key}.wav"
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            write_wav(path, soundtrack(self.project))
        return path

    def toggle_play(self) -> None:
        if self.preview.playing:
            self.stop()
            return
        track = self._soundtrack()
        if track is not None and self.sound.available and self.sound.play(track, self.preview.t):
            self.preview.play(source=self.sound.position)
        else:
            self.preview.play()
        self.play_button.setIcon(icons.icon("pause", design.TEXT, 22))

    def stop(self) -> None:
        self.preview.stop()
        self.sound.pause()
        self.play_button.setIcon(icons.icon("play", design.TEXT, 22))

    def seek(self, t: float) -> None:
        if self.preview.playing:
            self.stop()
        self.preview.seek(t)

    def _moved(self, t: float) -> None:
        self.timeline.set_time(t)
        self._update_time()
        if not self.preview.playing and self.sound.playing:
            self.sound.pause()
        if self.preview.playing is False:
            self.play_button.setIcon(icons.icon("play", design.TEXT, 22))

    def _update_time(self) -> None:
        length = self.project.length() if self.project else 0.0
        self.time_label.setText(f"{fmt_time(self.preview.t)} / {fmt_time(length)}")

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            self.toggle_play()
            return
        super().keyPressEvent(event)

    # ── ELI ──
    def eli_plan(self) -> None:
        if self.project is None:
            return
        if not self.studio.main.available:
            self.shell.toast(f"ELI needs the main model to plan: {self.studio.main.why_unavailable}", "warn")
            return
        logline = self.project.logline or self.project.title
        prompt = (f"Logline: {logline}\nGoal: {self.project.goal}\nLook: {self.project.direction}\n"
                  f"Format: {self.project.format}. Plan 4 to 7 scenes. For each: 'title' (2-4 words), 'picture' (a "
                  "concrete image prompt, at most 30 words), 'camera' (one of " + ", ".join(CAMERA) + "), 'seconds' "
                  "(2-8), 'words' (on-screen text, at most 6 words, or empty). Also 'narration' (spoken over it). "
                  'Answer as {"scenes": [...], "narration": "..."}')
        self.plan_eli.setEnabled(False)
        self.plan_eli.setText("ELI is planning…")

        def work() -> Any:
            from eli_creation.engines.writing import parse_json

            return parse_json(self.studio.main.generate(system=SCENES_SYSTEM, prompt=prompt, max_tokens=1600,
                                                        temperature=0.7, json_mode=True))

        self.shell.run_in_background(work, self._planned, lambda exc: self._planned(exc))

    def _planned(self, result: Any) -> None:
        self.plan_eli.setEnabled(True)
        self.plan_eli.setText("ELI: plan the scenes from the logline")
        if self.project is None or not isinstance(result, dict):
            self.shell.toast(f"ELI could not plan it: {result}", "warn")
            return
        scenes = []
        for raw in result.get("scenes") or []:
            if not isinstance(raw, dict):
                continue
            scenes.append(Scene(title=str(raw.get("title") or "Scene")[:40], description=str(raw.get("picture") or "")[:400],
                                camera=str(raw.get("camera")) if raw.get("camera") in CAMERA else "push_in",
                                seconds=max(2.0, min(10.0, float(raw.get("seconds") or 4))),
                                title_text=str(raw.get("words") or "")[:60]))
        if scenes:
            self.project.scenes = scenes
            self.strip.show_project(self.project)
            self.timeline.show_project(self.project)
            self.preview.seek(0.0)
            self._save_soon()
            self.shell.toast(f"ELI planned {len(scenes)} scenes. Picture them all with the spark beside the strip.",
                             "good")
        narration = str(result.get("narration") or "").strip()
        if narration:
            self.add_voice(narration)

    # ── export and jobs ──
    def export(self) -> None:
        if self.project is None:
            return
        if not self.project.scenes:
            self.shell.toast("Add a scene first.", "warn")
            return
        self._save_now()
        from eli_creation.production.render import multimedia

        ok, why = multimedia()
        if not ok:
            pictures = [s.image for s in self.project.scenes if s.image]
            if not pictures:
                self.shell.toast(f"The film cannot be written here ({why}), and no scene has a picture for an "
                                 "animatic.", "warn")
                return
            fmt = FORMATS.get(self.project.format, FORMATS["youtube"])
            shape = "square" if fmt.aspect == "square" else "story" if fmt.height > fmt.width else "wide"
            self._submit("videos.animatic", {"images": pictures, "aspect": shape, "title": self.project.title,
                                             "seconds": max(1.0, self.project.length() / len(pictures)),
                                             "project": self.project.library_project}, "export",
                         {"film": self.project.id})
            self.shell.toast(f"Writing an animatic (no sound) instead: {why}", "warn")
            return
        self._submit("videos.film", {"project_id": self.project.id, "project": self.project.library_project},
                     "export", {"film": self.project.id})
        self.status.setText("Writing the film…")

    def _submit(self, engine: str, request: dict[str, Any], purpose: str, details: dict[str, Any]) -> None:
        try:
            job = self.studio.submit(engine, request)
        except Exception as exc:
            self.shell.toast(str(exc), "warn")
            return
        self.jobs[job.id] = (purpose, details)

    def on_job(self, job: Job) -> None:
        if job.id not in self.jobs:
            return
        purpose, details = self.jobs[job.id]
        if purpose == "export" and not job.finished:
            self.status.setText(job.message or "Writing the film…")
        if not job.finished:
            return
        self.jobs.pop(job.id, None)
        if job.state != "done":
            if job.state == "failed":
                self.shell.toast(f"Film: {job.error}", "bad")
            self.status.setText("")
            return
        film = self.project if self.project is not None and self.project.id == details.get("film") else None
        if purpose == "scene_picture" and job.assets and film is not None:
            self._set_picture(str(job.assets[0].path), str(details["scene"]))
        elif purpose == "ingredient_picture" and job.assets and film is not None:
            ing = next((i for i in film.ingredients if i.id == details["ingredient"]), None)
            if ing is not None:
                ing.image = str(job.assets[0].path)
                self._show_ingredients()
                self._save_soon()
        elif purpose in ("voice", "music", "sfx") and job.assets and film is not None:
            from eli_creation.production import captions
            from eli_creation.production.audio import duration

            path = Path(job.assets[0].path)
            clip = Clip(kind={"voice": "narration"}.get(purpose, purpose), path=str(path),
                        start=round(float(details.get("start", 0.0)), 2), duration=duration(path),
                        text=str(details.get("text", "")), voice=str(details.get("voice", "")),
                        label=job.assets[0].title, gain=0.75 if purpose == "music" else 1.0,
                        fade_out=1.5 if purpose == "music" else 0.0)
            film.clips.append(clip)
            if purpose == "voice" and film.captions_on:
                film.cues = sorted(film.cues + captions.cues_for(clip), key=lambda c: c.start)
            self._sound_changed()
            self.shell.toast(f"{clip.label} is on the timeline", "good")
        elif purpose == "export" and job.assets:
            video = job.assets[-1]
            self.status.setText("")
            codec = json.loads(job.text or "{}").get("codec", "") if job.engine == "videos.film" else "animatic"
            tile = Tile.from_asset(video)
            name = {"H264": "H.264", "MPEG4": "MPEG-4", "animatic": "an animatic"}.get(codec, codec)
            self.shell.toast(f"The film is written ({name})", "good",
                             action=("Watch", lambda: open_lightbox(self.shell, [tile], tile)))
        elif purpose == "ad":
            made = json.loads(job.text or "{}").get("film", "")
            self._list(made)
            videos = [a for a in job.assets if a.kind == "video"]
            if videos:
                tile = Tile.from_asset(videos[-1])
                self.shell.toast("The ad is made: it is open here to change, and written as an MP4", "good",
                                 action=("Watch", lambda: open_lightbox(self.shell, [tile], tile)))

    def shown(self, **wanted: Any) -> None:
        sent = wanted.get("sound")
        if sent:
            self._take_sound(dict(sent))
        if wanted.get("ad"):
            self.new_ad(wanted["ad"] if isinstance(wanted["ad"], dict) else None)
        if wanted.get("template"):
            self.new_from_template()
        if wanted.get("add") and self.project is not None:
            for path in wanted["add"]:
                self.project.scenes.append(Scene(title=Path(str(path)).stem[:30], image=str(path)))
            self.strip.show_project(self.project)
            self.timeline.show_project(self.project)
            self._save_soon()
            self.shell.toast(f"Added {len(wanted['add'])} scene(s)", "good")
        elif wanted.get("add"):
            project = Project(title=self.shell.project_name() or "New film",
                              scenes=[Scene(title=Path(str(p)).stem[:30], image=str(p)) for p in wanted["add"]])
            self._new(project)
        if wanted.get("format"):
            self.new_blank(str(wanted["format"]))

    def _take_sound(self, sent: dict[str, Any]) -> None:
        from eli_creation.production.audio import duration

        path = Path(str(sent.get("path", "")))
        if not path.is_file():
            return
        if self.project is None:
            self.new_blank()
        if self.project is None:
            return
        kind = str(sent.get("kind") or "music")
        start = 0.0 if kind == "music" else round(self.preview.t, 2)
        self.project.clips.append(Clip(kind=kind if kind in ("narration", "music", "sfx") else "music", path=str(path),
                                       start=start, duration=duration(path), label=str(sent.get("title") or path.stem),
                                       gain=0.75 if kind == "music" else 1.0, fade_out=1.5 if kind == "music" else 0.0))
        self._sound_changed()
        self.shell.toast(f"{sent.get('title') or path.stem} is on the timeline of “{self.project.title}”", "good")

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        self.stop()
        self._save_now()
        super().hideEvent(event)
