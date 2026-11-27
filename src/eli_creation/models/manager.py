"""Which models are loaded, where, and for how long.

The rule: **the main model stays loaded; every specialist is loaded when a job needs it and
unloaded when it has been idle.** A job asks for a specialist with ``use``:

    with manager.use("image.ssd-1b") as model:
        paths = model.call("generate", {"prompt": ..., "out_dir": ...})

``use`` loads the model if it is not loaded (in a worker process of its own, on the device the
planner chose), marks it busy for the job, and marks it idle again afterwards. A background reaper
ends the workers of models idle for longer than the policy allows, which returns all of their
memory. Before loading, the planner finds room for the model:

  1. on an accelerator the model can use, beside what is loaded there now;
  2. by unloading idle specialists on that accelerator, the longest idle first;
  3. on the processor, when the model may run there and system memory has room;
  4. by having the main model step aside for this job, only if the person allowed it; it is
     loaded again as soon as the job ends;
  5. otherwise not at all: the job is refused with the reason, and nothing is unloaded.

The main model is never unloaded by the planner in any other case.

Memory figures are the catalogue's estimates against what the machine reported free when
Creation Station started (so ELI v3's model, ELI VR and other programs are already counted).
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from eli_creation.models.catalogue import Catalogue, ModelSpec
from eli_creation.models.main import MainModel
from eli_creation.models.residency import Policy
from eli_creation.tiers import Machine

log = logging.getLogger("eli_creation.models")

STATES = ("unloaded", "loading", "ready", "busy", "unloading", "failed")


class Worker(Protocol):
    def start_and_load(self) -> dict[str, Any]: ...
    def call(self, method: str, args: dict[str, Any], *, timeout: float | None = None) -> Any: ...
    def stop(self) -> None: ...
    @property
    def alive(self) -> bool: ...


Launcher = Callable[[ModelSpec, str], Worker]


class Refused(RuntimeError):
    """A specialist cannot be loaded on this machine now; the message says why."""


class LoadFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class Placement:
    device: str  # "gpu:<index>" or "cpu"
    memory_mb: int
    evict: tuple[str, ...] = ()
    swap_main: bool = False
    note: str = ""


@dataclass
class Resident:
    spec: ModelSpec
    device: str
    memory_mb: int
    worker: Worker
    state: str = "loading"
    users: int = 0
    last_used: float = 0.0
    swapped_main: bool = False


@dataclass(frozen=True)
class ModelStatus:
    id: str
    title: str
    role: str
    state: str
    device: str = ""
    memory_mb: int = 0
    idle_seconds: float = 0.0
    detail: str = ""


@dataclass
class _Failure:
    reason: str
    at: float


class Handle:
    """A loaded specialist, for the length of one job."""

    def __init__(self, resident: Resident) -> None:
        self._resident = resident

    @property
    def spec(self) -> ModelSpec:
        return self._resident.spec

    @property
    def device(self) -> str:
        return self._resident.device

    def call(self, method: str, args: dict[str, Any] | None = None, *, timeout: float | None = None) -> Any:
        return self._resident.worker.call(method, dict(args or {}), timeout=timeout)


class ModelManager:
    def __init__(
        self,
        machine: Machine,
        catalogue: Catalogue,
        policy: Policy,
        *,
        main: MainModel,
        launcher: Launcher,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.machine = machine
        self.catalogue = catalogue
        self.policy = policy
        self.main = main
        self._launch = launcher
        self._clock = clock
        self._residents: dict[str, Resident] = {}
        self._failures: dict[str, _Failure] = {}
        self._cond = threading.Condition(threading.RLock())
        self._load_lock = threading.Lock()  # one load or unload sequence at a time
        self._listeners: list[Callable[[], None]] = []
        self._reaper: threading.Thread | None = None
        self._stop_reaper = threading.Event()

    # ── listening ─────────────────────────────────────────────────────────
    def on_change(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _changed(self) -> None:
        self._cond.notify_all()
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                log.debug("a model listener failed", exc_info=True)

    # ── what is where ─────────────────────────────────────────────────────
    def resident_ids(self) -> list[str]:
        with self._cond:
            return [k for k, r in self._residents.items() if r.state in ("loading", "ready", "busy")]

    def status(self) -> list[ModelStatus]:
        now = self._clock()
        out = [
            ModelStatus(
                id="main",
                title=self.main.name,
                role="main",
                state=self.main.state,
                device=self.main.device,
                memory_mb=self.main.memory_mb,
                detail="" if self.main.available else self.main.why_unavailable,
            )
        ]
        with self._cond:
            for spec in self.catalogue.models:
                if spec.role != "specialist":
                    continue
                r = self._residents.get(spec.id)
                if r is not None:
                    idle = now - r.last_used if r.state == "ready" else 0.0
                    out.append(ModelStatus(spec.id, spec.title, spec.role, r.state, r.device, r.memory_mb, idle))
                elif spec.id in self._failures:
                    out.append(ModelStatus(spec.id, spec.title, spec.role, "failed",
                                           detail=self._failures[spec.id].reason))
                else:
                    out.append(ModelStatus(spec.id, spec.title, spec.role, "unloaded"))
        return out

    def _capacity(self, device: str) -> int:
        """What a device had free at start-up, less the reserve and the main model on it."""
        reserve = self.policy.reserve_mb
        main_here = self.main.memory_mb if self.main.device == device and self.main.available else 0
        if device == "cpu":
            # unified memory is system memory: what is placed on the GPU comes out of it too
            unified = sum(
                r.memory_mb
                for r in self._residents.values()
                if r.device.startswith("gpu:") and self._is_unified(r.device)
            )
            return self.machine.available_ram_mb - reserve - main_here - unified
        acc = self._accelerator(device)
        if acc is None:
            return 0
        return acc.usable_mb - reserve - main_here

    def _accelerator(self, device: str):
        if not device.startswith("gpu:"):
            return None
        index = int(device.split(":", 1)[1])
        return next((a for a in self.machine.accelerators if a.index == index), None)

    def _is_unified(self, device: str) -> bool:
        acc = self._accelerator(device)
        return acc is not None and acc.kind == "unified"

    def _used(self, device: str) -> int:
        return sum(r.memory_mb for r in self._residents.values() if r.device == device)

    def _idle_on(self, device: str | None) -> list[Resident]:
        idle = [
            r for r in self._residents.values()
            if r.state == "ready" and r.users == 0 and (device is None or r.device == device)
        ]
        return sorted(idle, key=lambda r: r.last_used)

    # ── planning ──────────────────────────────────────────────────────────
    def plan(self, spec: ModelSpec) -> Placement:
        """Where this specialist would be loaded now, and what would be unloaded for it.
        Raises Refused with the reason when it cannot be placed."""
        if spec.role != "specialist":
            raise Refused(f"{spec.title} is not a specialist model")
        if spec.planned:
            raise Refused(f"{spec.title} is planned for a later release")
        ok, why = spec.runs_here(self.machine)
        if not ok:
            raise Refused(f"{spec.title} {why}")
        with self._cond:
            # the count limit first: the longest-idle specialists make way
            over = len(self.resident_ids()) + 1 - self.policy.max_resident_specialists
            by_count = [r.spec.id for r in self._idle_on(None)][: max(0, over)]
            if over > len(by_count):
                raise Refused(
                    f"{self.policy.max_resident_specialists} specialist model(s) may be loaded at "
                    "once on this machine and all are working; this job waits for one to finish"
                )
            gpu_devices = [
                f"gpu:{a.index}"
                for a in sorted(self.machine.accelerators, key=lambda a: -a.usable_mb)
                if set(a.backends) & set(spec.backends)
            ]
            for device in gpu_devices:
                placed = self._fit(spec.memory_mb, device, by_count)
                if placed is not None:
                    return placed
            if spec.cpu_ok:
                need = spec.ram_mb or spec.memory_mb
                placed = self._fit(need, "cpu", by_count, note="on the processor: slower")
                if placed is not None:
                    return placed
            if self.policy.allow_main_swap and self.main.available and self.main.device in gpu_devices:
                device = self.main.device
                every_idle = tuple(dict.fromkeys([*by_count, *(r.spec.id for r in self._idle_on(device))]))
                room = self._capacity(device) + self.main.memory_mb - self._used(device) + sum(
                    self._residents[i].memory_mb for i in every_idle if self._residents[i].device == device
                )
                if room >= spec.memory_mb:
                    return Placement(device, spec.memory_mb, every_idle, swap_main=True,
                                     note="the main model steps aside for this job")
        best = max(self.machine.accelerators, key=lambda a: a.usable_mb, default=None)
        where = f"{best.describe()}" if best is not None else "no graphics card"
        hint = "" if self.policy.allow_main_swap else (
            " Settings → Models can let the main model step aside for jobs like this on this machine."
        )
        raise Refused(
            f"{spec.title} needs about {spec.memory_mb / 1024:.1f} GB and there is not that much free "
            f"beside the main model ({where}).{hint}"
        )

    def _fit(self, need: int, device: str, already: list[str], note: str = "") -> Placement | None:
        free = self._capacity(device) - self._used(device)
        freed = sum(self._residents[i].memory_mb for i in already if self._residents[i].device == device)
        if free + freed >= need:
            return Placement(device, need, tuple(already), note=note)
        evict = list(already)
        for r in self._idle_on(device):
            if r.spec.id in evict:
                continue
            evict.append(r.spec.id)
            freed += r.memory_mb
            if free + freed >= need:
                return Placement(device, need, tuple(evict), note=note)
        return None

    # ── using ─────────────────────────────────────────────────────────────
    @contextlib.contextmanager
    def use(self, model_id: str) -> Iterator[Handle]:
        resident = self._acquire(model_id)
        try:
            yield Handle(resident)
        finally:
            self._release(resident)

    def _take(self, model_id: str) -> Resident | None:
        """The resident, marked busy, if it is loaded; waits while it is loading or unloading."""
        with self._cond:
            while True:
                r = self._residents.get(model_id)
                if r is None:
                    return None
                if r.state in ("ready", "busy"):
                    r.users += 1
                    r.state = "busy"
                    self._changed()
                    return r
                self._cond.wait(timeout=1.0)

    def _acquire(self, model_id: str) -> Resident:
        spec = self.catalogue.get(model_id)
        held = self._take(model_id)
        if held is not None:
            return held
        with self._load_lock:
            held = self._take(model_id)  # loaded by another job while this one waited
            if held is not None:
                return held
            with self._cond:
                placement = self.plan(spec)
            for victim in placement.evict:
                self._stop(victim)
            if placement.swap_main:
                log.info("the main model steps aside for %s", spec.id)
                self.main.suspend()
            try:
                worker = self._launch(spec, placement.device)
            except Exception as exc:
                if placement.swap_main:
                    self.main.resume()
                raise LoadFailed(str(exc)) from exc
            resident = Resident(spec, placement.device, placement.memory_mb, worker,
                                last_used=self._clock(), swapped_main=placement.swap_main)
            with self._cond:
                self._failures.pop(model_id, None)
                self._residents[model_id] = resident
                self._changed()
            log.info("loading %s on %s (%s)", spec.id, placement.device, placement.note or "fits")
            try:
                info = worker.start_and_load()
            except Exception as exc:
                with self._cond:
                    self._residents.pop(model_id, None)
                    self._failures[model_id] = _Failure(str(exc), self._clock())
                    self._changed()
                try:
                    worker.stop()
                finally:
                    if placement.swap_main:
                        self.main.resume()
                raise LoadFailed(f"{spec.title} could not be loaded: {exc}") from exc
            with self._cond:
                reported = int((info or {}).get("memory_mb") or 0)
                if reported > 0:
                    resident.memory_mb = reported
                resident.state, resident.users = "busy", 1
                self._changed()
            return resident

    def _release(self, resident: Resident) -> None:
        with self._cond:
            resident.users = max(0, resident.users - 1)
            resident.last_used = self._clock()
            if resident.users == 0 and resident.state == "busy":
                resident.state = "ready"
            self._changed()
            done = resident.users == 0
        if done and (resident.swapped_main or self.policy.idle_unload_seconds <= 0):
            # a model the main model stepped aside for goes as soon as its job is done
            self.unload(resident.spec.id)

    # ── unloading ─────────────────────────────────────────────────────────
    def _stop(self, model_id: str) -> None:
        """End one specialist's worker. Called with the load lock held."""
        with self._cond:
            r = self._residents.get(model_id)
            if r is None or r.users > 0:
                return
            r.state = "unloading"
            self._changed()
        try:
            r.worker.stop()
        finally:
            with self._cond:
                self._residents.pop(model_id, None)
                self._changed()
            log.info("unloaded %s", model_id)
            if r.swapped_main:
                log.info("the main model comes back")
                self.main.resume()

    def unload(self, model_id: str) -> bool:
        with self._load_lock:
            with self._cond:
                r = self._residents.get(model_id)
                if r is None or r.users > 0:
                    return False
            self._stop(model_id)
            return True

    def unload_idle(self, now: float | None = None) -> list[str]:
        now = self._clock() if now is None else now
        with self._cond:
            stale = [
                r.spec.id for r in self._idle_on(None)
                if now - r.last_used >= self.policy.idle_unload_seconds
            ]
        return [model_id for model_id in stale if self.unload(model_id)]

    def unload_all(self) -> list[str]:
        with self._cond:
            ids = list(self._residents)
        return [model_id for model_id in ids if self.unload(model_id)]

    # ── the reaper ────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._reaper is not None:
            return
        self._stop_reaper.clear()
        every = max(1.0, min(10.0, self.policy.idle_unload_seconds / 4 or 1.0))

        def reap() -> None:
            while not self._stop_reaper.wait(every):
                try:
                    self.unload_idle()
                except Exception:
                    log.warning("unloading idle models failed", exc_info=True)

        self._reaper = threading.Thread(target=reap, name="eli-creation-model-reaper", daemon=True)
        self._reaper.start()

    def close(self) -> None:
        self._stop_reaper.set()
        if self._reaper is not None:
            self._reaper.join(timeout=5)
            self._reaper = None
        self.unload_all()
