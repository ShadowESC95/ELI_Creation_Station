"""Settings: this machine, the main model, how specialists load, the models, ELI, the licence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from eli_creation import PRODUCT, TITLE, __version__
from eli_creation.gui import theme
from eli_creation.gui.studio_tab import Bridge
from eli_creation.gui.widgets import button, card, label, row, table
from eli_creation.tiers import TIER_EXAMPLES, TIER_LABELS

if TYPE_CHECKING:
    from eli_creation.services import Studio


class SettingsTab(QWidget):
    def __init__(self, studio: Studio, bridge: Bridge) -> None:
        super().__init__()
        self.studio = studio
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.addWidget(label("Settings", "title"))
        lay.addWidget(self._machine())
        lay.addWidget(self._main_model())
        lay.addWidget(self._loading())
        lay.addWidget(self._models())
        lay.addWidget(self._eli())
        lay.addWidget(self._output())
        lay.addWidget(self._about())
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        bridge.models_changed.connect(self.refresh_models)

    # ── this machine ──────────────────────────────────────────────────────
    def _machine(self):
        m = self.studio.machine
        lines = [f"<b>Tier {m.tier}: {TIER_LABELS[m.tier]}</b> (machines like it: {TIER_EXAMPLES[m.tier]})",
                 f"{m.os}, {m.arch}, {m.cpu_threads} processor threads, {m.ram_mb / 1024:.0f} GB memory",
                 "Graphics: " + ("; ".join(a.describe() for a in m.accelerators) or "none that can be used"),
                 "Runs on: " + ", ".join(m.backends),
                 f"Read through {'ELI v3' if m.source == 'eli_v3' else 'ELI’s own probes'}."]
        return card("This machine", label("<br>".join(lines), wrap=True, selectable=True))

    # ── the main model ────────────────────────────────────────────────────
    def _main_model(self):
        s = self.studio.settings
        self.source = QComboBox()
        for text, data in (("Automatic", "auto"), ("ELI v3's model (when opened from ELI v3)", "eli_v3"),
                           ("A GGUF file", "gguf"), ("A model server", "openai"), ("None", "none")):
            self.source.addItem(text, data)
        self.source.setCurrentIndex(max(0, self.source.findData(s.main_model_source)))
        self.path = QLineEdit(s.main_model_path)
        browse = button("Choose…", self._choose_gguf)
        self.url = QLineEdit(s.main_model_url)
        self.model_name = QLineEdit(s.main_model_name)
        self.licence = QLineEdit(s.main_model_licence)
        self.licence.setPlaceholderText("Apache-2.0, MIT… as the model's card states it")
        self.context = QSpinBox()
        self.context.setRange(2048, 262144)
        self.context.setSingleStep(1024)
        self.context.setValue(s.main_context)
        self.remote = QCheckBox("Allow a model server on another machine (prompts would leave this machine)")
        self.remote.setChecked(s.allow_remote_main_model)
        state = label(f"Now: {self.studio.main.name} ({self.studio.main.state})"
                      + ("" if self.studio.main.available else f": {self.studio.main.why_unavailable}"), "muted", wrap=True)
        form = QWidget()
        f = QFormLayout(form)
        f.addRow("Main model", self.source)
        f.addRow("GGUF file", row(self.path, browse, stretch_last=False))
        f.addRow("Server address", self.url)
        f.addRow("Server's model name", self.model_name)
        f.addRow("Its licence", self.licence)
        f.addRow("Context (tokens)", self.context)
        f.addRow("", self.remote)
        f.addRow("", state)
        f.addRow("", button("Apply (takes effect at the next start)", self._apply_main))
        return card("Main model: the one that stays loaded", form)

    def _choose_gguf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Main model", "", "GGUF models (*.gguf)")
        if path:
            self.path.setText(path)
            self.source.setCurrentIndex(self.source.findData("gguf"))

    def _apply_main(self) -> None:
        s = self.studio.settings
        s.main_model_source = str(self.source.currentData())
        s.main_model_path, s.main_model_url = self.path.text().strip(), self.url.text().strip()
        s.main_model_name, s.main_model_licence = self.model_name.text().strip(), self.licence.text().strip()
        s.main_context, s.allow_remote_main_model = self.context.value(), self.remote.isChecked()
        self.studio.save_settings()
        QMessageBox.information(self, TITLE, "Saved. The main model changes at the next start.")

    # ── loading specialists ───────────────────────────────────────────────
    def _loading(self):
        s = self.studio.settings
        self.idle = QSpinBox()
        self.idle.setRange(0, 3600)
        self.idle.setSuffix(" s")
        self.idle.setValue(s.idle_unload_seconds)
        self.most = QSpinBox()
        self.most.setRange(0, 8)
        self.most.setSpecialValueText("by this machine's tier")
        self.most.setValue(s.max_resident_specialists)
        self.swap = QCheckBox("Let the main model step aside for a job that cannot fit beside it "
                              "(it is loaded again straight after)")
        self.swap.setChecked(s.allow_main_swap)
        form = QWidget()
        f = QFormLayout(form)
        f.addRow("Unload a specialist after it is idle for", self.idle)
        f.addRow("Specialists loaded at once", self.most)
        f.addRow("", self.swap)
        f.addRow("", button("Apply", self._apply_loading))
        return card("Loading: only the main model stays loaded", label(
            "Image, video, music and other specialist models load in a process of their own when a job "
            "needs them, and are unloaded when idle, which gives all their memory back.", "muted", wrap=True), form)

    def _apply_loading(self) -> None:
        s = self.studio.settings
        s.idle_unload_seconds, s.max_resident_specialists = self.idle.value(), self.most.value()
        s.allow_main_swap = self.swap.isChecked()
        self.studio.save_settings()

    # ── the models ────────────────────────────────────────────────────────
    def _models(self):
        self.models_table = table(["Model", "For", "Licence", "Size", "Here", "Now"], stretch=4)
        self.refresh_models()
        folder = button("Open the models folder", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.studio.layout.models))))
        unload = button("Unload idle specialists now", lambda: self.studio.manager.unload_idle(now=float("inf")))
        return card("Models", self.models_table, row(folder, unload))

    def refresh_models(self) -> None:
        states = {s.id: s for s in self.studio.manager.status()}
        rows = [spec for spec in self.studio.catalogue.models if spec.role == "specialist"]
        self.models_table.setRowCount(len(rows))
        for r, spec in enumerate(rows):
            ok, why = spec.runs_here(self.studio.machine)
            here = "planned" if spec.planned else ("yes" + (" (slowly)" if why else "") if ok else why)
            st = states.get(spec.id)
            now = st.state if st else "unloaded"
            for c, text in enumerate((spec.title, ", ".join(spec.tasks), f"{spec.licence} ({spec.licence_class})",
                                      f"{spec.size_mb / 1024:.1f} GB", here, now)):
                item = QTableWidgetItem(text)
                if c == 5:
                    item.setForeground(QColor(theme.colour_for(now)))
                self.models_table.setItem(r, c, item)

    # ── ELI ───────────────────────────────────────────────────────────────
    def _eli(self):
        s = self.studio.settings
        self.level = QComboBox()
        for text, data in (("Off: says nothing unasked", "off"), ("Quiet: keeps notes for when you look", "quiet"),
                           ("Helpful: offers an insight now and then", "helpful"),
                           ("Active: also asks to pause and talk the project through", "active")):
            self.level.addItem(text, data)
        self.level.setCurrentIndex(max(0, self.level.findData(s.companion_level)))
        self.watch = QCheckBox("Follow the project's folder (what changed in it)")
        self.watch.setChecked(s.companion_watch_project)
        self.read_screen_box = QCheckBox("Read the screen when ELI looks (on this machine only, never kept)")
        self.read_screen_box.setChecked(s.companion_read_screen)
        self.gap = QSpinBox()
        self.gap.setRange(1, 240)
        self.gap.setSuffix(" min")
        self.gap.setValue(s.companion_min_gap_minutes)
        form = QWidget()
        f = QFormLayout(form)
        f.addRow("ELI", self.level)
        f.addRow("", self.watch)
        f.addRow("", self.read_screen_box)
        f.addRow("At most one thing unasked every", self.gap)
        f.addRow("", button("Apply", self._apply_eli))
        return card("ELI in the studio", form)

    def _apply_eli(self) -> None:
        s = self.studio.settings
        s.companion_level = str(self.level.currentData())
        s.companion_watch_project, s.companion_read_screen = self.watch.isChecked(), self.read_screen_box.isChecked()
        s.companion_min_gap_minutes = self.gap.value()
        self.studio.save_settings()

    # ── outputs, licence, about ───────────────────────────────────────────
    def _output(self):
        self.label_box = QCheckBox("Add a visible 'AI-generated' note to what is made (the machine-readable "
                                   "marking is always written)")
        self.label_box.setChecked(self.studio.settings.visible_ai_label)
        self.label_box.toggled.connect(self._apply_label)
        outputs = button("Open the outputs folder", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.studio.layout.outputs))))
        ok, why = self.studio.ledger.verify()
        ledger = label(f"Provenance ledger: {self.studio.ledger.count()} entries, "
                       f"{'whole' if ok else 'BROKEN: ' + why}", "muted")
        return card("Outputs and provenance", self.label_box, outputs, ledger)

    def _apply_label(self, on: bool) -> None:
        self.studio.settings.visible_ai_label = on
        self.studio.save_settings()

    def _about(self):
        where = "opened by ELI v3" if self.studio.hosted else "on its own"
        return card("About", label(f"{TITLE} {__version__} · bundle id <code>{PRODUCT}</code> · {where}<br>"
                                   f"Data: {self.studio.layout.root}", wrap=True, selectable=True))
