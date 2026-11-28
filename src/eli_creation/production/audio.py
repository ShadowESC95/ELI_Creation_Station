"""Sound as numbers: read and write WAV files, mix tracks with their gains and starts, duck music
under a voice, and the peaks a waveform is drawn from. Standard library and numpy only."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RATE = 44100


def write_wav(path: Path, samples: np.ndarray, rate: int = RATE) -> Path:
    """Write float samples (-1…1), mono (n,) or stereo (n, 2), as 16-bit PCM."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(samples, dtype=np.float32)
    if data.ndim == 1:
        data = data[:, None]
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return path


def read_wav(path: Path, rate: int = RATE) -> np.ndarray:
    """A WAV as float stereo samples at ``rate`` (resampled if it was made at another)."""
    with wave.open(str(path), "rb") as w:
        channels, width, src_rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(frames)
    if width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"{path.name}: {width * 8}-bit samples are not read")
    data = data.reshape(-1, channels)
    if channels == 1:
        data = np.repeat(data, 2, axis=1)
    elif channels > 2:
        data = data[:, :2]
    if src_rate != rate and len(data):
        n = max(1, round(len(data) * rate / src_rate))
        x_old = np.linspace(0.0, 1.0, len(data))
        x_new = np.linspace(0.0, 1.0, n)
        data = np.stack([np.interp(x_new, x_old, data[:, c]) for c in range(2)], axis=1).astype(np.float32)
    return data


def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


@dataclass
class Placed:
    """A sound on the timeline: where it starts, how loud, and whether music dips under it."""

    path: Path
    start: float = 0.0
    gain: float = 1.0
    voice: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    trim: float = 0.0  # seconds cut from its start


def mix(sounds: list[Placed], length: float, *, duck: float = 0.35, rate: int = RATE) -> np.ndarray:
    """Every sound placed on one stereo track ``length`` seconds long. Music (not a voice) is
    lowered to ``duck`` of its level wherever a voice speaks, with soft edges."""
    total = max(1, int(length * rate))
    voices = np.zeros(total, dtype=np.float32)
    music = np.zeros((total, 2), dtype=np.float32)
    speech = np.zeros((total, 2), dtype=np.float32)
    for sound in sounds:
        try:
            data = read_wav(sound.path, rate)
        except (OSError, ValueError, EOFError, wave.Error):
            continue
        data = data[int(sound.trim * rate):] * float(sound.gain)
        data = _fades(data, sound.fade_in, sound.fade_out, rate)
        at = int(sound.start * rate)
        if at >= total or not len(data):
            continue
        piece = data[: total - at]
        target = speech if sound.voice else music
        target[at: at + len(piece)] += piece
        if sound.voice:
            voices[at: at + len(piece)] = np.maximum(voices[at: at + len(piece)], np.abs(piece).max(axis=1) > 0.003)
    if voices.any() and duck < 1.0:
        # a ducking envelope: 1 in the clear, ``duck`` under the voice, eased over 0.25 s
        window = max(1, int(0.25 * rate))
        kernel = np.ones(window, dtype=np.float32) / window
        held = np.convolve(voices, kernel, mode="same")
        envelope = 1.0 - (1.0 - duck) * np.clip(held * 1.5, 0.0, 1.0)
        music *= envelope[:, None]
    out = music + speech
    peak = float(np.abs(out).max()) if len(out) else 0.0
    if peak > 0.98:
        out *= 0.98 / peak
    return out


def _fades(data: np.ndarray, fade_in: float, fade_out: float, rate: int) -> np.ndarray:
    data = data.copy()
    n_in, n_out = min(len(data), int(fade_in * rate)), min(len(data), int(fade_out * rate))
    if n_in > 1:
        data[:n_in] *= np.linspace(0.0, 1.0, n_in)[:, None]
    if n_out > 1:
        data[-n_out:] *= np.linspace(1.0, 0.0, n_out)[:, None]
    return data


def peaks(path: Path, buckets: int = 400) -> list[float]:
    """How loud each of ``buckets`` stretches of a sound is (0…1), to draw its waveform."""
    try:
        data = read_wav(path, 22050)
    except (OSError, ValueError, EOFError, wave.Error):
        return []
    if not len(data):
        return []
    mono = np.abs(data).max(axis=1)
    size = max(1, len(mono) // buckets)
    usable = mono[: size * (len(mono) // size)].reshape(-1, size)
    found = usable.max(axis=1)
    top = float(found.max()) or 1.0
    return [round(float(v) / top, 3) for v in found]


def normalise(samples: np.ndarray, level: float = 0.9) -> np.ndarray:
    peak = float(np.abs(samples).max()) if len(samples) else 0.0
    return samples * (level / peak) if peak > 0 else samples
