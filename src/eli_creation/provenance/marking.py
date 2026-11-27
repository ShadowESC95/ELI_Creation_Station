"""The AI-content marking written into a file: XMP with the IPTC digital source type, which image
tools, platforms and content-credential checkers read.

PNG carries it as an ``XML:com.adobe.xmp`` iTXt chunk (with a short summary beside it); WebP and
JPEG carry it as their XMP block. Signed C2PA content credentials need the publisher's own
certificate and are not written yet (provenance/__init__.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, PngImagePlugin

from eli_creation import TITLE, __version__

XMP_KEY = "XML:com.adobe.xmp"


def xmp_packet(manifest: dict[str, Any], *, visible_label: bool = False) -> str:
    dst = manifest.get("digital_source_type") or ""
    models = ", ".join(f"{m.get('title') or m.get('id')} ({m.get('licence')})" for m in manifest.get("models", []))
    credit = "Made with " + TITLE + (f" using {models}" if models else "")
    said = ("AI-generated. " if manifest.get("ai_generated") else "") + credit
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""'
        ' xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"'
        ' xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"'
        + (f' Iptc4xmpExt:DigitalSourceType="{escape(dst)}"' if dst else "")
        + f' xmp:CreatorTool="{escape(TITLE)} {escape(__version__)}"'
        f' xmp:CreateDate="{escape(str(manifest.get("created", "")))}"'
        f' photoshop:Credit="{escape(credit)}">'
        f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{escape(said)}</rdf:li></rdf:Alt></dc:description>'
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    )


def summary(manifest: dict[str, Any]) -> str:
    return json.dumps(
        {
            "generator": manifest.get("generator"),
            "ai_generated": manifest.get("ai_generated"),
            "digital_source_type": manifest.get("digital_source_type"),
            "models": [m.get("id") for m in manifest.get("models", [])],
            "output_licence_class": manifest.get("output_licence_class"),
        },
        sort_keys=True,
    )


def save_marked(image: Image.Image, path: Path, manifest: dict[str, Any], *, visible_label: bool = False,
                **options: Any) -> Path:
    """Save an image with the marking in it, in the format its suffix names."""
    path = Path(path)
    xmp = xmp_packet(manifest, visible_label=visible_label)
    suffix = path.suffix.lower()
    if suffix == ".png":
        info = PngImagePlugin.PngInfo()
        info.add_itxt(XMP_KEY, xmp)
        info.add_text("eli_creation", summary(manifest))
        image.save(path, pnginfo=info, **options)
    elif suffix in (".webp", ".jpg", ".jpeg"):
        try:
            image.save(path, xmp=xmp.encode("utf-8"), **options)
        except TypeError:  # a Pillow too old to write XMP for this format
            image.save(path, **options)
    else:
        image.save(path, **options)
    return path


def mark_file(path: Path, manifest: dict[str, Any], *, visible_label: bool = False) -> bool:
    """Write the marking into an image a model or the image engine already saved."""
    path = Path(path)
    if path.suffix.lower() not in (".png", ".webp", ".jpg", ".jpeg"):
        return False
    with Image.open(path) as im:
        im.load()
        image = im.copy()
    save_marked(image, path, manifest, visible_label=visible_label)
    return True


def read_marking(path: Path) -> dict[str, Any]:
    """The marking in a file: {"digital_source_type": ..., "summary": {...}} (empty if none)."""
    out: dict[str, Any] = {}
    with Image.open(path) as im:
        info = dict(getattr(im, "text", {}) or {})
        info.update({k: v for k, v in im.info.items() if isinstance(v, (str, bytes))})
    xmp = info.get(XMP_KEY) or info.get("xmp") or ""
    if isinstance(xmp, bytes):
        xmp = xmp.decode("utf-8", "replace")
    marker = 'Iptc4xmpExt:DigitalSourceType="'
    if marker in xmp:
        found = xmp.split(marker, 1)[1].split('"', 1)[0]
        if found:
            out["digital_source_type"] = found
    if info.get("eli_creation"):
        try:
            out["summary"] = json.loads(str(info["eli_creation"]))
        except ValueError:
            pass
    return out
