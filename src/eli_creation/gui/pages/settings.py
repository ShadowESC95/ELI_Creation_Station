"""Settings: this machine and its tier, the main model, how models load, ELI, the outputs, the
licence (the settings themselves are settings_tab.py's)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QLabel, QVBoxLayout

from eli_creation.gui.pages.base import Page
from eli_creation.gui.settings_tab import SettingsTab

if TYPE_CHECKING:
    from eli_creation.gui.main_window import MainWindow


class SettingsPage(Page):
    key = "settings"

    def __init__(self, shell: MainWindow) -> None:
        super().__init__(shell)
        self.settings = SettingsTab(self.studio, shell.bridge)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 0)
        lay.setSpacing(14)
        lay.addLayout(self.header("Settings", "This machine and what it can run, the main model, how the other "
                                              "models load and unload, ELI, and your licence."))
        lay.addWidget(self.settings, 1)
        for label in self.settings.findChildren(QLabel):
            label.setWordWrap(True)

    def shown(self, **wanted: Any) -> None:
        refresh = getattr(self.settings, "refresh_models", None)
        if callable(refresh):
            refresh()
