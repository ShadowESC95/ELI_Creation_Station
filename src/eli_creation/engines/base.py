"""What every engine is: what it needs, whether this machine and this moment can run it, and how."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eli_creation.jobs import Job
    from eli_creation.services import Studio

Progress = Callable[[float, str], None]


@dataclass(frozen=True)
class Availability:
    ok: bool
    reason: str = ""  # why not, or a note (runs on the processor, slowly)
    model: str = ""  # the specialist it would load, if any
    loads_on_demand: bool = False


class Engine:
    id = ""
    tab = ""
    title = ""
    summary = ""
    uses_main = False  # needs the main model
    task = ""  # the specialist task it needs ("image", "video"...), or ""
    planned = False  # shown, greyed, as coming in a later release

    @property
    def lane(self) -> str:
        return "gpu" if self.task else "main" if self.uses_main else "light"

    def availability(self, studio: Studio) -> Availability:
        if self.planned:
            return Availability(False, "planned for a later release")
        if self.uses_main and not studio.main.available:
            return Availability(False, studio.main.why_unavailable)
        if self.task:
            spec, why = studio.catalogue.best_for(self.task, studio.machine)
            if spec is None:
                return Availability(False, why)
            if studio.model_files(spec) is None:
                return Availability(
                    False,
                    f"{spec.title} is not on this machine yet: put its files in "
                    f"{studio.model_dir(spec)} (model downloads come in a later release)",
                    spec.id,
                )
            note = why or f"{spec.title} loads when you start, and unloads when it has been idle"
            return Availability(True, note, spec.id, loads_on_demand=True)
        return Availability(True)

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        raise NotImplementedError

    def describe_main(self, studio: Studio) -> dict[str, Any]:
        """The main model as a provenance entry."""
        licence = studio.settings.main_model_licence
        return {"id": f"main:{studio.main.name}", "title": studio.main.name, "licence": licence or "unknown"}
