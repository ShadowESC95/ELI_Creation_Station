"""ELI Creation Station as an ELI edition pack, in the shape ELI Legal's is (its
``eli_legal.edition``): a manifest in ELI v3's schema, the policy hooks, and ``register``, the
activation entry point advertised to ELI v3 through the ``eli.editions`` entry-point group.

It takes in ELI v3's ``content`` edition (copywriting, social, brand voice, image generation),
which was a scaffold with nothing in it, so the product has one name.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from eli_creation import PRODUCT, __version__
from eli_creation.edition import policy

EDITION_NAME = PRODUCT
CONTRACT_VERSION = 1
_HERE = Path(__file__).resolve().parent


def manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((_HERE / "manifest.json").read_text(encoding="utf-8"))
    data["package_version"] = __version__
    return data


def register(host: Mapping[str, Any] | None = None, entitled: Iterable[str] | None = None) -> dict[str, Any]:
    """What ELI v3's edition registry reads: the manifest and the policy hooks, when this machine is
    entitled to the edition (or when ELI v3 does not say)."""
    granted = entitled is None or EDITION_NAME in set(entitled)
    return {
        "contract": CONTRACT_VERSION,
        "edition": EDITION_NAME,
        "active": granted,
        "manifest": manifest(),
        "policy": {
            "system_prompt_addendum": policy.system_prompt_addendum,
            "output_disclaimer": policy.output_disclaimer,
            "blocked_actions": policy.blocked_actions,
        },
    }
