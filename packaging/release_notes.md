<!-- Adapted from ELI_Legal: packaging/release_notes.md @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes. -->
ELI Creation Station: platform content, images, video, games and code, made on this machine, with ELI beside you on the project.

**An early build (@TAG@).** What runs today: posts for each platform, a game design and its browser game, and code through ELI v3's coding agent (each with a main model); images on any machine through ELI v3's procedural renderer, and with a local image model where its files are present; image edits; animatics. Video models, narration, captions, music and 3D are shown in the app with what each machine will need, and arrive in later releases.

## Which file

| Your system | Download |
|---|---|
| Linux, nothing to install | `ELI_Creation_Station-…-linux-x86_64.AppImage`: `chmod +x` it and run it |
| Linux, installed for your user | `ELI_Creation_Station-…-linux-x86_64.run`: `sh <file>` (and `--uninstall` to remove) |
| Debian, Ubuntu | `eli-creation_…_amd64.deb`: `sudo apt install ./<file>` |
| Windows 10 or 11, 64-bit | `ELI_Creation_Station-…-windows-x64-setup.exe` |
| macOS, Apple silicon | `ELI_Creation_Station-…-macos-arm64.dmg` |
| macOS, Intel | `ELI_Creation_Station-…-macos-x86_64.dmg` |

## Before you run it

- **These builds are not signed.** Windows SmartScreen and macOS Gatekeeper will warn. Check your download against `SHA256SUMS` first: `sha256sum -c SHA256SUMS --ignore-missing`.
- **An installed copy runs a seven-day trial from its first use**, then needs a licence key: an ELI Creation Station key, or an ELI v3 key that includes it. The terms are in `LICENSE`, shipped with every build.
- No model ships inside: choose a main model (a GGUF file, or a model server on this machine) in Settings, or open Creation Station from ELI v3 to use ELI v3's.
