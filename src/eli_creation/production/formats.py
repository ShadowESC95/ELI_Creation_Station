"""The shapes a piece is made in, the ways a camera moves over a still, and how one shot gives way
to the next."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    key: str
    name: str
    width: int
    height: int
    seconds: int  # a usual length for it
    platforms: tuple[str, ...] = ()

    @property
    def aspect(self) -> str:
        """The image engines' name for this shape."""
        ratio = self.width / self.height
        if abs(ratio - 1) < 0.05:
            return "square"
        if ratio > 1.6:
            return "wide"
        if ratio > 1:
            return "landscape"
        if ratio < 0.65:
            return "story"
        return "portrait"

    def scaled(self, longest: int) -> tuple[int, int]:
        """This shape at most ``longest`` pixels on its long side, both sides even (video needs it)."""
        scale = min(1.0, longest / max(self.width, self.height))
        return (max(2, round(self.width * scale / 2) * 2), max(2, round(self.height * scale / 2) * 2))


FORMATS: dict[str, Format] = {
    f.key: f
    for f in (
        Format("square", "Social media ad", 1080, 1080, 15, ("instagram", "facebook", "linkedin", "x")),
        Format("story", "Instagram story / Reel", 1080, 1920, 15, ("instagram", "tiktok", "youtube")),
        Format("youtube", "YouTube ad", 1920, 1080, 30, ("youtube",)),
        Format("promo", "Product promo (vertical)", 1080, 1920, 20, ("tiktok", "instagram")),
        Format("feed", "Feed post 4:5", 1080, 1350, 15, ("instagram", "facebook")),
        Format("linkedin", "LinkedIn video", 1920, 1080, 30, ("linkedin",)),
        Format("film", "Cinematic short", 1920, 1080, 60, ()),
        Format("trailer", "Trailer (scope)", 1920, 800, 45, ()),
        Format("thumbnail", "YouTube thumbnail", 1280, 720, 0, ("youtube",)),
    )
}

# How the camera moves over a still: (start, end) of (zoom, x, y), x and y as a share of the room
# the zoom leaves (-1 left/top … 1 right/bottom).
CAMERA: dict[str, tuple[str, tuple[float, float, float], tuple[float, float, float]]] = {
    "static": ("Static", (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    "push_in": ("Push in", (1.0, 0.0, 0.0), (1.18, 0.0, 0.0)),
    "pull_out": ("Pull out", (1.2, 0.0, 0.0), (1.0, 0.0, 0.0)),
    "pan_left": ("Pan left", (1.15, 0.8, 0.0), (1.15, -0.8, 0.0)),
    "pan_right": ("Pan right", (1.15, -0.8, 0.0), (1.15, 0.8, 0.0)),
    "tilt_up": ("Tilt up", (1.15, 0.0, 0.8), (1.15, 0.0, -0.8)),
    "tilt_down": ("Tilt down", (1.15, 0.0, -0.8), (1.15, 0.0, 0.8)),
    "drift": ("Slow drift", (1.08, -0.4, 0.3), (1.14, 0.4, -0.3)),
    "reveal": ("Reveal", (1.35, 0.0, 0.6), (1.0, 0.0, 0.0)),
}

TRANSITIONS: dict[str, str] = {
    "cut": "Cut",
    "crossfade": "Crossfade",
    "fade_black": "Fade through black",
    "fade_white": "Flash to white",
    "slide_left": "Slide left",
    "zoom": "Zoom through",
}

EASING = ("linear", "ease", "ease_in", "ease_out")


def ease(t: float, kind: str = "ease") -> float:
    t = max(0.0, min(1.0, t))
    if kind == "linear":
        return t
    if kind == "ease_in":
        return t * t
    if kind == "ease_out":
        return 1 - (1 - t) * (1 - t)
    return t * t * (3 - 2 * t)
