<!-- Adapted from ELI_Legal: packaging/release_notes.md @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes. -->
ELI Creation Station: platform content, images, video, games and code, made on this machine, with ELI beside you on the project.

**@TAG@: Film and Audio studios, and ELI everywhere.** Film makes films and ads as projects, from plan to export: notes, characters, places and props, scenes with camera moves, transitions, words on screen and a colour look, a timeline of picture, voice, music, effects and captions, a preview that plays exactly what is written, and one MP4 with its sound on any machine, written by Qt itself with nothing else to install. Ten templates, and a 1-click ad maker: a few answers, and ELI plans it, every scene is pictured, a voice reads it over music and captions follow. Audio makes voice-overs (ELI v3's voices, Piper, or the computer's own speech), music composed on your machine for a mood, length, tempo and key, sound effects, and captions from a recording, each with its waveform, played in the window and sent to a film. Socials gains a content calendar (ELI can plan the week; it exports to any calendar app), cards cut from one picture for each platform, and a brand kit. Editing gains ten colour looks, vignette, grain, words, a logo, a border, and undo. Images gains a prompt builder, ideas from ELI and variations. Games gains six ready-made games and a design editor; Coding, ELI's explanations and reviews. Ask ELI from the top bar of any studio and it answers with what it would make, each a card you run with one click; the models dock shows ELI's main model and every specialist, loaded when a job needs one, with the means to let go of them. The look is ELI's own. Everything Creation Station composes, synthesises and designs is its own: no samples, loops or stock assets. Posts, game design, code and ELI's answers need a main model; images, films, sound, ready-made games and edits run on any machine.

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
