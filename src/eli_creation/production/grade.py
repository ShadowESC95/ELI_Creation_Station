"""Colour grading for stills and shots: warmth, light, contrast, colour, mood, a vignette, film
grain, and named looks (a cinematic teal and orange, vintage, noir…). Pillow and numpy only; the
same functions grade a film's scenes and an edit in the Editing studio, so a look is the same
wherever it is used."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

# name: (title, what it does)
LOOKS: dict[str, tuple[str, str]] = {
    "none": ("None", "As it is"),
    "cinematic": ("Cinematic", "Teal shadows, warm skin, deeper blacks"),
    "vintage": ("Vintage", "Faded, warm, soft"),
    "noir": ("Noir", "High-contrast black and white"),
    "vivid": ("Vivid", "Punchy colour for feeds"),
    "matte": ("Matte", "Lifted blacks, gentle colour"),
    "cool": ("Cool", "Blue, clean, modern"),
    "golden": ("Golden hour", "Warm, glowing light"),
    "bleach": ("Bleach bypass", "Silvery, gritty, desaturated"),
    "neon": ("Neon night", "Magenta and cyan, deep shadows"),
}


def _rgb(image: Image.Image) -> tuple[np.ndarray, np.ndarray | None]:
    alpha = np.asarray(image.getchannel("A"), dtype=np.float32) if image.mode == "RGBA" else None
    return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0, alpha


def _back(rgb: np.ndarray, alpha: np.ndarray | None) -> Image.Image:
    out = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")
    if alpha is not None:
        out.putalpha(Image.fromarray(alpha.astype(np.uint8), "L"))
    return out


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def look(image: Image.Image, name: str, strength: float = 1.0) -> Image.Image:
    if name in ("", "none") or strength <= 0:
        return image
    rgb, alpha = _rgb(image)
    base = rgb.copy()
    y = _luma(rgb)[..., None]
    if name == "cinematic":
        shadows = (1 - y) ** 2
        highlights = y ** 2
        rgb = rgb + shadows * np.array([-0.06, 0.02, 0.07]) + highlights * np.array([0.07, 0.03, -0.05])
        rgb = (rgb - 0.5) * 1.12 + 0.5
    elif name == "vintage":
        rgb = rgb * 0.88 + 0.08 + np.array([0.05, 0.02, -0.04])
        rgb = rgb * 0.8 + y * 0.2
    elif name == "noir":
        g = np.clip((y - 0.5) * 1.45 + 0.5, 0, 1)
        rgb = np.repeat(g, 3, axis=2)
    elif name == "vivid":
        rgb = y + (rgb - y) * 1.45
        rgb = (rgb - 0.5) * 1.08 + 0.5
    elif name == "matte":
        rgb = rgb * 0.86 + 0.09
        rgb = y + (rgb - y) * 0.85
    elif name == "cool":
        rgb = rgb + np.array([-0.04, 0.0, 0.06])
        rgb = (rgb - 0.5) * 1.05 + 0.5
    elif name == "golden":
        rgb = rgb + np.array([0.08, 0.04, -0.06]) * (0.4 + y)
        rgb = rgb * 1.04
    elif name == "bleach":
        g = np.repeat(y, 3, axis=2)
        rgb = (rgb * 0.45 + g * 0.55 - 0.5) * 1.3 + 0.5
    elif name == "neon":
        shadows = (1 - y) ** 1.5
        rgb = rgb + shadows * np.array([0.10, -0.04, 0.12]) + y * np.array([-0.04, 0.06, 0.08])
        rgb = (rgb - 0.5) * 1.18 + 0.45
    rgb = base + (rgb - base) * float(strength)
    return _back(rgb, alpha)


def adjust(image: Image.Image, *, warmth: float = 0.0, light: float = 0.0, contrast: float = 0.0,
           colour: float = 0.0, mood: float = 0.0) -> Image.Image:
    """Each from -1 to 1 (0: unchanged)."""
    if warmth:
        rgb, alpha = _rgb(image)
        rgb = rgb + np.array([0.08, 0.02, -0.08]) * float(warmth)
        image = _back(rgb, alpha)
    if light:
        image = ImageEnhance.Brightness(image).enhance(1 + 0.6 * light)
    if contrast:
        image = ImageEnhance.Contrast(image).enhance(1 + 0.7 * contrast)
    if colour:
        image = ImageEnhance.Color(image).enhance(max(0.0, 1 + colour))
    if mood:
        rgb, alpha = _rgb(image)
        if mood < 0:  # darker, moodier: crush the shadows and cool them
            rgb = rgb ** (1 - 0.5 * mood) + np.array([-0.02, 0.0, 0.03]) * -mood
        else:  # airier: lift and soften
            rgb = rgb * (1 - 0.25 * mood) + 0.25 * mood
        image = _back(rgb, alpha)
    return image


def vignette(image: Image.Image, amount: float) -> Image.Image:
    if amount <= 0:
        return image
    rgb, alpha = _rgb(image)
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    mask = 1 - np.clip((d - 0.55) / 0.85, 0, 1) ** 1.6 * float(amount)
    return _back(rgb * mask[..., None], alpha)


def grain(image: Image.Image, amount: float, seed: int = 5) -> Image.Image:
    if amount <= 0:
        return image
    rgb, alpha = _rgb(image)
    noise = np.random.default_rng(seed).normal(0, 0.06 * float(amount), rgb.shape[:2]).astype(np.float32)
    return _back(rgb + noise[..., None], alpha)


def apply(image: Image.Image, grade: object) -> Image.Image:
    """A production.project.Grade (or anything with its fields) applied to a picture."""
    if getattr(grade, "is_plain", lambda: True)():
        return image
    out = look(image, str(getattr(grade, "look", "none")))
    out = adjust(out, warmth=float(getattr(grade, "warmth", 0.0)), light=float(getattr(grade, "light", 0.0)),
                 contrast=float(getattr(grade, "contrast", 0.0)), colour=float(getattr(grade, "colour", 0.0)),
                 mood=float(getattr(grade, "mood", 0.0)))
    out = vignette(out, float(getattr(grade, "vignette", 0.0)))
    return grain(out, float(getattr(grade, "grain", 0.0)))


def autocontrast(image: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(image.convert("RGB"))
