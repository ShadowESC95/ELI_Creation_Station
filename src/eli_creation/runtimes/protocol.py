"""The worker protocol: one JSON object per line, each way.

    → {"id": 1, "op": "hello"}
    ← {"id": 1, "ok": true, "result": {"protocol": 1, "pid": 4242, "python": "3.12.8"}}
    → {"id": 2, "op": "load", "adapter": "module:Class", "spec": {...}, "device": {...}}
    ← {"id": 2, "ok": true, "result": {"memory_mb": 5800}}
    → {"id": 3, "op": "call", "method": "generate", "args": {...}}
    ← {"id": 3, "ok": false, "error": "OutOfMemoryError: ..."}
    → {"id": 4, "op": "shutdown"}

Files (images, video, audio) never travel in a message: the worker writes them into the job's
folder and answers with their paths.
"""

from __future__ import annotations

import json
from typing import Any

PROTOCOL = 1
OPS = ("hello", "load", "call", "unload", "shutdown")
# The only modules a worker loads an adapter from.
ADAPTER_PREFIX = "eli_creation.engines.adapters."


def encode(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n"


def decode(line: str) -> dict[str, Any]:
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("a worker message is a JSON object")
    return value
