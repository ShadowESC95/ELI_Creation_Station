"""Work in the studio: made, marked, filed, recorded in a ledger that shows tampering; refused
outright where the policy says so; the companion's look; the window's studios."""

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


def test_the_window_has_every_studio_in_its_rail(studio: Studio):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from eli_creation.gui.main_window import ORDER, MainWindow

    app = QApplication.instance() or QApplication([])
    studio.settings.extra["ui"] = {"style_previews": False}
    window = MainWindow(studio)
    assert list(window.pages) == list(ORDER) == ["home", "socials", "images", "videos", "audio", "games",
                                                 "editing", "coding", "library", "settings"]
    assert list(window.rail.buttons) == list(ORDER)
    assert window.current == "home"
    images = window.pages["images"]
    assert images.engines.current == "images.procedural", "a studio opens on an engine this machine can run"
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


def test_sound_music_effects_cards_and_ready_made_games_need_no_model(studio: Studio, tmp_path: Path):
    """What Creation Station makes itself: no model, no samples, each with its record."""
    music = studio.queue.wait(studio.submit("audio.music", {"mood": "lofi", "seconds": 4}))
    effect = studio.queue.wait(studio.submit("audio.sfx", {"effect": "riser"}))
    for job in (music, effect):
        assert job.state == "done", job.error
        asset = job.assets[0]
        assert asset.path.suffix == ".wav" and asset.kind == "audio" and asset.manifest_path.is_file()
        assert asset.licence_class, "every sound carries its licence class"
    photo = tmp_path / "photo.png"
    Image.new("RGB", (900, 600), (200, 90, 30)).save(photo)
    cards = studio.queue.wait(studio.submit("socials.cards", {"path": str(photo), "platforms": ["instagram", "story", "x"],
                                                              "text": "Roasted this morning", "look": "golden"}))
    assert cards.state == "done", cards.error
    sizes = []
    for asset in cards.assets:
        with Image.open(asset.path) as im:
            sizes.append(round(im.width / im.height, 2))
    assert sizes == [0.8, 0.56, 1.78], "4:5, 9:16 and 16:9"
    assert "digital_source_type" not in marking.read_marking(cards.assets[0].path), "a photo's card is not AI"
    game = studio.queue.wait(studio.submit("games.template", {"template": "bubble_pop", "title": "Pop!"}))
    assert game.state == "done", game.error
    import json

    spec = json.loads(game.assets[0].path.read_text(encoding="utf-8"))
    assert spec["title"] == "Pop!" and spec["kind"] == "targets"
    changed = studio.queue.wait(studio.submit("games.template", {"base": str(game.assets[0].path), "seconds": 90}))
    assert json.loads(changed.assets[0].path.read_text(encoding="utf-8"))["seconds"] == 90


def test_an_ad_is_made_from_a_few_answers_without_a_main_model(studio: Studio):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from eli_creation.production import render

    QApplication.instance() or QApplication([])
    ok, why = render.multimedia()
    if not ok:
        pytest.skip(why)
    job = studio.queue.wait(studio.submit("videos.admaker", {
        "template": "square_ad", "voice": "none", "longest": 480, "fps": 12,
        "answers": {"product": "Northwind Coffee", "tagline": "Roasted this morning", "cta": "Order today"}}),
        timeout=600)
    if job.state == "failed" and "encode" in (job.error or "").lower():
        pytest.skip(job.error)
    assert job.state == "done", job.error
    kinds = [a.kind for a in job.assets]
    assert kinds.count("image") == 3 and kinds[-1] == "video", "a picture for each scene, then the ad"
    assert job.assets[-1].path.read_bytes()[4:8] == b"ftyp"


def test_edits_give_a_look_words_a_logo_and_a_border(studio: Studio, tmp_path: Path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (400, 300), (90, 90, 90)).save(photo)
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(logo)
    ops = [{"op": "look", "name": "noir"}, {"op": "vignette", "amount": 0.6}, {"op": "grain", "amount": 0.3},
           {"op": "text", "text": "Hello there", "position": "top"},
           {"op": "watermark", "path": str(logo), "corner": "bottom_right", "share": 0.2, "opacity": 1.0},
           {"op": "border", "share": 0.05, "colour": "#ffffff"}]
    job = studio.queue.wait(studio.submit("editing.image", {"path": str(photo), "ops": ops}))
    assert job.state == "done", job.error
    with Image.open(job.assets[0].path) as im:
        rgb = im.convert("RGB")
        assert rgb.size == (430, 330), "a border of 5% of the short side, all round"
        assert rgb.getpixel((2, 2)) == (255, 255, 255)
        red = rgb.getpixel((15 + 400 - 12 - 40, 15 + 300 - 12 - 40))
        assert red[0] > 200 and red[1] < 60, "the logo sits in its corner"


def test_what_is_made_is_told_to_eli_v3_when_it_runs_here_and_never_when_switched_off(studio: Studio, monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from eli_creation import eli_link, eli_share

    heard: list[dict] = []

    class FakeEliV3(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, payload, code=200):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            self._send({"product": "eli_v3"})

        def do_POST(self):  # noqa: N802
            heard.append({"path": self.path, **json.loads(self.rfile.read(int(self.headers["Content-Length"])))})
            self._send({"ok": True, "id": len(heard)})

    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeEliV3)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(eli_link, "_ports", lambda: [server.server_address[1]])
    sent = threading.Event()
    real = eli_share._send
    monkeypatch.setattr(eli_share, "_send", lambda payload: (real(payload), sent.set()))
    eli_link.forget()
    try:
        job = studio.queue.wait(studio.submit("audio.sfx", {"effect": "whoosh", "project": "Northwind"}))
        assert job.state == "done" and sent.wait(10)
        assert len(heard) == 1 and heard[0]["path"] == "/v1/bundles/creation/shared"
        assert heard[0]["category"] == "work" and "Northwind" in heard[0]["text"]
        assert heard[0]["refs"]["paths"] == [str(job.assets[0].path)]
        studio.settings.share_with_eli_v3 = False
        sent.clear()
        studio.queue.wait(studio.submit("audio.sfx", {"effect": "pop"}))
        assert not sent.wait(1) and len(heard) == 1, "switched off: ELI v3 is told nothing"
    finally:
        server.shutdown()
        eli_link.forget()
