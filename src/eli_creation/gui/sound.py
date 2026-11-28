"""Sound in the window, through Qt Multimedia, on every system: play a voice, a track or a film's
soundtrack from any moment, and know where it is. Where Qt Multimedia cannot run (a Linux machine
with no sound library), it says why and the pictures still play."""

from __future__ import annotations

import atexit
import weakref
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl, Signal

_alive: weakref.WeakSet[Sound] = weakref.WeakSet()


class Sound(QObject):
    moved = Signal(float)  # seconds
    playing_changed = Signal(bool)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        from eli_creation.production.render import multimedia

        self.available, self.why = multimedia()
        self._player: Any = None  # made when something is first played, let go of by release()
        self._output: Any = None
        self.path = ""
        _alive.add(self)

    def _ensure(self) -> bool:
        if self._player is not None:
            return True
        if not self.available:
            return False
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

        self._player = QMediaPlayer()
        self._output = QAudioOutput()
        self._output.setVolume(0.9)
        self._player.setAudioOutput(self._output)
        self._player.positionChanged.connect(self._position)
        self._player.playbackStateChanged.connect(self._state)
        return True

    def _position(self, ms: int) -> None:
        self.moved.emit(ms / 1000.0)

    def release(self) -> None:
        """Stop and let go of the player now, while Qt is still running: a media player left for
        the interpreter to collect at exit can be torn down after Qt is, and crash it."""
        player, output = self._player, self._output
        self._player = self._output = None
        self.path = ""
        if player is None:
            return
        try:
            player.stop()
            player.setSource(QUrl())
            player.setAudioOutput(None)
        except RuntimeError:  # already gone with Qt
            return
        import shiboken6

        for thing in (player, output):
            if thing is not None and shiboken6.isValid(thing):
                shiboken6.delete(thing)

    def _state(self, state: object) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.playing_changed.emit(playing)
        if state == QMediaPlayer.PlaybackState.StoppedState and self._player is not None \
                and self._player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()

    def play(self, path: str | Path, start: float = 0.0) -> bool:
        if not Path(path).is_file() or not self._ensure():
            return False
        if str(path) != self.path:
            self.path = str(path)
            self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.setPosition(int(start * 1000))
        self._player.play()
        return True

    def pause(self) -> None:
        if self._player is not None:
            self._player.pause()

    def stop(self) -> None:
        if self._player is not None:
            self._player.stop()

    def forget(self) -> None:
        """Let go of the file (so it can be rewritten)."""
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())
        self.path = ""

    @property
    def playing(self) -> bool:
        if self._player is None:
            return False
        from PySide6.QtMultimedia import QMediaPlayer

        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def position(self) -> float:
        return (self._player.position() / 1000.0) if self._player is not None else 0.0

    def volume(self, level: float) -> None:
        if self._output is not None:
            self._output.setVolume(max(0.0, min(1.0, level)))


_shared: Sound | None = None


def shared() -> Sound:
    """One player for quick listening across the window (a new sound stops the last)."""
    global _shared
    if _shared is None:
        _shared = Sound()
    return _shared


def release_all() -> None:
    """Let go of every player (the window calls it as it closes; Python as it exits)."""
    global _shared
    for sound in list(_alive):
        sound.release()
    _shared = None


atexit.register(release_all)
