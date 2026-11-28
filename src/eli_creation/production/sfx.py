"""Sound effects synthesised on this machine: the transitions and stingers ads, reels and trailers
use (a whoosh between shots, a riser before a reveal, an impact on the logo)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from eli_creation.production.audio import RATE, normalise, write_wav


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * RATE), dtype=np.float32) / RATE


def _filtered_noise(n: int, rng: np.random.Generator, width: int) -> np.ndarray:
    noise = rng.standard_normal(n).astype(np.float32)
    return np.convolve(noise, np.ones(width, dtype=np.float32) / width, mode="same")


def whoosh(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(seconds)
    shape = np.sin(np.pi * t / seconds) ** 2
    hiss = _filtered_noise(len(t), rng, 4) * 0.7 + _filtered_noise(len(t), rng, 16) * 0.9
    return hiss * shape


def riser(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(seconds)
    sweep = 120 * (2 ** (t / seconds * 3.5))
    tone = np.sin(2 * np.pi * np.cumsum(sweep) / RATE) + 0.5 * np.sin(4 * np.pi * np.cumsum(sweep) / RATE)
    noise = _filtered_noise(len(t), rng, 3)
    return (0.6 * tone + 0.5 * noise) * (t / seconds) ** 2


def downlifter(seconds: float, rng: np.random.Generator) -> np.ndarray:
    return riser(seconds, rng)[::-1].copy()


def impact(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(seconds)
    sweep = 35 + 90 * np.exp(-t * 6)
    body = np.sin(2 * np.pi * np.cumsum(sweep) / RATE) * np.exp(-t * 2.4)
    crack = _filtered_noise(len(t), rng, 2) * np.exp(-t * 18)
    return body + 0.6 * crack


def pop(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(min(seconds, 0.25))
    sweep = 900 * np.exp(-t * 40) + 300
    return np.sin(2 * np.pi * np.cumsum(sweep) / RATE) * np.exp(-t * 30)


def shimmer(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(seconds)
    out = np.zeros_like(t)
    for k, f in enumerate((2093.0, 2637.0, 3136.0, 3951.0, 4186.0)):
        start = k * 0.07
        env = np.clip((t - start) * 20, 0, 1) * np.exp(-np.clip(t - start, 0, None) * 3.0)
        out += np.sin(2 * np.pi * f * t) * env
    return out


def chime(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(seconds)
    out = np.zeros_like(t)
    for k, f in enumerate((880.0, 1318.5)):
        start = k * 0.12
        env = (t >= start) * np.exp(-np.clip(t - start, 0, None) * 4.5)
        out += (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t)) * env
    return out


def glitch(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(seconds)
    out = np.zeros_like(t)
    step = int(0.03 * RATE)
    for i in range(0, len(t), step):
        if rng.random() < 0.6:
            f = float(rng.choice([220, 440, 880, 1760, 3520]))
            seg = t[i: i + step]
            out[i: i + len(seg)] = np.sign(np.sin(2 * np.pi * f * seg)) * float(rng.uniform(0.3, 1))
    return out * np.exp(-t * 1.5)


def heartbeat(seconds: float, rng: np.random.Generator) -> np.ndarray:
    t = _t(seconds)
    out = np.zeros_like(t)
    beat = 0.85
    for start in np.arange(0, seconds, beat):
        for lag, gain in ((0.0, 1.0), (0.22, 0.7)):
            s = start + lag
            env = (t >= s) * np.exp(-np.clip(t - s, 0, None) * 22)
            out += np.sin(2 * np.pi * 55 * (t - s)) * env * gain
    return out


EFFECTS: dict[str, tuple[str, float, Any, str]] = {
    "whoosh": ("Whoosh", 0.9, whoosh, "Air moving past: between shots"),
    "riser": ("Riser", 3.0, riser, "Climbing tension before a reveal"),
    "downlifter": ("Downlifter", 2.0, downlifter, "Falling away after a drop"),
    "impact": ("Impact", 2.0, impact, "A deep hit: logos, titles, cuts to black"),
    "pop": ("Pop", 0.25, pop, "A light tap: icons and text appearing"),
    "shimmer": ("Shimmer", 1.5, shimmer, "Sparkle: product shine, magic"),
    "chime": ("Chime", 1.2, chime, "A friendly ding: notifications, success"),
    "glitch": ("Glitch", 0.8, glitch, "Digital stutter: tech, gaming"),
    "heartbeat": ("Heartbeat", 3.4, heartbeat, "A pulse under suspense"),
}


def make(path: Path, effect: str, seconds: float = 0.0, *, seed: int = 3) -> Path:
    entry = EFFECTS.get(effect, EFFECTS["whoosh"])
    default, build = float(entry[1]), entry[2]
    rng = np.random.default_rng(seed)
    mono = normalise(build(seconds or default, rng).astype(np.float32), 0.9)
    return write_wav(path, np.stack([mono, mono], axis=1))
