"""The parent side: start a worker process, load a model in it, call it, end it."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import eli_creation
from eli_creation.layout import Layout
from eli_creation.models.catalogue import ModelSpec
from eli_creation.runtimes.protocol import decode, encode
from eli_creation.tiers import Machine


class WorkerError(RuntimeError):
    pass


def runtime_python(layout: Layout, runtime: str) -> Path:
    folder = layout.runtimes / runtime
    return folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _package_parent() -> str:
    """The folder that holds the eli_creation package (a frozen copy ships its sources as files)."""
    return str(Path(eli_creation.__file__).resolve().parents[1])


class ProcessWorker:
    """One worker process holding one specialist model on one device."""

    def __init__(
        self,
        spec: ModelSpec,
        device: str,
        *,
        layout: Layout,
        machine: Machine,
        load_timeout: float = 900.0,
        call_timeout: float = 3600.0,
    ) -> None:
        self.spec = spec
        self.device = device
        self.layout = layout
        self.machine = machine
        self.load_timeout = load_timeout
        self.call_timeout = call_timeout
        self._proc: subprocess.Popen[str] | None = None
        self._replies: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._next_id = 0
        self._lock = threading.Lock()  # one request at a time per worker

    # ── starting ──────────────────────────────────────────────────────────
    def command(self) -> list[str]:
        if self.spec.runtime in ("", "same"):
            if getattr(sys, "frozen", False):
                # the console program beside the windowed one (packaging/pyinstaller): eli-creation
                cli = Path(sys.executable).with_name("eli-creation" + (".exe" if os.name == "nt" else ""))
                return [str(cli if cli.is_file() else Path(sys.executable)), "_worker"]
            return [sys.executable, "-m", "eli_creation.runtimes.worker"]
        python = runtime_python(self.layout, self.spec.runtime)
        if not python.is_file():
            raise WorkerError(
                f"the {self.spec.runtime} runtime that {self.spec.title} runs in is not installed "
                f"here (expected {python}). Runtimes are set up by a later release; a developer "
                f"can make one with: python -m venv {python.parent.parent}"
            )
        return [str(python), "-m", "eli_creation.runtimes.worker"]

    def _accelerator(self):
        if not self.device.startswith("gpu:"):
            return None
        index = int(self.device.split(":", 1)[1])
        return next((a for a in self.machine.accelerators if a.index == index), None)

    def environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env["ELI_CREATION_WORKER"] = "1"
        parent = _package_parent()
        env["PYTHONPATH"] = parent + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        acc = self._accelerator()
        # The worker sees only the card it was placed on, as device 0, whatever its vendor.
        if acc is not None and acc.vendor == "nvidia":
            env["CUDA_VISIBLE_DEVICES"] = str(acc.index)
        elif acc is not None and acc.vendor == "amd":
            env["HIP_VISIBLE_DEVICES"] = env["ROCR_VISIBLE_DEVICES"] = str(acc.index)
        elif self.device == "cpu":
            env["CUDA_VISIBLE_DEVICES"] = ""
        return env

    def device_info(self) -> dict[str, Any]:
        acc = self._accelerator()
        if acc is None:
            return {"device": "cpu", "backends": ["cpu"], "vendor": "", "kind": "cpu", "memory_mb": 0}
        return {
            "device": self.device,
            "backends": list(acc.backends),
            "vendor": acc.vendor,
            "kind": acc.kind,
            "memory_mb": acc.memory_mb,
        }

    def _reader(self, stream) -> None:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                self._replies.put(decode(line))
            except ValueError:
                continue
        self._replies.put(None)  # the worker ended

    def start(self) -> None:
        self.layout.logs.mkdir(parents=True, exist_ok=True)
        log = open(self.layout.logs / f"worker-{self.spec.id}.log", "a", encoding="utf-8")  # noqa: SIM115
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            self._proc = subprocess.Popen(
                self.command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=self.environment(),
                creationflags=flags,
            )
        except OSError as exc:
            raise WorkerError(f"the worker for {self.spec.title} could not start: {exc}") from exc
        finally:
            log.close()  # the child holds its own handle
        threading.Thread(
            target=self._reader, args=(self._proc.stdout,), name=f"worker-{self.spec.id}", daemon=True
        ).start()

    def _files_dir(self) -> Path:
        """models/<folder>/<model id>, or the same model in ELI v3's folders (models/folders.py)."""
        from eli_creation.models import folders

        task = self.spec.tasks[0] if self.spec.tasks else "other"
        found = folders.find_model(self.layout.models, self.spec.id, task)
        return found or folders.model_dir(self.layout.models, self.spec.id, task)

    def start_and_load(self) -> dict[str, Any]:
        self.start()
        self.request("hello", timeout=120)
        result = self.request(
            "load",
            adapter=self.spec.adapter,
            # where the model's files are: models/<id> in the data folder
            spec={**self.spec.to_dict(), "files_dir": str(self._files_dir())},
            device=self.device_info(),
            timeout=self.load_timeout,
        )
        return result if isinstance(result, dict) else {}

    # ── talking ───────────────────────────────────────────────────────────
    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def request(self, op: str, *, timeout: float | None = None, **fields: Any) -> Any:
        with self._lock:
            if not self.alive or self._proc is None or self._proc.stdin is None:
                raise WorkerError(f"the worker for {self.spec.title} is not running")
            self._next_id += 1
            ident = self._next_id
            try:
                self._proc.stdin.write(encode({"id": ident, "op": op, **fields}))
                self._proc.stdin.flush()
            except OSError as exc:
                raise WorkerError(f"the worker for {self.spec.title} stopped: {exc}") from exc
            wait = self.call_timeout if timeout is None else timeout
            while True:
                try:
                    reply = self._replies.get(timeout=wait)
                except queue.Empty as exc:
                    self.kill()
                    raise WorkerError(f"{self.spec.title} did not answer within {wait:.0f} s; its worker was stopped") from exc
                if reply is None:
                    raise WorkerError(
                        f"the worker for {self.spec.title} ended (see {self.layout.logs / f'worker-{self.spec.id}.log'})"
                    )
                if reply.get("id") != ident:
                    continue  # a late answer to a request that timed out
                if not reply.get("ok"):
                    raise WorkerError(str(reply.get("error") or "the worker reported an error"))
                return reply.get("result")

    def call(self, method: str, args: dict[str, Any], *, timeout: float | None = None) -> Any:
        return self.request("call", method=method, args=args, timeout=timeout)

    # ── ending ────────────────────────────────────────────────────────────
    def stop(self) -> None:
        if self._proc is None:
            return
        if self.alive:
            try:
                self.request("shutdown", timeout=15)
            except WorkerError:
                pass
        try:
            self._proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.kill()
        self._proc = None

    def kill(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
