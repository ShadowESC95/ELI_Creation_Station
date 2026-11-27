"""The worker side: runs in its own process and holds one specialist model.

    python -m eli_creation.runtimes.worker        (a source install, or a runtime environment)
    eli-creation _worker                          (an installed, frozen copy)

It imports nothing of Creation Station beyond the protocol and the adapter it is told to load, so
it starts quickly and runs in a runtime environment that has only the engine's own libraries.
"""

from __future__ import annotations

import importlib
import os
import sys
import traceback
from typing import Any, TextIO

from eli_creation.runtimes.protocol import ADAPTER_PREFIX, PROTOCOL, decode, encode


def _adapter_class(path: str) -> Any:
    module_name, _, attr = str(path).partition(":")
    if not module_name.startswith(ADAPTER_PREFIX) or not attr:
        raise ValueError(f"a worker loads adapters from {ADAPTER_PREFIX}* only, not {path!r}")
    return getattr(importlib.import_module(module_name), attr)


def serve(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    source = stdin or sys.stdin
    out = stdout or sys.stdout
    # The protocol owns standard output. Anything a model library prints goes to standard error,
    # which the parent keeps in the worker's log.
    sys.stdout = sys.stderr
    adapter: Any = None
    try:
        for raw in source:
            line = raw.strip()
            if not line:
                continue
            try:
                message = decode(line)
            except ValueError as exc:
                out.write(encode({"id": None, "ok": False, "error": f"unreadable message: {exc}"}))
                out.flush()
                continue
            op = message.get("op")
            reply: dict[str, Any] = {"id": message.get("id"), "ok": True, "result": {}}
            try:
                if op == "hello":
                    reply["result"] = {
                        "protocol": PROTOCOL,
                        "pid": os.getpid(),
                        "python": sys.version.split()[0],
                    }
                elif op == "load":
                    if adapter is not None:
                        adapter.unload()
                    adapter = _adapter_class(message["adapter"])()
                    reply["result"] = adapter.load(message.get("spec") or {}, message.get("device") or {}) or {}
                elif op == "call":
                    if adapter is None:
                        raise RuntimeError("no model is loaded in this worker")
                    reply["result"] = adapter.call(str(message.get("method")), message.get("args") or {})
                elif op == "unload":
                    if adapter is not None:
                        adapter.unload()
                    adapter = None
                elif op == "shutdown":
                    out.write(encode(reply))
                    out.flush()
                    break
                else:
                    raise ValueError(f"unknown operation {op!r}")
            except Exception as exc:
                reply = {
                    "id": message.get("id"),
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "trace": traceback.format_exc(limit=6),
                }
            out.write(encode(reply))
            out.flush()
    finally:
        if adapter is not None:
            try:
                adapter.unload()
            except Exception:
                traceback.print_exc()
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
