"""Music composed on this machine, with no model: a mood's chords, tempo and instruments, built
into an intro, a body and an ending of the length asked for.

Every sound is synthesised here (additive pads and plucks, a bass, drums from shaped noise and
pitch sweeps), so the result belongs to whoever made it: there is no model, sample or loop with
a licence of its own in it. The same seed gives the same piece.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from eli_creation.production.audio import RATE, normalise, write_wav

NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
}


@dataclass(frozen=True)
class Mood:
    key: str
    name: str
    scale: str
    tempo: int
    progression: tuple[int, ...]  # scale degrees, one chord a bar (0 = the tonic)
    pad: float
    pluck: float
    bass: float
    kick: str  # "" | "four" | "half" | "boom" | "lofi"
    hats: float
    snare: float
    sevenths: bool = False
    swing: float = 0.0
    bright: float = 0.5
    blurb: str = ""


MOODS: dict[str, Mood] = {
    m.key: m
    for m in (
        Mood("cinematic", "Cinematic", "minor", 84, (0, 5, 2, 6), 1.0, 0.35, 0.6, "boom", 0.0, 0.0,
             bright=0.35, blurb="Wide pads, slow drums: trailers, reveals, films"),
        Mood("uplifting", "Uplifting", "major", 112, (0, 4, 5, 3), 0.7, 0.8, 0.6, "four", 0.5, 0.55,
             bright=0.7, blurb="Bright plucks and a steady beat: launches and good news"),
        Mood("ambient", "Ambient", "lydian", 70, (0, 3, 0, 4), 1.0, 0.25, 0.3, "", 0.0, 0.0,
             sevenths=True, bright=0.45, blurb="Slow and spacious: backgrounds, calm, focus"),
        Mood("tense", "Tense", "minor", 96, (0, 5, 3, 4), 0.6, 0.5, 0.9, "half", 0.7, 0.3,
             bright=0.3, blurb="A pulsing bass under suspense: thrillers, countdowns"),
        Mood("lofi", "Lo-fi", "dorian", 82, (1, 4, 0, 5), 0.5, 0.7, 0.55, "lofi", 0.45, 0.45,
             sevenths=True, swing=0.18, bright=0.3, blurb="Warm keys and a lazy beat: vlogs, study, cafés"),
        Mood("epic", "Epic", "minor", 126, (0, 5, 2, 6), 0.9, 0.6, 0.8, "boom", 0.6, 0.7,
             bright=0.6, blurb="Big drums and a rising stack: sport, action, finales"),
        Mood("corporate", "Corporate", "major", 106, (0, 5, 3, 4), 0.55, 0.75, 0.5, "four", 0.4, 0.4,
             bright=0.6, blurb="Light and positive: products, explainers, presentations"),
        Mood("electronic", "Electronic", "minor", 124, (0, 0, 5, 6), 0.5, 0.65, 0.9, "four", 0.8, 0.6,
             bright=0.65, blurb="Four on the floor and a driving bass: ads, reels, fashion"),
    )
}


def _freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _env(n: int, attack: float, release: float, rate: int = RATE) -> np.ndarray:
    a, r = max(1, int(attack * rate)), max(1, int(release * rate))
    env = np.ones(n, dtype=np.float32)
    env[: min(a, n)] = np.linspace(0, 1, min(a, n))
    if r < n:
        env[-r:] *= np.linspace(1, 0, r)
    return env


def _tone(freq: float, seconds: float, harmonics: int, bright: float, detune: float = 0.0,
          rng: np.random.Generator | None = None) -> np.ndarray:
    """A band-limited, slightly detuned tone: brighter with more weight on upper harmonics."""
    n = max(1, int(seconds * RATE))
    t = np.arange(n, dtype=np.float32) / RATE
    out = np.zeros(n, dtype=np.float32)
    phase = float(rng.uniform(0, 6.28)) if rng is not None else 0.0
    for h in range(1, harmonics + 1):
        f = freq * h * (1 + detune * (h % 3 - 1) * 0.001)
        if f > RATE / 2.2:
            break
        out += np.sin(2 * np.pi * f * t + phase * h) * (1.0 / h ** (1.6 - bright))
    return out / max(1.0, float(np.abs(out).max()))


def _kick(rate: int = RATE) -> np.ndarray:
    n = int(0.45 * rate)
    t = np.arange(n) / rate
    sweep = 45 + 95 * np.exp(-t * 28)
    return (np.sin(2 * np.pi * np.cumsum(sweep) / rate) * np.exp(-t * 7.5)).astype(np.float32)


def _boom(rate: int = RATE) -> np.ndarray:
    n = int(1.2 * rate)
    t = np.arange(n) / rate
    sweep = 38 + 60 * np.exp(-t * 9)
    return (np.sin(2 * np.pi * np.cumsum(sweep) / rate) * np.exp(-t * 3.2)).astype(np.float32)


def _noise(seconds: float, decay: float, rng: np.random.Generator, high: bool) -> np.ndarray:
    n = int(seconds * RATE)
    noise = rng.standard_normal(n).astype(np.float32)
    if high:  # take the low part away: a hat's hiss
        smooth = np.convolve(noise, np.ones(6, dtype=np.float32) / 6, mode="same")
        noise = noise - smooth
    return noise * np.exp(-np.arange(n) / RATE * decay).astype(np.float32)


def _snare(rng: np.random.Generator) -> np.ndarray:
    body = _tone(185, 0.25, 3, 0.2) * np.exp(-np.arange(int(0.25 * RATE)) / RATE * 22)
    return (0.55 * _noise(0.25, 18, rng, high=True)[: len(body)] + 0.45 * body).astype(np.float32)


def _place(track: np.ndarray, sound: np.ndarray, at: float, gain: float, pan: float = 0.0) -> None:
    i = int(at * RATE)
    if i >= len(track):
        return
    piece = sound[: len(track) - i] * gain
    track[i: i + len(piece), 0] += piece * (1 - max(0.0, pan))
    track[i: i + len(piece), 1] += piece * (1 + min(0.0, pan))


def compose(mood_key: str, seconds: float, *, tempo: int = 0, key: str = "C", seed: int = 7,
            intensity: float = 0.7, instruments: dict[str, bool] | None = None) -> np.ndarray:
    """A piece in ``mood_key`` of ``seconds``, as float stereo samples."""
    mood = MOODS.get(mood_key, MOODS["cinematic"])
    use = {"pad": True, "pluck": True, "bass": True, "drums": True, **(instruments or {})}
    rng = np.random.default_rng(seed)
    bpm = tempo or mood.tempo
    beat = 60.0 / bpm
    bar = beat * 4
    total = max(2.0, float(seconds))
    track = np.zeros((int((total + 2.5) * RATE), 2), dtype=np.float32)
    root = 48 + (NOTES.index(key) if key in NOTES else 0)
    scale = SCALES[mood.scale]
    bars = int(np.ceil(total / bar))
    intro, outro = (1 if bars > 4 else 0), (1 if bars > 6 else 0)

    def chord_notes(degree: int) -> list[int]:
        steps = (0, 2, 4, 6) if mood.sevenths else (0, 2, 4)
        notes = []
        for s in steps:
            idx = degree + s
            notes.append(root + 12 + scale[idx % 7] + 12 * (idx // 7))
        return notes

    for b in range(bars):
        t0 = b * bar
        degree = mood.progression[b % len(mood.progression)]
        notes = chord_notes(degree)
        energy = 0.55 if b < intro else (0.75 if b >= bars - outro else 1.0)
        energy *= 0.6 + 0.4 * intensity
        if use["pad"] and mood.pad:
            for k, note in enumerate(notes):
                tone = _tone(_freq(note), bar + 0.6, 7, mood.bright, detune=4, rng=rng)
                _place(track, tone * _env(len(tone), bar * 0.35, 0.8), t0, 0.11 * mood.pad * energy,
                       pan=(k - 1) * 0.35)
        if use["pluck"] and mood.pluck and b >= intro:
            pattern = (0, 1, 2, 1, 0, 2, 1, 2) if len(notes) >= 3 else (0, 1)
            for step in range(8):
                swing = mood.swing * beat * 0.5 if step % 2 else 0.0
                note = notes[pattern[step] % len(notes)] + 12
                tone = _tone(_freq(note), beat * 0.9, 5, mood.bright + 0.2, rng=rng)
                tone *= np.exp(-np.arange(len(tone)) / RATE * 7).astype(np.float32)
                _place(track, tone, t0 + step * beat / 2 + swing, 0.08 * mood.pluck * energy,
                       pan=0.4 if step % 2 else -0.4)
        if use["bass"] and mood.bass and b >= intro:
            bass_note = root - 12 + scale[degree % 7]
            hits = (0, 1, 2, 3) if mood.key in ("tense", "electronic") else (0, 2.5) if mood.key == "lofi" else (0, 2)
            for h in hits:
                length = beat * (0.9 if len(hits) > 2 else 1.8)
                tone = _tone(_freq(bass_note), length, 3, 0.3) * _env(int(length * RATE), 0.01, 0.12)
                _place(track, tone, t0 + h * beat, 0.22 * mood.bass * energy)
        if use["drums"] and b >= intro and b < bars - outro + (1 if not outro else 0):
            if mood.kick == "four":
                for k in range(4):
                    _place(track, _kick(), t0 + k * beat, 0.5 * energy)
            elif mood.kick == "half":
                for at in (0.0, 2.5):
                    _place(track, _kick(), t0 + at * beat, 0.45 * energy)
            elif mood.kick == "lofi":
                for at in (0.0, 1.75, 2.5):
                    _place(track, _kick(), t0 + at * beat, 0.4 * energy)
            elif mood.kick == "boom" and b % 2 == 0:
                _place(track, _boom(), t0, 0.55 * energy)
            if mood.snare:
                for k in (1, 3):
                    _place(track, _snare(rng), t0 + k * beat + (mood.swing * beat * 0.3), 0.28 * mood.snare * energy)
            if mood.hats:
                for k in range(8):
                    swing = mood.swing * beat * 0.5 if k % 2 else 0.0
                    _place(track, _noise(0.06, 60, rng, high=True), t0 + k * beat / 2 + swing,
                            0.09 * mood.hats * energy * (0.6 if k % 2 else 1.0), pan=0.25)
    # a sense of space: a few soft echoes of the whole
    for delay, gain in ((0.11, 0.18), (0.23, 0.11), (0.37, 0.07)):
        shift = int(delay * RATE)
        track[shift:, 0] += track[:-shift, 1] * gain
        track[shift:, 1] += track[:-shift, 0] * gain
    out = track[: int(total * RATE)]
    fade = min(len(out), int(min(2.5, total / 4) * RATE))
    if fade > 1:
        out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    lead = min(len(out), int(0.4 * RATE))
    out[:lead] *= np.linspace(0, 1, lead)[:, None]
    return normalise(out, 0.85)


def make(path: Path, mood_key: str, seconds: float, **options: object) -> Path:
    return write_wav(path, compose(mood_key, seconds, **options))  # type: ignore[arg-type]
