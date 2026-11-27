"""Nothing non-commercial, research-only, custom or territory-limited is ever fetched for a buyer,
and every output carries the licence class of what made it."""

from __future__ import annotations

from pathlib import Path

from eli_creation.models import catalogue, folders, licences


def test_every_model_says_its_licence_and_source():
    for spec in catalogue.load().models:
        assert spec.licence and spec.source.startswith("https://"), spec.id
        assert spec.min_tier in ("T0", "T1", "T2", "T3", "T4"), spec.id


def test_only_permissive_verified_pinned_models_may_be_fetched():
    for spec in catalogue.load().models:
        ok, why = spec.may_fetch()
        if ok:
            assert spec.licence_class == "permissive" and spec.verified and spec.revision, spec.id


def test_the_known_traps_are_never_in_the_catalogue():
    cat = catalogue.load()
    for spec in cat.models:
        assert not cat.excluded_reason(spec.source), f"{spec.id} is a known licence trap"
    assert "non-commercial" in cat.excluded_reason("https://huggingface.co/black-forest-labs/FLUX.1-dev")
    assert "European Union" in cat.excluded_reason("https://huggingface.co/tencent/HunyuanVideo")


def test_licence_classes_and_what_an_output_inherits():
    assert licences.licence_class("Apache-2.0") == "permissive"
    assert licences.licence_class("CC-BY-NC-4.0") == "non-commercial"
    assert licences.licence_class("Stability AI Community License") == "custom"
    assert licences.output_class(["permissive", "non-commercial"]) == "non-commercial"
    assert "may not be used commercially" in licences.output_warning("non-commercial")


def test_the_models_folder_has_a_folder_for_every_kind(tmp_path: Path):
    made = folders.ensure(tmp_path / "models")
    names = {p.name for p in made}
    for wanted in ("llm", "embeddings", "vision", "image", "video", "speech", "transcription", "music", "3d", "ocr"):
        assert wanted in names
    assert all((p / "README.txt").is_file() for p in made)
    assert folders.model_dir(tmp_path / "models", "image.ssd-1b", "image").parent.name == "image"
    for spec in catalogue.load().models:
        for task in spec.tasks:
            assert folders.folder_for_task(task).name != "other", f"{spec.id}: no folder for {task}"
