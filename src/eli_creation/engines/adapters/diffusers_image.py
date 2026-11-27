"""An image model in a worker process, through ELI v3's own diffusion backend (reused:
engines/image_engine/visual_core.DiffusionBackend, which loads a diffusers pipeline at half
precision on a graphics card and offloads it in parts where memory is short).

It runs in the ``torch`` runtime (PyTorch and diffusers for the machine's card), never in Creation
Station's own process. Not yet run on a graphics card in this repository's tests: the fake adapter
stands in for it there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _torch_device(device: dict[str, Any]) -> str:
    """The worker sees only the card it was placed on, as device 0 (runtimes/process.py)."""
    backends = set(device.get("backends") or ())
    if device.get("device", "cpu") == "cpu":
        return "cpu"
    if "cuda" in backends or "rocm" in backends:
        return "cuda"  # PyTorch's ROCm build answers to "cuda" as well
    if "mps" in backends:
        return "mps"
    if "xpu" in backends:
        return "xpu"
    return "cpu"


class DiffusersImage:
    def __init__(self) -> None:
        self.backend: Any = None

    def load(self, spec: dict[str, Any], device: dict[str, Any]) -> dict[str, Any]:
        from eli_creation.engines.image_engine import visual_core as core

        folder = Path(spec.get("files_dir", ""))
        if not core.weights_present(str(folder)):
            raise FileNotFoundError(f"no model weights in {folder}")
        self.backend = core.DiffusionBackend(str(folder), _torch_device(device))
        torch = getattr(self.backend, "torch", None)
        used = 0
        if torch is not None and _torch_device(device) == "cuda":
            used = int(torch.cuda.memory_allocated() // 2**20)
        return {"memory_mb": used, "device": _torch_device(device)}

    def call(self, method: str, args: dict[str, Any]) -> Any:
        if method != "generate":
            raise ValueError(f"unknown method {method!r}")
        from eli_creation.engines.image_engine import visual_core as core

        out_dir = Path(args["out_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        prompt, seed = str(args.get("prompt", "")), int(args.get("seed", 77))
        if args.get("steps"):
            self.backend.steps = int(args["steps"])
        paths = []
        for n in range(max(1, int(args.get("count", 1)))):
            spec = core.SceneSpec(
                prompt=prompt, negative_prompt=str(args.get("negative", "")),
                scene_type=core.infer_scene_type(prompt), style=core.infer_style(prompt),
                title=core.title_from_prompt(prompt), width=int(args.get("width", 1024)),
                height=int(args.get("height", 1024)), seed=seed + n, variant=n, supersample=1,
                palette=core.choose_palette(prompt, seed + n), project_tags=[], output_format="png")
            path = out_dir / f"image-{n}.png"
            self.backend.generate(spec).save(path)
            paths.append(str(path))
        return paths

    def unload(self) -> None:
        self.backend = None
