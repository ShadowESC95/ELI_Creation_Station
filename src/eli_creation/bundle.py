# Adapted from ELI_Legal: src/eli_legal/bundle.py @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
"""ELI Creation Station as an ELI v3 bundle: a separate application ELI v3 can open in place of its own
window, on ELI v3's core.

The contract (``eli.bundles`` in ELI v3) asks a bundle for a description and a launch function.
Installed in ELI v3's Python environment, ELI Creation Station is found through the ``eli.bundles`` entry
point and runs inside ELI v3's process, using ELI v3's loaded model unless another is chosen.
Installed on its own (an AppImage, an installer), ``eli-creation bundle register`` tells ELI v3
where it is, and ELI v3 starts it as its own program.

This module imports nothing heavy at load: ELI v3 reads the description without starting
anything.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from eli_creation import PRODUCT, TITLE, __version__
from eli_creation.layout import DATA_FOLDER

CONTRACT = 1
_ICON = Path(__file__).resolve().parent / "gui" / "assets" / "eli_creation_256.png"


def describe() -> dict[str, Any]:
    """Contract 1, which every ELI v3 reads, with contract 2's fields beside it: an ELI v3 that
    reads contract 1 keeps them as extras, and eli-sdk's check_bundle reads them all."""
    return {
        "contract": CONTRACT,
        "id": PRODUCT,
        "title": TITLE,
        "summary": "Images, videos, platform content, games and code, made on this machine, with ELI "
        "beside you on the project. Every output's models and licences recorded.",
        "version": __version__,
        "edition": PRODUCT,
        "publisher": "ShadowESC95",
        "icon": str(_ICON) if _ICON.is_file() else "",
        "launch": "eli_creation.bundle:launch",
        "requires_core": ">=3.0",
        # contract 2 (eli-sdk docs/bundles.md)
        "core": {"min": "3.0", "below": "4"},
        "capabilities": ["model.generate", "settings.read", "server.speech_in", "server.speech_out"],
        "data": {"folder": DATA_FOLDER},
        "upgrade": {"data_version": 1, "migrates_from": 1},
    }


def launch(argv: list[str] | None = None, *, host: dict[str, Any] | None = None) -> int:
    """Open ELI Creation Station's window, hosted by ELI v3.

    Its data goes where an installed copy keeps it, never into ELI v3's folders, so the same
    projects are there whichever way Creation Station is opened. Unless a main model has been
    chosen in its own settings, it uses the model ELI v3 has loaded, and ELI in the studio is
    ELI v3's own ELI (its eyes, attention and voice), not a second one.
    """
    from eli_creation import licensing

    licensing.hosted_by_eli()
    os.environ.setdefault("ELI_CREATION_HOME", str(_data_home()))
    os.environ["ELI_CREATION_MODE"] = "eli_v3"
    if host:
        os.environ["ELI_CREATION_HOST"] = (
            f"{host.get('name', 'ELI v3')} {host.get('version', '')}".strip()
        )
    if argv and argv[0] not in ("gui",):
        from eli_creation.cli import main as cli_main

        return int(cli_main(argv))
    from eli_creation.gui.app import main as gui_main

    return int(gui_main([]))


def _data_home() -> Path:
    from eli_creation.paths import user_data_dir

    return user_data_dir()


# ── registering a separately installed copy with ELI v3 ───────────────────────
def own_command() -> list[str]:
    """How to start this copy of ELI Creation Station's window from outside."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return [appimage]
    if getattr(sys, "frozen", False):
        gui = Path(sys.executable).with_name("eli-creation-gui" + (".exe" if os.name == "nt" else ""))
        return [str(gui if gui.exists() else sys.executable)]
    return [sys.executable, "-m", "eli_creation", "gui"]


def v3_bundle_dirs() -> list[Path]:
    """The folders ELI v3 looks in for separately installed bundles."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    out = [base / "ELI_v3" / "bundles"]
    if os.environ.get("ELI_DATA_DIR"):
        out.append(Path(os.environ["ELI_DATA_DIR"]) / "bundles")
    return out


def register(target: Path | None = None) -> Path:
    """Tell ELI v3 where this copy is, so it can offer to open it. Writes one small file."""
    folder = target or v3_bundle_dirs()[0]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{PRODUCT}.json"
    record = {**describe(), "command": own_command(), "launch": ""}
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def _version_key(text: str) -> tuple[int, ...]:
    m = re.match(r"\s*(\d+(?:\.\d+)*)", str(text or ""))
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def installed_copy() -> bool:
    """An AppImage or an installed, packaged program; not a source checkout."""
    return bool(os.environ.get("APPIMAGE")) or bool(getattr(sys, "frozen", False))


def refresh_registration(target: Path | None = None) -> Path | None:
    """Keep ELI v3's record of ELI Creation Station pointing at the newest copy on this machine.

    Called when an installed copy starts. It registers this copy if ELI v3 is on this machine
    and its record names no copy, a copy that has since been removed, or an older version;
    a copy of the same version leaves the record alone, so two copies never take turns. A
    source checkout registers only when told to. Never raises: ELI Creation Station starts regardless.
    """
    if target is None and (not installed_copy() or os.environ.get("ELI_CREATION_MODE") == "eli_v3"):
        return None  # a source checkout, or ELI v3's own process hosting ELI Creation Station
    try:
        folder = target or v3_bundle_dirs()[0]
        if target is None and not folder.parent.is_dir():
            return None  # ELI v3 is not on this machine
        path = folder / f"{PRODUCT}.json"
        if path.is_file():
            held = json.loads(path.read_text(encoding="utf-8"))
            command = held.get("command") or []
            present = bool(command) and Path(str(command[0])).exists()
            if present and _version_key(held.get("version", "")) >= _version_key(__version__):
                return None
        return register(folder)
    except (OSError, ValueError, TypeError):
        return None


def eli_v3_present() -> bool:
    return v3_bundle_dirs()[0].parent.is_dir()


def _names_this_copy(path: Path) -> bool:
    try:
        command = json.loads(path.read_text(encoding="utf-8")).get("command") or []
        return bool(command) and Path(str(command[0])).resolve() == Path(own_command()[0]).resolve()
    except (OSError, ValueError, TypeError):
        return False


def unregister(target: Path | None = None, *, this_copy: bool = False) -> list[Path]:
    """Take ELI Creation Station off ELI v3's list; with ``this_copy``, only where the record names this
    copy (an uninstaller must not remove the record of another copy)."""
    removed = []
    for folder in [target] if target else v3_bundle_dirs():
        path = folder / f"{PRODUCT}.json"
        if path.is_file() and (not this_copy or _names_this_copy(path)):
            path.unlink()
            removed.append(path)
    return removed
