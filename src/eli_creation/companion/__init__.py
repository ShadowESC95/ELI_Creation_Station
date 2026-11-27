"""ELI in the studio: follows the project being worked on (with permission), notices what matters,
offers insight, and can ask to pause and talk the project through.

Opened by ELI v3, this is ELI v3's own ELI, not a second mind: the screen is read through ELI v3's
capture (eli.perception.os_controller), which handles Wayland's portal, X11, Windows and macOS. On
its own, Creation Station reads the screen with Pillow's capture (Windows, macOS, X11) and ELI
Legal's Tesseract OCR (reused: adapters/local/ocr.py), and keeps what it wants to raise in ELI v3's
attention queue (reused: companion/attention_queue.py), which ranks by severity and age and never
raises the same thing twice inside its suppression window.

Nothing is looked at until the person turns it on (Settings → ELI), and never more than the
project's own folder and, if allowed, the screen. What is read stays on this machine.
"""
