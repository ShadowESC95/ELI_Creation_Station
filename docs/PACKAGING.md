# Packaging: one process for every ELI bundle

ELI Creation Station is packaged and released exactly as ELI Legal is: its packaging, installers
and workflows are ELI Legal's, adapted only in names and wording (reuse.json, "adapted"). ELI VR,
being a Godot application, releases differently today; the table says where.

## Bundles and packages

The two words mean different things in ELI:

| | A **bundle** | A **package** |
|---|---|---|
| What it is | A separate ELI application on ELI v3's core, in a window of its own (ELI Legal, ELI VR, ELI Creation Station) | Anything listed on ELI's marketplace: a plugin, an MCP server, an integration, or a bundle |
| How ELI v3 finds it | The `eli.bundles` entry point (installed in ELI v3's Python), or a `<id>.json` registration in ELI v3's `bundles` data folder (`eli-creation bundle register`) | A package manifest (`eli_plugin.json`): id, kind, permissions, pip requirements, sha256, source, price |
| Described by | The bundle contract (eli-sdk `docs/bundles.md`): id, version, launch or command, core range, capabilities, data folder | The package schema (eli-sdk `docs/packages.md`), with a signed release statement |
| Licensed by | For an official bundle, an ELI licence key for its product (or an ELI v3 key that includes it) | Its publisher (`free`, `perpetual`, `subscription`...); official only when the marketplace signs it |
| Shipped as | Its own installers (AppImage, .run, .deb, setup.exe, .dmg) | A file or a pip requirement the marketplace installs into ELI v3, after asking for each permission |

A bundle may also be listed on the marketplace as a package of kind `bundle`. "Package" in the build
sense (an installer, a wheel) is a third meaning; this document calls those installers.

## The process, step by step

| Step | ELI Legal | ELI Creation Station | ELI VR today |
|---|---|---|---|
| Version | `__init__.__version__` | the same (pyproject reads it) | `VERSION`, `pyproject.toml` and `project.godot` must agree |
| Frozen build | PyInstaller, one folder, two programs (`eli-legal`, `eli-legal-gui`); Qt kept as replaceable files (LGPL) | the same (`eli-creation`, `eli-creation-gui`) | Godot export templates, plus a Rust desktop helper |
| Linux | AppImage, `.run`, `.deb`, `.tar.gz`, built on Ubuntu 22.04 (glibc 2.35+) | the same | AppImage and `.tar.gz`, built on Ubuntu 24.04 (glibc 2.39+) |
| Windows | Inno Setup `setup.exe` | the same, its own AppId | `.zip` |
| macOS | a `.dmg` for each of Intel and Apple silicon | the same | one universal `.zip` |
| Names | `ELI_Legal-<v>-linux-x86_64.AppImage` | `ELI_Creation_Station-<v>-linux-x86_64.AppImage` | `ELI_VR-<v>-x86_64.AppImage` (no `linux-`) |
| Checksums | `SHA256SUMS` | the same | `SHA256SUMS.txt` |
| Supply chain | CycloneDX SBOM + pip-audit gate with written exceptions | the same | none |
| Privacy gate | none | ELI VR's (`scripts/check_release.py`) | `tools/make_release.py` |
| Proof it runs | `eli-legal demo` on every frozen build; the window opened and typed into | `eli-creation selftest`; the same window test | a headless start; with and without a licence |
| Licence in CI | an ELI Legal key secret | none needed: the self-test needs no licence, and the window opens on the seven-day trial | trial, tampered trial, and a key secret (branch `licence-trial-parity`) |
| Publishing | a draft release for a person to publish | the same | published at once |
| Registers with ELI v3 on install | yes (`bundle register --if-eli-v3`); removed on uninstall | the same | only by hand (`eli-vr bundle register`) |

## To make ELI VR follow the same process

1. Name the AppImage `ELI_VR-<v>-linux-x86_64.AppImage` and the checksums file `SHA256SUMS`.
2. Publish releases as drafts.
3. Add the SBOM and audit step for the Python side and the Rust helper (`cargo audit`).
4. Register with ELI v3 when installed, as ELI Legal's installers do.
5. Run the release privacy gate in ELI Legal and Creation Station too (done here).

## What each repository needs

- The secret `ELI_SDK_TOKEN` (a fine-grained token with Contents: read on eli-sdk only), so CI can
  fetch eli-sdk's wheel; the same token as ELI Legal's works.
- Signing certificates when the builds are to be signed (`ELI_CREATION_SIGN_CMD`,
  `ELI_CREATION_CODESIGN_IDENTITY`, `ELI_CREATION_NOTARY_PROFILE`), as ELI Legal's.
