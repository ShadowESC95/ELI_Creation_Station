"""Which models may be fetched for a buyer, and what an output made with a model may be used for.

ELI's rule, the same one ELI v3's builds enforce: ELI passes on (bundles, publishes, fetches) only
models whose licence lets a closed, paid product do so. A non-commercial, research-only, custom or
territory-restricted model is never fetched by Creation Station, because fetching it would accept
its licence on the buyer's behalf (the reason ELI v3 removed XTTS-v2).

A buyer may still bring a model of their own (Settings, or a folder in the models directory). Its
licence is theirs to accept, and every asset that model touches carries that licence's class in
its provenance, so an export can warn before a non-commercial output is used commercially.
"""

from __future__ import annotations

from collections.abc import Iterable

# SPDX ids that let a closed, paid product pass the model on and its outputs be used commercially.
PERMISSIVE = frozenset(
    {
        "Apache-2.0",
        "MIT",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Unlicense",
        "CC0-1.0",
        "CC-BY-4.0",
        "Zlib",
    }
)
COPYLEFT_PREFIXES = ("GPL-", "AGPL-", "LGPL-", "MPL-", "CC-BY-SA")

# From most to least permissive. An output's class is the least permissive of its models'.
CLASSES = ("permissive", "copyleft", "custom", "territory", "non-commercial", "unknown")


def licence_class(licence: str) -> str:
    lic = (licence or "").strip()
    if not lic:
        return "unknown"
    if lic in PERMISSIVE:
        return "permissive"
    if lic.startswith(COPYLEFT_PREFIXES):
        return "copyleft"
    low = lic.lower()
    if "-nc" in low or "non-commercial" in low or "noncommercial" in low or "research" in low:
        return "non-commercial"
    return "custom"


def may_fetch(licence: str, *, verified: bool, revision: str) -> tuple[bool, str]:
    """Whether Creation Station may download this model for a buyer, and why not."""
    cls = licence_class(licence)
    if cls != "permissive":
        return False, f"its licence ({licence or 'not stated'}) is {cls}; bring it yourself if you accept it"
    if not verified:
        return False, "its licence has not yet been checked against the model card and recorded"
    if not revision:
        return False, "no revision is pinned, so the files fetched could change under the same name"
    return True, ""


def output_class(classes: Iterable[str]) -> str:
    """The class of an output made with models of these classes: the least permissive wins."""
    worst = "permissive"
    for cls in classes:
        cls = cls if cls in CLASSES else "unknown"
        if CLASSES.index(cls) > CLASSES.index(worst):
            worst = cls
    return worst


def output_warning(cls: str) -> str:
    """What an export says about an output of this class, or "" when it is free to use."""
    return {
        "permissive": "",
        "copyleft": "Made with a copyleft-licensed model: its licence may attach conditions to sharing this output.",
        "custom": "Made with a model under a custom licence: check that licence before using this output commercially.",
        "territory": "Made with a model whose licence excludes some countries: check it applies where you are.",
        "non-commercial": "Made with a non-commercial model: this output may not be used commercially.",
        "unknown": "Made with a model whose licence is unknown: do not use this output commercially until you know it.",
    }.get(cls, "")
