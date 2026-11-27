"""The job queue: work runs off the window's thread, in three lanes, so a long render never
blocks a post being written.

    main    work for the main model (it answers one request at a time)
    gpu     work for a specialist model (one model's job at a time; the manager loads it)
    light   work with no model (the procedural renderer, editing, exports)
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("eli_creation.jobs")

LANES = ("main", "gpu", "light")


class Cancelled(Exception):
    pass


@dataclass
class Job:
    engine: str
    tab: str
    request: dict[str, Any]
    lane: str = "light"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: str = "queued"  # queued | running | done | failed | cancelled
    progress: float = 0.0
    message: str = ""
    assets: list[Any] = field(default_factory=list)
    text: str = ""  # what a job that writes (a post, a design, code) said
    error: str = ""
    created: float = field(default_factory=time.time)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def finished(self) -> bool:
        return self.state in ("done", "failed", "cancelled")

    def cancel(self) -> None:
        self._cancel.set()

    def check(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()


Runner = Callable[[Job, Callable[[float, str], None]], None]


class JobQueue:
    def __init__(self, run: Runner) -> None:
        self._run = run
        self._queues: dict[str, queue.Queue[Job]] = {lane: queue.Queue() for lane in LANES}
        self._jobs: dict[str, Job] = {}
        self._listeners: list[Callable[[Job], None]] = []
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        for lane in LANES:
            thread = threading.Thread(target=self._worker, args=(lane,), name=f"eli-creation-{lane}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def on_change(self, callback: Callable[[Job], None]) -> None:
        self._listeners.append(callback)

    def _changed(self, job: Job) -> None:
        for callback in list(self._listeners):
            try:
                callback(job)
            except Exception:
                log.debug("a job listener failed", exc_info=True)

    def submit(self, job: Job) -> Job:
        self._jobs[job.id] = job
        self._queues[job.lane if job.lane in LANES else "light"].put(job)
        self._changed(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def jobs(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)

    def cancel(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is not None and not job.finished:
            job.cancel()
            if job.state == "queued":
                job.state = "cancelled"
                self._changed(job)

    def wait(self, job: Job, timeout: float = 600.0) -> Job:
        deadline = time.monotonic() + timeout
        while not job.finished and time.monotonic() < deadline:
            time.sleep(0.05)
        return job

    def _worker(self, lane: str) -> None:
        q = self._queues[lane]
        while not self._stop.is_set():
            try:
                job = q.get(timeout=0.5)
            except queue.Empty:
                continue
            if job.state == "cancelled":
                continue
            job.state = "running"
            self._changed(job)

            def progress(fraction: float, message: str = "", job: Job = job) -> None:
                job.check()
                job.progress = max(0.0, min(1.0, float(fraction)))
                job.message = message or job.message
                self._changed(job)

            try:
                self._run(job, progress)
                job.state, job.progress = "done", 1.0
            except Cancelled:
                job.state, job.message = "cancelled", "cancelled"
            except Exception as exc:
                log.warning("job %s (%s) failed", job.id, job.engine, exc_info=True)
                job.state, job.error = "failed", f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            self._changed(job)

    def close(self) -> None:
        self._stop.set()
        for job in self._jobs.values():
            job.cancel()
