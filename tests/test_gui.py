"""The window as a person uses it: studios in the rail, the palette, making images and seeing them
arrive in the gallery, editing with a live preview and undo, a film made from pictures with music,
the Audio studio, the content calendar, ELI's action cards, the models dock, ready-made games, posts
read as each platform shows them, the library's filters, the viewer, and every icon drawn."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from eli_creation.gui import design, icons, imaging  # noqa: E402
from eli_creation.layout import Layout  # noqa: E402
from eli_creation.models.main import make_main_model  # noqa: E402
from eli_creation.services import Studio  # noqa: E402
from eli_creation.settings import Settings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from eli_creation.gui import theme
    from eli_creation.gui.main_window import MainWindow

    monkeypatch.setenv("ELI_CREATION_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ELI_KEYS_DIR", str(tmp_path / "keys"))
    app.setStyleSheet(theme.stylesheet() + design.stylesheet())
    settings = Settings(main_model_source="none")
    settings.extra["ui"] = {"style_previews": False}
    studio = Studio(where=Layout(tmp_path / "studio"), settings=settings, hosted=False,
                    main=make_main_model(settings, hosted=False))
    win = MainWindow(studio)
    win.resize(1500, 950)
    win.show()
    app.processEvents()
    yield win
    win.timer.stop()
    win.eli.timer.stop()
    imaging.thumbnails().wait(5000)
    win.hide()
    studio.close()
    app.processEvents()


def settle(app, until, seconds: float = 60.0) -> None:
    """Let the window's thread take the job news until ``until()`` holds."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if until():
            return
        time.sleep(0.02)
    raise AssertionError("the window did not get there in time")


def make_images(window, app, prompt: str = "a red kite over green hills", count: int = 2) -> list[str]:
    page = window.pages["images"]
    window.go("images")
    page.prompt.setPlainText(prompt)
    page.count.set_value(count)
    page.submit()
    assert page.gallery.model_.has_pending(), "the work shows where its results will be"
    settle(app, lambda: page.jobs and all(j.finished for j in page.jobs.values()) and not page.gallery.model_.has_pending())
    job = next(iter(page.jobs.values()))
    assert job.state == "done", job.error
    return [str(a.path) for a in job.assets]


def test_the_rail_opens_each_studio_and_remembers_where_you_were(window, app):
    for key in ("images", "videos", "library", "settings", "home"):
        window.go(key)
        app.processEvents()
        assert window.stack.currentWidget() is window.pages[key]
        assert window.rail.buttons[key].isChecked()
        assert window.recall("page") == key


def test_the_palette_finds_a_studio_from_a_few_letters_and_goes_there(window, app):
    palette = window.open_palette()
    palette.search.setText("img")
    first = palette.list.item(0).data(256)
    assert first.title == "Images", [palette.list.item(i).text() for i in range(palette.list.count())]
    palette._run(palette.list.item(0))
    app.processEvents()
    assert window.current == "images"


def test_images_made_on_the_page_arrive_in_its_gallery_and_in_the_library(window, app):
    made = make_images(window, app)
    page = window.pages["images"]
    shown = [t.path for t in page.gallery.tiles()]
    assert len(made) == 2 and set(made) <= set(shown)
    assert page.history.items()[0] == "a red kite over green hills", "the prompt is kept for next time"
    window.go("library")
    library = window.pages["library"]
    library.kinds.set_value("image")
    assert {t.path for t in library.gallery.tiles()} >= set(made)
    library.search.setText("no such thing at all")
    assert library.gallery.tiles() == [] and library.empty.isVisibleTo(library)


def test_the_seed_changes_each_time_unless_it_is_locked(window, app):
    page = window.pages["images"]
    page.prompt.setPlainText("a kite")
    first = page.request()["seed"]
    second = page.request()["seed"]
    assert first != second
    page.lock.setChecked(True)
    assert page.request()["seed"] == page.request()["seed"] == page.seed.value()


def test_an_edit_previews_as_it_is_made_and_saves_beside_the_original(window, app):
    made = make_images(window, app, count=1)
    window.go("editing", path=made[0])
    page = window.pages["editing"]
    assert page.path == made[0] and page.canvas.isVisibleTo(page)
    page.crop.set_value("16:9")
    page.brightness.set_value(1.4)
    page.grey.setChecked(True)
    ops = page.ops()
    assert [o["op"] for o in ops] == ["crop_aspect", "adjust", "grayscale"]
    # the preview follows the edits, cropped as it will be saved
    settle(app, lambda: not page.edited_q.isNull()
           and abs(page.edited_q.width() / page.edited_q.height() - 16 / 9) < 0.02)
    page.submit()
    settle(app, lambda: page.jobs and all(j.finished for j in page.jobs.values()))
    job = next(iter(page.jobs.values()))
    assert job.state == "done", job.error
    from eli_creation.provenance import marking

    edit = Path(job.assets[0].path)
    assert edit.is_file() and edit.parent.name == "edit"
    assert marking.read_marking(edit)["digital_source_type"].endswith("algorithmicMedia"), \
        "an edit keeps what its source was"


def test_pictures_become_a_film_with_music_played_and_written(window, app):
    from eli_creation.production import render

    made = make_images(window, app, count=2)
    window.go("videos", add=made)
    page = window.pages["videos"]
    film = page.project
    assert film is not None and [s.image for s in film.scenes] == made
    assert page.strip.count() == 2 and page.preview.compositor is not None
    page.seek(1.0)
    assert page.preview._frame is not None and not page.preview._frame.isNull(), "the preview draws the film"
    page._submit("audio.music", {"mood": "ambient", "seconds": 6}, "music", {"film": film.id, "start": 0.0})
    settle(app, lambda: not page.jobs)
    assert [c.kind for c in film.clips] == ["music"] and film.clips[0].duration > 5
    settle(app, lambda: bool(page.store.load(film.id).clips), seconds=5)  # saved half a second after a change
    page.export()
    settle(app, lambda: not page.jobs, seconds=300)
    videos = window.studio.library.recent(kind="video", limit=5)
    assert videos, "the film is written and filed"
    ok, _why = render.multimedia()
    assert videos[0].path.suffix == (".mp4" if ok else ".webp"), "an MP4, or an animatic where Qt cannot encode"


def test_a_scene_takes_a_look_and_the_timeline_follows_its_length(window, app):
    made = make_images(window, app, count=1)
    window.go("videos", add=made)
    page = window.pages["videos"]
    page.seconds.set_value(6.0)
    page.look.setCurrentIndex(page.look.findData("noir"))
    app.processEvents()
    scene = page.project.scenes[0]
    assert scene.seconds == 6.0 and scene.grade.look == "noir"
    assert page.project.length() == 6.0 and "06.00" in page.time_label.text()


def test_the_audio_studio_composes_plays_and_sends_to_a_film(window, app):
    window.go("audio")
    page = window.pages["audio"]
    page.mode.set_value("music")
    page.length.set_value(5)
    page.compose()
    settle(app, lambda: not page.jobs)
    assert page.rows and page.rows[0].asset.engine == "audio.music"
    assert page.rows[0].wave.peaks, "its waveform is drawn"
    page.rows[0].to_film()
    app.processEvents()
    film = window.pages["videos"].project
    assert window.current == "videos" and film is not None and film.clips[-1].kind == "music"


def test_a_planned_post_is_in_the_calendar_and_marked_posted(window, app):
    import datetime as dt

    from eli_creation.gui.socials_tools import PostLine, calendar_of
    from eli_creation.production.social import Planned

    window.go("socials", room="calendar")
    page = window.pages["socials"]
    assert page.rooms.currentWidget() is page.calendar
    today = dt.date.today()
    item = calendar_of(window).put(Planned(day=today.isoformat(), platform="instagram", text="Spring roast, at last"))
    page.calendar.refresh()
    assert page.calendar.view.items[today.isoformat()][0].id == item.id
    line = next(w for w in page.calendar.findChildren(PostLine) if w.item.id == item.id)
    line._posted()
    assert calendar_of(window).all()[0].status == "posted"


def test_an_edit_is_undone_and_redone(window, app):
    made = make_images(window, app, count=1)
    window.go("editing", path=made[0])
    page = window.pages["editing"]
    page.look.set_value("vintage")
    settle(app, lambda: page.at == 1, seconds=5)
    page.words.setText("Sale")
    settle(app, lambda: page.at == 2, seconds=5)
    assert [o["op"] for o in page.ops()] == ["look", "text"]
    page.undo()
    assert [o["op"] for o in page.ops()] == ["look"] and page.words.text() == ""
    page.undo()
    assert page.ops() == []
    page.redo()
    page.redo()
    assert [o["op"] for o in page.ops()] == ["look", "text"]


def test_eli_offers_where_to_make_it_without_the_main_model(window, app):
    from eli_creation.gui.eli_agent import ActionCard, run, suggest

    assert [a["do"] for a in suggest("write an instagram post and a picture for our launch")] == ["image", "posts"]
    window.ask_eli.setText("make a soundtrack for my trailer")
    window._ask_eli()
    app.processEvents()
    offered = [c for c in window.eli.findChildren(ActionCard) if c.isVisible()]
    assert offered, "ELI still knows where it is done"
    run(window, "music", {"mood": "epic"})
    assert window.current == "audio" and window.pages["audio"].mood.value() == "epic"


def test_the_models_dock_shows_the_main_model_and_every_specialist(window, app):
    window.show_models()
    app.processEvents()
    dock = window._dock
    assert dock.isVisible()
    words = " ".join(label.text() for label in dock.findChildren(type(window.main_chip)))
    assert window.studio.main.name in words and "loads when a job needs it" in words
    dock.hide()


def test_a_ready_made_game_is_set_up_and_made_playable(window, app):
    window.go("games")
    page = window.pages["games"]
    assert page.engines.current != "games.template", "the strip keeps to the pitch and play engines"
    page.from_template("star_catcher", play=True)
    settle(app, lambda: not [j for j in page.jobs.values() if not j.finished] and
           any(a.path.suffix == ".html" for a in window.studio.library.recent(kind="game", limit=5)), seconds=60)
    kinds = sorted(a.path.suffix for a in window.studio.library.recent(kind="game", limit=5))
    assert kinds == [".html", ".json"]


def test_posts_are_read_as_each_platform_shows_them():
    from eli_creation.gui.pages.socials import parse_drafts, platform_of

    text = ("# X: a launch\n\n## Draft 1 (24/280 characters)\n\nWe launch on Monday! #new\n\n"
            "## Draft 2 (300/280 characters, 20 over)\n\n" + "x" * 300 + "\n")
    drafts = parse_drafts(text, "x")
    assert [d.number for d in drafts] == [1, 2] and drafts[0].text == "We launch on Monday! #new"
    assert drafts[1].limit == 280 and len(drafts[1].text) == 300
    assert platform_of("/out/post/a-launch-instagram-abc123.md") == "instagram"


def test_without_a_main_model_the_writing_studios_say_why(window, app):
    for key in ("socials", "coding"):
        window.go(key)
        page = window.pages[key]
        assert not page.create_button.isEnabled()
        assert "main model" in page.reason.text()


def test_the_viewer_shows_a_things_record(window, app):
    from eli_creation.gui.gallery import describe, open_lightbox

    made = make_images(window, app, count=1)
    page = window.pages["images"]
    tile = next(t for t in page.gallery.tiles() if t.path == made[0])
    record = describe(tile)
    assert "Made by a model" in record and ">No<" in record, "the procedural renderer is not a trained model"
    assert ">Yes, and marked as such in the file<" in describe(replace(tile, ai=True))
    box = open_lightbox(window, page.gallery.tiles(), tile)
    app.processEvents()
    assert box.current().path == made[0] and not box.view.item.pixmap().isNull()
    box.close()


def test_every_icon_is_drawn():
    for name in icons.ICONS:
        pix = icons.pixmap(name, "#ffffff", 24)
        image = pix.toImage()
        assert any(image.pixelColor(x, y).alpha() for x in range(0, image.width(), 2)
                   for y in range(0, image.height(), 2)), name


def test_a_gallery_on_a_page_grows_to_show_every_tile(window, app):
    from eli_creation.gui.gallery import Gallery, Tile

    gallery = Gallery(size="small")
    gallery.resize(640, 400)
    gallery.fit_to_content()
    gallery.set_tiles([Tile(path=f"/nowhere/{n}.png", title=str(n)) for n in range(9)])
    columns = gallery.columns()
    rows = -(-9 // columns)
    assert gallery.height() == rows * gallery.cell_size().height() + 8
