# Adapted from ELI_v3.0: eli/planning/attention_queue.py @ ccb8c4c42f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from eli_creation.layout import layout


def _artifacts_dir() -> Path:
    """Creation Station's own data folder, where ELI v3 used its artifacts folder."""
    return layout().root

_SEVERITY_SCORE = {
    "critical": 100,
    "high": 75,
    "medium": 50,
    "low": 25,
    "info": 10,
}

def attention_path() -> Path:
    # artifacts_dir() rather than project_root()/artifacts: identical under the
    # frozen rthook (both pin the same user root) and correct for a bare pip
    # install, where the project root is the package directory.
    return _artifacts_dir() / "runtime" / "attention_queue.jsonl"

def suppression_path() -> Path:
    return _artifacts_dir() / "runtime" / "attention_suppression.json"



def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Every JSON object in a JSON-lines file, skipping lines that are not one (ELI v3's
    eli.utils.jsonio.read_jsonl_dicts)."""
    out: list[dict[str, Any]] = []
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    out.append(value)
    except OSError:
        pass
    return out

def _load_suppression() -> dict[str, Any]:
    p = suppression_path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}

def _save_suppression(data: dict[str, Any]) -> None:
    p = suppression_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _severity_score(severity: str) -> int:
    return _SEVERITY_SCORE.get(str(severity or "medium").lower(), 50)

def _rank_item(rec: dict[str, Any], now: float | None = None) -> float:
    now = time.time() if now is None else float(now)
    sev = _severity_score(str(rec.get("severity") or "medium"))
    ts = float(rec.get("ts") or now)
    freshness = max(0.0, 3600.0 - min(3600.0, now - ts)) / 3600.0
    freshness_score = freshness * 20.0
    state = str(rec.get("state") or "pending")
    state_bonus = 0.0
    if state == "pending_confirmation":
        state_bonus = 20.0
    elif state == "blocked":
        state_bonus = 25.0
    elif state == "pending":
        state_bonus = 10.0
    return float(sev) + freshness_score + state_bonus

def append_attention(
    kind: str,
    title: str,
    state: str = "pending",
    severity: str = "medium",
    source: str = "autonomy_scheduler",
    metadata: dict[str, Any] | None = None,
    suppression_key: str | None = None,
    suppression_window_sec: int = 0,
) -> dict[str, Any]:
    now = time.time()
    suppression_key = str(suppression_key or f"{kind}:{title}").strip()
    suppression_window_sec = max(0, int(suppression_window_sec))

    if suppression_window_sec > 0:
        sup = _load_suppression()
        last = float(sup.get(suppression_key, 0.0) or 0.0)
        if last > 0 and (now - last) < suppression_window_sec:
            return {
                "ok": True,
                "suppressed": True,
                "suppression_key": suppression_key,
                "remaining_sec": max(0, int(suppression_window_sec - (now - last))),
            }

    rec = {
        "attention_id": f"attn_{uuid.uuid4().hex[:12]}",
        "ts": now,
        "kind": str(kind or "attention"),
        "title": str(title or "attention").strip(),
        "state": str(state or "pending"),
        "severity": str(severity or "medium"),
        "source": str(source or "autonomy_scheduler"),
        "metadata": dict(metadata or {}),
        "suppression_key": suppression_key,
    }
    rec["rank_score"] = _rank_item(rec, now=now)

    p = attention_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True, default=str) + "\n")

    if suppression_window_sec > 0:
        sup = _load_suppression()
        sup[suppression_key] = now
        _save_suppression(sup)

    rec["ok"] = True
    rec["suppressed"] = False
    return rec

def recent_attention(limit: int = 25, ranked: bool = True) -> dict[str, Any]:
    items = _read_jsonl(attention_path())
    if ranked:
        items = sorted(items, key=lambda r: _rank_item(r), reverse=True)
    else:
        # Take the tail (most recent appended entries) then reverse so newest is first.
        items = items[-max(1, int(limit)) :]
        items.reverse()
    items = items[: max(1, int(limit))]
    return {"ok": True, "count": len(items), "items": items, "path": str(attention_path())}

def summarize_attention() -> dict[str, Any]:
    states: dict[str, int] = {}
    severities: dict[str, int] = {}
    for rec in _read_jsonl(attention_path()):
        state = str(rec.get("state") or "unknown")
        sev = str(rec.get("severity") or "unknown")
        states[state] = states.get(state, 0) + 1
        severities[sev] = severities.get(sev, 0) + 1
    return {
        "ok": True,
        "path": str(attention_path()),
        "states": states,
        "severities": severities,
        "needs_attention_now": states.get("blocked", 0) + states.get("pending_confirmation", 0),
    }

def top_attention(limit: int = 10) -> dict[str, Any]:
    return recent_attention(limit=limit, ranked=True)
