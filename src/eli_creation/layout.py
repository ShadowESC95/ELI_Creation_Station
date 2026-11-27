"""Every folder Creation Station writes, under the one root ``paths`` decides.

``paths`` (ELI Legal's, reused) says where the data of an installed copy, of a folder named by
ELI_CREATION_HOME, or of a developer checkout lives. This names what is inside it. A bundle keeps
its data in a folder of its own and never in ELI v3's (ELI v3: docs/BUNDLES.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from eli_creation.paths import home_dir

DATA_FOLDER = "eli-creation"  # what the bundle description declares as its data folder


@dataclass(frozen=True)
class Layout:
    root: Path

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.json"

    @property
    def projects(self) -> Path:
        """One folder per project: its brief, its assets' index, ELI's notes on it."""
        return self.root / "projects"

    @property
    def library(self) -> Path:
        return self.root / "library"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def models(self) -> Path:
        explicit = os.environ.get("ELI_CREATION_MODELS", "").strip()
        return Path(explicit).expanduser() if explicit else self.root / "models"

    @property
    def runtimes(self) -> Path:
        """Worker environments, one per engine family (PyTorch, ONNX, stable-diffusion.cpp)."""
        return self.root / "runtime" / "workers"

    @property
    def provenance(self) -> Path:
        return self.root / "provenance"

    @property
    def secrets(self) -> Path:
        return self.root / "secrets"

    @property
    def jobs(self) -> Path:
        """Scratch space a worker writes a job's files into before the library takes them."""
        return self.root / "jobs"

    @property
    def logs(self) -> Path:
        return self.root / "logs"


def layout() -> Layout:
    # As ELI Legal: an installed copy uses its data folder; a source checkout the folder it runs in.
    return Layout(home_dir() or Path.cwd())
