"""Every kind of machine buyers have gets a tier, and a feature it cannot run says why."""

from __future__ import annotations

import pytest

from eli_creation.tiers import Need, can_run, classify, from_hardware, machine_from_dict


def gpu(vendor, memory_gb, kind="discrete", backends=("cuda",), index=0):
    return {"index": index, "vendor": vendor, "name": f"{vendor} {memory_gb} GB", "kind": kind,
            "memory_mb": int(memory_gb * 1024), "backends": list(backends)}


@pytest.mark.parametrize(
    ("accelerators", "tier"),
    [
        ([], "T0"),  # a laptop or server with no usable graphics
        ([gpu("intel", 2, "integrated", ("vulkan",))], "T1"),
        ([gpu("amd", 0.5, "integrated", ("vulkan",))], "T1"),  # an APU's carve-out
        ([gpu("apple", 8 * 0.66, "unified", ("mps", "metal"))], "T1"),  # M-series, 8 GB
        ([gpu("nvidia", 4)], "T1"),
        ([gpu("nvidia", 8)], "T2"),
        ([gpu("amd", 8, backends=("rocm", "vulkan"))], "T2"),
        ([gpu("apple", 16 * 0.66, "unified", ("mps", "metal"))], "T2"),
        ([gpu("nvidia", 16)], "T3"),
        ([gpu("apple", 32 * 0.66, "unified", ("mps", "metal"))], "T3"),
        ([gpu("nvidia", 24)], "T4"),
        ([gpu("nvidia", 12), gpu("nvidia", 12, index=1)], "T4"),  # two 12 GB cards
        ([gpu("nvidia", 8), gpu("nvidia", 8, index=1)], "T2"),
    ],
)
def test_tier(accelerators, tier):
    assert classify(machine_from_dict({"accelerators": accelerators})) == tier


def test_a_feature_says_why_it_cannot_run():
    laptop = machine_from_dict({"accelerators": []})
    ok, why = can_run(Need(min_tier="T3", accelerator_mb=12000, backends=("cuda",), cpu_ok=False), laptop)
    assert not ok and "graphics card" in why
    mac = machine_from_dict({"os": "macos", "accelerators": [gpu("apple", 20, "unified", ("mps", "metal"))]})
    ok, why = can_run(Need(min_tier="T2", accelerator_mb=8000, backends=("cuda",), cpu_ok=False), mac)
    assert not ok and "NVIDIA CUDA" in why and "Apple" in why
    ok, why = can_run(Need(min_tier="T2", accelerator_mb=8000, backends=("cuda",), cpu_ok=True), laptop)
    assert ok and "slowly" in why


def test_reading_eli_legals_hardware_reading():
    class Hw:
        cpu_threads, ram_gb, available_ram_gb = 8, 16.0, 9.0
        has_gpu, gpu_name, gpu_vendor, gpu_integrated = True, "Apple M3", "apple", True
        total_vram_mb, free_vram_mb, vram_measured, vulkan_loader, gpu_count = 10800, 10000, False, False, 1

    m = from_hardware(Hw())
    assert m.accelerators[0].kind == "unified" and "mps" in m.accelerators[0].backends
    assert m.tier == "T2"
