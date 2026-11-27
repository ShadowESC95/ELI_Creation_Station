"""The desktop application: the licence (or the trial), then the studio."""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

from eli_creation import TITLE

ICON = Path(__file__).resolve().parent / "assets" / "eli_creation_256.png"


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from eli_creation import bundle, licensing
    from eli_creation.gui import theme, zoom
    from eli_creation.gui.licence_dialog import LicenceDialog, trial_notice
    from eli_creation.gui.main_window import MainWindow
    from eli_creation.services import Studio

    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv[:1] + list(argv or []))
    app.setApplicationName(TITLE)
    app.setOrganizationName("ELI")
    if ICON.is_file():
        app.setWindowIcon(QIcon(str(ICON)))
    zoom.install(app)
    app.setStyleSheet(theme.stylesheet(zoom.level()))

    standing = licensing.standing(start=True)
    if not standing.granted:
        dialog = LicenceDialog(None, blocking=True)
        if not dialog.exec() or not licensing.standing().granted:
            return 3
        standing = licensing.standing()
    if standing.on_trial and standing.days_left == licensing.trial().days:
        trial_notice(None, standing.days_left)
    bundle.refresh_registration()

    try:
        studio = Studio()
    except Exception as exc:
        QMessageBox.critical(None, TITLE, f"{TITLE} could not start: {exc}")
        return 1
    studio.start()
    window = MainWindow(studio, licence_line=standing.describe() if standing.on_trial else "")
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
