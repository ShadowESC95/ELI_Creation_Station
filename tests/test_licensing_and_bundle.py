"""The same licence rule as every ELI product, and a bundle description ELI v3 reads."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from eli_creation import bundle, licensing


@pytest.fixture()
def required(home, tmp_path, monkeypatch):
    monkeypatch.setattr(licensing, "_hosted", False)
    monkeypatch.setattr(licensing, "_trial_locations", [tmp_path / "t1", tmp_path / "t2"])
    return tmp_path


def test_an_installed_copy_starts_a_seven_day_trial_on_first_use(required):
    assert not licensing.standing().granted
    started = licensing.standing(start=True)
    assert started.granted and started.on_trial and started.days_left == 7


def test_deleting_the_trial_once_used_does_not_restart_it(required, home):
    licensing.standing(start=True)
    for folder in licensing._trial_locations:
        (folder / ".creation-trial").unlink()
    (home / "projects" / "a").mkdir(parents=True)
    got = licensing.standing(start=True)
    assert not got.granted and "used on this machine before" in got.reason


def test_a_copy_run_from_its_source_needs_a_licence_like_any_other(monkeypatch):
    """A git clone of the repository was a free copy of the product: it never checked a licence."""
    monkeypatch.setattr(licensing, "_hosted", False)
    assert (Path(licensing.__file__).resolve().parents[2] / ".git").exists(), "this test runs from the source"
    assert licensing.required()
    assert not any("ELI_CREATION_REQUIRE_LICENCE" in line or "_source_checkout" in line
                   for line in Path(licensing.__file__).read_text(encoding="utf-8").splitlines())


def test_hosted_by_an_eli_v3_that_does_not_know_the_product_still_checks_its_own_key(required):
    licensing.hosted_by_eli()  # no ELI v3 here: the host cannot have checked
    assert licensing.required()


def test_the_description_passes_eli_sdks_check():
    from eli_sdk import check_bundle

    report = check_bundle(bundle.describe(), core_version="3.0.173")
    assert report.ok, report.problems
    assert report.bundle.id == "creation" and report.bundle.data_folder == "eli-creation"


def test_eli_v3s_own_loader_reads_it_where_eli_v3_is_beside_this_checkout():
    core = Path(__file__).resolve().parents[2] / "ELI_v3.0"
    if not (core / "eli" / "bundles" / "__init__.py").is_file():
        pytest.skip("no ELI v3 checkout beside this one")
    import importlib.util
    import sys

    sys.path.insert(0, str(core))
    try:
        spec = importlib.util.spec_from_file_location("eli_bundles_probe", core / "eli" / "bundles" / "__init__.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # its dataclasses look themselves up there
        spec.loader.exec_module(module)
        found = module.Bundle.from_description(bundle.describe(), origin="test")
    finally:
        sys.path.remove(str(core))
        sys.modules.pop("eli_bundles_probe", None)
    assert found.id == "creation" and found.edition == "creation" and "core" in found.extra


def test_register_and_unregister_this_copy(tmp_path: Path):
    path = bundle.register(tmp_path)
    record = json.loads(path.read_text())
    assert path.name == "creation.json" and record["command"] and record["launch"] == ""
    assert bundle.unregister(tmp_path, this_copy=True) == [path]
    assert not path.exists()
    assert os.path.basename(str(bundle.v3_bundle_dirs()[0])) == "bundles"
