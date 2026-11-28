"""Narration: words spoken in a chosen voice, as a WAV.

Voices come from, in order of quality:

- **ELI v3**, when its server runs on this machine: its own voices (Kokoro and the others it has),
  loaded and unloaded by ELI v3 itself;
- **Piper**, when its program and a voice model are on this machine (the person's own: each
  voice's licence travels onto what it speaks);
- **the system's own speech**: eSpeak NG on Linux, ``say`` on macOS, Windows' speech synthesiser.

A voice is named ``source:name`` (``eli:af_heart``, ``piper:/path/voice.onnx``, ``system:en-gb``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from eli_creation import eli_link


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    source: str  # eli | piper | system
    language: str = ""
    licence: str = ""

    @property
    def label(self) -> str:
        where = {"eli": "ELI v3", "piper": "Piper", "system": "this computer"}.get(self.source, self.source)
        return f"{self.name} · {where}"


def piper_program() -> str:
    return os.environ.get("ELI_CREATION_PIPER") or shutil.which("piper") or ""


def piper_voice_folders() -> list[Path]:
    home = Path.home()
    out = [home / ".local" / "share" / "piper" / "voices", home / ".local" / "share" / "piper",
           home / "piper" / "voices"]
    if os.environ.get("ELI_CREATION_PIPER_VOICES"):
        out.insert(0, Path(os.environ["ELI_CREATION_PIPER_VOICES"]).expanduser())
    from eli_creation.layout import layout

    out.insert(0, layout().models / "speech")
    return out


def _piper_voices() -> list[Voice]:
    if not piper_program():
        return []
    found: dict[str, Voice] = {}
    for folder in piper_voice_folders():
        if not folder.is_dir():
            continue
        for model in folder.rglob("*.onnx"):
            if not model.with_name(model.name + ".json").is_file():
                continue
            stem = model.stem  # en_US-amy-medium
            parts = stem.split("-")
            name = parts[1].capitalize() if len(parts) > 1 else stem
            found.setdefault(stem, Voice(f"piper:{model}", f"{name} ({parts[0] if parts else ''})", "piper",
                                         parts[0] if parts else ""))
    return sorted(found.values(), key=lambda v: v.name)


def _system_voices() -> list[Voice]:
    if sys.platform == "darwin" and shutil.which("say"):
        try:
            listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            listing = ""
        voices = []
        for line in listing.splitlines():
            bits = line.split()
            if len(bits) >= 2 and bits[1].startswith("en"):
                voices.append(Voice(f"system:{bits[0]}", bits[0], "system", bits[1]))
        return voices[:24]
    if os.name == "nt":
        return [Voice("system:default", "Windows voice", "system", "en")]
    engine = shutil.which("espeak-ng") or shutil.which("espeak")
    if engine:
        return [Voice(f"system:{code}", label, "system", code) for code, label in (
            ("en-us", "American English"), ("en-gb", "British English"), ("en-gb-scotland", "Scottish English"),
            ("en-us+f3", "American English (higher)"), ("en-gb+m3", "British English (lower)"),
            ("fr", "French"), ("de", "German"), ("es", "Spanish"), ("it", "Italian"), ("pt", "Portuguese"))]
    return []


_cached: dict[bool, tuple[float, list[Voice]]] = {}


def voices(*, include_eli: bool = True, fresh: bool = False) -> list[Voice]:
    """Every voice this machine has now (remembered for 30 seconds)."""
    import time

    hit = _cached.get(include_eli)
    if hit is not None and not fresh and time.monotonic() - hit[0] < 30:
        return list(hit[1])
    found = _voices(include_eli)
    _cached[include_eli] = (time.monotonic(), found)
    return list(found)


def _voices(include_eli: bool) -> list[Voice]:
    out: list[Voice] = []
    if include_eli:
        link = eli_link.find()
        if link is not None:
            try:
                names, _active = link.voices()
                out += [Voice(f"eli:{n}", n.replace("_", " "), "eli",
                              licence="Apache-2.0" if n[:3] in ("af_", "am_", "bf_", "bm_") else "") for n in names]
            except Exception:
                pass
    return out + _piper_voices() + _system_voices()


def best_voice() -> Voice | None:
    found = voices()
    return found[0] if found else None


def speak(text: str, voice_id: str, target: Path, *, speed: float = 1.0) -> Path:
    """Speak ``text`` into ``target`` (a WAV). Raises RuntimeError with the reason on failure."""
    text = " ".join(text.split())
    if not text:
        raise RuntimeError("there is nothing to say")
    target.parent.mkdir(parents=True, exist_ok=True)
    source, _, name = voice_id.partition(":")
    speed = max(0.5, min(2.0, float(speed or 1.0)))
    if source == "eli":
        link = eli_link.find(fresh=True)
        if link is None:
            raise RuntimeError("ELI v3 is not running on this machine: start it to use its voices")
        target.write_bytes(link.speak(text, name))
        return _respeed(target, speed) if abs(speed - 1.0) > 0.02 else target
    if source == "piper":
        program = piper_program()
        if not program:
            raise RuntimeError("Piper is not installed")
        _run([program, "-m", name, "-f", str(target), "--length-scale", f"{1 / speed:.3f}"], text)
        return target
    if source == "system":
        return _system(text, name, target, speed)
    raise RuntimeError(f"unknown voice {voice_id!r}")


def _run(cmd: list[str], stdin: str = "", timeout: int = 600) -> None:
    try:
        done = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"{Path(cmd[0]).name} could not run: {exc}") from exc
    if done.returncode != 0:
        raise RuntimeError(f"{Path(cmd[0]).name} failed: {(done.stderr or done.stdout).strip()[-300:]}")


def _system(text: str, name: str, target: Path, speed: float) -> Path:
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as tmp:
            aiff = Path(tmp) / "speech.aiff"
            cmd = ["say", "-o", str(aiff), "-r", str(int(180 * speed))]
            if name and name != "default":
                cmd += ["-v", name]
            _run(cmd + [text])
            _run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", str(aiff), str(target)])
        return target
    if os.name == "nt":
        script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$s.Rate = {max(-10, min(10, round((speed - 1) * 10)))}; "
                  f"$s.SetOutputToWaveFile('{target}'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
        _run(["powershell", "-NoProfile", "-Command", script], text)
        return target
    engine = shutil.which("espeak-ng") or shutil.which("espeak")
    if not engine:
        raise RuntimeError("no speech engine on this computer: install espeak-ng, or Piper, or start ELI v3")
    _run([engine, "-v", name or "en-us", "-s", str(int(165 * speed)), "-w", str(target), "--stdin"], text)
    return target


def _respeed(path: Path, speed: float) -> Path:
    """Faster or slower speech, by resampling (it changes the pitch a little)."""
    from eli_creation.production.audio import RATE, read_wav, write_wav

    data = read_wav(path)
    import numpy as np

    n = max(1, int(len(data) / speed))
    x_old = np.linspace(0, 1, len(data))
    x_new = np.linspace(0, 1, n)
    out = np.stack([np.interp(x_new, x_old, data[:, c]) for c in range(2)], axis=1)
    return write_wav(path, out, RATE)


def voice_record(voice_id: str) -> dict[str, str]:
    """The voice as a provenance entry: what spoke, under what licence."""
    source, _, name = voice_id.partition(":")
    if source == "eli":
        lic = "Apache-2.0" if name[:3] in ("af_", "am_", "bf_", "bm_") else ""
        return {"id": f"voice:eli:{name}", "title": f"ELI v3 voice {name}", "licence": lic}
    if source == "piper":
        return {"id": f"voice:piper:{Path(name).stem}", "title": f"Piper {Path(name).stem}", "licence": ""}
    return {"id": f"voice:system:{name}", "title": f"System speech ({name})", "licence": "system-speech"}
