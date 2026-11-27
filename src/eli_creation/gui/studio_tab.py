"""What every creative tab shares: its engines (greyed with the reason where this machine or this
moment cannot run one), a form, a Create button, progress, and the results."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from eli_creation.engines import registry
from eli_creation.gui import theme
from eli_creation.gui.widgets import button, label

if TYPE_CHECKING:
    from eli_creation.jobs import Job
    from eli_creation.services import Studio

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


class Bridge(QObject):
    """Carries job and model news from worker threads to the window's thread."""

    job_changed = Signal(object)
    models_changed = Signal()


class StudioTab(QWidget):
    key = ""
    heading = ""
    blurb = ""

    def __init__(self, studio: Studio, bridge: Bridge, project: Any) -> None:
        super().__init__()
        self.studio, self.bridge, self.project = studio, bridge, project
        self.engines = registry.for_tab(self.key)
        self.job: Job | None = None

        outer = QVBoxLayout(self)
        outer.addWidget(label(self.heading, "title"))
        outer.addWidget(label(self.blurb, "muted", wrap=True))

        top = QHBoxLayout()
        self.engine = QComboBox()
        for engine in self.engines:
            self.engine.addItem(engine.title + ("  (planned)" if engine.planned else ""), engine.id)
        self.engine.currentIndexChanged.connect(self.refresh)
        top.addWidget(QLabel("Engine"))
        top.addWidget(self.engine, 1)
        outer.addLayout(top)
        self.needs = label("", "muted", wrap=True)
        outer.addWidget(self.needs)

        split = QSplitter(Qt.Orientation.Horizontal)
        form_box = QWidget()
        self.form = QFormLayout(form_box)
        self.build_form(self.form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_box)
        split.addWidget(scroll)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.results = QListWidget()
        self.results.setIconSize(QSize(160, 160))
        self.results.itemDoubleClicked.connect(self._open)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("What was made appears here. Double-click a result to open it.")
        rl.addWidget(self.results, 2)
        rl.addWidget(self.output, 1)
        split.addWidget(right)
        split.setSizes([420, 560])
        outer.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.create_button = button("Create", self.submit, kind="primary")
        self.cancel_button = button("Cancel", self.cancel)
        self.cancel_button.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status = label("", "muted")
        bottom.addWidget(self.create_button)
        bottom.addWidget(self.cancel_button)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.status, 2)
        outer.addLayout(bottom)

        bridge.job_changed.connect(self.on_job)
        bridge.models_changed.connect(self.refresh)
        # open on the first engine this machine can run now (the best one, where several can)
        for index, engine in enumerate(self.engines):
            if engine.availability(self.studio).ok:
                self.engine.setCurrentIndex(index)
                break
        self.refresh()

    # ── for each tab to fill in ───────────────────────────────────────────
    def build_form(self, form: QFormLayout) -> None:
        raise NotImplementedError

    def request(self) -> dict[str, Any]:
        raise NotImplementedError

    # ── shared ────────────────────────────────────────────────────────────
    @property
    def engine_id(self) -> str:
        return str(self.engine.currentData())

    def refresh(self) -> None:
        engine = registry.get(self.engine_id)
        got = engine.availability(self.studio)
        colour = theme.GOOD if got.ok else (theme.WARN if engine.planned else theme.BAD)
        text = engine.summary + ("\n" + got.reason if got.reason else "")
        self.needs.setText(text)
        self.needs.setStyleSheet(f"color: {colour};")
        busy = self.job is not None and not self.job.finished
        self.create_button.setEnabled(got.ok and not busy)
        self.create_button.setToolTip("" if got.ok else got.reason)

    def submit(self) -> None:
        try:
            req = self.request()
            req.setdefault("project", self.project.text().strip())
            self.job = self.studio.submit(self.engine_id, req)
        except Exception as exc:  # refused by policy, not available, a missing input
            QMessageBox.warning(self, self.heading, str(exc))
            return
        self.cancel_button.setEnabled(True)
        self.status.setText("Queued")
        self.refresh()

    def cancel(self) -> None:
        if self.job is not None:
            self.studio.queue.cancel(self.job.id)

    def on_job(self, job: Job) -> None:
        if self.job is None or job.id != self.job.id:
            return
        self.progress.setValue(int(job.progress * 100))
        self.status.setText(job.error or job.message or job.state)
        if job.finished:
            self.cancel_button.setEnabled(False)
            self.show_result(job)
            self.refresh()

    def show_result(self, job: Job) -> None:
        if job.text:
            self.output.setPlainText(job.text)
        for asset in job.assets:
            item = QListWidgetItem(f"{asset.title}\n{asset.licence_class}{' · AI' if asset.ai_generated else ''}")
            item.setData(Qt.ItemDataRole.UserRole, str(asset.path))
            if asset.path.suffix.lower() in IMAGE_SUFFIXES:
                pix = QPixmap(str(asset.path))
                if not pix.isNull():
                    item.setIcon(QIcon(pix.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)))
            self.results.insertItem(0, item)
        if job.state == "failed":
            QMessageBox.warning(self, self.heading, job.error)

    def _open(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path))))

    def selected_path(self) -> str:
        item = self.results.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""
