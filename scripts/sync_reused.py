#!/usr/bin/env python3
"""Bring the code Creation Station reuses from ELI Legal, ELI v3 and ELI VR up to date.

    python3 scripts/sync_reused.py            copy every "copy" file again; write any "adapted"
                                             file that is not here yet
    python3 scripts/sync_reused.py --check    change nothing; say which files differ from their
                                             original (exit 1 if any copy is out of date)

reuse.json names each file, the product it comes from, the renames applied (eli_legal to
eli_creation, ELI_LEGAL_ to ELI_CREATION_, ...) and any patch, each with its reason. A patch must
match its original exactly once, so a change upstream that moves it is reported, never guessed at.
Each file gets a first line saying where it came from and at which commit; reuse.lock.json keeps
the commit and the SHA-256 of the original, so --check can tell "changed here" from "changed in
the original".

The products are found beside this checkout (../ELI_Legal, ../ELI_v3.0, ../ELI_VR), or where
ELI_LEGAL_SRC, ELI_V3_SRC and ELI_VR_SRC point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reuse.json"
LOCK = ROOT / "reuse.lock.json"

# How a first line is written in each kind of file; None: the format has no comments.
COMMENT = {
    ".py": "#", ".sh": "#", ".ps1": "#", ".yml": "#", ".yaml": "#", ".toml": "#", ".spec": "#",
    ".desktop": "#", ".iss": ";", ".md": "<!--", "": "#",
}
NO_HEADER = {".json", ".txt", ".xml", ".png", ".ico", ".icns"}


class PatchFailed(Exception):
    pass


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_root(name: str, sources: dict) -> Path:
    spec = sources[name]
    explicit = os.environ.get(spec["env"], "").strip()
    return Path(explicit).expanduser() if explicit else (ROOT / spec["default"]).resolve()


def commit_of(repo: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=10", "HEAD"],
                             capture_output=True, text=True, check=True, timeout=20)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def header(dest: Path, mode: str, origin: str, src: str, commit: str) -> str:
    suffix = dest.suffix.lower() if dest.suffix else ""
    if suffix in NO_HEADER:
        return ""
    mark = COMMENT.get(suffix, "#")
    if mode == "copy":
        words = (f"Reused from {origin}: {src} @ {commit}. Do not edit here: change it in "
                 f"{origin} and run scripts/sync_reused.py.")
    else:
        words = (f"Adapted from {origin}: {src} @ {commit}. Edited for ELI Creation Station; "
                 "scripts/sync_reused.py --check says when the original changes.")
    if mark == "<!--":
        return f"<!-- {words} -->\n"
    return f"{mark} {words}\n"


def render(text: str, dest: Path, mode: str, origin: str, src: str, commit: str,
           rewrites: list[list[str]], patches: list[dict]) -> str:
    for old, new in rewrites:
        text = text.replace(old, new)
    for patch in patches:
        count = text.count(patch["old"])
        if count != 1:
            raise PatchFailed(f"{dest.relative_to(ROOT)}: the patch for {patch.get('why', '?')!r} "
                              f"matches {count} times in the original, not once")
        text = text.replace(patch["old"], patch["new"])
    first = header(dest, mode, origin, src, commit)
    if not first:
        return text
    lines = text.splitlines(keepends=True)
    keep = 0
    # a shebang, and an XML or encoding declaration, stay first
    while keep < len(lines) and (lines[keep].startswith("#!") or "coding:" in lines[keep][:30]):
        keep += 1
    return "".join(lines[:keep]) + first + "".join(lines[keep:])


def entries(manifest: dict):
    for group in manifest["files"]:
        rewrites = [pair for name in group.get("rewrite", []) for pair in manifest["rewrites"][name]]
        for item in group["items"]:
            src, dest = item[0], item[1]
            patches = item[2] if len(item) > 2 else []
            yield group["from"], group["mode"], src, ROOT / dest, rewrites, patches


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="change nothing; report differences")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.is_file() else {}
    commits: dict[str, str] = {}
    problems: list[str] = []
    notes: list[str] = []
    new_lock: dict[str, dict] = {}
    for origin, mode, src, dest, rewrites, patches in entries(manifest):
        root = source_root(origin, manifest["sources"])
        rel = str(dest.relative_to(ROOT))
        source = root / src
        if not source.is_file():
            problems.append(f"{rel}: {origin} has no {src} (is {origin} at {root}?)")
            if rel in lock:
                new_lock[rel] = lock[rel]
            continue
        commit = commits.setdefault(origin, commit_of(root))
        original = source.read_text(encoding="utf-8")
        held = lock.get(rel, {})
        try:
            wanted = render(original, dest, mode, origin, src, held.get("commit", commit) if args.check else commit,
                            rewrites, patches)
        except PatchFailed as exc:
            problems.append(str(exc))
            continue
        record = {"from": origin, "src": src, "mode": mode, "commit": commit, "source_sha256": sha256(original)}
        if args.check:
            upstream = held.get("source_sha256") not in (None, record["source_sha256"])
            here = dest.is_file() and held.get("dest_sha256") not in (None, sha256(dest.read_text(encoding="utf-8")))
            if not dest.is_file():
                problems.append(f"{rel}: missing; run scripts/sync_reused.py")
            elif mode == "copy" and here:
                problems.append(f"{rel}: edited here, but it is a copy: make the change in {origin}")
            elif upstream:
                (problems if mode == "copy" else notes).append(
                    f"{rel}: {origin}'s {src} has changed since it was taken"
                    + ("; run scripts/sync_reused.py" if mode == "copy" else "; merge the change by hand")
                )
            continue
        if mode == "copy" or not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(wanted, encoding="utf-8")
            if source.stat().st_mode & 0o111:
                dest.chmod(dest.stat().st_mode | 0o755)
            record["dest_sha256"] = sha256(wanted)
        else:
            # an adapted file already here is never overwritten; the original it follows is noted
            record["dest_sha256"] = held.get("dest_sha256", sha256(dest.read_text(encoding="utf-8")))
            if held.get("source_sha256") not in (None, record["source_sha256"]):
                notes.append(f"{rel}: {origin}'s {src} has changed; merge the change by hand")
                record["source_sha256"] = held["source_sha256"]
                record["commit"] = held.get("commit", commit)
        new_lock[rel] = record
    if not args.check:
        LOCK.write_text(json.dumps(dict(sorted(new_lock.items())), indent=2) + "\n", encoding="utf-8")
        print(f"synced {sum(1 for r in new_lock.values() if r['mode'] == 'copy')} copied and "
              f"{sum(1 for r in new_lock.values() if r['mode'] == 'adapted')} adapted files "
              f"({', '.join(f'{k} @ {v}' for k, v in sorted(commits.items()))})")
    for line in notes:
        print(f"note: {line}")
    for line in problems:
        print(f"problem: {line}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
