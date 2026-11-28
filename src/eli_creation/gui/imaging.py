"""Pictures for the window: thumbnails, full views and the frames of an animation.

Read with Pillow, which reads every format the studio writes (WebP included, which not every Qt
build can), off the window's thread, and kept in a small cache so a gallery of hundreds scrolls
smoothly.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage

PICTURES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")


def is_picture(path: str | Path) -> bool:
    return Path(path).suffix.lower() in PICTURES


def to_qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    return QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


def load(path: str | Path, max_side: int = 0) -> QImage:
    """The picture (its first frame, for an animation), no larger than ``max_side`` (0: as it is)."""
    with Image.open(path) as im:
        im.seek(0)
        frame = ImageOps.exif_transpose(im.copy())
    if max_side and max(frame.size) > max_side:
        frame.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return to_qimage(frame)


def load_pil(path: str | Path, max_side: int = 0) -> Image.Image:
    with Image.open(path) as im:
        im.seek(0)
        frame = ImageOps.exif_transpose(im.copy())
    if max_side and max(frame.size) > max_side:
        frame.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return frame.convert("RGBA" if frame.mode in ("RGBA", "LA", "P") else "RGB")


def frames(path: str | Path, max_side: int = 0) -> list[tuple[QImage, int]]:
    """Every frame of an animation with how long it shows (ms); one frame for a still."""
    out: list[tuple[QImage, int]] = []
    with Image.open(path) as im:
        for frame in ImageSequence.Iterator(im):
            pic = frame.copy()
            if max_side and max(pic.size) > max_side:
                pic.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            out.append((to_qimage(pic), int(frame.info.get("duration", 100) or 100)))
    return out


class _Signals(QObject):
    loaded = Signal(str, int, QImage)


class _Load(QRunnable):
    def __init__(self, path: str, side: int, signals: _Signals) -> None:
        super().__init__()
        self.path, self.side, self.signals = path, side, signals

    def run(self) -> None:
        try:
            image = load(self.path, self.side)
        except Exception:
            image = QImage()
        self.signals.loaded.emit(self.path, self.side, image)


class Thumbnails(QObject):
    """Thumbnails loaded in the background: ``get`` gives one now if it is ready, and ``ready``
    says when one that was not has arrived."""

    ready = Signal(str)

    def __init__(self, capacity: int = 400) -> None:
        super().__init__()
        self.capacity = capacity
        self._cache: OrderedDict[tuple[str, int], QImage] = OrderedDict()
        self._pending: set[tuple[str, int]] = set()
        self._signals = _Signals()
        self._signals.loaded.connect(self._loaded)
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(3)
        self._lock = threading.Lock()

    def get(self, path: str | Path, side: int = 360) -> QImage | None:
        key = (str(path), side)
        found = self._cache.get(key)
        if found is not None:
            self._cache.move_to_end(key)
            return found
        if key not in self._pending and Path(key[0]).is_file():
            self._pending.add(key)
            self._pool.start(_Load(key[0], side, self._signals))
        return None

    def forget(self, path: str | Path) -> None:
        for key in [k for k in self._cache if k[0] == str(path)]:
            del self._cache[key]

    def _loaded(self, path: str, side: int, image: QImage) -> None:
        key = (path, side)
        self._pending.discard(key)
        self._cache[key] = image
        while len(self._cache) > self.capacity:
            self._cache.popitem(last=False)
        self.ready.emit(path)

    def wait(self, msecs: int = 5000) -> bool:
        return bool(self._pool.waitForDone(msecs))


_shared: Thumbnails | None = None


def thumbnails() -> Thumbnails:
    global _shared
    if _shared is None:
        _shared = Thumbnails()
    return _shared
