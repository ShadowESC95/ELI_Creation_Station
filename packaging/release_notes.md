<!-- Adapted from ELI_Legal: packaging/release_notes.md @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes. -->
ELI Creation Station: platform content, images, video, games and code, made on this machine, with ELI beside you on the project.

**@TAG@: a redesigned studio, with ELI found by itself.** The window is rebuilt: a rail of studios, Home, a Library of everything made with each item's record (its models, their licences, whether a model made it), a viewer, and Ctrl+K to find any studio, action or creation. Images shows styles as pictures rendered on your machine and keeps or rolls seeds; Socials shows each draft as it reads on its platform; Videos plays a storyboard before it is made; Editing previews every change on a canvas. When ELI v3 runs on the same machine, Creation Station uses its model as ELI's own, with nothing to set. Inside this build, tested but not yet in the window, is the production engine the next release builds its Film and Audio studios on: music and sound effects composed on your machine, narration (ELI v3's voices, Piper, or the computer's own speech), captions, camera moves, transitions and grading, and video with sound written by Qt itself on every system, with nothing else to install. Posts, game designs and code need a main model; images, edits and animatics run on any machine.

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
