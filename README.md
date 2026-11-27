# ELI Creation Station

A studio for entertainment, work and projects: posts for every platform, images, videos, games and
code, made on your own machine, with ELI beside you on the project. For paid work and for hobbyists
alike, on whatever machine they have.

It is an official ELI bundle (product id `creation`), like ELI Legal and ELI VR: an application of
its own that ELI v3 can open in place of its window, or that runs on its own with its own licence.

**Version 0.1.0 · an early build.** Linux, Windows, macOS.

## The tabs

| Tab | What it makes today | Coming, shown in the app with what your machine needs |
|---|---|---|
| **Socials** | Posts for X, Threads, Bluesky, Instagram, TikTok, LinkedIn, Facebook and YouTube from one brief, in your voice, within each platform's limit | A content calendar; thumbnails in each platform's shape |
| **Images** | With a local image model (SSD-1B now; FLUX.1 schnell and others as they are added), or ELI v3's procedural renderer on any machine | stable-diffusion.cpp for AMD, Intel and Apple through Vulkan and Metal |
| **Videos** | Animatics: images in order, timed and crossfaded | Text and image to video, narration, captions, music |
| **Games** | A game designed from a pitch, and played in a browser from one HTML file | Played in ELI VR (the kinds are the ones ELI VR plays); 3D assets |
| **Editing** | Crop to a platform's shape, resize, enlarge, turn, adjust, sharpen, caption, convert | AI upscale; background removal |
| **Coding** | ELI v3's coding agent: it plans, writes, runs and repairs code against tests it writes | |
| **Settings** | This machine and its tier, the main model, how models load, the models, ELI, provenance, the licence | |

**ELI beside the tabs.** With your permission ELI follows the project you are working on (its folder,
and the screen if you allow it), notices what matters (a platform's limit, a licence warning on an
asset, a look or a voice drifting), offers it, and can ask to pause and talk the project through. You
choose how much: off, quiet, helpful or active. Opened by ELI v3, it is ELI v3's own ELI: its eyes,
attention and voice. Nothing is looked at until you turn it on, and nothing leaves the machine.

## The main model stays loaded between jobs; the others load when needed

The main model (a GGUF file, a model server on this machine, or ELI v3's model when ELI v3 opens
Creation Station) stays loaded between jobs: it writes, plans, codes and is ELI's voice. When a heavy
image or video job needs its memory, it steps aside for that job and is loaded again, in the
background, as soon as the job is done (Settings → Models can keep it loaded instead). Every specialist model
(images, video, music, speech, 3D, upscaling, reading the screen) is loaded **in a process of its
own when a job needs it**, and unloaded when it has been idle, which gives all of its memory back
on every vendor's graphics driver. Before loading, the planner finds room: beside what is loaded,
on another card, by unloading the longest-idle specialist, by letting the main model step aside
for the job, or on the processor. Otherwise the job is refused with the reason. See [docs/MODELS.md](docs/MODELS.md).

## Every machine, honestly

Sold for every kind of machine: a laptop with no graphics card, an Apple silicon Mac, a gaming PC,
a workstation. Each machine gets a tier (T0 processor only, T1 integrated or small graphics, T2
6-12 GB, T3 12-24 GB, T4 24 GB or more), and every feature this machine cannot run is shown greyed
with the reason, never silently made worse. The machine is read by ELI's own probes (ELI Legal's
standalone copy of ELI v3's). Run on real hardware so far: Linux with NVIDIA. See
[docs/HARDWARE.md](docs/HARDWARE.md).

## What every output carries

A manifest of the models that made it and their licences; an entry in a tamper-evident ledger
(ELI Legal's HMAC-chained audit ledger); and, in the file, the IPTC mark that says whether a trained
model made it. Only models whose licence lets a paid product pass them on are ever downloaded, and
a model you bring yourself has its licence carried onto everything it makes.

## Licence

An installed copy runs for **seven days from its first use**, then needs a key: an ELI Creation
Station key, or an ELI v3 key sold with ELI Creation Station included. Keys for other ELI products
don't open it. The terms are in [LICENSE](LICENSE).

A key bought from the store is **activated once**, the first time it is entered on a computer (Help →
Licence… → Enter a key, or `eli-creation licence activate`): the key and the computer's activation
code (a one-way code from the operating system's install id) go to ELI's licence server, which counts
the computer against the licence's seats; after that the key is checked offline. Moving to a new
computer: **Deactivate this computer** in the licence window (`eli-creation licence deactivate`). No
internet on this computer: activate it from any other device at https://licences.geteli.tech/activate
with the code the licence window shows (`eli-creation licence code`).

When online, Creation Station also asks the licence server at launch for its list of withdrawn
licences and, during the trial, for this computer's trial (the product and the activation code).
Nothing you make, write or open is ever sent.

## Run it

From a release: download the file for your system, check it against `SHA256SUMS`, install, start
**ELI Creation Station**. From source (Python 3.10 or newer):

```bash
./install.sh                    # Linux, macOS: a private environment, launchers, a menu entry
./install.ps1                   # Windows
eli-creation selftest           # an image, an edit and an animatic; the ledger checked
eli-creation hardware           # this machine, its tier, what each feature needs
```

For development: `python -m venv .venv && .venv/bin/pip install -e ".[dev,all]"` (eli-sdk is
private: `scripts/fetch_eli_sdk.py`), then `pytest`, `ruff check src tests`, `mypy`.

## Made from ELI's own code

Most of Creation Station is code ELI already has, taken whole and kept in step:
[reuse.json](reuse.json) lists every file, the product and commit it came from, and the few
patches (each with its reason); `scripts/sync_reused.py` brings them up to date and `--check` says
when an original has changed. From ELI Legal: the hardware probes, GGUF fitting, graphics packs,
model servers, the network guard, the audit ledger, licensing, the bundle register, the look of the
window and the whole packaging and release process. From ELI v3: the image engine, the coding agent,
screen analysis and the attention queue. From ELI VR: the release privacy gate. See
[docs/REUSE.md](docs/REUSE.md) and [docs/PACKAGING.md](docs/PACKAGING.md).

## Documents

| | |
|---|---|
| [docs/MODELS.md](docs/MODELS.md) | The loading rule, the models folder, the catalogue and the licence gate |
| [docs/HARDWARE.md](docs/HARDWARE.md) | Tiers, what each needs, what has been tested |
| [docs/PACKAGING.md](docs/PACKAGING.md) | How every ELI bundle is packaged and released; bundles and packages |
| [docs/REUSE.md](docs/REUSE.md) | What came from ELI Legal, ELI v3 and ELI VR |
| [RELEASE.md](RELEASE.md) | Cutting a release |
| [SECURITY.md](SECURITY.md) | Reporting a vulnerability |

ShadowESC95 · jaybridgeman0095@gmail.com
