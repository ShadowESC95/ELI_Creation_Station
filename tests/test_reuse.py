"""The code taken from ELI Legal, ELI v3 and ELI VR says where it came from, matches its record, and
reaches into ELI v3 only through the modules allowed."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_reused_file_says_where_it_came_from():
    lock = json.loads((ROOT / "reuse.lock.json").read_text())
    for rel, record in lock.items():
        path = ROOT / rel
        assert path.is_file(), rel
        if path.suffix in (".json", ".txt", ".xml"):
            continue
        head = path.read_text(encoding="utf-8")[:600]
        word = "Reused from" if record["mode"] == "copy" else "Adapted from"
        assert f"{word} {record['from']}" in head, rel


def test_the_copies_match_their_originals_where_the_products_are_beside_this_checkout():
    if not all((ROOT.parent / name).is_dir() for name in ("ELI_Legal", "ELI_v3.0", "ELI_VR")):
        import pytest

        pytest.skip("the other ELI products are not beside this checkout")
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_reused.py"), "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def test_eli_v3_is_reached_only_through_the_allowed_modules():
    from eli_creation.adapters.eli_v3.compat import ALLOWED_HOST_MODULES

    for path in (ROOT / "src" / "eli_creation").rglob("*.py"):
        if "Reused from ELI_v3.0" in path.read_text(encoding="utf-8")[:300]:
            continue  # ELI v3's own modules, reused: their lazy imports of ELI v3 fall back when it is absent
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "import_attr":
                module = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
                if module is not None:
                    assert module in ALLOWED_HOST_MODULES, f"{path.name} imports {module}"
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "eli":
                raise AssertionError(f"{path.relative_to(ROOT)} imports {node.module} directly")
