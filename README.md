# ELI Creation Station

A studio for entertainment, work and projects: posts for every platform, images, videos, games and
code, made on your own machine, with ELI beside you on the project. For paid work and for hobbyists
alike, on whatever machine they have.

It is an official ELI bundle (product id `creation`), like ELI Legal and ELI VR: an application of
its own that ELI v3 can open in place of its window, or that runs on its own with its own licence.

**Version 0.2.0.** Linux, Windows, macOS.

## The studios

| Studio | What it makes today | Coming, shown in the app with what your machine needs |
|---|---|---|
| **Home** | A line to say what to make and where, the studios with what this machine can do in each, what was made last | |
| **Socials** | Posts for X, Threads, Bluesky, Instagram, TikTok, LinkedIn, Facebook and YouTube from one brief, in your voice, within each platform's limit, each draft shown as it reads there with its share of the limit | A content calendar; thumbnails in each platform's shape |
| **Images** | With a local image model (SSD-1B now; FLUX.1 schnell and others as they are added), or ELI v3's procedural renderer on any machine; styles shown as pictures rendered on this machine; seeds kept or rolled; prompts improved by ELI | stable-diffusion.cpp for AMD, Intel and Apple through Vulkan and Metal |
| **Videos** | Animatics: a storyboard of pictures in order, played in the window as it will move, then made | Text and image to video, narration, captions, music |
| **Games** | A game designed from a pitch, shown as a design card, and played in a browser from one HTML file | Played in ELI VR (the kinds are the ones ELI VR plays); 3D assets |
| **Editing** | Crop to a platform's shape, turn, mirror, light and colour, sharpen, black and white, caption, resize, convert, every change previewed as it is made | AI upscale; background removal |
| **Coding** | ELI v3's coding agent: it plans, writes, runs and repairs code against tests it writes; the code shown highlighted with whether it passed | |
| **Library** | Everything made, by kind, project and name, each with its record: the models that made it, their licences, whether a model did | |
| **Settings** | This machine and its tier, the main model, how models load, the models, ELI, provenance, the licence | |

**The window.** The studios down the left (each in its own colour, marked while something of it is
running); the project and a search for anything above (Ctrl+K: a studio, an action, something made);
what is running and what finished under the activity button; ELI on the right. Work in progress shows
in the studio's gallery where its results will appear. Ctrl+Enter creates, Ctrl+1 to Ctrl+9 open the
studios, Ctrl+. shows or hides ELI. The look is drawn by the studio itself (its icons too), so it is the
same on Windows, macOS and Linux.

**ELI beside the studios.** With your permission ELI follows the project you are working on (its folder,
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

Creation Station never goes online for its licence. A licence covers a number of computers, each
with its own key: send the seller your licence number and this computer's activation code (Help →
Licence… shows it, or `eli-creation licence code`; a one-way code made from the operating system's
install id), and enter the key you get back. Moving to a new computer: **Deactivate this computer**
removes the key here; tell the seller, who frees its seat. Buy at https://geteli.tech.

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
