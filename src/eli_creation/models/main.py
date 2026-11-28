"""The main model: the one language model that stays loaded while Creation Station runs.

It writes posts and scripts, designs games, codes, turns a short request into a full prompt for a
specialist, and is ELI's voice in the studio. It is built from the adapters ELI Legal already ships
(reused, adapters/inference and adapters/eli_v3), which size a GGUF model to the memory free now,
switch on a graphics pack that has shown it works, and refuse a model server on another machine
unless its host is approved:

    eli_v3   opened by ELI v3: the model ELI v3 has loaded, through its raw calls. Nothing is loaded
             twice, and nothing passes through ELI v3's chat history or memory.
    gguf     on its own: a GGUF file, loaded once at start-up and kept loaded.
    openai   on its own: a model server (Ollama, LM Studio, llama.cpp's server, vLLM).
    none     no model: what needs one says so; everything else still works.

The main model is never unloaded to make room for a specialist, unless the person allowed it to
step aside (Settings → Models), and then only for that one job (models/manager.py).
"""

from __future__ import annotations

import inspect
import logging
import os
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from eli_creation.settings import Settings

log = logging.getLogger("eli_creation.main")


class MainModelUnavailable(RuntimeError):
    pass


class MainModel:
    """One main model, whatever it runs on. ``memory_mb`` and ``device`` are what it holds of this
    machine, for the specialist planner; a model in another process (ELI v3's, a server's) holds
    nothing of ours, and its memory is already gone from what the machine reports free."""

    def __init__(self, backend: Any, *, source: str, name: str, why: str = "") -> None:
        self.backend = backend
        self.source = source
        self.name = name
        self._why = why
        self._state = "ready" if source in ("eli_v3", "openai") and not why else ("unavailable" if why else "unloaded")
        self.via = source  # where it comes from: eli_v3, eli_v3_server, gguf, openai, none
        self._error = ""
        self._lock = threading.Lock()
        self._settled = threading.Event()  # set while it is not loading
        self._settled.set()
        self.stepped_aside_for = ""
        self.memory_mb = 0
        self.device = ""
        self.report: dict[str, Any] = {}

    # ── what it is now ────────────────────────────────────────────────────
    @property
    def available(self) -> bool:
        return self._state == "ready" and bool(getattr(self.backend, "available", False))

    @property
    def state(self) -> str:
        return self._state

    @property
    def why_unavailable(self) -> str:
        if self._why:
            return self._why
        if self._state == "loading":
            return f"the main model ({self.name}) is still loading"
        if self._state == "stepped_aside":
            return (f"the main model ({self.name}) has stepped aside to give "
                    f"{self.stepped_aside_for or 'a job'} its memory, and is loaded again as soon as that is done")
        if self._error:
            return f"the main model could not be loaded: {self._error}"
        return f"the main model ({self.name}) is not loaded"

    # ── loading ───────────────────────────────────────────────────────────
    def load(self) -> None:
        """Load it now, if it is a file (blocking: call it on a background thread)."""
        try:
            self._load()
        finally:
            self._settled.set()

    def _load(self) -> None:
        if self.source != "gguf" or self._why:
            return
        with self._lock:
            if self._state == "ready":
                return
            self._state, self._error = "loading", ""
            try:
                report = self.backend.warm()
                self.report = report.as_dict() if hasattr(report, "as_dict") else {}
                on_card = int(self.report.get("layers_on_card", 0) or 0)
                total = max(1, int(self.report.get("layers_total", 1) or 1))
                size_mb = self.backend.path.stat().st_size // 2**20
                # the share of the weights on the card, and the cache and buffers that follow them
                self.memory_mb = int(size_mb * on_card / total * 1.15) if on_card else 0
                self.device = "gpu:0" if on_card else "cpu"
                self._state = "ready"
            except Exception as exc:  # out of memory, a damaged file, no llama.cpp
                self._error = f"{type(exc).__name__}: {str(exc)[:240]}"
                self._state = "failed"
                log.warning("the main model did not load: %s", self._error)

    def load_in_background(self) -> threading.Thread:
        self._settled.clear()  # anyone waiting for it waits for this load
        thread = threading.Thread(target=self.load, name="eli-creation-main-model", daemon=True)
        thread.start()
        return thread

    def unload(self) -> None:
        if self.source != "gguf":
            return
        from eli_creation.adapters.inference import gguf

        with self._lock:
            gguf.release()
            self._state, self.memory_mb, self.device = "unloaded", 0, ""

    def suspend(self, for_what: str = "") -> None:
        """Step aside for one job that needs its memory (Settings → Models allows it; on by
        default). It is loaded again when that job's model is unloaded (resume)."""
        self.unload()
        if self.source == "gguf":
            self._state, self.stepped_aside_for = "stepped_aside", for_what

    def resume(self, *, wait: bool = False) -> None:
        """Load it again after stepping aside: in the background, so the job's result is shown at
        once and ELI comes back a moment later (``wait`` to load it here instead)."""
        self.stepped_aside_for = ""
        if wait:
            self.load()
        else:
            self.load_in_background()

    def wait_settled(self, timeout: float | None = None) -> bool:
        """Wait until it is not loading (loaded, failed or unloaded). Returns False on timeout."""
        return self._settled.wait(timeout)

    # ── using ─────────────────────────────────────────────────────────────
    def generate(self, *, system: str, prompt: str, max_tokens: int = 1024, temperature: float = 0.7,
                 json_mode: bool = False, wait: float = 600.0) -> str:
        """``wait``: how long to wait for the main model while it has stepped aside for a job, or is
        loading (0: not at all). Every caller runs off the window's thread."""
        if wait > 0 and self._state in ("stepped_aside", "loading"):
            self._wait_back(wait)
        if not self.available:
            raise MainModelUnavailable(self.why_unavailable)
        kwargs: dict[str, Any] = {"system": system, "prompt": prompt, "max_tokens": max_tokens,
                                  "json_mode": json_mode}
        if "temperature" in inspect.signature(self.backend.generate).parameters:
            kwargs["temperature"] = temperature
        try:
            return str(self.backend.generate(**kwargs))
        except Exception as exc:
            raise MainModelUnavailable(f"{type(exc).__name__}: {str(exc)[:240]}") from exc

    def _wait_back(self, timeout: float) -> None:
        import time

        deadline = time.monotonic() + timeout
        while self._state in ("stepped_aside", "loading") and time.monotonic() < deadline:
            time.sleep(0.25)

    def as_generate(self, *, system: str = "", temperature: float = 0.2):
        """A ``generate(prompt) -> str`` for ELI v3's coding agent (eli_creation.coding), which takes
        its model as an injected function."""

        def generate(prompt: str, **options: Any) -> str:
            return self.generate(system=system or "You are a careful senior software engineer.",
                                 prompt=prompt, max_tokens=int(options.get("max_tokens", 2048)),
                                 temperature=float(options.get("temperature", temperature)))

        return generate

    def describe(self) -> dict[str, Any]:
        return {"source": self.source, "name": self.name, "state": self.state, "available": self.available,
                "why": "" if self.available else self.why_unavailable, "memory_mb": self.memory_mb,
                "device": self.device, "load": self.report}


def make_main_model(settings: Settings, *, hosted: bool, network: Any = None) -> MainModel:
    from eli_creation.adapters.inference.local import NullInference, OpenAICompatInference

    source = settings.main_model_source
    found_path = ""
    if source == "auto":
        if hosted:
            source = "eli_v3"
        else:
            link = _running_eli_v3()
            if link is not None:
                return link
            if settings.main_model_path:
                source = "gguf"
            else:
                found_path = best_local_gguf(settings)
                source = "gguf" if found_path else "none"
    if source == "eli_v3":
        if not hosted:
            return MainModel(NullInference(), source="none", name="no main model",
                             why="ELI v3's model is only there when ELI v3 opens Creation Station")
        from eli_creation.adapters.eli_v3.inference import EliV3Inference

        hosted_backend = EliV3Inference()
        return MainModel(hosted_backend, source="eli_v3", name=f"ELI v3 ({hosted_backend.model_id})")
    if source == "gguf":
        from eli_creation.adapters.inference.gguf import GgufInference

        try:
            gguf_backend = GgufInference(found_path or settings.main_model_path, working_ctx=settings.main_context)
        except Exception as exc:
            return MainModel(NullInference(), source="none", name="no main model", why=str(exc))
        return MainModel(gguf_backend, source="gguf", name=gguf_backend.path.name)
    if source == "openai":
        try:
            server_backend = OpenAICompatInference(base_url=settings.main_model_url,
                                                   model=settings.main_model_name, network=network)
        except Exception as exc:
            host = urlparse(settings.main_model_url).hostname or settings.main_model_url
            return MainModel(NullInference(), source="none", name="no main model",
                             why=f"the model server at {host} cannot be used: {exc}")
        return MainModel(server_backend, source="openai", name=server_backend.model_id)
    return MainModel(NullInference(), source="none", name="no main model",
                     why="no main model yet: start ELI v3 on this machine, or choose a GGUF file or a "
                         "model server in Settings")


def _running_eli_v3() -> MainModel | None:
    """ELI v3's own model, when its server runs on this machine: the same ELI as everywhere else."""
    from eli_creation import eli_link
    from eli_creation.adapters.inference.local import OpenAICompatInference

    link = eli_link.find()
    if link is None:
        return None
    try:
        names = link.models()
        backend = OpenAICompatInference(base_url=link.base + "/v1", model=names[0] if names else "eli",
                                        api_key=link.token or None)
    except Exception:
        return None
    main = MainModel(backend, source="openai", name="ELI v3 on this machine")
    main.via = "eli_v3_server"
    return main


def best_local_gguf(settings: Settings) -> str:
    """A chat GGUF already on this machine for ELI to think with: the catalogue's choice for this
    machine's tier where it is here, otherwise the smallest that leaves the machine room to work."""
    from eli_creation.adapters.inference.gguf import discover

    hub = Path(os.environ.get("HF_HUB_CACHE") or Path.home() / ".cache" / "huggingface" / "hub")
    try:
        found = [m for m in discover(extra=str(hub)) if 1.5e9 < m.size]
    except OSError:
        return ""
    if not found:
        return ""
    try:
        import psutil

        budget = psutil.virtual_memory().available * 0.6
    except Exception:
        budget = 8e9
    named = _named_links(hub)  # the Hugging Face cache keeps files under hashes; their names are links
    # Only a general assistant model is taken unasked; anything else found (a coder, an
    # uncensored or special-purpose model) is offered in the models list for the person to choose.
    for word in GENERAL_MODELS:
        for model in found:
            name = named.get(str(model.path), model.path).name.lower()
            if word in name and model.size < budget and not any(w in name for w in NOT_GENERAL):
                return str(named.get(str(model.path), model.path))
    return ""


GENERAL_MODELS = ("qwen3-8b", "qwen3-4b", "qwen3-14b", "llama-3.1-8b-instruct", "llama-3.2-3b-instruct",
                  "qwen2.5-7b-instruct", "mistral-7b-instruct", "gemma-3", "phi-4")
NOT_GENERAL = ("uncensored", "abliterated", "coder", "offensive", "heretic", "nsfw", "roleplay")


def local_ggufs() -> list[tuple[str, float]]:
    """Every chat GGUF found on this machine (with the Hugging Face cache), by name, in GB."""
    from eli_creation.adapters.inference.gguf import discover

    hub = Path(os.environ.get("HF_HUB_CACHE") or Path.home() / ".cache" / "huggingface" / "hub")
    named = _named_links(hub)
    try:
        found = discover(extra=str(hub))
    except OSError:
        return []
    return [(str(named.get(str(m.path), m.path)), round(m.size / 1e9, 1)) for m in found if m.size > 1.5e9]


def _named_links(hub: Path) -> dict[str, Path]:
    """Each GGUF in the Hugging Face cache by its real file, to the link that carries its name."""
    out: dict[str, Path] = {}
    if not hub.is_dir():
        return out
    for link in hub.glob("models--*/snapshots/*/**/*.gguf"):
        try:
            out[str(link.resolve())] = link
        except OSError:
            continue
    return out
