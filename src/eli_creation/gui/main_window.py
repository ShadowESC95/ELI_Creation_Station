"""The window: the project, seven tabs, ELI beside them, and what is loaded in the status bar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolBar,
)

from eli_creation import TITLE, __version__
from eli_creation.gui import theme
from eli_creation.gui.eli_panel import EliPanel
from eli_creation.gui.settings_tab import SettingsTab
from eli_creation.gui.studio_tab import Bridge
from eli_creation.gui.tabs import TABS
from eli_creation.tiers import TIER_LABELS

if TYPE_CHECKING:
    from eli_creation.services import Studio

TAB_ORDER = ("Socials", "Images", "Videos", "Games", "Editing", "Coding", "Settings")


class MainWindow(QMainWindow):
    def __init__(self, studio: Studio, *, licence_line: str = "") -> None:
        super().__init__()
        self.studio = studio
        self.setWindowTitle(f"{TITLE} {__version__}")
        self.resize(1360, 860)
        self.bridge = Bridge()
        studio.queue.on_change(self.bridge.job_changed.emit)
        studio.manager.on_change(self.bridge.models_changed.emit)

        bar = QToolBar("Project")
        bar.setMovable(False)
        bar.addWidget(QLabel("  Project  "))
        self.project = QLineEdit()
        self.project.setPlaceholderText("A client job, a channel, a game…")
        self.project.setMaximumWidth(320)
        bar.addWidget(self.project)
        self.addToolBar(bar)

        self.tabs = QTabWidget()
        for cls in TABS:
            self.tabs.addTab(cls(studio, self.bridge, self.project), cls.heading)
        self.tabs.addTab(SettingsTab(studio, self.bridge), "Settings")
        names = [self.tabs.tabText(i) for i in range(self.tabs.count())]
        start = studio.settings.last_tab.capitalize()
        self.tabs.setCurrentIndex(names.index(start) if start in names else 0)
        self.tabs.currentChanged.connect(self._remember_tab)
        self.setCentralWidget(self.tabs)

        dock = QDockWidget("ELI", self)
        dock.setObjectName("eli")
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.eli = EliPanel(studio, self.project)
        dock.setWidget(self.eli)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self.main_chip, self.models_chip, self.tier_chip = QLabel(), QLabel(), QLabel()
        self.licence_chip = QLabel(licence_line)
        for chip in (self.main_chip, self.models_chip, self.tier_chip, self.licence_chip):
            self.statusBar().addPermanentWidget(chip)
        self.tier_chip.setText(f"Tier {studio.machine.tier}: {TIER_LABELS[studio.machine.tier]}")
        self.bridge.models_changed.connect(self.refresh_status)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(2000)
        self._menus()
        self.refresh_status()

    def _menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        outputs = QAction("Open the outputs folder", self)
        outputs.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.studio.layout.outputs))))
        file_menu.addAction(outputs)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        models = self.menuBar().addMenu("&Models")
        unload = QAction("Unload idle specialists now", self)
        unload.triggered.connect(lambda: self.studio.manager.unload_idle(now=float("inf")))
        models.addAction(unload)
        help_menu = self.menuBar().addMenu("&Help")
        lic = QAction("Licence…", self)
        lic.triggered.connect(self._licence)
        help_menu.addAction(lic)
        about = QAction("About", self)
        about.triggered.connect(lambda: QMessageBox.about(self, TITLE, f"{TITLE} {__version__}\nAn ELI bundle."))
        help_menu.addAction(about)

    def _licence(self) -> None:
        from eli_creation.gui.licence_dialog import LicenceDialog

        LicenceDialog(self).exec()

    def _remember_tab(self, index: int) -> None:
        self.studio.settings.last_tab = self.tabs.tabText(index).lower()

    def refresh_status(self) -> None:
        main = self.studio.main
        colour = theme.colour_for(main.state)
        self.main_chip.setText(f"Main model: {main.name} ({main.state})")
        self.main_chip.setStyleSheet(f"color: {colour}; padding: 0 8px;")
        loaded = [s for s in self.studio.manager.status() if s.role == "specialist" and s.state in ("loading", "ready", "busy", "unloading")]
        self.models_chip.setText("Specialists: " + (", ".join(f"{s.title} ({s.state})" for s in loaded) or "none loaded"))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt's name
        self.studio.save_settings()
        self.studio.close()
        super().closeEvent(event)
