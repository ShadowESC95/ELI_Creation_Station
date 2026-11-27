"""The models folder: one folder per kind of model, so a person (or a support call) can see at a
glance what is on the machine, and each model's licence sits beside its files.

    models/
      llm/             main language models (GGUF)
      code/            coding models (GGUF)
      embeddings/      text and image embedders: searching the library by meaning
      vision/          vision-language models and their projectors: reading the screen, describing images
      image/           text-to-image and image-to-image (diffusers folders, or GGUF for stable-diffusion.cpp)
      image-adapters/  LoRA, ControlNet and IP-Adapter weights for the image models
      upscale/         upscalers
      segmentation/    background removal and masks
      depth/           depth estimation (parallax, 2D to 3D)
      video/           text-to-video and image-to-video
      interpolation/   frame interpolation: smoother video
      speech/          text-to-speech voices: narration
      transcription/   speech-to-text: captions and subtitles
      music/           music and sound effects
      3d/              image-to-3D and meshes: game and ELI VR assets
      ocr/             text recognition data (Tesseract languages)
      voices/          voice clones made with the speaker's consent: the person's own, never published
      lora/            styles trained on the person's own work: never published

A model lives in ``models/<folder>/<model id>/`` with ``LICENSE.<model id>.txt`` beside its files,
as ELI v3 keeps them (eli/runtime/model_licences.py there). The folder names follow ELI v3's where
the two share a kind (``embeddings``, ``vision``), and ELI v3's own model folders are read too, never
written, so a model ELI v3 already fetched is not fetched twice (``shared_folders``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eli_creation.paths import data_roots


@dataclass(frozen=True)
class Folder:
    name: str
    holds: str
    tasks: tuple[str, ...]
    private: bool = False  # the person's own data: never published, never in a support bundle
    eli_v3: tuple[str, ...] = ()  # where ELI v3 keeps the same kind, under its models folder


FOLDERS: tuple[Folder, ...] = (
    Folder("llm", "Main language models (GGUF): the one model that stays loaded", ("text",), eli_v3=("gguf/base", "")),
    Folder("code", "Coding models (GGUF)", ("code",)),
    Folder("embeddings", "Text and image embedders, for searching the library by meaning", ("embed",), eli_v3=("embeddings",)),
    Folder("vision", "Vision-language models and their projectors: reading the screen, describing images", ("vision",), eli_v3=("vision",)),
    Folder("image", "Text-to-image and image-to-image models (diffusers folders, or GGUF for stable-diffusion.cpp)", ("image",)),
    Folder("image-adapters", "LoRA, ControlNet and IP-Adapter weights for the image models", ("image_adapter",)),
    Folder("upscale", "Upscalers", ("upscale",)),
    Folder("segmentation", "Background removal and masks", ("background_removal", "segmentation")),
    Folder("depth", "Depth estimation: parallax, 2D to 3D", ("depth",)),
    Folder("video", "Text-to-video and image-to-video models", ("video",)),
    Folder("interpolation", "Frame interpolation: smoother video", ("interpolation",)),
    Folder("speech", "Text-to-speech voices: narration", ("speech",), eli_v3=("tts",)),
    Folder("transcription", "Speech-to-text: captions and subtitles", ("transcription",), eli_v3=("whisper",)),
    Folder("music", "Music and sound effects", ("music", "sfx")),
    Folder("3d", "Image-to-3D and mesh models: game and ELI VR assets", ("3d",)),
    Folder("ocr", "Text recognition data (Tesseract languages)", ("ocr",)),
    Folder("voices", "Voice clones made with the speaker's recorded consent", ("voice_clone",), private=True),
    Folder("lora", "Styles trained on the person's own work", ("style",), private=True),
)

_BY_TASK = {task: f for f in FOLDERS for task in f.tasks}


def folder_for_task(task: str) -> Folder:
    return _BY_TASK.get(task, FOLDERS[0] if task == "text" else Folder("other", "Other models", (task,)))


def model_dir(root: Path, model_id: str, task: str) -> Path:
    """Where one model's files are: models/<folder>/<model id>."""
    return Path(root) / folder_for_task(task).name / model_id


def _readme(folder: Folder) -> str:
    lines = [
        f"{folder.name}/ - {folder.holds}.",
        "",
        "One folder per model: <model id>/, with LICENSE.<model id>.txt beside its files.",
    ]
    if folder.private:
        lines += ["", "What is here is the person's own (made from their voice or their work). It is never",
                  "published, uploaded or included in a support bundle."]
    else:
        lines += ["", "ELI Creation Station fetches only models whose licence lets a paid product pass them on",
                  "(models/licences.py). A model you bring yourself keeps its own licence, and what it makes",
                  "carries that licence's class in its provenance."]
    return "\n".join(lines) + "\n"


def ensure(root: Path) -> list[Path]:
    """Make every folder, each with its README.txt. Returns the folders."""
    made = []
    for folder in FOLDERS:
        path = Path(root) / folder.name
        path.mkdir(parents=True, exist_ok=True)
        readme = path / "README.txt"
        if not readme.exists():
            readme.write_text(_readme(folder), encoding="utf-8")
        made.append(path)
    return made


def shared_folders(task: str) -> list[Path]:
    """ELI v3's model folders of the same kind on this machine: read, never written."""
    folder = folder_for_task(task)
    out = []
    for root in data_roots("ELI_v3"):
        for sub in folder.eli_v3:
            path = root / "models" / sub if sub else root / "models"
            if path.is_dir() and path not in out:
                out.append(path)
    return out


def find_model(root: Path, model_id: str, task: str) -> Path | None:
    """A model's files: in Creation Station's own folder, else in ELI v3's of the same kind."""
    own = model_dir(root, model_id, task)
    if own.is_dir() and any(own.iterdir()):
        return own
    name = model_id.split(".", 1)[-1]
    for shared in shared_folders(task):
        for candidate in (shared / model_id, shared / name):
            if candidate.exists():
                return candidate
    return None
