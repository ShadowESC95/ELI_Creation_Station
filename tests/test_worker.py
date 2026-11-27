"""A specialist runs in a process of its own; ending that process is how it is unloaded."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from eli_creation.layout import Layout
from eli_creation.models.catalogue import ModelSpec
from eli_creation.runtimes.process import ProcessWorker, WorkerError
from eli_creation.runtimes.worker import serve
from eli_creation.tiers import machine_from_dict

FAKE = ModelSpec("test.fake", "Fake", "specialist", ("image",), "MIT", memory_mb=16,
                 adapter="eli_creation.engines.adapters.fake:FakeModel")


def test_a_real_worker_process_loads_answers_and_ends(tmp_path: Path):
    worker = ProcessWorker(FAKE, "cpu", layout=Layout(tmp_path), machine=machine_from_dict({}), load_timeout=60)
    info = worker.start_and_load()
    try:
        assert info["memory_mb"] == 16
        pid = info["pid"]
        assert worker.call("echo", {"x": 1})["echo"] == {"x": 1}
        paths = worker.call("generate", {"out_dir": str(tmp_path / "out")})
        assert Path(paths[0]).is_file()
    finally:
        worker.stop()
    assert not worker.alive and pid > 0


def test_a_worker_loads_adapters_from_its_own_package_only():
    out = io.StringIO()
    serve(io.StringIO(json.dumps({"id": 1, "op": "load", "adapter": "os:system"}) + "\n"), out)
    reply = json.loads(out.getvalue())
    assert reply["ok"] is False and "adapters" in reply["error"]


def test_a_missing_runtime_says_where_it_was_looked_for(tmp_path: Path):
    other = ModelSpec("x", "X", "specialist", ("image",), "MIT", runtime="torch", adapter="eli_creation.engines.adapters.fake:FakeModel")
    with pytest.raises(WorkerError, match="torch runtime"):
        ProcessWorker(other, "cpu", layout=Layout(tmp_path), machine=machine_from_dict({})).command()
