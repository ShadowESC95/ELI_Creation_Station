"""Work in the studio: made, marked, filed, recorded in a ledger that shows tampering; refused
outright where the policy says so; the companion's look; the window's seven tabs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from eli_creation.layout import Layout
from eli_creation.models.main import make_main_model
from eli_creation.provenance import marking
from eli_creation.services import Studio
from eli_creation.settings import Settings


@pytest.fixture()
def studio(tmp_path: Path):
    settings = Settings(main_model_source="none")
    s = Studio(where=Layout(tmp_path), settings=settings, hosted=False, main=make_main_model(settings, hosted=False))
    yield s
    s.close()


def test_an_image_is_made_marked_filed_and_recorded(studio: Studio):
    job = studio.queue.wait(studio.submit("images.procedural", {"prompt": "a red kite over hills", "count": 1}))
    assert job.state == "done", job.error
    asset = job.assets[0]
    assert asset.path.is_file() and asset.manifest_path.is_file()
    assert marking.read_marking(asset.path)["digital_source_type"].endswith("algorithmicMedia")
    assert studio.ledger.verify() == (True, "")


def test_an_edit_of_a_photo_does_not_claim_to_be_ai(studio: Studio, tmp_path: Path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (300, 200), (10, 120, 30)).save(photo)
    job = studio.queue.wait(studio.submit("editing.image", {"path": str(photo), "ops": [{"op": "crop_aspect", "aspect": "1:1"}]}))
    assert job.state == "done", job.error
    assert "digital_source_type" not in marking.read_marking(job.assets[0].path)
    with Image.open(job.assets[0].path) as im:
        assert im.size == (200, 200)


def test_a_changed_ledger_entry_is_found(studio: Studio):
    studio.queue.wait(studio.submit("images.procedural", {"prompt": "a lighthouse", "count": 1}))
    db = studio.layout.provenance / "ledger.sqlite3"
    con = sqlite3.connect(db)
    con.execute("UPDATE audit_log SET event_json = replace(event_json, 'image', 'video')")
    con.commit()
    con.close()
    ok, why = studio.ledger.verify()
    assert not ok and why


def test_what_the_policy_refuses_is_refused_before_any_work(studio: Studio):
    with pytest.raises(PermissionError):
        studio.submit("images.procedural", {"prompt": "nude teenage girl"})


def test_without_a_main_model_the_writing_tabs_say_why(studio: Studio):
    with pytest.raises(RuntimeError, match="main model"):
        studio.submit("socials.posts", {"brief": "a launch"})


def test_the_companion_says_nothing_unasked_without_a_main_model(studio: Studio):
    assert studio.companion.think("demo") is None
    ok, why = studio.companion.may_speak_now()
    assert not ok and "main model" in why


def test_the_window_has_the_seven_tabs_in_order(studio: Studio):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from eli_creation.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(studio)
    names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert names == ["Socials", "Images", "Videos", "Games", "Editing", "Coding", "Settings"]
    images = window.tabs.widget(1)
    assert images.engine_id == "images.procedural", "a tab opens on an engine this machine can run"
    window.timer.stop()
    window.eli.timer.stop()
    app.processEvents()


def test_closing_releases_the_log_files_in_its_folder(tmp_path: Path):
    """Windows cannot delete an open file: the image engine's log, held open through the root
    logger, kept the selftest's folder from being removed."""
    import logging
    import shutil

    settings = Settings(main_model_source="none")
    s = Studio(where=Layout(tmp_path / "studio"), settings=settings, hosted=False,
               main=make_main_model(settings, hosted=False))
    job = s.queue.wait(s.submit("images.procedural", {"prompt": "a lantern", "count": 1}))
    assert job.state == "done", job.error
    inside = [h for h in logging.getLogger().handlers
              if str(getattr(h, "baseFilename", "")).startswith(str((tmp_path / "studio").resolve()))]
    assert inside, "the image engine logs into the studio's folder"
    s.close()
    assert not [h for h in logging.getLogger().handlers if h in inside]
    assert all(getattr(h, "stream", None) is None for h in inside)  # closed
    shutil.rmtree(tmp_path / "studio")
