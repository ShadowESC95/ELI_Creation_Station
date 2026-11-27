"""A stand-in model for tests and the self-test: it holds a block of memory while loaded, answers
``echo`` and ``generate`` (a flat image), and lets go of everything when its worker ends."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class FakeModel:
    def __init__(self) -> None:
        self.block: bytearray | None = None

    def load(self, spec: dict[str, Any], device: dict[str, Any]) -> dict[str, Any]:
        mb = int(spec.get("memory_mb") or 8)
        self.block = bytearray(min(mb, 64) * 2**20)
        return {"memory_mb": mb, "pid": os.getpid(), "device": device.get("device", "cpu")}

    def call(self, method: str, args: dict[str, Any]) -> Any:
        if method == "echo":
            return {"echo": args, "pid": os.getpid()}
        if method == "generate":
            from PIL import Image

            out = Path(args["out_dir"])
            out.mkdir(parents=True, exist_ok=True)
            path = out / "fake-0.png"
            Image.new("RGB", (int(args.get("width", 64)), int(args.get("height", 64))), (40, 90, 160)).save(path)
            return [str(path)]
        raise ValueError(f"unknown method {method!r}")

    def unload(self) -> None:
        self.block = None
