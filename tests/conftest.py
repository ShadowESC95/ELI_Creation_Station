from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data folder of the test's own, and a key folder of its own: nothing touches the machine's."""
    monkeypatch.setenv("ELI_CREATION_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ELI_KEYS_DIR", str(tmp_path / "keys"))
    return tmp_path / "home"
