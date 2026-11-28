"""Engines that make pictures and moving pictures: images, edits, and video."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from eli_creation.engines.base import Availability, Engine, Progress
from eli_creation.library import slug
from eli_creation.provenance import manifest as manifests
from eli_creation.provenance import marking

if TYPE_CHECKING:
    from eli_creation.jobs import Job
    from eli_creation.services import Studio

SIZES = {"square": (1024, 1024), "portrait": (832, 1216), "landscape": (1216, 832), "wide": (1344, 768),
         "story": (768, 1344)}


def _title(request: dict[str, Any], n: int) -> str:
    """What a person calls an image: its prompt, numbered when one prompt made several."""
    prompt = " ".join(str(request.get("prompt") or "Image").split())
    short = prompt if len(prompt) <= 72 else prompt[:71].rstrip() + "…"
    return short if int(request.get("count", 1) or 1) <= 1 else f"{short} ({n + 1})"


def _size(request: dict[str, Any]) -> tuple[int, int]:
    return SIZES.get(str(request.get("aspect", "square")), SIZES["square"])


class ProceduralImages(Engine):
    """ELI v3's image engine, procedural backend: no model, any machine, every OS."""

    id = "images.procedural"
    tab = "images"
    title = "Procedural (any machine)"
    summary = "ELI v3's own renderer: scenes, posters, emblems and abstracts from your words, with no model."

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        from eli_creation.engines.image_engine.contracts import JobRequest
        from eli_creation.engines.image_engine.service import ImageEngine

        r = job.request
        width, height = _size(r)
        progress(0.1, "Rendering")
        result = ImageEngine().generate_images(JobRequest(
            prompt=str(r.get("prompt", "")), negative_prompt=str(r.get("negative", "")),
            count=max(1, min(8, int(r.get("count", 2)))), width=width, height=height,
            seed=int(r.get("seed", 77)), style=str(r.get("style", "auto")), backend="procedural"))
        if result.status != "complete":
            raise RuntimeError(result.error or "the image engine did not finish")
        folder = studio.library.folder("image", r.get("project", ""))
        for n, artifact in enumerate(a for a in result.artifacts if a.artifact_type == "image"):
            progress(0.5 + 0.5 * n / max(1, len(result.artifacts)), "Marking and filing")
            target = folder / f"{slug(r.get('prompt', 'image'))}-{job.id}-{n}.png"
            man = manifests.build(kind="image", engine=self.id, models=[],
                                  request={"seed": artifact.metadata.get("spec", {}).get("seed"),
                                           "size": [width, height], "style": r.get("style", "auto"),
                                           "score": artifact.score},
                                  digital_source_type=manifests.ALGORITHMIC, project=r.get("project", ""))
            with Image.open(artifact.path) as im:
                marking.save_marked(im.copy(), target, man, visible_label=studio.settings.visible_ai_label)
            job.assets.append(studio.library.add(target, manifest=man, title=_title(r, n), job=job.id))


class DiffusionImages(Engine):
    """An image model, loaded in a worker process for the job and unloaded when idle."""

    id = "images.diffusion"
    tab = "images"
    title = "Image model"
    summary = "A local image model (SSD-1B, FLUX.1 schnell...): the best one this machine runs."
    task = "image"

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        r = job.request
        spec, why = studio.catalogue.best_for("image", studio.machine)
        if spec is None:
            raise RuntimeError(why)
        width, height = _size(r)
        out_dir = studio.layout.jobs / "images" / job.id
        out_dir.mkdir(parents=True, exist_ok=True)
        progress(0.05, f"Loading {spec.title} (only for this job)")
        with studio.manager.use(spec.id) as model:
            job.check()
            progress(0.3, f"Generating with {spec.title}")
            paths = model.call("generate", {
                "prompt": str(r.get("prompt", "")), "negative": str(r.get("negative", "")),
                "width": width, "height": height, "seed": int(r.get("seed", 77)),
                "count": max(1, min(4, int(r.get("count", 1)))), "steps": int(r.get("steps", 0) or 0),
                "out_dir": str(out_dir)})
        folder = studio.library.folder("image", r.get("project", ""))
        for n, source in enumerate(paths or []):
            target = folder / f"{slug(r.get('prompt', 'image'))}-{job.id}-{n}.png"
            man = manifests.build(kind="image", engine=self.id, models=[spec.to_dict()],
                                  request={"seed": int(r.get("seed", 77)) + n, "size": [width, height]},
                                  digital_source_type=manifests.TRAINED, project=r.get("project", ""))
            with Image.open(source) as im:
                marking.save_marked(im.copy(), target, man, visible_label=studio.settings.visible_ai_label)
            job.assets.append(studio.library.add(target, manifest=man, title=_title(r, n), job=job.id))
        shutil.rmtree(out_dir, ignore_errors=True)


def _source_type(studio: Studio, path: Path) -> str | None:
    """An edit of a model's output is a composite with it; an edit of a photo is not AI media."""
    try:
        found = marking.read_marking(path).get("digital_source_type", "")
    except Exception:
        found = ""
    if found.endswith(manifests.TRAINED) or found.endswith(manifests.COMPOSITE_TRAINED):
        return manifests.COMPOSITE_TRAINED
    if found.endswith(manifests.ALGORITHMIC):
        return manifests.ALGORITHMIC
    return None


class ImageEdits(Engine):
    """Edits that need no model: size, crop, turn, light, colour, sharpness, text, format."""

    id = "editing.image"
    tab = "editing"
    title = "Edit an image"
    summary = "Resize, crop to a platform's shape, turn, adjust, sharpen, add a caption, convert."
    ASPECTS = {"1:1": 1.0, "4:5": 0.8, "9:16": 9 / 16, "16:9": 16 / 9, "3:2": 1.5}

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        r = job.request
        source = Path(str(r.get("path", "")))
        with Image.open(source) as im:
            image = ImageOps.exif_transpose(im).convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        done: list[dict[str, Any]] = []
        for n, op in enumerate(r.get("ops", [])):
            job.check()
            progress(n / max(1, len(r.get("ops", []))), str(op.get("op", "")))
            image = self.apply(image, op)
            done.append(op)
        fmt = str(r.get("format", "png")).lower()
        if fmt in ("jpg", "jpeg") and image.mode == "RGBA":
            image = image.convert("RGB")
        folder = studio.library.folder("edit", r.get("project", ""))
        target = folder / f"{slug(source.stem)}-edit-{job.id}.{fmt}"
        man = manifests.build(kind="image", engine=self.id, models=[], request={"from": source.name},
                              digital_source_type=_source_type(studio, source), edits=done,
                              project=r.get("project", ""))
        marking.save_marked(image, target, man, visible_label=studio.settings.visible_ai_label)
        job.assets.append(studio.library.add(target, manifest=man, title=f"{source.stem} (edited)", job=job.id))

    def apply(self, image: Image.Image, op: dict[str, Any]) -> Image.Image:
        kind = op.get("op")
        if kind == "resize":
            w, h = int(op.get("width") or 0), int(op.get("height") or 0)
            if w and not h:
                h = round(image.height * w / image.width)
            if h and not w:
                w = round(image.width * h / image.height)
            return image.resize((max(1, w), max(1, h)), Image.Resampling.LANCZOS)
        if kind == "upscale":
            f = max(1.0, min(4.0, float(op.get("factor", 2))))
            return image.resize((round(image.width * f), round(image.height * f)), Image.Resampling.LANCZOS)
        if kind == "crop_aspect":
            ratio = self.ASPECTS.get(str(op.get("aspect", "1:1")), 1.0)
            return ImageOps.fit(image, (image.width, round(image.width / ratio)) if image.width / image.height < ratio
                                else (round(image.height * ratio), image.height), Image.Resampling.LANCZOS)
        if kind == "rotate":
            return image.rotate(-float(op.get("degrees", 90)), expand=True)
        if kind == "flip":
            return ImageOps.mirror(image)
        if kind == "adjust":
            for name, enhancer in (("brightness", ImageEnhance.Brightness), ("contrast", ImageEnhance.Contrast),
                                   ("saturation", ImageEnhance.Color)):
                if name in op:
                    image = enhancer(image).enhance(float(op[name]))
            return image
        if kind == "autocontrast":
            return ImageOps.autocontrast(image.convert("RGB"))
        if kind == "sharpen":
            return image.filter(ImageFilter.UnsharpMask(radius=2, percent=int(op.get("amount", 120))))
        if kind == "grayscale":
            return ImageOps.grayscale(image).convert("RGB")
        if kind == "caption":
            draw = ImageDraw.Draw(image)
            text = str(op.get("text", ""))
            size = max(16, image.width // 24)
            try:
                from PIL import ImageFont

                font = ImageFont.load_default(size=size)
            except TypeError:
                font = None
            box = draw.textbbox((0, 0), text, font=font)
            x = (image.width - (box[2] - box[0])) // 2
            y = image.height - (box[3] - box[1]) - size
            draw.text((x, y), text, fill=(255, 255, 255), font=font, stroke_width=max(1, size // 12),
                      stroke_fill=(0, 0, 0))
            return image
        raise ValueError(f"unknown edit {kind!r}")


class Animatic(Engine):
    """Pictures in order, each held for its time, crossfaded: a storyboard that moves, on any machine."""

    id = "videos.animatic"
    tab = "videos"
    title = "Animatic (any machine)"
    summary = ("Your images or the library's, in order, with timings and crossfades, as an animated WebP "
               "(video files with sound come with the encoder in a later release).")

    def run(self, job: Job, studio: Studio, progress: Progress) -> None:
        r = job.request
        paths = [Path(p) for p in r.get("images", []) if Path(p).is_file()]
        if not paths:
            raise ValueError("choose at least one image")
        width, height = SIZES.get(str(r.get("aspect", "landscape")), SIZES["landscape"])
        width, height = width // 2, height // 2  # a preview size
        hold, fade = int(float(r.get("seconds", 2.0)) * 1000), int(r.get("fade_frames", 6))
        frames: list[Image.Image] = []
        durations: list[int] = []
        stills = []
        for n, path in enumerate(paths):
            progress(n / len(paths) * 0.8, f"Frame {n + 1} of {len(paths)}")
            with Image.open(path) as im:
                stills.append(ImageOps.fit(im.convert("RGB"), (width, height), Image.Resampling.LANCZOS))
        for n, still in enumerate(stills):
            frames.append(still)
            durations.append(hold)
            if n + 1 < len(stills):
                for step in range(1, fade + 1):
                    frames.append(Image.blend(still, stills[n + 1], step / (fade + 1)))
                    durations.append(60)
        folder = studio.library.folder("video", r.get("project", ""))
        target = folder / f"{slug(r.get('title', 'animatic'))}-{job.id}.webp"
        kinds = {_source_type(studio, p) for p in paths}
        dst = manifests.COMPOSITE_TRAINED if kinds & {manifests.COMPOSITE_TRAINED} else (
            manifests.ALGORITHMIC if manifests.ALGORITHMIC in kinds else None)
        man = manifests.build(kind="video", engine=self.id, models=[], request={"frames": len(stills), "hold_ms": hold},
                              digital_source_type=dst, sources=[p.name for p in paths], project=r.get("project", ""))
        progress(0.9, "Writing")
        xmp = marking.xmp_packet(man, visible_label=studio.settings.visible_ai_label).encode("utf-8")
        try:
            frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0,
                           quality=80, xmp=xmp)
        except TypeError:
            frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0, quality=80)
        job.assets.append(studio.library.add(target, manifest=man, title=str(r.get("title") or "Animatic"), job=job.id))


class Planned(Engine):
    """A feature shown so people see what is coming, and what their machine will need for it."""

    planned = True

    def __init__(self, id: str, tab: str, title: str, summary: str, task: str = "") -> None:
        self.id, self.tab, self.title, self.summary, self.task = id, tab, title, summary, task

    def availability(self, studio: Studio) -> Availability:
        if self.task:
            spec, why = None, ""
            candidates = studio.catalogue.for_task(self.task)
            if candidates:
                spec = candidates[0]
                ok, why = spec.runs_here(studio.machine)
                where = "this machine can run it" if ok else f"on this machine: {why}"
                return Availability(False, f"planned for a later release ({spec.title}; {where})", spec.id)
        return Availability(False, "planned for a later release")
