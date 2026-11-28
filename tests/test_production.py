"""Films, ads, music, effects, narration, captions and the calendar: made on any machine, with
nothing outside the application, and nothing in it under a licence that would stop its sale."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from eli_creation.production import captions, music, sfx, social, templates
from eli_creation.production.audio import Placed, duration, mix, peaks, read_wav, write_wav
from eli_creation.production.project import Clip, Grade, Project, ProjectStore, Scene


def test_music_is_composed_for_each_mood_and_the_same_seed_gives_the_same_piece(tmp_path: Path):
    for key in music.MOODS:
        piece = music.compose(key, 4.0, seed=11)
        assert piece.shape == (4 * 44100, 2) and float(np.abs(piece).max()) > 0.2, key
    assert np.array_equal(music.compose("lofi", 3.0, seed=5), music.compose("lofi", 3.0, seed=5))
    path = music.make(tmp_path / "m.wav", "epic", 5.0)
    assert abs(duration(path) - 5.0) < 0.01 and len(peaks(path, 50)) == 50


def test_every_sound_effect_is_made(tmp_path: Path):
    for key in sfx.EFFECTS:
        path = sfx.make(tmp_path / f"{key}.wav", key)
        assert duration(path) > 0.1 and float(np.abs(read_wav(path)).max()) > 0.5, key


def test_music_dips_under_the_narration(tmp_path: Path):
    t = np.arange(44100 * 4) / 44100
    write_wav(tmp_path / "bed.wav", np.sin(2 * np.pi * 220 * t) * 0.5)
    voice = np.zeros(44100 * 4)
    voice[44100:88200] = np.sin(2 * np.pi * 440 * t[:44100]) * 0.5
    write_wav(tmp_path / "voice.wav", voice)
    out = mix([Placed(tmp_path / "bed.wav"), Placed(tmp_path / "voice.wav", voice=True)], 4.0, duck=0.3)
    quiet = np.abs(out[int(3.3 * 44100):int(3.9 * 44100)]).max()
    assert quiet < 0.55 and np.abs(out[int(1.3 * 44100):int(1.7 * 44100)]).max() > 0.3


def test_captions_follow_the_narration_and_are_written_for_every_platform(tmp_path: Path):
    clip = Clip(kind="narration", start=1.0, duration=6.0,
                text="A new world waits beyond the light. Come and see it for yourself, before the sun goes down.")
    cues = captions.cues_for(clip)
    assert cues[0].start == 1.0 and abs(cues[-1].end - 7.0) < 0.01
    assert all(len(c.text) <= captions.MAX_CHARS for c in cues)
    srt = captions.write_srt(cues, tmp_path / "c.srt").read_text()
    vtt = captions.write_vtt(cues, tmp_path / "c.vtt").read_text()
    assert srt.startswith("1\n00:00:01,000 --> ") and vtt.startswith("WEBVTT")


def test_a_project_is_kept_and_read_back_whole(tmp_path: Path):
    store = ProjectStore(tmp_path)
    project = Project(title="Dawn", scenes=[Scene(title="One", seconds=3, grade=Grade(look="noir", vignette=0.3))],
                      clips=[Clip(kind="music", path="m.wav", duration=9)])
    store.save(project)
    again = store.load(project.id)
    assert again.scenes[0].grade.look == "noir" and again.clips[0].duration == 9
    assert [p.id for p in store.all()] == [project.id]


def test_scenes_overlap_by_their_transitions():
    project = Project(scenes=[Scene(seconds=4, transition="crossfade", transition_seconds=1),
                              Scene(seconds=4, transition="cut"), Scene(seconds=2)])
    times = project.scene_times()
    assert [round(s, 2) for _, s, _ in times] == [0.0, 3.0, 7.0] and project.length() == 9.0


def test_a_template_is_filled_from_a_few_answers():
    answers = {"product": "Northwind Coffee", "tagline": "Roasted this morning", "point1": "Single origin",
               "point2": "Fair prices", "point3": "Free delivery", "cta": "Order today"}
    for template in templates.TEMPLATES.values():
        project, narration = templates.build(template, answers)
        assert project.scenes and all(s.description for s in project.scenes), template.key
        assert "{" not in narration and all("{" not in s.description + s.title_text for s in project.scenes)
    project, narration = templates.build(templates.TEMPLATES["launch"], answers)
    assert project.scenes[0].title_text == "Northwind Coffee" and "Order today" in narration


def test_the_calendar_plans_counts_and_exports(tmp_path: Path):
    cal = social.Calendar(tmp_path / "calendar.json")
    cal.put(social.Planned(day="2026-12-01", platform="instagram", text="Spring roast, at last; come in", time="11:00"))
    posted = cal.put(social.Planned(day="2026-11-20", platform="x", text="Done", status="posted"))
    assert cal.stats(date(2026, 11, 28)) == {"planned": 1, "posted_month": 1, "this_week": 1, "overdue": 0}
    assert list(cal.month(2026, 12)) == ["2026-12-01"]
    ics = cal.ics(tmp_path / "plan.ics").read_text()
    assert "DTSTART:20261201T110000" in ics and "come in" in ics and r"roast\, at last\; come" in ics
    cal.remove(posted.id)
    assert len(cal.all()) == 1


@pytest.fixture(scope="module")
def qt():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _picture(path: Path, colour: tuple[int, int, int]) -> str:
    from PIL import Image

    Image.new("RGB", (640, 360), colour).save(path)
    return str(path)


def test_the_compositor_draws_scenes_transitions_and_captions(qt, tmp_path: Path):
    from eli_creation.production.compositor import Compositor
    from eli_creation.production.project import Cue

    project = Project(format="youtube", scenes=[
        Scene(image=_picture(tmp_path / "a.png", (200, 30, 30)), seconds=2, transition="crossfade",
              transition_seconds=1, camera="static"),
        Scene(image=_picture(tmp_path / "b.png", (30, 30, 200)), seconds=2, camera="static")],
        cues=[Cue(0.0, 0.5, "Hello")])
    comp = Compositor(project, (320, 180))
    first, middle, last = comp.frame(0.6), comp.frame(1.5), comp.frame(2.8)
    red = first.pixelColor(160, 40)
    mid = middle.pixelColor(160, 40)
    blue = last.pixelColor(160, 40)
    assert red.red() > 150 and blue.blue() > 150 and 60 < mid.red() < 170 and 60 < mid.blue() < 170


def test_a_film_is_written_with_its_sound_by_qt_alone(qt, tmp_path: Path):
    pytest.importorskip("PySide6.QtMultimedia")
    from eli_creation.production import render

    bed = music.make(tmp_path / "m.wav", "corporate", 3.0)
    project = Project(format="square", scenes=[Scene(image=_picture(tmp_path / "a.png", (20, 160, 120)), seconds=3)],
                      clips=[Clip(kind="music", path=str(bed), duration=3.0)])
    try:
        path, codec = render.export(project, tmp_path / "film.mp4", fps=12, longest=320)
    except render.RenderError as exc:  # a machine with no multimedia backend at all says why
        pytest.skip(f"Qt Multimedia cannot encode here: {exc}")
    assert path.is_file() and path.stat().st_size > 10_000 and codec in ("H264", "MPEG4")


def test_nothing_shipped_is_under_a_licence_that_stops_its_sale(qt):
    """Only Qt modules offered under the LGPL are used, and no GPL encoder library is a dependency."""
    import eli_creation.gui.main_window  # noqa: F401  (the whole window, with every page)
    import eli_creation.production.render  # noqa: F401

    lgpl = {"QtCore", "QtGui", "QtWidgets", "QtNetwork", "QtMultimedia"}
    used = {name.split(".")[1] for name in sys.modules if name.startswith("PySide6.Qt")}
    assert used <= lgpl, used - lgpl
    assert "av" not in sys.modules
    project = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    for forbidden in ('"av', "x264", "pyav", "ffmpeg-python", "imageio-ffmpeg"):
        assert forbidden not in project, forbidden
