"""Engines for sound, films, ads, platform cards and ready-made games.

    audio.narration   words spoken in a voice (ELI v3's, Piper's, or the computer's own)
    audio.music       a piece composed on this machine for a mood and a length
    audio.sfx         a sound effect synthesised on this machine
    audio.captions    a recording's words, heard by ELI v3's ears, as captions
    videos.film       a film project written out as one MP4 with its sound and captions
    videos.admaker    an ad from a few answers: its scenes, pictures, narration, music, captions
    socials.cards     one picture in every chosen platform's shape, with its words and logo
    games.template    a ready-made game design, to play or to change
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from eli_creation.engines.base import Availability, Engine, Progress
from eli_creation.library import slug
from eli_creation.provenance import manifest as manifests

if TYPE_CHECKING:
    from eli_creation.jobs import Job
    from eli_creation.services import Studio


def _projects(studio: Studio) -> Any:
    from eli_creation.production.project import ProjectStore

    return ProjectStore(studio.layout.projects / "films")


def _audio_asset(studio: Studio, job: Job, path: Path, *, engine: str, title: str, models: list[dict[str, Any]],
                 source: str | None, request: dict[str, Any]) -> Any:
    man = manifests.build(kind="audio", engine=engine, models=models, request=request, digital_source_type=source,
                          project=job.request.get("project", ""))
    return studio.library.add(path, manifest=man, title=title, job=job.id)


class Narration(Engine):
    id = "audio.narration"
    tab = "audio"
    title = "Narration"
    summary = "Words spoken in a voice: ELI v3's own, Piper's, or this computer's."

    def availability(self, studio: Studio) -> Availability:
        from eli_creation.production import speech

        if not speech.voices(include_eli=True):
            return Availability(False, "no voice on this computer yet: start ELI v3, or install Piper or eSpeak NG")
        return Availability(True)

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation.production import speech
        from eli_creation.production.audio import duration

        r = job.request
        best = speech.best_voice()
        voice = str(r.get("voice") or (best.id if best is not None else ""))
        text = str(r.get("text", "")).strip()
        if not text:
            raise ValueError("write what should be said first")
        progress(0.1, "Speaking")
        folder = studio.library.folder("audio", r.get("project", ""))
        target = folder / f"{slug(str(r.get('title') or text[:40]))}-{job.id}.wav"
        speech.speak(text, voice, target, speed=float(r.get("speed", 1.0)))
        job.check()
        record = speech.voice_record(voice)
        neural = voice.startswith(("eli:", "piper:"))
        asset = _audio_asset(studio, job, target, engine=self.id, title=str(r.get("title") or text[:60]),
                             models=[record], source=manifests.TRAINED if neural else manifests.ALGORITHMIC,
                             request={"voice": voice, "speed": r.get("speed", 1.0), "seconds": round(duration(target), 2)})
        job.assets.append(asset)
        job.text = text


class Music(Engine):
    id = "audio.music"
    tab = "audio"
    title = "Music (any machine)"
    summary = "A piece composed here for a mood and a length: no model, no samples, yours to use."

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation.production import music

        r = job.request
        mood = str(r.get("mood", "cinematic"))
        seconds = max(3.0, min(600.0, float(r.get("seconds", 30))))
        progress(0.1, "Composing")
        folder = studio.library.folder("audio", r.get("project", ""))
        name = music.MOODS.get(mood, music.MOODS["cinematic"]).name
        target = folder / f"{slug(name)}-music-{job.id}.wav"
        music.make(target, mood, seconds, tempo=int(r.get("tempo", 0) or 0), key=str(r.get("key", "C")),
                   seed=int(r.get("seed", 7)), intensity=float(r.get("intensity", 0.7)),
                   instruments=r.get("instruments") or None)
        job.assets.append(_audio_asset(studio, job, target, engine=self.id, title=str(r.get("title") or f"{name} music"),
                                       models=[], source=manifests.ALGORITHMIC,
                                       request={k: r.get(k) for k in ("mood", "seconds", "tempo", "key", "seed")}))


class SoundEffect(Engine):
    id = "audio.sfx"
    tab = "audio"
    title = "Sound effects (any machine)"
    summary = "Whooshes, risers, impacts, shimmers: synthesised here for transitions and stingers."

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation.production import sfx

        r = job.request
        effect = str(r.get("effect", "whoosh"))
        folder = studio.library.folder("audio", r.get("project", ""))
        target = folder / f"{effect}-{job.id}.wav"
        sfx.make(target, effect, float(r.get("seconds", 0) or 0), seed=int(r.get("seed", 3)))
        name = sfx.EFFECTS.get(effect, sfx.EFFECTS["whoosh"])[0]
        job.assets.append(_audio_asset(studio, job, target, engine=self.id, title=name, models=[],
                                       source=manifests.ALGORITHMIC, request={"effect": effect}))


class Transcribe(Engine):
    id = "audio.captions"
    tab = "audio"
    title = "Captions from a recording"
    summary = "A recording's words heard by ELI v3's ears (local Whisper), written as captions."

    def availability(self, studio: Studio) -> Availability:
        from eli_creation import eli_link

        if eli_link.find() is None:
            return Availability(False, "needs ELI v3 running on this machine (its ears do the listening)")
        return Availability(True, "ELI v3 loads its speech model for this and unloads it after")

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation import eli_link
        from eli_creation.production import captions
        from eli_creation.production.audio import duration
        from eli_creation.production.project import Clip

        r = job.request
        source = Path(str(r.get("path", "")))
        if source.suffix.lower() != ".wav" or not source.is_file():
            raise ValueError("choose a WAV recording")
        link = eli_link.find(fresh=True)
        if link is None:
            raise RuntimeError("ELI v3 is not running on this machine")
        progress(0.2, "ELI is listening")
        text = link.transcribe(source.read_bytes())
        cues = captions.cues_for(Clip(kind="narration", text=text, duration=duration(source)))
        folder = studio.library.folder("note", r.get("project", ""))
        srt = captions.write_srt(cues, folder / f"{slug(source.stem)}-{job.id}.srt")
        man = manifests.build(kind="note", engine=self.id, models=[{"id": "eli_v3:stt", "title": "ELI v3 (Whisper)",
                                                                   "licence": "MIT"}],
                              request={"from": source.name}, digital_source_type=manifests.TRAINED,
                              project=r.get("project", ""))
        job.assets.append(studio.library.add(srt, manifest=man, title=f"Captions: {source.stem}", job=job.id))
        job.text = text


class Film(Engine):
    id = "videos.film"
    tab = "videos"
    title = "Film (any machine)"
    summary = "Your scenes with camera moves, transitions, narration, music and captions, as one MP4."

    def availability(self, studio: Studio) -> Availability:
        from eli_creation.production import render

        ok, why = render.multimedia()
        return Availability(ok, why)

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        film = _projects(studio).load(str(job.request.get("project_id", "")))
        render_film(job, studio, film, progress)


def render_film(job: Job, studio: Studio, film: Any, progress: Progress) -> None:
    from eli_creation.production import captions, render

    project_name = job.request.get("project") or film.library_project
    folder = studio.library.folder("video", project_name)
    target = folder / f"{slug(film.title)}-{job.id}.mp4"
    longest = int(job.request.get("longest", 1920))
    path, codec = render.export(film, target, fps=int(job.request.get("fps", 24)), longest=longest,
                                progress=progress, cancelled=job._cancel.is_set)
    pictures = [Path(s.image) for s in film.scenes if s.image]
    kinds = {_kind_of(p) for p in pictures}
    voices = [c for c in film.clips if c.kind == "narration" and c.voice.startswith(("eli:", "piper:"))]
    trained = manifests.TRAINED in kinds or manifests.COMPOSITE_TRAINED in kinds or bool(voices)
    source = manifests.COMPOSITE_TRAINED if trained else (manifests.ALGORITHMIC if pictures else None)
    from eli_creation.production import speech

    models = [speech.voice_record(c.voice) for c in film.clips if c.kind == "narration" and c.voice]
    man = manifests.build(kind="video", engine="videos.film", models=models,
                          request={"film": film.id, "codec": codec, "seconds": round(film.length(), 2),
                                   "format": film.format},
                          digital_source_type=source, sources=[p.name for p in pictures], project=project_name)
    job.assets.append(studio.library.add(path, manifest=man, title=film.title, job=job.id))
    if film.cues:
        captions.write_srt(film.cues, path.with_suffix(".srt"))
        captions.write_vtt(film.cues, path.with_suffix(".vtt"))
    job.text = json.dumps({"codec": codec, "seconds": round(film.length(), 2)})


def _kind_of(path: Path) -> str:
    from eli_creation.provenance import marking

    try:
        found = str(marking.read_marking(path).get("digital_source_type", ""))
    except Exception:
        return ""
    for kind in (manifests.COMPOSITE_TRAINED, manifests.TRAINED, manifests.ALGORITHMIC):
        if found.endswith(kind):
            return kind
    return ""


class AdMaker(Engine):
    id = "videos.admaker"
    tab = "videos"
    title = "1-click ad maker"
    summary = ("An ad from a few answers: ELI plans it (with the main model), pictures are made for each scene, "
               "a voice reads it over music, captions follow, and it is written out.")

    def availability(self, studio: Studio) -> Availability:
        return Film().availability(studio)

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation.engines import registry
        from eli_creation.jobs import Job as SubJob
        from eli_creation.production import captions, music, speech, templates
        from eli_creation.production.audio import duration
        from eli_creation.production.project import Clip

        r = job.request
        template = templates.TEMPLATES.get(str(r.get("template", "launch")), templates.TEMPLATES["launch"])
        answers = {k: str(v) for k, v in (r.get("answers") or {}).items()}
        film, narration = templates.build(template, answers, title=str(r.get("title") or ""))
        film.library_project = str(r.get("project", ""))
        if r.get("format"):
            film.format = str(r["format"])
        if studio.main.available and r.get("use_eli", True):
            progress(0.03, "ELI is planning the ad")
            try:
                plan = templates.eli_plan(studio.main.generate, template, answers)
                narration = templates.apply_plan(film, plan) or narration
            except Exception:
                pass  # the template's own words stand
        job.check()
        # a picture for every scene, from the best image engine this machine can run now
        engine_id = "images.diffusion" if registry.get("images.diffusion").availability(studio).ok else "images.procedural"
        engine = registry.get(engine_id)
        from eli_creation.production.formats import FORMATS

        aspect = FORMATS.get(film.format, FORMATS["youtube"]).aspect
        for n, scene in enumerate(film.scenes):
            job.check()
            progress(0.05 + 0.45 * n / len(film.scenes), f"Picturing scene {n + 1}: {scene.title}")
            sub = SubJob(engine=engine_id, tab="images", request={
                "prompt": scene.description, "count": 1, "aspect": aspect, "seed": 100 + n,
                "style": str(r.get("style") or template.style), "project": film.library_project})
            sub._cancel = job._cancel
            engine.run(sub, studio, lambda _f, _m: None)
            if sub.assets:
                scene.image = str(sub.assets[0].path)
                job.assets.extend(sub.assets)
        folder = studio.layout.projects / "films" / film.id
        folder.mkdir(parents=True, exist_ok=True)
        start = 0.4
        if narration and r.get("voice", "auto") != "none":
            voice = str(r.get("voice") or "")
            if not voice or voice == "auto":
                best = speech.best_voice()
                voice = best.id if best else ""
            if voice:
                progress(0.55, "Recording the narration")
                try:
                    spoken = speech.speak(narration, voice, folder / "narration.wav", speed=float(r.get("speed", 1.0)))
                    clip = Clip(kind="narration", path=str(spoken), start=start, text=narration, voice=voice,
                                duration=duration(spoken), label="Narration")
                    film.clips.append(clip)
                    film.cues = captions.cues_for(clip)
                except RuntimeError:
                    pass  # an ad without a voice is still an ad
        length = max(film.length(), sum(s.seconds for s in film.scenes))
        progress(0.62, "Composing the music")
        bed = music.make(folder / "music.wav", str(r.get("mood") or template.mood), length + 1.0, seed=int(r.get("seed", 7)))
        film.clips.append(templates.music_clip(str(bed), length + 1.0))
        _projects(studio).save(film)
        job.check()
        progress(0.65, "Writing the ad")
        render_film(job, studio, film, lambda f, m: progress(0.65 + 0.35 * f, m))
        job.text = json.dumps({"film": film.id, "narration": narration})


class PlatformCards(Engine):
    id = "socials.cards"
    tab = "socials"
    title = "Cards for each platform"
    summary = "One picture cut to every chosen platform's shape, with its words and your logo."

    SHAPES = {"instagram": ("4:5", "Instagram feed"), "story": ("9:16", "Stories and Reels"), "x": ("16:9", "X"),
              "linkedin": ("16:9", "LinkedIn"), "facebook": ("1:1", "Facebook"), "youtube": ("16:9", "YouTube thumbnail"),
              "tiktok": ("9:16", "TikTok"), "square": ("1:1", "Square")}

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from PIL import Image, ImageOps

        from eli_creation.engines.visual import ImageEdits, _source_type
        from eli_creation.provenance import marking

        r = job.request
        source = Path(str(r.get("path", "")))
        if not source.is_file():
            raise ValueError("choose a picture first")
        chosen = [k for k in r.get("platforms", []) if k in self.SHAPES] or ["instagram", "story", "x"]
        edits = ImageEdits()
        folder = studio.library.folder("image", r.get("project", ""))
        with Image.open(source) as im:
            base = ImageOps.exif_transpose(im).convert("RGB")
        for n, key in enumerate(chosen):
            job.check()
            progress(n / len(chosen), self.SHAPES[key][1])
            ops: list[dict[str, Any]] = [{"op": "crop_aspect", "aspect": self.SHAPES[key][0]}]
            if r.get("look") and r.get("look") != "none":
                ops.append({"op": "look", "name": r["look"]})
            if str(r.get("text", "")).strip():
                ops.append({"op": "text", "text": r["text"], "position": r.get("position", "bottom"),
                            "size": float(r.get("size", 0.06)), "box": bool(r.get("box", True))})
            if r.get("logo"):
                ops.append({"op": "watermark", "path": r["logo"], "corner": r.get("corner", "bottom_right")})
            picture = base
            for op in ops:
                picture = edits.apply(picture, op)
            target = folder / f"{slug(source.stem)}-{key}-{job.id}.png"
            man = manifests.build(kind="image", engine=self.id, models=[], request={"from": source.name, "for": key},
                                  digital_source_type=_source_type(studio, source), edits=ops,
                                  project=r.get("project", ""))
            marking.save_marked(picture, target, man, visible_label=studio.settings.visible_ai_label)
            job.assets.append(studio.library.add(target, manifest=man, title=f"{self.SHAPES[key][1]}: {source.stem}",
                                                 job=job.id))


class GameTemplate(Engine):
    id = "games.template"
    tab = "games"
    title = "Ready-made game"
    summary = "A game designed here and ready to play or change: no model needed."

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation.production.game_templates import DESIGNS

        r = job.request
        spec = dict(DESIGNS.get(str(r.get("template", "star_catcher")), DESIGNS["star_catcher"]))
        base = Path(str(r.get("base") or ""))
        if base.name.endswith(".game.json") and base.is_file():  # a design changed by hand
            try:
                found = json.loads(base.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                found = None
            if isinstance(found, dict):
                spec = found
        for key in ("title", "goal", "seconds", "pieces", "palette", "rules", "player", "pieces_look", "design_notes"):
            if r.get(key):
                spec[key] = r[key]
        folder = studio.library.folder("game", r.get("project", ""))
        design = folder / f"{slug(str(spec['title']))}-{job.id}.game.json"
        design.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        made_from = {"from": base.name} if base.name else {"template": r.get("template")}
        man = manifests.build(kind="game", engine=self.id, models=[], request=made_from,
                              digital_source_type=None, project=r.get("project", ""))
        job.assets.append(studio.library.add(design, manifest=man, title=str(spec["title"]), job=job.id))
        job.text = json.dumps(spec, indent=2, ensure_ascii=False)
