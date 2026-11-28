"""Audio: voices, music and effects, made on this machine, heard here, and sent to a film.

- **Voice**: words spoken by ELI v3's voices, Piper's or this computer's own; ELI can write the
  script from a brief with the main model.
- **Music**: a piece composed here for a mood, a length, a tempo and a key, with the instruments
  chosen: no samples, no loops, nothing of anyone else's.
- **Effects**: whooshes, risers, impacts and shimmers, synthesised here.
- **Captions**: a recording's words, heard by ELI v3's ears, written as captions.

Everything made is in the list beside it, with its waveform: play it, send it to the Film studio,
or open its folder.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from eli_creation.gui import components as ui
from eli_creation.gui import design, icons
from eli_creation.gui.film_widgets import fmt_time
from eli_creation.gui.pages.base import Page
from eli_creation.gui.pages.film import voice_box
from eli_creation.gui.sound import shared
from eli_creation.production import music as music_lib
from eli_creation.production import sfx as sfx_lib

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.jobs import Job
    from eli_creation.library import Asset

SCRIPT_SYSTEM = ("You are ELI, a script writer for voice-overs. Write words to be spoken aloud: short sentences, "
                 "natural rhythm, no stage directions, no headings, no quotation marks.")


class Wave(QWidget):
    """A recording's shape, with how far it has played."""

    def __init__(self, path: Path, colour: str) -> None:
        super().__init__()
        from eli_creation.production.audio import peaks

        self.colour = colour
        self.played = 0.0
        try:
            self.peaks = peaks(path, 160)
        except Exception:
            self.peaks = []
        self.setMinimumHeight(34)
        self.setMinimumWidth(160)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 3, -1, -3)
        mid = r.center().y()
        if not self.peaks:
            p.setPen(QPen(QColor(design.LINE_STRONG), 1))
            p.drawLine(QPointF(r.left(), mid), QPointF(r.right(), mid))
            p.end()
            return
        step = r.width() / len(self.peaks)
        for i, value in enumerate(self.peaks):
            x = r.left() + i * step
            played = (i / len(self.peaks)) < self.played
            p.setPen(QPen(QColor(self.colour) if played else design.alpha_q(self.colour, 0.38), max(1.0, step * 0.6)))
            h = max(1.0, value * r.height() / 2)
            p.drawLine(QPointF(x, mid - h), QPointF(x, mid + h))
        p.end()


class SoundRow(QFrame):
    """One sound in the list: play, its name and shape, its length, and what to do with it."""

    def __init__(self, page: AudioPage, asset: Asset) -> None:
        super().__init__()
        from eli_creation.production.audio import duration

        self.page = page
        self.asset = asset
        self.setProperty("card", "soft")
        kind = page.kind_of(asset)
        colour = {"narration": design.BRAND_A, "music": "#a78bfa", "sfx": "#facc15"}.get(kind, design.MUTED)
        self.seconds = duration(asset.path) if asset.path.is_file() else 0.0
        self.play = ui.icon_button("play", "Play", self.toggle, size=18, colour=colour)
        self.wave = Wave(asset.path, colour)
        name = ui.text(asset.title, "small")
        name.setMaximumWidth(360)
        meta = ui.text(f"{ {'narration': 'Voice', 'music': 'Music', 'sfx': 'Effect'}.get(kind, 'Sound')} · "
                       f"{fmt_time(self.seconds)[:5]}", "tiny", tone="muted")
        words = QVBoxLayout()
        words.setSpacing(2)
        words.addWidget(name)
        words.addWidget(meta)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(10)
        row.addWidget(self.play)
        row.addLayout(words)
        row.addWidget(self.wave, 1)
        row.addWidget(ui.icon_button("film", "Put it in the open film, at the playhead", self.to_film))
        row.addWidget(ui.icon_button("folder", "Show it in its folder", self.reveal))

    def toggle(self) -> None:
        self.page.toggle(self)

    def set_playing(self, playing: bool) -> None:
        self.play.setIcon(icons.icon("pause" if playing else "play", design.TEXT, 18))

    def to_film(self) -> None:
        self.page.shell.go("videos", sound={"path": str(self.asset.path), "kind": self.page.kind_of(self.asset),
                                            "title": self.asset.title})

    def reveal(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.asset.path.parent)))


class AudioPage(Page):
    key = "audio"

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.jobs: dict[str, str] = {}  # job id: what to do when it is done ("play" or "")
        self.rows: list[SoundRow] = []
        self.playing: SoundRow | None = None
        self.sound = shared()
        self.sound.moved.connect(self._moved)
        self.sound.playing_changed.connect(self._playing_changed)

        self.mode = ui.Segmented([("Voice", "voice"), ("Music", "music"), ("Effects", "sfx"), ("Captions", "captions")],
                                 "voice", accent=self.accent)
        self.mode.changed.connect(self._mode)
        self.stack = QStackedWidget()
        self.panels = {"voice": self._voice_panel(), "music": self._music_panel(), "sfx": self._sfx_panel(),
                       "captions": self._captions_panel()}
        for panel in self.panels.values():
            self.stack.addWidget(panel)
        left = ui.Card(padding=18, spacing=12)
        left.add(self.mode, self.stack)
        left.setMinimumWidth(460)

        self.filter = ui.Segmented([("All", ""), ("Voices", "narration"), ("Music", "music"), ("Effects", "sfx")], "",
                                   accent=self.accent)
        self.filter.changed.connect(lambda _k: self.refresh())
        self.list = QListWidget()
        self.list.setSpacing(4)
        self.list.setStyleSheet("QListWidget { background: transparent; border: none; }")
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.empty = ui.EmptyState("music", "Nothing to hear yet",
                                   "Speak some words, compose a piece or make an effect: it appears here with its "
                                   "waveform, ready to play or to put in a film.", accent=self.accent)
        right = ui.Card(padding=16, spacing=10)
        head = QHBoxLayout()
        head.addWidget(ui.text("Your sounds", "h3"))
        head.addStretch(1)
        head.addWidget(self.filter)
        right.add(head, self.list, self.empty)
        if not self.sound.available:
            right.add(ui.text(f"Playing sound here needs Qt Multimedia: {self.sound.why}", "tiny", tone="warn", wrap=True))

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(left, 5)
        body.addWidget(right, 6)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 20, 26, 18)
        lay.setSpacing(14)
        lay.addLayout(self.header("Audio", "Voices, music and effects, made on this machine and yours to use: "
                                           "no samples, no loops, nothing of anyone else's."))
        lay.addLayout(body, 1)
        self.refresh()

    # ── the panels ──
    def _voice_panel(self) -> QWidget:
        self.script = QPlainTextEdit()
        self.script.setPlaceholderText("What should be said. Or write a brief (“a 20-second voice-over for a coffee "
                                       "launch, warm and confident”) and let ELI write it.")
        self.script.setMinimumHeight(170)
        self.voice = voice_box()
        self.speed = ui.SliderField("Speed", 0.7, 1.4, 1.0, step=0.05, fmt="×{:.2f}", icon="clock")
        self.voices_note = ui.text("", "tiny", tone="muted", wrap=True)
        self.write_button = ui.button("ELI: write it from the brief", self.write_script, icon="sparkles")
        self.speak_button = ui.GlowButton("Speak", "mic", accent=self.accent)
        self.speak_button.clicked.connect(self.speak)
        voices = QHBoxLayout()
        voices.addWidget(self.voice, 1)
        voices.addWidget(ui.icon_button("refresh", "Look for voices again", self._refresh_voices))
        voices.addWidget(ui.icon_button("play", "Hear a sample of this voice", self.sample))
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(ui.Field("Words", self.script))
        lay.addWidget(self.write_button)
        lay.addWidget(ui.Field("Voice", voices))
        lay.addWidget(self.voices_note)
        lay.addWidget(self.speed)
        lay.addStretch(1)
        lay.addWidget(self.speak_button)
        self._voices_note()
        return panel

    def _music_panel(self) -> QWidget:
        self.mood = ui.ChipGroup([(m.name, k) for k, m in music_lib.MOODS.items()], chosen=("cinematic",),
                                 accent=self.accent)
        self.mood_note = ui.text("", "small", tone="muted", wrap=True)
        self.mood.changed.connect(self._mood_changed)
        self.length = ui.SliderField("Length", 5, 300, 30, step=1, fmt="{:.0f} s", icon="clock")
        self.tempo = ui.SliderField("Tempo (0: the mood's own)", 0, 180, 0, step=2, fmt="{:.0f} bpm")
        self.music_key = QComboBox()
        for note in music_lib.NOTES:
            self.music_key.addItem(note, note)
        self.intensity = ui.SliderField("Intensity", 0.2, 1.0, 0.7, step=0.05, fmt="{:.2f}")
        self.seed = ui.Stepper(1, 9999, 7)
        self.parts = {name: ui.Switch(label_text, True) for name, label_text in
                      (("pad", "Pads"), ("pluck", "Melody"), ("bass", "Bass"), ("drums", "Drums"))}
        parts = QHBoxLayout()
        for switch in self.parts.values():
            parts.addWidget(switch)
        parts.addStretch(1)
        seed_row = QHBoxLayout()
        seed_row.addWidget(self.seed)
        seed_row.addWidget(ui.icon_button("dice", "Another variation", self._dice))
        seed_row.addStretch(1)
        self.compose_button = ui.GlowButton("Compose", "music", accent=self.accent)
        self.compose_button.clicked.connect(self.compose)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(ui.Field("Mood", self.mood))
        lay.addWidget(self.mood_note)
        lay.addWidget(self.length)
        lay.addWidget(self.tempo)
        lay.addWidget(self.intensity)
        grid = QGridLayout()
        grid.addWidget(ui.Field("Key", self.music_key), 0, 0)
        grid.addWidget(ui.Field("Variation", seed_row), 0, 1)
        lay.addLayout(grid)
        lay.addWidget(ui.Field("Instruments", parts))
        lay.addStretch(1)
        lay.addWidget(self.compose_button)
        self._mood_changed()
        return panel

    def _sfx_panel(self) -> QWidget:
        grid = QGridLayout()
        grid.setSpacing(10)
        for n, (key, (name, _seconds, _fn, blurb)) in enumerate(sfx_lib.EFFECTS.items()):
            card = ui.Card(soft=True, padding=12, spacing=4)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.add(ui.text(name, "body"), ui.text(blurb, "tiny", tone="muted", wrap=True))
            card.mousePressEvent = partial(self._effect_clicked, key)  # type: ignore[method-assign]
            card.setToolTip(f"Make a {name.lower()} and hear it")
            grid.addWidget(card, n // 3, n % 3)
        self.sfx_length = ui.SliderField("Length (0: the effect's own)", 0, 8, 0, step=0.1, fmt="{:.1f} s")
        self.sfx_seed = ui.Stepper(1, 999, 3)
        seed_row = QHBoxLayout()
        seed_row.addWidget(ui.text("Variation", "small", tone="subtle"))
        seed_row.addWidget(self.sfx_seed)
        seed_row.addStretch(1)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(ui.text("Choose one: it is made here and plays when it is ready.", "small", tone="muted"))
        lay.addLayout(grid)
        lay.addWidget(self.sfx_length)
        lay.addLayout(seed_row)
        lay.addStretch(1)
        return panel

    def _captions_panel(self) -> QWidget:
        self.recording = ""
        self.recording_label = ui.text("No recording chosen", "small", tone="muted", wrap=True)
        self.heard = QPlainTextEdit()
        self.heard.setReadOnly(True)
        self.heard.setPlaceholderText("What ELI heard appears here, and as captions (.srt) in the library.")
        self.ears = ui.text("", "tiny", tone="muted", wrap=True)
        self.hear_button = ui.GlowButton("Hear it", "captions", accent=self.accent)
        self.hear_button.clicked.connect(self.hear)
        choose = QHBoxLayout()
        choose.addWidget(ui.button("Choose a recording…", self._choose_recording, icon="upload"))
        choose.addWidget(ui.button("Use the selected sound", self._use_selected, icon="music", variant="flat"))
        choose.addStretch(1)
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(ui.text("A recording's words, heard by ELI v3's own ears (Whisper, on this machine), timed as "
                              "captions.", "small", tone="muted", wrap=True))
        lay.addLayout(choose)
        lay.addWidget(self.recording_label)
        lay.addWidget(self.ears)
        lay.addWidget(self.heard, 1)
        lay.addWidget(self.hear_button)
        return panel

    # ── what the panels do ──
    def _mode(self, key: str) -> None:
        self.stack.setCurrentWidget(self.panels[key])
        if key == "captions":
            self._ears()

    def _voices_note(self) -> None:
        from eli_creation.production import speech

        found = speech.voices()
        counts = {source: sum(1 for v in found if v.source == source) for source in ("eli", "piper", "system")}
        parts = [f"{counts['eli']} from ELI v3" if counts["eli"] else "ELI v3's voices when it runs",
                 f"{counts['piper']} Piper" if counts["piper"] else "",
                 f"{counts['system']} of this computer's" if counts["system"] else ""]
        self.voices_note.setText("Voices: " + ", ".join(p for p in parts if p) + ". A voice's licence travels with "
                                 "what it says, in the file's provenance.")

    def _refresh_voices(self) -> None:
        from eli_creation.production import speech

        speech.voices(fresh=True)
        chosen = self.voice.currentData()
        fresh = voice_box(str(chosen or ""))
        self.voice.clear()
        for i in range(fresh.count()):
            self.voice.addItem(fresh.itemText(i), fresh.itemData(i))
        self.voice.setCurrentIndex(max(0, self.voice.findData(chosen)))
        self._voices_note()

    def _mood_changed(self) -> None:
        mood = music_lib.MOODS.get(self.mood.value(), music_lib.MOODS["cinematic"])
        self.mood_note.setText(f"{mood.blurb} · {mood.tempo} bpm · {mood.scale}")

    def _dice(self) -> None:
        import random

        self.seed.set_value(random.randint(1, 9999))

    def _ears(self) -> None:
        from eli_creation import eli_link

        here = eli_link.find() is not None
        self.ears.setText("ELI v3 is running: its ears are ready." if here else
                          "Start ELI v3 on this machine: it does the listening (its speech model loads for this and "
                          "unloads after).")
        self.hear_button.setEnabled(here)

    def _submit(self, engine: str, request: dict[str, Any], then: str = "") -> None:
        request.setdefault("project", self.shell.project_name())
        try:
            job = self.studio.submit(engine, request)
        except Exception as exc:
            self.shell.toast(str(exc), "warn")
            return
        self.jobs[job.id] = then

    def speak(self) -> None:
        words = self.script.toPlainText().strip()
        if not words:
            self.shell.toast("Write what should be said first.", "warn")
            return
        if not self.voice.currentData():
            self.shell.toast("No voice on this computer yet: start ELI v3, or install Piper or eSpeak NG.", "warn")
            return
        self._submit("audio.narration", {"text": words, "voice": self.voice.currentData(), "speed": self.speed.value(),
                                         "title": f"Voice: {words[:48]}"}, "play")
        self.speak_button.set_busy(True)

    def sample(self) -> None:
        if self.voice.currentData():
            self._submit("audio.narration", {"text": "Hello. This is how I sound, reading your words.",
                                             "voice": self.voice.currentData(), "speed": self.speed.value(),
                                             "title": f"Sample: {self.voice.currentText()}"}, "play")

    def write_script(self) -> None:
        brief = self.script.toPlainText().strip()
        if not brief:
            self.shell.toast("Write a brief first: what it is for, how long, how it should feel.", "warn")
            return
        if not self.studio.main.available:
            self.shell.toast(f"ELI needs the main model to write: {self.studio.main.why_unavailable}", "warn")
            return
        self.write_button.setEnabled(False)
        self.write_button.setText("ELI is writing…")

        def work() -> str:
            return self.studio.main.generate(system=SCRIPT_SYSTEM, prompt=f"Brief: {brief}\n\nWrite the voice-over.",
                                             max_tokens=700, temperature=0.7)

        self.shell.run_in_background(work, self._written, self._written)

    def _written(self, result: Any) -> None:
        self.write_button.setEnabled(True)
        self.write_button.setText("ELI: write it from the brief")
        if isinstance(result, Exception):
            self.shell.toast(f"ELI could not write it: {result}", "warn")
            return
        self.script.setPlainText(str(result).strip().strip('"'))

    def compose(self) -> None:
        self._submit("audio.music", {
            "mood": self.mood.value(), "seconds": self.length.value(), "tempo": int(self.tempo.value()),
            "key": self.music_key.currentData(), "intensity": self.intensity.value(), "seed": self.seed.value(),
            "instruments": {k: s.isChecked() for k, s in self.parts.items()}}, "play")
        self.compose_button.set_busy(True)

    def _effect_clicked(self, key: str, _event: object) -> None:
        self.effect(key)

    def effect(self, key: str) -> None:
        self._submit("audio.sfx", {"effect": key, "seconds": self.sfx_length.value(), "seed": self.sfx_seed.value()},
                     "play")

    def _choose_recording(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "A recording", "", "WAV recordings (*.wav)")
        if path:
            self.recording = path
            self.recording_label.setText(Path(path).name)

    def _use_selected(self) -> None:
        row = self.playing or (self.rows[0] if self.rows else None)
        if row is not None:
            self.recording = str(row.asset.path)
            self.recording_label.setText(row.asset.title)

    def hear(self) -> None:
        if not self.recording:
            self.shell.toast("Choose a recording first.", "warn")
            return
        self._submit("audio.captions", {"path": self.recording})
        self.hear_button.set_busy(True)

    # ── the list ──
    def kind_of(self, asset: Asset) -> str:
        return {"audio.narration": "narration", "audio.music": "music", "audio.sfx": "sfx"}.get(asset.engine, "music")

    def refresh(self) -> None:
        self.sound.stop() if self.playing is not None else None
        self.playing = None
        self.list.clear()
        self.rows = []
        wanted = self.filter.value()
        for asset in self.studio.library.recent(kind="audio", limit=80):
            if not asset.path.is_file() or (wanted and self.kind_of(asset) != wanted):
                continue
            row = SoundRow(self, asset)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 62))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self.rows.append(row)
        self.list.setVisible(bool(self.rows))
        self.empty.setVisible(not self.rows)

    def toggle(self, row: SoundRow) -> None:
        if self.playing is row and self.sound.playing:
            self.sound.pause()
            return
        if self.playing is not None and self.playing is not row:
            self.playing.set_playing(False)
            self.playing.wave.played = 0.0
            self.playing.wave.update()
            self.sound.stop()
        self.playing = row
        start = self.sound.position() if self.sound.path == str(row.asset.path) else 0.0
        if not self.sound.play(row.asset.path, start if start < row.seconds - 0.05 else 0.0):
            self.shell.toast(f"It cannot play here: {self.sound.why or 'the file is missing'}", "warn")

    def _moved(self, seconds: float) -> None:
        row = self.playing
        if row is not None and self.sound.path == str(row.asset.path) and row.seconds:
            row.wave.played = min(1.0, seconds / row.seconds)
            row.wave.update()

    def _playing_changed(self, playing: bool) -> None:
        if self.playing is not None and self.sound.path == str(self.playing.asset.path):
            self.playing.set_playing(playing)

    def on_job(self, job: Job) -> None:
        if job.id not in self.jobs or not job.finished:
            return
        then = self.jobs.pop(job.id)
        for button in (self.speak_button, self.compose_button, self.hear_button):
            button.set_busy(False)
        if job.state != "done":
            if job.state == "failed":
                self.shell.toast(f"Audio: {job.error}", "bad")
            return
        if job.engine == "audio.captions":
            self.heard.setPlainText(job.text or "")
            self.shell.toast("Heard: the captions are in the library", "good")
            return
        self.refresh()
        if then == "play" and self.rows and job.assets:
            made = str(job.assets[0].path)
            row = next((r for r in self.rows if str(r.asset.path) == made), None)
            if row is not None:
                self.toggle(row)

    def shown(self, **wanted: Any) -> None:
        if wanted.get("mode") in self.panels:
            self.mode.set_value(str(wanted["mode"]))
            self._mode(str(wanted["mode"]))
        if wanted.get("mood") in music_lib.MOODS:
            self.mood.set_value(str(wanted["mood"]))
        if wanted.get("seconds"):
            try:
                self.length.set_value(float(wanted["seconds"]))
            except ValueError:
                pass
        if wanted.get("text"):
            self.mode.set_value("voice")
            self._mode("voice")
            self.script.setPlainText(str(wanted["text"]))
        self.refresh()

    def hideEvent(self, event: Any) -> None:  # noqa: N802
        if self.playing is not None:
            self.sound.pause()
        super().hideEvent(event)

