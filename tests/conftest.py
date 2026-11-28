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


@pytest.fixture(autouse=True)
def _no_real_eli_v3(monkeypatch: pytest.MonkeyPatch):
    """No test reaches an ELI v3 running on this machine (its voices, its model, its shared store):
    a test that needs one starts a stand-in of its own and points eli_link at it."""
    from eli_creation import eli_link

    monkeypatch.setattr(eli_link, "_ports", lambda: [])
    eli_link.forget()
    yield
    eli_link.forget()
