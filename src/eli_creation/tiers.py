"""What this machine can do, as a tier, so every feature can say whether it runs here and why not.

Creation Station is sold for every kind of machine: a laptop with no graphics card, an Apple
silicon Mac, a gaming PC, a workstation with several cards, a headless server. Nothing is sized
for one machine. Every feature declares what it needs (a ``Need``), and ``can_run`` answers for
this machine in words, so a feature it cannot run is shown greyed with the reason, never silently
made worse.

The machine is read by the probes ELI already uses, not new ones:

    hosted by ELI v3   ELI v3's own profile (eli.core.hardware_profile), card by card
    on its own         ELI Legal's standalone copy of the same probes (adapters/inference/hardware:
                       nvidia-smi, rocm-smi and the amdgpu counters, the kernel's device list for
                       Intel and shared-memory graphics, the Windows display registry, macOS's
                       system_profiler), with each NVIDIA card read on its own

This module only turns what they report into tiers and placements.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TIERS = ("T0", "T1", "T2", "T3", "T4")
TIER_LABELS = {
    "T0": "Processor only",
    "T1": "Integrated or small graphics",
    "T2": "Mid-range graphics (6-12 GB)",
    "T3": "High-end graphics (12-24 GB)",
    "T4": "Workstation (24 GB or more, or several cards)",
}
TIER_EXAMPLES = {
    "T0": "older laptops, virtual machines, servers without a graphics card",
    "T1": "Apple M-series with 8 GB, Intel and AMD integrated graphics, 4 GB cards",
    "T2": "RTX 2060-4060 class, Radeon RX 6600-7600, Arc A750, Apple silicon with 16 GB",
    "T3": "RTX 4070 Ti-4080 class, Radeon RX 7900, Apple silicon with 32 GB",
    "T4": "24 GB cards and up, several cards, Apple silicon with 64 GB or more",
}


@dataclass(frozen=True)
class Accelerator:
    index: int
    vendor: str  # nvidia | amd | intel | apple | qualcomm | unknown
    name: str
    kind: str  # discrete | integrated | unified
    memory_mb: int  # dedicated memory, or for shared memory the share the GPU may use
    free_mb: int | None = None
    backends: tuple[str, ...] = ()
    measured: bool = True  # False: estimated from the card's model, corrected by what loads

    @property
    def usable_mb(self) -> int:
        return int(self.free_mb if self.free_mb is not None else self.memory_mb)

    def describe(self) -> str:
        size = f"{self.memory_mb / 1024:.0f} GB" if self.memory_mb else "memory unknown"
        if not self.measured:
            size = f"about {size}"
        kind = {"unified": "unified memory", "integrated": "shared memory"}.get(self.kind, self.kind)
        return f"{self.name} ({size}, {kind})"


@dataclass(frozen=True)
class Machine:
    os: str  # linux | windows | macos | android | other
    arch: str
    cpu_threads: int
    ram_mb: int
    available_ram_mb: int
    accelerators: tuple[Accelerator, ...] = ()
    source: str = "probe"  # eli_v3 | probe | given

    @property
    def tier(self) -> str:
        return classify(self)

    @property
    def backends(self) -> tuple[str, ...]:
        found: list[str] = []
        for acc in self.accelerators:
            found += [b for b in acc.backends if b not in found]
        return (*found, "cpu")

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out.update(tier=self.tier, tier_label=TIER_LABELS[self.tier], backends=list(self.backends))
        return out


@dataclass(frozen=True)
class Need:
    """What one feature or model needs to run."""

    min_tier: str = "T0"
    accelerator_mb: int = 0  # memory one accelerator must have; 0: the processor will do
    backends: tuple[str, ...] = ()  # any one of these; empty: any, the processor included
    ram_mb: int = 0
    cpu_ok: bool = True  # may run on the processor when no accelerator fits (slowly)


# ── tiers ───────────────────────────────────────────────────────────────────
def _tier_of(acc: Accelerator) -> int:
    gb = acc.memory_mb / 1024
    if acc.kind == "integrated":
        return 1  # shares the processor's memory and its bandwidth
    if gb >= 24:
        return 4
    if gb >= 12:
        return 3
    if gb >= 6:
        return 2
    return 1


def classify(machine: Machine) -> str:
    """The tier of the machine's best accelerator; two or more 12 GB cards together make a T4."""
    if not machine.accelerators:
        return "T0"
    best = max(_tier_of(a) for a in machine.accelerators)
    big = [a for a in machine.accelerators if a.kind == "discrete" and a.memory_mb >= 12 * 1024]
    if len(big) >= 2:
        best = 4
    return TIERS[best]


def tier_at_least(machine: Machine, tier: str) -> bool:
    return TIERS.index(machine.tier) >= TIERS.index(tier)


def _backend_name(backend: str) -> str:
    return {
        "cuda": "NVIDIA CUDA", "rocm": "AMD ROCm", "mps": "Apple Metal (MPS)", "metal": "Apple Metal",
        "xpu": "Intel XPU", "directml": "DirectML", "vulkan": "Vulkan", "cpu": "the processor",
    }.get(backend, backend)


def can_run(need: Need, machine: Machine) -> tuple[bool, str]:
    """Whether this machine can run something that needs ``need``, and if not, why, in words."""
    if machine.ram_mb and need.ram_mb and machine.ram_mb < need.ram_mb:
        return False, (f"needs {need.ram_mb / 1024:.0f} GB of system memory; "
                       f"this machine has {machine.ram_mb / 1024:.0f} GB")
    wanted = tuple(b for b in need.backends if b != "cpu")
    if need.accelerator_mb <= 0 and not wanted:
        return True, ""
    fitting = [
        a for a in machine.accelerators
        if (not wanted or set(a.backends) & set(wanted)) and a.memory_mb >= need.accelerator_mb
    ]
    if fitting and tier_at_least(machine, need.min_tier):
        return True, ""
    if need.cpu_ok:
        return True, "runs on the processor here, slowly: no graphics card here fits it"
    if not machine.accelerators:
        return False, (f"needs a graphics card with {need.accelerator_mb / 1024:.0f} GB or more; "
                       "this machine has none that can be used")
    if wanted and not any(set(a.backends) & set(wanted) for a in machine.accelerators):
        offered = ", ".join(_backend_name(b) for b in machine.backends if b != "cpu") or "none"
        return False, f"needs {', '.join(_backend_name(b) for b in wanted)}; this machine offers {offered}"
    best = max(machine.accelerators, key=lambda a: a.memory_mb)
    return False, (f"needs a graphics card with {need.accelerator_mb / 1024:.0f} GB or more "
                   f"(tier {need.min_tier}); the best here is {best.describe()}")


# ── reading the machine, through ELI's own probes ───────────────────────────
def _os_name() -> str:
    if "ANDROID_ROOT" in os.environ or sys.platform == "android":
        return "android"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    return "windows" if os.name == "nt" else "other"


def _backends(vendor: str, kind: str, os_name: str, vulkan: bool) -> tuple[str, ...]:
    out: list[str] = []
    if vendor == "nvidia":
        out.append("cuda")
    elif vendor == "amd":
        rocm = Path("/opt/rocm").is_dir() or bool(shutil.which("rocminfo"))
        if os_name == "linux" and kind == "discrete" and rocm:
            out.append("rocm")
        if os_name == "windows":
            out.append("directml")
    elif vendor == "intel":
        if kind == "discrete":
            out.append("xpu")
        if os_name == "windows":
            out.append("directml")
    elif vendor == "apple":
        out += ["mps", "metal"]
    if vulkan and vendor != "apple":
        out.append("vulkan")
    return tuple(out)


def _from_eli_v3() -> Machine | None:
    """ELI v3's own reading, card by card, when ELI v3 hosts Creation Station."""
    from eli_creation.adapters.eli_v3.compat import EliV3Unavailable, import_attr

    try:
        hw = import_attr("eli.core.hardware_profile", "detect_hardware")()
    except (EliV3Unavailable, Exception):
        return None
    os_name = _os_name()
    ram_mb = int(float(getattr(hw, "ram_gb", 0)) * 1024)
    vulkan = bool(getattr(hw, "vulkan_available", False))
    accs = []
    for i, gpu in enumerate(getattr(hw, "gpus", None) or []):
        vendor = str(gpu.get("vendor") or "unknown").lower()
        kind = "unified" if vendor == "apple" else "integrated" if gpu.get("integrated") else "discrete"
        free = gpu.get("free_mb")
        accs.append(Accelerator(int(gpu.get("index", i)), vendor, str(gpu.get("name") or vendor), kind,
                                int(gpu.get("total_mb") or 0), int(free) if free is not None else None,
                                _backends(vendor, kind, os_name, vulkan)))
    return Machine(os_name, platform.machine().lower(), int(getattr(hw, "cpu_threads", 1)), ram_mb,
                   int(float(getattr(hw, "available_ram_gb", 0)) * 1024), tuple(accs), "eli_v3")


def from_hardware(hw: Any, *, nvidia_cards: list[tuple[str, int, int]] | None = None) -> Machine:
    """A Machine from ELI Legal's ``Hardware`` reading (and, for NVIDIA, each card on its own)."""
    os_name = _os_name()
    vulkan = bool(getattr(hw, "vulkan_loader", False))
    accs: list[Accelerator] = []
    vendor = str(getattr(hw, "gpu_vendor", "") or "").lower()
    if getattr(hw, "has_gpu", False):
        if vendor == "nvidia" and nvidia_cards:
            for i, (name, total, free) in enumerate(nvidia_cards):
                accs.append(Accelerator(i, "nvidia", name, "discrete", int(total), int(free),
                                        _backends("nvidia", "discrete", os_name, vulkan)))
        else:
            kind = "unified" if vendor == "apple" else "integrated" if hw.gpu_integrated else "discrete"
            accs.append(Accelerator(0, vendor or "unknown", hw.gpu_name or "graphics", kind,
                                    int(hw.total_vram_mb), int(hw.free_vram_mb),
                                    _backends(vendor, kind, os_name, vulkan), bool(hw.vram_measured)))
    return Machine(os_name, platform.machine().lower(), int(hw.cpu_threads), int(float(hw.ram_gb) * 1024),
                   int(float(hw.available_ram_gb) * 1024), tuple(accs), "probe")


def probe(*, hosted: bool = False) -> Machine:
    """Read this machine now. Never raises: anything unreadable counts as absent."""
    if hosted:
        machine = _from_eli_v3()
        if machine is not None:
            return machine
    from eli_creation.adapters.inference import hardware

    hw = hardware.detect(force=True)
    cards = None
    if str(getattr(hw, "gpu_vendor", "")).lower() == "nvidia" and int(getattr(hw, "gpu_count", 1)) > 1:
        try:
            cards = hardware._nvidia_cards()  # each card's name, total and free memory
        except Exception:
            cards = None
    return from_hardware(hw, nvidia_cards=cards)


def machine_from_dict(data: dict[str, Any]) -> Machine:
    """A machine described by hand (tests, a support report): {os, ram_mb, accelerators: [...]}."""
    accs = tuple(
        Accelerator(int(a.get("index", i)), str(a.get("vendor", "unknown")), str(a.get("name", "graphics")),
                    str(a.get("kind", "discrete")), int(a.get("memory_mb", 0)), a.get("free_mb"),
                    tuple(a.get("backends", ())))
        for i, a in enumerate(data.get("accelerators", []))
    )
    ram = int(data.get("ram_mb", 16384))
    return Machine(str(data.get("os", "linux")), str(data.get("arch", "x86_64")),
                   int(data.get("cpu_threads", 8)), ram, int(data.get("available_ram_mb", ram // 2)),
                   accs, "given")
