"""A film written out as one MP4 with its sound, by Qt Multimedia: no outside program is needed on
any system.

The pictures come from the compositor (the same drawing the preview shows) and the sound from the
mix of narration, music and effects. Qt encodes them with what the machine has: H.264 through the
operating system's or the graphics card's own encoder (Media Foundation, VideoToolbox, NVENC,
VA-API) where there is one, otherwise MPEG-4 with AAC through FFmpeg's own encoders, which every
machine can run. Qt's FFmpeg is an LGPL build with no GPL encoder in it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from eli_creation.production import audio
from eli_creation.production.audio import RATE, Placed
from eli_creation.production.compositor import Compositor
from eli_creation.production.formats import FORMATS
from eli_creation.production.project import Project

Progress = Callable[[float, str], None]


class RenderError(RuntimeError):
    pass


def soundtrack(project: Project, length: float | None = None) -> np.ndarray:
    """Every clip of the film mixed onto one stereo track, music ducked under the narration."""
    total = length if length is not None else project.length()
    placed = [Placed(Path(c.path), c.start, c.gain, c.kind == "narration", c.fade_in, c.fade_out)
              for c in project.clips if c.path and Path(c.path).is_file()]
    return audio.mix(placed, total, duck=project.duck)


def export(project: Project, target: Path, *, fps: int = 24, longest: int = 1920,
           progress: Progress | None = None, cancelled: Callable[[], bool] | None = None) -> tuple[Path, str]:
    """Write ``project`` to ``target`` (.mp4). Returns the path and the video codec used."""
    from PySide6.QtCore import QCoreApplication

    if QCoreApplication.instance() is None:
        raise RenderError("a film is written from the window or the command line (Qt is not running)")
    if not project.scenes:
        raise RenderError("the film has no scenes yet")
    fmt = FORMATS.get(project.format, FORMATS["youtube"])
    size = fmt.scaled(longest)
    length = project.length()
    sound = soundtrack(project, length)
    errors: list[str] = []
    for codec in ("H264", "MPEG4"):
        try:
            _encode(project, target, size, fps, length, sound, codec, progress, cancelled)
            return target, codec
        except _CodecUnavailable as exc:
            errors.append(str(exc))
            target.unlink(missing_ok=True)
            continue
    raise RenderError("no video encoder could be opened: " + "; ".join(errors))


class _CodecUnavailable(RenderError):
    pass


def _encode(project: Project, target: Path, size: tuple[int, int], fps: int, length: float, sound: np.ndarray,
            codec: str, progress: Progress | None, cancelled: Callable[[], bool] | None) -> None:
    from PySide6.QtCore import QEventLoop, QSize, QUrl
    from PySide6.QtGui import QImage
    from PySide6.QtMultimedia import (
        QAudioBuffer,
        QAudioBufferInput,
        QAudioFormat,
        QMediaCaptureSession,
        QMediaFormat,
        QMediaRecorder,
        QVideoFrame,
        QVideoFrameInput,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    loop = QEventLoop()
    session = QMediaCaptureSession()
    video_in = QVideoFrameInput()
    audio_in = QAudioBufferInput()
    session.setVideoFrameInput(video_in)
    session.setAudioBufferInput(audio_in)
    recorder = QMediaRecorder()
    session.setRecorder(recorder)
    media = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
    media.setVideoCodec(getattr(QMediaFormat.VideoCodec, codec))
    media.setAudioCodec(QMediaFormat.AudioCodec.AAC)
    recorder.setMediaFormat(media)
    recorder.setQuality(QMediaRecorder.Quality.HighQuality)
    recorder.setVideoResolution(QSize(*size))
    recorder.setVideoFrameRate(fps)
    recorder.setAudioSampleRate(RATE)
    recorder.setAudioChannelCount(2)
    recorder.setOutputLocation(QUrl.fromLocalFile(str(target)))
    failures: list[str] = []
    recorder.errorOccurred.connect(lambda _e, words: failures.append(words))

    compositor = Compositor(project, size)
    frames = max(1, int(round(length * fps)))
    pcm = (np.clip(sound, -1, 1) * 32767).astype("<i2").tobytes()
    fmt = QAudioFormat()
    fmt.setSampleRate(RATE)
    fmt.setChannelCount(2)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    chunk = (RATE // fps) * 4
    state = {"frame": 0, "audio": 0}

    def send_video() -> None:
        while state["frame"] < frames:
            if cancelled is not None and cancelled():
                return
            n = state["frame"]
            image = compositor.frame(n / fps).convertToFormat(QImage.Format.Format_RGBA8888)
            frame = QVideoFrame(image)
            frame.setStartTime(int(n * 1_000_000 / fps))
            frame.setEndTime(int((n + 1) * 1_000_000 / fps))
            if not video_in.sendVideoFrame(frame):
                return
            state["frame"] += 1
            if progress is not None and n % max(1, fps // 2) == 0:
                progress(0.05 + 0.9 * n / frames, f"Writing frame {n + 1} of {frames}")

    def send_audio() -> None:
        while state["audio"] * chunk < len(pcm):
            piece = pcm[state["audio"] * chunk:(state["audio"] + 1) * chunk]
            buffer = QAudioBuffer(piece, fmt, int(state["audio"] * chunk / 4 * 1_000_000 / RATE))
            if not audio_in.sendAudioBuffer(buffer):
                return
            state["audio"] += 1

    video_in.readyToSendVideoFrame.connect(send_video)
    audio_in.readyToSendAudioBuffer.connect(send_audio)
    recorder.record()
    deadline = time.monotonic() + max(120.0, length * 30)
    stopping = False
    while time.monotonic() < deadline:
        loop.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if failures:
            recorder.stop()
            if any("initialize encoder" in f.lower() or "codec" in f.lower() for f in failures):
                raise _CodecUnavailable(f"{codec}: {failures[0]}")
            raise RenderError(failures[0])
        if cancelled is not None and cancelled():
            recorder.stop()
            raise RenderError("cancelled")
        done = state["frame"] >= frames and state["audio"] * chunk >= len(pcm)
        if done and not stopping:
            recorder.stop()
            stopping = True
        if stopping and recorder.recorderState() == QMediaRecorder.RecorderState.StoppedState:
            break
    else:
        recorder.stop()
        raise RenderError("writing the film took too long and was stopped")
    if not target.is_file() or target.stat().st_size == 0:
        raise _CodecUnavailable(f"{codec}: nothing was written")
