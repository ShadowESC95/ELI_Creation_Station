"""Captions: narration split into readable lines, each shown while it is spoken, and written as SRT
and WebVTT for the platforms that take a caption file."""

from __future__ import annotations

import re
from pathlib import Path

from eli_creation.production.project import Clip, Cue

MAX_CHARS = 42


def lines_of(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Sentences, then phrases, then words, packed into lines of at most ``limit`` characters."""
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
        words = sentence.split()
        line = ""
        for word in words:
            if line and len(line) + 1 + len(word) > limit:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            out.append(line)
    return out


def cues_for(clip: Clip) -> list[Cue]:
    """A narration clip's words, each line timed by its share of the characters spoken."""
    lines = lines_of(clip.text)
    if not lines or clip.duration <= 0:
        return []
    total = sum(len(x) + 3 for x in lines)
    t = clip.start
    cues = []
    for line in lines:
        span = clip.duration * (len(line) + 3) / total
        cues.append(Cue(round(t, 3), round(t + span, 3), line))
        t += span
    return cues


def _stamp(seconds: float, comma: bool) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"


def write_srt(cues: list[Cue], path: Path) -> Path:
    body = "\n".join(f"{n}\n{_stamp(c.start, True)} --> {_stamp(c.end, True)}\n{c.text}\n"
                     for n, c in enumerate(cues, 1))
    path.write_text(body, encoding="utf-8")
    return path


def write_vtt(cues: list[Cue], path: Path) -> Path:
    body = "WEBVTT\n\n" + "\n".join(f"{_stamp(c.start, False)} --> {_stamp(c.end, False)}\n{c.text}\n" for c in cues)
    path.write_text(body, encoding="utf-8")
    return path
