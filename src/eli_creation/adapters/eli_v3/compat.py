# Reused from ELI_Legal: src/eli_legal/adapters/eli_v3/compat.py @ 3b05ccd88f. Do not edit here: change it in ELI_Legal and run scripts/sync_reused.py.
from __future__ import annotations

import importlib
from typing import Any


class EliV3Unavailable(RuntimeError):
    pass


# The complete list of host modules ELI Creation Station may import. A test asserts nothing else is used.
ALLOWED_HOST_MODULES = frozenset(
    {
        "eli.cognition.gguf_inference",
        "eli.core.netguard",
        "eli.tools.registry.capability_registry",
        # Creation Station also reads the machine, the licence products, and ELI's own eyes,
        # attention and world, so ELI in the studio is the same ELI, not a second mind.
        "eli.core.hardware_profile",
        "eli.licensing.products",
        "eli.perception.os_controller",
        "eli.perception.screen_analysis",
        "eli.perception.vision",
        "eli.perception.conversation",
        "eli.planning.attention_queue",
        "eli.planning.insight_synthesis",
        "eli.world.games",
        "eli.world.building",
    }
)


def import_attr(module_name: str, attr_name: str) -> Any:
    if module_name not in ALLOWED_HOST_MODULES:
        raise EliV3Unavailable(f"ELI Creation Station may not import host module {module_name!r}")
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - depends on an optional ELI installation
        raise EliV3Unavailable(
            f"ELI v3 module {module_name!r} is unavailable; this adapter only works inside ELI v3"
        ) from exc
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:  # pragma: no cover
        raise EliV3Unavailable(f"host attribute {module_name}.{attr_name} is unavailable") from exc
