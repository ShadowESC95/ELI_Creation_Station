"""Sound in the window, through Qt Multimedia, on every system: play a voice, a track or a film's
soundtrack from any moment, and know where it is. Where Qt Multimedia cannot run (a Linux machine
with no sound library), it says why and the pictures still play."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal


class Sound(QObject):
    moved = Signal(float)  # seconds
    playing_changed = Signal(bool)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        from eli_creation.production.render import multimedia

        self.available, self.why = multimedia()
        self._player = None
        self._output = None
        self.path = ""
        if self.available:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._player = QMediaPlayer(self)
            self._output = QAudioOutput(self)
            self._output.setVolume(0.9)
            self._player.setAudioOutput(self._output)
            self._player.positionChanged.connect(lambda ms: self.moved.emit(ms / 1000.0))
            self._player.playbackStateChanged.connect(self._state)

    def _state(self, state: object) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.playing_changed.emit(playing)
        if state == QMediaPlayer.PlaybackState.StoppedState and self._player is not None \
                and self._player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()

    def play(self, path: str | Path, start: float = 0.0) -> bool:
        if self._player is None or not Path(path).is_file():
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
