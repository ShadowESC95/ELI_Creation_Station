"""Carries job and model news from worker threads to the window's thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Bridge(QObject):
    job_changed = Signal(object)
    models_changed = Signal()
