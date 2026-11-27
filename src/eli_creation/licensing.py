# Adapted from ELI_Legal: src/eli_legal/licensing.py @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
"""Whether this copy of ELI Creation Station may run.

The same rule as every ELI product (ELI v3, ELI Legal, ELI VR): an installed copy needs a licence,
and before a key is entered it runs a **seven-day trial** from its first use. ELI Creation Station
opens only with an ELI Creation Station key, or an ELI v3 key sold with ELI Creation Station
included (a bundle); keys for any other ELI product open nothing here. Keys are kept in one folder
on the computer that each ELI product reads for its own key, so an ELI v3 key with ELI Creation
Station included works here wherever it was entered. They are checked offline against ELI's public
key (eli-sdk), with the revocation lists ELI has published.

The trial covers every feature; what is made during it carries the same AI-content marking as
always. It is kept by eli_sdk.trial.LocalTrial, so deleting its record, changing environment
variables, editing it or setting the clock back does not restart it, and nor does deleting it once
Creation Station's own data shows it has been used. A key can be entered at any time: during the
trial, at its end, or later.

A source checkout needs no licence. A copy ELI v3 opened in its own process needs none of its own
only when that ELI v3 knows Creation Station as an ELI product, and so checked its licence before
starting it; an ELI v3 that does not know it yet would start it as another publisher's bundle,
with no check at all, so then this copy checks its own.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eli_sdk import Entitlement, InvalidKey, KeyStore, License, LocalTrial, TrialStatus, read_key
from eli_sdk.products import register_product

from eli_creation import PRODUCT, TITLE, __version__

# eli-sdk 1.3.0 predates this product; making it known lets keys for it be read (eli-sdk docs/keys.md).
register_product(PRODUCT, TITLE)

OFFERING = "creation-pro"
# Where to buy: the website, opened in the browser when the person asks. Nothing in this
# program ever goes online for its licence.
BUY = "https://geteli.tech"
TRIAL_SCOPE = "every feature"

_YES = {"1", "true", "yes", "on"}
_public_key: Any = None
_hosted = False
_trial_locations: list[Path] | None = None  # tests only: where the trial's record is kept


def host_checks_this_product() -> bool:
    """Whether the ELI v3 hosting this process knows Creation Station as an ELI product, and so
    checked its licence before starting it (eli.bundles.entitled)."""
    try:
        from eli_creation.adapters.eli_v3.compat import import_attr

        bundle_product = import_attr("eli.licensing.products", "bundle_product")
        return bundle_product(PRODUCT, PRODUCT) == PRODUCT
    except Exception:
        return False


def hosted_by_eli() -> None:
    global _hosted
    _hosted = host_checks_this_product()


def required() -> bool:
    if _hosted:
        return False
    if os.environ.get("ELI_CREATION_REQUIRE_LICENCE", "").strip().lower() in _YES:
        return True
    return not _source_checkout()


def _source_checkout() -> bool:
    """Running from a git working copy of ELI Creation Station's source, as its developer does: never a
    packaged build, and never a copy installed with pip (from a wheel or from the repository),
    which is a copy someone may have paid for. Those all need a licence or the trial."""
    if getattr(sys, "frozen", False):
        return False
    root = Path(__file__).resolve().parents[2]
    return (root / ".git").exists() and (root / "pyproject.toml").is_file() and (root / "src").is_dir()


def store() -> KeyStore:
    return KeyStore.shared()


def status() -> Entitlement:
    """What the keys on this machine grant (a trial *key* included), not the local trial."""
    return store().entitlement(PRODUCT, _public_key, version=__version__)


# ── the trial ────────────────────────────────────────────────────────────────
def _default_data_folders() -> list[Path]:
    """Where an installed Creation Station keeps its data, found from the account itself, so
    pointing ELI_CREATION_HOME or XDG_DATA_HOME somewhere new does not hide earlier use."""
    from eli_sdk.machine import account_home, windows_folder

    home = account_home()
    if os.name == "nt":
        return [(windows_folder("local") or home / "AppData" / "Local") / "ELI Creation Station"]
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "ELI Creation Station"]
    return [home / ".local" / "share" / "eli-creation"]


def _used_before() -> bool:
    """Creation Station's own data from earlier use: its provenance ledger, or a project."""
    from eli_creation.paths import home_dir

    folders = _default_data_folders()
    explicit = home_dir()
    if explicit is not None:
        folders.append(explicit)
    for folder in folders:
        if (folder / "provenance" / "ledger.sqlite3").exists():
            return True
        projects = folder / "projects"
        if projects.is_dir() and any(projects.iterdir()):
            return True
    return False


def trial() -> LocalTrial:
    return LocalTrial(PRODUCT, used_before=_used_before, locations=_trial_locations)


@dataclass(frozen=True)
class Standing:
    """May this copy run, and on what terms."""

    granted: bool
    reason: str
    on_trial: bool = False
    days_left: int = 0
    licence: License | None = None
    trial: TrialStatus | None = None

    def describe(self) -> str:
        if not self.granted:
            return f"ELI Creation Station is not licensed on this machine: {self.reason}"
        if self.on_trial:
            n = self.days_left
            return (
                f"ELI Creation Station trial: {n} day{'s' if n != 1 else ''} left, {TRIAL_SCOPE}. "
                "A licence key can be entered at any time."
            )
        lic = self.licence
        if lic is None:
            return "ELI Creation Station: no licence needed for this copy"
        return f"{self.reason}: {lic.tier}, {lic.seats} seat(s), ELI Creation Station {lic.major_version}.x"


def _days_left(lic: License) -> int:
    from datetime import datetime, timezone

    if not lic.expires_at:
        return 0
    ends = datetime.fromisoformat(str(lic.expires_at).replace("Z", "+00:00"))
    seconds = int((ends - datetime.now(timezone.utc)).total_seconds())
    return max(0, -(-seconds // 86400))


def standing(*, start: bool = False) -> Standing:
    """Where this copy stands. ``start`` begins the trial on first use (at launch), and also
    records that Creation Station ran now, so a clock set back is noticed."""
    if not required():
        return Standing(True, "no licence needed for this copy")
    got = status()
    if got.granted and got.license is not None:
        lic = got.license
        return Standing(
            True,
            got.reason,
            on_trial=lic.trial,
            days_left=_days_left(lic) if lic.trial else 0,
            licence=lic,
        )
    held_trial = [
        lic for lic in store().licenses(_public_key) if lic.product == PRODUCT and lic.trial
    ]
    if held_trial:  # a trial key from the store was this machine's trial; no second one
        return Standing(False, got.reason)
    local = trial()
    ts = local.start() if start else local.status()
    if ts.active:
        return Standing(True, "ELI Creation Station trial", on_trial=True, days_left=ts.days_left, trial=ts)
    reason = ts.why if ts.state == "ended" else got.reason
    return Standing(False, reason, trial=ts)


def allowed() -> bool:
    """Whether this run may go on; begins the trial on first use."""
    return standing(start=True).granted


# ── keys ─────────────────────────────────────────────────────────────────────
def ask_the_seller() -> str:
    """What to do with a licence that still needs this computer's key: the same in every ELI product."""
    return (
        "This is the ELI Creation Station licence, not this computer's key. Send the seller your licence number and "
        f"this computer's activation code:\n  {activation_code()}\nand enter the key you get back. It "
        "works on this computer, with no internet needed."
    )


def activate(key: str) -> License:
    """Keep this computer's key and confirm it licenses ELI Creation Station. Nothing is sent anywhere. An ELI v3
    key that doesn't include ELI Creation Station is still kept, for ELI v3, and the error says why it isn't
    enough here; a licence that is not this computer's key says how to get it (ask_the_seller)."""
    if read_key(key, _public_key).needs_activation:
        raise InvalidKey(ask_the_seller())
    lic = store().add(key, _public_key)
    got = status()
    if not got.granted:
        raise InvalidKey(got.reason)
    return lic


def deactivate() -> bool:
    """Remove ELI Creation Station's key from this computer (then tell the seller, who frees its seat for another
    computer). Nothing is sent anywhere."""
    return store().remove(PRODUCT)


def remove() -> bool:
    """The same as deactivate."""
    return store().remove(PRODUCT)


def activation_code() -> str:
    """This computer's activation code: what the seller needs to make this computer's key."""
    from eli_sdk.activation import activation_code as code

    return code()


def explain() -> str:
    st = standing()
    return (
        f"ELI Creation Station needs a licence: {st.reason}.\n"
        "Enter this computer's ELI Creation Station key (or an ELI v3 key sold with ELI Creation Station included):\n"
        "    eli-creation licence activate YOUR-KEY\n"
        "Each computer has its own key: send the seller your licence number and this computer's\n"
        f"activation code ({activation_code()}).\n"
        f"Buy one (eli-creation licence buy, or {BUY})"
    )
