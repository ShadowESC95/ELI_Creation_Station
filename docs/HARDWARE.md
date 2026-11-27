# Hardware

Every feature declares what it needs; this machine's tier and accelerators decide whether it runs,
on the graphics card or slowly on the processor, or why not. `eli-creation hardware` prints it all.

| Tier | Machines like it | What runs well |
|---|---|---|
| T0 Processor only | Older laptops, virtual machines, servers | Writing and code with a small main model, procedural images, editing, animatics |
| T1 Integrated or small graphics | Apple M-series 8 GB, Intel and AMD integrated, 4 GB cards | The above, faster; small image models (quantized) |
| T2 6-12 GB | RTX 2060-4060, RX 6600-7600, Arc A750, Apple silicon 16 GB | SDXL-class images, an 8B main model, short video with offloading |
| T3 12-24 GB | RTX 4070 Ti-4080, RX 7900, Apple silicon 32 GB | Larger image models, music, image-to-3D, a 14B main model |
| T4 24 GB+ or several cards | Workstations, Apple silicon 64 GB+ | Video, several specialists at once, the largest main models |

Two cards of 12 GB or more count as T4; the main model and a specialist then sit on different cards.

## How the machine is read

Opened by ELI v3: ELI v3's own profile, card by card. On its own: ELI Legal's standalone copy of
ELI v3's probes (`adapters/inference/hardware.py`): nvidia-smi; rocm-smi and the amdgpu driver's
counters; the kernel's device list for Intel Arc and shared-memory graphics; the Windows display
registry; macOS's system_profiler. Free memory is read when a model is placed, not assumed.

## Backends by vendor

| Vendor | Linux | Windows | macOS |
|---|---|---|---|
| NVIDIA | CUDA, Vulkan | CUDA, Vulkan | |
| AMD | ROCm (discrete, where installed), Vulkan | DirectML, Vulkan | Metal (Intel Macs) |
| Intel | XPU (Arc), Vulkan | DirectML, Vulkan | |
| Apple | | | Metal (MPS) |

## What has been run

| | State |
|---|---|
| Linux, NVIDIA (two RTX 2060 SUPER) | Probed, tiered (T2), the self-test and the window run |
| Processor only (CI runners, Linux, Windows, macOS) | The test suite and the self-test, by CI |
| AMD, Intel, Apple silicon graphics | Written from the vendors' interfaces and ELI's probes; not yet run on hardware |
| A specialist model on a graphics card | The worker and its protocol run with a stand-in model; the diffusers adapter is not yet run on a card |
