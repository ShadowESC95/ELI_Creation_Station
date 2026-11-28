"""ELI v3 on this machine: found, and used for what it already does well.

When ELI v3's server runs on this computer it says where, in ``server.json`` in its own folder
(``eli/runtime/server_util.announce_port``), and answers on loopback without a token. Creation
Station then reaches the same ELI the person talks to everywhere else:

- **ELI itself**, through ``/v1/chat``: a turn of the owner's own conversation with ELI, in a
  Creation Station session, so ELI answers as itself, knows who it is talking to and follows the
  conversation (the web chat, the phone, ELI VR and the desktop are the same person to ELI v3);
- its **main model**, through the OpenAI-compatible ``/v1/chat/completions``, for the studios' own
  work (planning a film, writing a post): a model call, never stored as something the owner said;
- its **voices** (Kokoro and the others it has), through ``/v1/voice/voices`` and ``/v1/voice/tts``;
- its **ears** (local faster-whisper), through ``/v1/voice/stt``, to caption a recording.

ELI v3 loads and unloads those models itself. Only loopback is ever used: nothing leaves the
machine. Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PORT = 8081
_cache: dict[str, Any] = {"at": 0.0, "found": None}


def v3_folder() -> Path:
    """ELI v3's own per-user folder, where its running server leaves ``server.json``."""
    if os.environ.get("ELI_V3_HOME"):
        return Path(os.environ["ELI_V3_HOME"]).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "ELI_v3"


def _ports() -> list[int]:
    ports: list[int] = []
    env = os.environ.get("ELI_V3_PORT") or os.environ.get("ELI_API_PORT")
    if env and env.isdigit():
        ports.append(int(env))
    try:
        note = json.loads((v3_folder() / "server.json").read_text(encoding="utf-8"))
        if note.get("product") == "eli_v3" and int(note.get("port") or 0):
            ports.append(int(note["port"]))
    except (OSError, ValueError, TypeError):
        pass
    ports.append(DEFAULT_PORT)
    return list(dict.fromkeys(ports))


@dataclass(frozen=True)
class EliV3:
    base: str  # http://127.0.0.1:PORT
    token: str = ""

    def _request(self, path: str, *, body: bytes | None = None, content_type: str = "application/json",
                 timeout: float = 120.0) -> tuple[bytes, str]:
        headers = {"Content-Type": content_type}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=body, headers=headers,
                                     method="POST" if body is not None else "GET")
        with urllib.request.urlopen(req, timeout=timeout) as reply:  # noqa: S310 - loopback only
            return reply.read(), reply.headers.get("Content-Type", "")

    def json(self, path: str, payload: dict[str, Any] | None = None, *, timeout: float = 120.0) -> Any:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        raw, _ = self._request(path, body=body, timeout=timeout)
        return json.loads(raw.decode("utf-8") or "null")

    # ── what ELI v3 offers ──
    def models(self) -> list[str]:
        found = self.json("/v1/models", timeout=5)
        data = found.get("data", []) if isinstance(found, dict) else []
        return [str(m.get("id")) for m in data if isinstance(m, dict) and m.get("id")]

    def voices(self) -> tuple[list[str], str]:
        found = self.json("/v1/voice/voices", timeout=10)
        if not isinstance(found, dict) or not found.get("ok"):
            return [], ""
        return [str(v) for v in found.get("voices", [])], str(found.get("active") or "")

    def chat(self, message: str, session_id: str, *, timeout: float = 600.0) -> str:
        """ELI's own reply to the owner, as a turn of their conversation (``/v1/chat``)."""
        found = self.json("/v1/chat", {"message": message, "session_id": session_id}, timeout=timeout)
        if not isinstance(found, dict) or "response" not in found:
            raise RuntimeError("ELI v3 did not answer")
        return str(found.get("response") or "").strip()

    def speak(self, text: str, voice: str = "", *, timeout: float = 300.0) -> bytes:
        """A WAV of ``text`` in one of ELI v3's voices."""
        raw, kind = self._request("/v1/voice/tts", body=json.dumps({"text": text, "voice": voice or None}).encode(),
                                  timeout=timeout)
        if "audio" not in kind and not raw.startswith(b"RIFF"):
            raise RuntimeError("ELI v3 did not answer with audio")
        return raw

    def transcribe(self, wav: bytes, *, timeout: float = 600.0) -> str:
        raw, _ = self._request("/v1/voice/stt?ext=wav", body=wav, content_type="audio/wav", timeout=timeout)
        answer = json.loads(raw.decode("utf-8") or "{}")
        if not answer.get("ok"):
            raise RuntimeError(str(answer.get("error") or "ELI v3 could not transcribe it"))
        return str(answer.get("text") or "")


def _token() -> str:
    return os.environ.get("ELI_V3_TOKEN", "").strip()


def find(*, fresh: bool = False, timeout: float = 0.6) -> EliV3 | None:
    """ELI v3's server on this machine, if one answers (remembered for 20 seconds)."""
    if not fresh and time.monotonic() - float(_cache["at"]) < 20:
        return _cache["found"]  # type: ignore[no-any-return]
    found: EliV3 | None = None
    for port in _ports():
        base = f"http://127.0.0.1:{port}"
        try:
            with urllib.request.urlopen(base + "/api", timeout=timeout) as reply:  # noqa: S310 - loopback only
                about = json.loads(reply.read().decode("utf-8") or "{}")
            if isinstance(about, dict) and about.get("product") == "eli_v3":  # ELI v2 answers here too
                found = EliV3(base, _token())
                break
        except (OSError, ValueError, urllib.error.URLError):
            continue
    _cache.update(at=time.monotonic(), found=found)
    return found


def forget() -> None:
    _cache.update(at=0.0, found=None)
