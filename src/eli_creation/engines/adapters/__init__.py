"""What a worker process loads: one adapter per kind of model runtime.

An adapter is a class with ``load(spec, device) -> dict``, ``call(method, args) -> Any`` and
``unload()``. The worker (runtimes/worker.py) loads adapters from this package only.
"""
