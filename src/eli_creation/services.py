"""The studio: everything a window, the command line or a test needs, wired once.

    settings   what the person chose (settings.py)
    machine    what this machine can do, and its tier (tiers.py, on ELI's own probes)
    main       the main model: the one that stays loaded (models/main.py)
    manager    the specialist models: loaded for a job, unloaded when idle (models/manager.py)
    library    every asset made, with its manifest; the provenance ledger behind it
    queue      the jobs, in three lanes
    companion  ELI in the studio
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from eli_creation.layout import Layout, layout
from eli_creation.models import catalogue as catalogues
from eli_creation.models import folders
from eli_creation.models.catalogue import ModelSpec
from eli_creation.models.main import MainModel, make_main_model
from eli_creation.models.manager import Launcher, ModelManager
from eli_creation.models.residency import Policy
from eli_creation.settings import Settings
from eli_creation.tiers import Machine, probe

log = logging.getLogger("eli_creation")


def hosted_now() -> bool:
    """Whether ELI v3 opened this process (bundle.launch says so)."""
    return os.environ.get("ELI_CREATION_MODE") == "eli_v3"


class Studio:
    def __init__(
        self,
        *,
        where: Layout | None = None,
        settings: Settings | None = None,
        machine: Machine | None = None,
        hosted: bool | None = None,
        main: MainModel | None = None,
        launcher: Launcher | None = None,
    ) -> None:
        from eli_creation.companion.companion import Companion
        from eli_creation.jobs import JobQueue
        from eli_creation.library import Library
        from eli_creation.provenance.ledger import ProvenanceLedger
        from eli_creation.runtimes.process import ProcessWorker

        self.layout = where or layout()
        self.layout.root.mkdir(parents=True, exist_ok=True)
        from eli_creation.engines import image_paths

        image_paths.use(self.layout)
        self.hosted = hosted_now() if hosted is None else hosted
        self.settings = settings or Settings.load(self.layout.settings_file)
        self.machine = machine or probe(hosted=self.hosted)
        self.catalogue = catalogues.load()
        self.policy = Policy.from_settings(self.settings, self.machine.tier)
        self.main = main or make_main_model(self.settings, hosted=self.hosted)
        folders.ensure(self.layout.models)

        def launch(spec: ModelSpec, device: str) -> Any:
            return ProcessWorker(spec, device, layout=self.layout, machine=self.machine)

        self.manager = ModelManager(self.machine, self.catalogue, self.policy, main=self.main,
                                    launcher=launcher or launch)
        self.ledger = ProvenanceLedger(self.layout)
        self.library = Library(self.layout, self.ledger)
        self.queue = JobQueue(self._run)
        self.companion = Companion(self)

    # ── models ────────────────────────────────────────────────────────────
    def model_dir(self, spec: ModelSpec) -> Path:
        return folders.model_dir(self.layout.models, spec.id, spec.tasks[0] if spec.tasks else "other")

    def model_files(self, spec: ModelSpec) -> Path | None:
        return folders.find_model(self.layout.models, spec.id, spec.tasks[0] if spec.tasks else "other")

    def start(self) -> None:
        """Load the main model (on a background thread) and start unloading idle specialists."""
        self.manager.start()
        if self.main.source == "gguf":
            self.main.load_in_background()

    def save_settings(self) -> None:
        self.settings.save(self.layout.settings_file)
        self.policy = Policy.from_settings(self.settings, self.machine.tier)
        self.manager.policy = self.policy

    def close(self) -> None:
        self.queue.close()
        self.manager.close()
        self.main.unload()
        self.library.close()
        self._release_log_files()

    def _release_log_files(self) -> None:
        """Close every log file kept under this studio's folder (the image engine logs to one
        through the root logger), so the folder can be moved or removed: Windows refuses to delete
        a file that is still open."""
        root = Path(self.layout.root).resolve()
        loggers: list[logging.Logger] = [logging.getLogger()]
        loggers += [lg for lg in logging.Logger.manager.loggerDict.values() if isinstance(lg, logging.Logger)]
        for lg in loggers:
            for handler in list(lg.handlers):
                name = getattr(handler, "baseFilename", "")
                if name and Path(name).resolve().is_relative_to(root):
                    lg.removeHandler(handler)
                    handler.close()

    # ── jobs ──────────────────────────────────────────────────────────────
    def submit(self, engine_id: str, request: dict[str, Any]):
        from eli_creation.edition import policy
        from eli_creation.engines import registry
        from eli_creation.jobs import Job

        engine = registry.get(engine_id)
        refusal = policy.refusal(request)
        if refusal:
            raise PermissionError(refusal)
        ok = engine.availability(self)
        if not ok.ok:
            raise RuntimeError(ok.reason)
        return self.queue.submit(Job(engine=engine.id, tab=engine.tab, request=dict(request), lane=engine.lane))

    def _run(self, job, progress) -> None:
        from eli_creation.engines import registry

        registry.get(job.engine).run(job, self, progress)
